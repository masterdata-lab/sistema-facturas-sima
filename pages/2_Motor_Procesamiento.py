import streamlit as st
import re
import json
import time
from datetime import datetime
from google.genai import types
from utils.conexiones import (obtener_cliente_gemini, leer_hoja_completa, descargar_archivo, actualizar_estado_carga, unificar_documentos, H_REVIS)

# 1. FORZAR BARRA LATERAL CERRADA
st.set_page_config(page_title="SIMA ERP | Motor IA", page_icon="⚙️", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS PARA JUNTAR TODO Y RESALTAR EL BOTÓN DEL MENÚ
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    [data-testid="collapsedControl"] {
        border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255, 75, 75, 0.8);
    }
</style>
""", unsafe_allow_html=True)

try: H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except: H_PENDIENTES = "PENDIENTES"

MAPEO_CUITS_SIMA = {
    "30111111111": "SIMA S.A.", "30222222222": "SIMA LOGISTICA SRL",
    "30333333333": "SIMA SERVICIOS", "30444444444": "SIMA AGRO"
}
CATEGORIAS_GASTO = ["BATERIAS", "CHAP PINT", "DOCUMENTACION", "EXTINTORES", "FILTROS Y FLUIDOS", "GOMERIA", "MANTENIMIENTO CORRECTIVO", "MANTENIMIENTO PREVENTIVO", "NEUMATICOS", "PLOTEO", "RASTREO GPS", "REPUESTOS", "VARIOS", "VTV", "PEAJE", "LAVADO", "ESTACIONAMIENTO", "CAJA CHICA S.F."]

ia_client = obtener_cliente_gemini()

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

def procesar_con_ia_y_reintentos(pdf_bytes, modelo_elegido, max_reintentos=5):
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
    for intento in range(max_reintentos):
        try:
            resp = ia_client.models.generate_content(model=modelo_elegido, contents=[doc, prompt], config=types.GenerateContentConfig(response_mime_type="application/json"))
            return json.loads(resp.text)
        except Exception as e:
            if "503" in str(e) or "429" in str(e) or "quota" in str(e).lower():
                if intento < max_reintentos - 1:
                    time.sleep(30 if "429" in str(e) else 10)
                    continue
            raise e

st.markdown("## ⚙️ Motor de Procesamiento (IA)")
st.divider()

reprocesar_fallidos = st.checkbox("🔄 Intentar reprocesar archivos que dieron error", value=True)
loop_activo = st.checkbox("🔄 **Modo Loop Automático (Procesar cada 5 minutos)**", value=False)

iniciar_manual = False
if not loop_activo:
    iniciar_manual = st.button("▶️ Iniciar Procesamiento Manual", type="primary")

if loop_activo or iniciar_manual:
    with st.spinner("Buscando facturas..."):
        datos_cola = leer_hoja_completa(H_PENDIENTES)
    pendientes = [f for f in datos_cola[1:] if len(f) >= 7 and (f[6] == "PENDIENTE" or (reprocesar_fallidos and f[6].startswith("ERROR_IA")))]
    
    if not pendientes:
        st.info("✅ No hay facturas pendientes.")
    else:
        st.success(f"Encontradas {len(pendientes)} facturas. Procesando...")
        barra_general = st.progress(0)
        status_text = st.empty()
        exitosos, fallidos = 0, 0
        
        for i, fila in enumerate(pendientes):
            id_carga, nombre_fac, link_fac, link_ot = fila[0], fila[2], fila[4], fila[5]
            motor_ia = fila[7] if len(fila) > 7 else 'gemini-3.5-flash'
            status_text.markdown(f"⏳ **{i+1}/{len(pendientes)}:** {nombre_fac}")
            
            try:
                id_fac = extraer_id_drive(link_fac)
                id_ot = extraer_id_drive(link_ot) if "N/A" not in link_ot else None
                fac_bytes = descargar_archivo(id_fac)
                ot_bytes = descargar_archivo(id_ot) if id_ot else None
                
                if not fac_bytes: raise Exception("No se pudo descargar el archivo")
                
                pdf_final = unificar_documentos(fac_bytes, ot_bytes, False)
                datos_ia = procesar_con_ia_y_reintentos(pdf_final, motor_ia)
                actualizar_estado_carga(H_PENDIENTES, id_carga, "PARA_AUDITAR", json.dumps(datos_ia, ensure_ascii=False))
                exitosos += 1
            except Exception as e:
                actualizar_estado_carga(H_PENDIENTES, id_carga, f"ERROR_IA: {str(e)[:100]}")
                fallidos += 1
            barra_general.progress((i + 1) / len(pendientes))
            
        status_text.empty()
        st.markdown("### 📊 Resumen:")
        c1, c2 = st.columns(2)
        c1.metric("✅ Procesados", exitosos)
        c2.metric("⚠️ Errores API", fallidos)
        if fallidos == 0: st.balloons()

    if loop_activo:
        st.write("---")
        reloj = st.empty()
        for i in range(300, 0, -1):
            reloj.info(f"⏱️ Próximo escaneo automático en: **{i} segundos**...")
            time.sleep(1)
        st.rerun()
