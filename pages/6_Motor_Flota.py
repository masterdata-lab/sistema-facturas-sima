import streamlit as st
import time
import json
import re
from google.genai import types

# 🔌 Importamos las conexiones de tu ecosistema real (Mismo que facturas)
from utils.conexiones import (
    obtener_cliente_gemini, 
    leer_hoja_completa, 
    descargar_archivo, 
    actualizar_estado_carga
)

st.set_page_config(page_title="Motor de Extracción - Flota", page_icon="🧠", layout="wide")

st.title("🧠 Motor de Extracción Cognitiva Real (Flota)")
st.markdown("---")

# 1. Conexión Real 
try:
    HOJA_FLOTA = st.secrets.get("HOJA_FLOTA", "PENDIENTES_FLOTA") 
    ia_client = obtener_cliente_gemini()
except Exception as e:
    st.error(f"Error al inicializar las conexiones: {e}")
    st.stop()

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', str(url_drive))
    return match.group(1) if match else None

col_opts_1, col_opts_2 = st.columns(2)
with col_opts_1:
    modelo_ia = st.selectbox("🧠 Seleccionar Cerebro IA", ["gemini-3.5-flash"])
with col_opts_2:
    reprocesar_errores = st.checkbox("🔄 Intentar reprocesar registros con error", value=True)
    loop_activo = st.checkbox("🔄 Modo Loop Automático (Procesar cada 60 seg)", value=False)

# 2. IA Blindada 
def procesar_documento_flota_ia(pdf_bytes, tipo_sugerido, modelo_ia):
    plantilla_prompt = """
    Actúa como un auditor experto en documentación automotriz. Analiza el documento de tipo: TIPO_DOCUMENTO.
    Devuelve estrictamente un objeto JSON estructurado con este formato exacto.
    NO envuelvas la respuesta en bloques de código markdown (```json ... ```). Devuelve solo el texto plano del JSON:
    {
        "patente": "Patente limpia sin espacios ni guiones",
        "tipo_sugerido": "TIPO_DOCUMENTO",
        "titular": "Nombre completo del titular registral",
        "cuit_cuil": "CUIT del titular sin guiones",
        "marca_modelo": "Marca y modelo del vehículo",
        "anio": "Año de fabricación",
        "nro_chasis": "Número de chasis largo",
        "nro_motor": "Número de motor completo"
    }
    """
    prompt = plantilla_prompt.replace("TIPO_DOCUMENTO", str(tipo_sugerido))
    
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    resp = ia_client.models.generate_content(
        model=modelo_ia, 
        contents=[doc, prompt], 
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    
    texto_limpio = resp.text.strip()
    if texto_limpio.startswith("```"):
        texto_limpio = texto_limpio.split("\n", 1)[1]
    texto_limpio = texto_limpio.rstrip("`").strip()
    
    return json.loads(texto_limpio)

# --- 🎯 MAPEO DE COLUMNAS 🎯 ---
COL_ID = 0         # Columna A
COL_ARCHIVO = 2    # Columna C 
COL_TIPO = 3       # Columna D 
COL_LINK = 4       # Columna E 
COL_ESTADO = 6     # Columna G 

btn_iniciar = st.button("▶️ Iniciar Procesamiento Manual", type="primary", disabled=loop_activo)

if btn_iniciar or loop_activo:
    with st.spinner(f"Buscando documentos en hoja '{HOJA_FLOTA}'..."):
        try:
            datos_cola = leer_hoja_completa(HOJA_FLOTA)
        except Exception as e:
            st.error(f"No se pudo leer la hoja. Asegurate de que '{HOJA_FLOTA}' existe. Error: {e}")
            st.stop()
    
    pendientes = []
    for fila in datos_cola[1:]:
        if len(fila) > COL_ESTADO:
            estado_actual = str(fila[COL_ESTADO]).strip().upper()
            # ACÁ ESTÁ EL CAMBIO: Ahora busca PENDIENTE_FLOTA
            if estado_actual == "PENDIENTE_FLOTA" or (reprocesar_errores and "ERROR_IA" in estado_actual):
                pendientes.append(fila)

    if not pendientes:
        st.info(f"✅ No se encontraron documentos 'PENDIENTE_FLOTA' en la hoja {HOJA_FLOTA}.")
    else:
        st.success(f"🚀 Encontrados {len(pendientes)} documentos. Procesando con Drive y Gemini...")
        barra_general = st.progress(0)
        status_text = st.empty()
        exitos = 0
        fallas = 0
        
        for i, fila in enumerate(pendientes):
            id_carga = fila[COL_ID]
            nombre_archivo = fila[COL_ARCHIVO] if len(fila) > COL_ARCHIVO else f"Fila_{i+1}"
            link_drive = fila[COL_LINK] if len(fila) > COL_LINK else ""
            tipo_doc = fila[COL_TIPO] if len(fila) > COL_TIPO else "Título Digital"
            
            status_text.markdown(f"⏳ **{i+1}/{len(pendientes)}:** {nombre_archivo}")
            
            try:
                id_drive = extraer_id_drive(link_drive)
                if not id_drive:
                    raise Exception("El link de Drive está vacío o es inválido.")
                    
                pdf_bytes = descargar_archivo(id_drive)
                if not pdf_bytes:
                    raise Exception("No se pudo descargar el archivo desde Google Drive.")
                    
                resultado_json = procesar_documento_flota_ia(pdf_bytes, tipo_doc, modelo_ia)
                
                json_str = json.dumps(resultado_json, ensure_ascii=False)
                actualizar_estado_carga(HOJA_FLOTA, id_carga, "PROCESADO", json_str)
                
                exitos += 1
            except Exception as e:
                error_msg = str(e)[:100]
                actualizar_estado_carga(HOJA_FLOTA, id_carga, f"ERROR_IA_FLOTA: {error_msg}")
                fallas += 1
                
            barra_general.progress((i + 1) / len(pendientes))
            time.sleep(2) 
            
        status_text.empty()
        st.subheader("📊 Resumen del Proceso:")
        col_r1, col_r2 = st.columns(2)
        col_r1.metric("✅ Procesados con Éxito", exitos)
        col_r2.metric("⚠️ Fallas Registradas", fallas)
        if fallas == 0: 
            st.balloons()

    if loop_activo:
        st.write("---")
        reloj = st.empty()
        for i in range(60, 0, -1):
            reloj.info(f"⏱️ Próximo escaneo automático en: **{i} segundos**... No cierres esta pestaña.")
            time.sleep(1)
        st.rerun()

st.markdown('<div style="text-align: right; font-size: 12px; color: gray; margin-top: 50px;">Motor Flota | Sistema SIMA</div>', unsafe_allow_html=True)
