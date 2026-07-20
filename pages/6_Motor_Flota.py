import streamlit as st
import time
import json
from google import genai
from google.genai import types

st.set_page_config(page_title="Motor de Extracción - Flota", page_icon="🧠", layout="wide")

st.title("🧠 Motor de Extracción Cognitiva (Flota)")
st.markdown("---")

try:
    ia_client = genai.Client()
except Exception:
    st.error("Error al inicializar el cliente de Google GenAI. Verifique la API Key.")
    st.stop()

col_opts_1, col_opts_2 = st.columns(2)

with col_opts_1:
    modelo_ia = st.selectbox(
        "🧠 Seleccionar Cerebro IA", 
        ["gemini-3.5-flash"]
    )

with col_opts_2:
    reprocesar_errores = st.checkbox(
        "🔄 Intentar reprocesar registros con marcas de error previas", 
        value=True
    )
    loop_activo = st.checkbox(
        "🔄 Modo Escaneo Continuo Automático (Loop)", 
        value=False
    )

def obtener_pendientes_flota(incluir_errores):
    if "mock_pendientes" not in st.session_state:
        st.session_state.mock_pendientes = [
            {"id": 1, "archivo": "PAG_1_DE_5_TITULO A162ABP.pdf", "tipo": "Título Digital", "estado": "ERROR_IA_FLOTA: 503"},
            {"id": 2, "archivo": "PAG_2_DE_5_TITULO A162ABP.pdf", "tipo": "Título Digital", "estado": "ERROR_IA_FLOTA: 503"}
        ]
    return [f for f in st.session_state.mock_pendientes if f["estado"] == "PENDIENTE" or (incluir_errores and "ERROR" in f["estado"])]

def actualizar_estado_flota(id_registro, estado_nuevo):
    for f in st.session_state.mock_pendientes:
        if f["id"] == id_registro:
            f["estado"] = estado_nuevo

def procesar_documento_flota_ia(pdf_bytes, tipo_sugerido, modelo_ia):
    # Usamos llaves simples y reemplazamos los placeholders para que GitHub no se confunda de color
    plantilla_prompt = """
    Actúa como un auditor experto en documentación automotriz. Analiza el documento de tipo: TIPO_DOCUMENTO.
    Devuelve estrictamente un objeto JSON estructurado con este formato exacto:
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
    prompt = plantilla_prompt.replace("TIPO_DOCUMENTO", tipo_sugerido)
    time.sleep(2) 
    return {"patente": "A162ABP", "tipo_sugerido": tipo_sugerido, "titular": "JUAN PEREZ"}

btn_iniciar = st.button("▶️ Iniciar Extracción Cognitiva Manual", disabled=loop_activo)

if btn_iniciar or loop_activo:
    placeholder_consola = st.empty()
    exitos = 0
    fallas = 0
    
    pendientes = obtener_pendientes_flota(incluir_errores=reprocesar_errores)
    
    if not pendientes:
        st.info("No se encontraron registros pendientes de procesamiento para la flota.")
    else:
        placeholder_consola.success(f"Encontrados {len(pendientes)} registros listos para lectura usando {modelo_ia}. Procesando...")
        
        for i, fila in enumerate(pendientes):
            status_text = f"⏳ Analizando archivo {i+1}/{len(pendientes)}: {fila['archivo']}"
            st.write(status_text)
            
            try:
                resultado_json = procesar_documento_flota_ia(b"pdf_mock_bytes", fila["tipo"], modelo_ia)
                actualizar_estado_flota(fila["id"], "PROCESADO")
                exitos += 1
            except Exception as e:
                actualizar_estado_flota(fila["id"], f"ERROR_IA_FLOTA: {str(e)}")
                fallas += 1
            
            time.sleep(2)
            
        st.subheader("📊 Reporte Final del Motor:")
        col_r1, col_r2 = st.columns(2)
        col_r1.metric("✅ Procesados con Éxito", exitos)
        col_r2.metric("⚠️ Fallas Registradas", fallas)

    if loop_activo:
        time.sleep(60)
        st.rerun()
