import streamlit as st
import re
import json
import time
import concurrent.futures
from datetime import datetime
from google.genai import types
from utils.conexiones import (obtener_cliente_gemini, leer_hoja_completa, descargar_archivo, actualizar_estado_carga, unificar_documentos)

st.set_page_config(page_title="SIMA ERP | Motor IA", page_icon="⚙️", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255, 75, 75, 0.8); }
</style>
""", unsafe_allow_html=True)

try: H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except: H_PENDIENTES = "PENDIENTES"

MAPEO_CUITS_SIMA = {
    "30111111111": "SIMA S.A.", "30222222222": "SIMA LOGISTICA SRL",
    "30333333333": "SIMA SERVICIOS", "30444444444": "SIMA AGRO"
}
CATEGORIAS_GASTO = ["BATERIAS", "CHAP PINT", "DOCUMENTACION", "EXTINTORES", "FILTROS Y FLUIDOS", "GOMERIA", "MANTENIMIENTO CORRECTIVO", "MANTENIMIENTO PREVENTIVO", "NEUMATICOS", "PLOTEO", "RASTREO GPS", "REPUESTOS", "VARIOS", "VTV", "PEAJE", "LAVADO", "ESTACIONAMIENTO", "CAJA CHICA S.F."]

try:
    ia_client = obtener_cliente_gemini()
except Exception as e:
    st.error(f"Error al inicializar IA: {e}")
    st.stop()

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

# NUEVA LÓGICA CON FAILOVER (IGUAL A FLOTA)
def procesar_con_ia_y_reintentos(pdf_bytes, status_text_ui, contexto_ui):
    prompt = f"""
    Extraé los datos. Identificá al CLIENTE y extraé su CUIT (cuit_cliente).
    Revisá TODO el documento. Si hay páginas que corresponden a una Orden de Trabajo (OT) generada por el taller o por SIMA, poné "ot_incluida_en_pdf": true.
    Asigná "tipo_gasto" de esta lista: {CATEGORIAS_GASTO}.
    Formato JSON:
    {{
        "cuit_proveedor": "0000", "razon_social": "Nombre", "cuit_cliente": "00000000000", "razon_social_cliente": "Nombre Sima",
        "fecha": "DD/MM/YYYY", "punto_venta": 0, "nro_factura": 0, "patente": "", "subtotal": 0.0, "total": 0.0, "nro_ot": "",
        "ot_incluida_en_pdf": false,
        "items": [ {{"descripcion": "Texto", "cantidad": 1.0, "precio_sin_impuestos": 0.0, "precio_con_impuestos": 0.0, "tipo_gasto": "VARIOS"}} ]
    }}
    """
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    
    # ORDEN DE PRIORIDAD APLICADO A FACTURACIÓN
    modelos_disponibles = ["gemini-3.1-flash-lite", "gemini-3.5-flash"]
    max_intentos_por_modelo = 2
    
    for modelo in modelos_disponibles:
        for intento in range(max_intentos_por_modelo):
            status_text_ui.markdown(f"⏳ **{contexto_ui}** | 🧠 Modelo: **{modelo}** | 🔄 Intento {intento + 1}/{max_intentos_por_modelo}")
            
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        ia_client.models.generate_content,
                        model=modelo,
                        contents=[doc, prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    resp = future.result(timeout=45)
                    
                texto_limpio = resp.text.strip()
                if texto_limpio.startswith("```"):
                    texto_limpio = texto_limpio.split("\n", 1)[1]
                texto_limpio = texto_limpio.rstrip("`").strip()
                return json.loads(texto_limpio)
                
            except concurrent.futures.TimeoutError:
                if intento < max_intentos_por_modelo - 1:
                    for seg in range(3, 0, -1):
                        status_text_ui.warning(f"⚠️ {modelo} tardó demasiado. Reintentando en **{seg}s**...")
                        time.sleep(1)
                    continue
                else:
                    status_text_ui.error(f"⚠️ {modelo} falló por Timeout. Saltando a modelo secundario...")
                    time.sleep(1.5)
                    
            except Exception as e:
                if "503" in str(e) or "429" in str(e) or "quota" in str(e).lower():
                    if intento < max_intentos_por_modelo - 1:
                        codigo_error = str(e)[:3] if len(str(e)) >= 3 else "API"
                        for seg in range(5, 0, -1):
                            status_text_ui.warning(f"⚠️ {modelo} saturado (Error {codigo_error}). Pausa: **{seg}s**...")
                            time.sleep(1)
                        continue
                    else:
                        status_text_ui.error(f"⚠️ {modelo} sigue saturado. Activando enrutador a modelo secundario...")
                        time.sleep(1.5)
                else:
                    raise e

    raise Exception("TIMEOUT_GLOBAL: Ambos modelos se encuentran saturados. Intente más tarde.")


st.markdown("## ⚙️ Motor de Procesamiento (IA)")
st.divider()

col_opts_1, col_opts_2 = st.columns(2)
with col_opts_1:
    st.info("🧠 Enrutador de IA Activo: 3.1-Flash-Lite ➡️ Failover a 3.5-Flash")
with col_opts_2:
    reprocesar_fallidos = st.checkbox("🔄 Intentar reprocesar archivos que dieron error", value=True)
    loop_activo = st.checkbox("🔄 **Modo Loop Automático (Procesar cada 60 seg)**", value=False)

st.markdown("---")
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    iniciar_manual = st.button("▶️ Iniciar Procesamiento Manual", type="primary", disabled=loop_activo)
with col_btn2:
    if st.button("⏹️ Detener / Cancelar Proceso"):
        st.warning("🛑 Proceso detenido por el usuario.")
        st.stop()
st.markdown("---")

if loop_activo or iniciar_manual:
    with st.spinner("Buscando facturas..."):
        try:
            datos_cola = leer_hoja_completa(H_PENDIENTES)
        except Exception as e:
            st.error(f"Error al leer hoja PENDIENTES: {e}")
            st.stop()
            
    pendientes = [f for f in datos_cola[1:] if len(f) >= 7 and (f[6] == "PENDIENTE" or (reprocesar_fallidos and f[6].startswith("ERROR_IA")))]
    
    if not pendientes:
        st.info("✅ No hay facturas pendientes.")
    else:
        st.success(f"🚀 Encontradas {len(pendientes)} facturas. Procesando...")
        barra_general = st.progress(0)
        status_text = st.empty()
        exitosos, fallidos = 0, 0
        
        for i, fila in enumerate(pendientes):
            id_carga, nombre_fac, link_fac, link_ot = fila[0], fila[2], fila[4], fila[5]
            contexto = f"{i+1}/{len(pendientes)}: {nombre_fac}"
            
            try:
                id_fac = extraer_id_drive(link_fac)
                id_ot = extraer_id_drive(link_ot) if "N/A" not in link_ot else None
                
                status_text.markdown(f"⏳ **{contexto}** | Descargando de Drive...")
                fac_bytes = descargar_archivo(id_fac)
                ot_bytes = descargar_archivo(id_ot) if id_ot else None
                
                if not fac_bytes: raise Exception("No se pudo descargar el archivo")
                
                pdf_final = unificar_documentos(fac_bytes, ot_bytes, False)
                
                # Usamos el nuevo sistema de Failover
                datos_ia = procesar_con_ia_y_reintentos(pdf_final, status_text, contexto)
                
                actualizar_estado_carga(H_PENDIENTES, id_carga, "PARA_AUDITAR", json.dumps(datos_ia, ensure_ascii=False))
                exitosos += 1
            except Exception as e:
                actualizar_estado_carga(H_PENDIENTES, id_carga, f"ERROR_IA: {str(e)[:150]}")
                fallidos += 1
                
            barra_general.progress((i + 1) / len(pendientes))
            time.sleep(1)
            
        status_text.empty()
        st.markdown("### 📊 Resumen:")
        c1, c2 = st.columns(2)
        c1.metric("✅ Procesados", exitosos)
        c2.metric("⚠️ Errores API", fallidos)
        if fallidos == 0: st.balloons()

    if loop_activo:
        st.write("---")
        reloj = st.empty()
        for i in range(60, 0, -1):
            reloj.info(f"⏱️ Próximo escaneo automático en: **{i} segundos**... (Usá el botón ⏹️ Detener para cancelar)")
            time.sleep(1)
        st.rerun()

st.markdown('<div style="text-align: right; font-size: 12px; color: gray; margin-top: 50px;">Software DPA | Creado por Serrano Cristian</div>', unsafe_allow_html=True)
