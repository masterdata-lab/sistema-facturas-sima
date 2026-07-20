import streamlit as st
import time
import json
import pandas as pd
from google import genai
from google.genai import types
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Motor de Extracción - Flota", page_icon="🧠", layout="wide")

st.title("🧠 Motor de Extracción Cognitiva Real (Flota)")
st.markdown("---")

# 1. Conexión Real a Google Sheets y Gemini
try:
    ia_client = genai.Client()
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Error de conexión: {str(e)}")
    st.stop()

col_opts_1, col_opts_2 = st.columns(2)

with col_opts_1:
    modelo_ia = st.selectbox("🧠 Seleccionar Cerebro IA", ["gemini-3.5-flash"])

with col_opts_2:
    reprocesar_errores = st.checkbox("🔄 Intentar reprocesar registros con error", value=True)
    loop_activo = st.checkbox("🔄 Modo Escaneo Continuo Automático", value=False)

# 2. Leer GSheet Real
def obtener_pendientes_flota_real(incluir_errores):
    try:
        df = conn.read(ttl="0d")
        df.columns = [c.lower().strip() for c in df.columns]
        
        if 'estado' not in df.columns:
            st.error("No se encontró la columna 'Estado' en tu Google Sheet.")
            return []
            
        df['estado_limpio'] = df['estado'].astype(str).str.upper().str.strip()
        
        if incluir_errores:
            condicion = df['estado_limpio'].isin(['PENDIENTE', '']) | df['estado_limpio'].str.contains('ERROR')
        else:
            condicion = df['estado_limpio'].isin(['PENDIENTE', ''])
            
        return df[condicion].to_dict(orient="records")
    except Exception as e:
        st.error(f"Error al leer tu GSheet: {str(e)}")
        return []

# 3. Llamada Real a Gemini
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
    prompt = plantilla_prompt.replace("TIPO_DOCUMENTO", tipo_sugerido)
    
    # Acá le pega a la API de verdad
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    resp = ia_client.models.generate_content(
        model=modelo_ia, 
        contents=[doc, prompt], 
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    
    # Limpieza anti-errores
    texto_limpio = resp.text.strip()
    if texto_limpio.startswith("```"):
        texto_limpio = texto_limpio.split("\n", 1)[1]
    texto_limpio = texto_limpio.rstrip("`").strip()
    
    return json.loads(texto_limpio)

# 4. Actualizar GSheet Real (Acá debes poner tu lógica de guardado)
def actualizar_estado_flota_real(id_registro, estado_nuevo):
    # NOTA: Reemplazá este print por tu código real para guardar en tu sheet
    print(f"Fila {id_registro} actualizada a {estado_nuevo}")

btn_iniciar = st.button("▶️ Iniciar Extracción Cognitiva Real", disabled=loop_activo)

if btn_iniciar or loop_activo:
    pendientes = obtener_pendientes_flota_real(incluir_errores=reprocesar_errores)
    
    if not pendientes:
        st.info("No se encontraron registros 'PENDIENTE' en tu GSheet.")
    else:
        st.success(f"🚀 Encontrados {len(pendientes)} documentos. Procesando...")
        exitos = 0
        fallas = 0
        
        for i, fila in enumerate(pendientes):
            st.write(f"⏳ Procesando: {fila.get('archivo', f'Fila {i}')}")
            
            try:
                # IMPORTANTE: Reemplazá b"bytes" por la variable real que descarga tu PDF
                resultado_json = procesar_documento_flota_ia(b"bytes_de_tu_pdf_real", fila.get('tipo', 'Documento'), modelo_ia)
                actualizar_estado_flota_real(fila.get('id', i), "PROCESADO")
                st.write(f"✅ Éxito: {resultado_json.get('patente')}")
                exitos += 1
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                actualizar_estado_flota_real(fila.get('id', i), f"ERROR_IA: {str(e)}")
                fallas += 1
            
            time.sleep(2)
            
        st.write(f"📊 Finalizado: {exitos} éxitos, {fallas} fallas.")

    if loop_activo:
        time.sleep(60)
        st.rerun()
