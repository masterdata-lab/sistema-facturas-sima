import streamlit as st
import re
import json
import time
from datetime import datetime
from google.genai import types
from utils.conexiones import (obtener_cliente_gemini, leer_hoja_completa, descargar_archivo, actualizar_estado_carga)

st.set_page_config(page_title="SIMA ERP | Motor IA Flota", page_icon="⚙️", layout="wide", initial_sidebar_state="collapsed")

ia_client = obtener_cliente_gemini()

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

def procesar_documento_flota_ia(pdf_bytes, tipo_sugerido, modelo_ia, max_reintentos=3):
    prompt = f"""
    Actúa como un auditor experto en documentación automotriz. Analiza el documento de tipo: {tipo_sugerido}.
    Devuelve estrictamente un objeto JSON estructurado con este formato exacto:
    {{
        "patente": "Patente limpia sin espacios ni guiones",
        "tipo_sugerido": "{tipo_sugerido}",
        "titular": "Nombre completo del titular registral",
        "cuit_cuil": "CUIT del titular sin guiones",
        "marca_modelo": "Marca y modelo del vehículo",
        "anio": "Año de fabricación",
        "nro_chasis": "Número de chasis largo",
        "nro_motor": "Número de motor completo"
    }}
    """
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    
    for intento in range(max_reintentos):
        try:
            resp = ia_client.models.generate_content(
                model=modelo_ia, 
                contents=[doc, prompt], 
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(resp.text)
        except Exception as e:
            if intento < max_reintentos - 1:
                time.sleep(8)
                continue
            raise e

st.markdown("## ⚙️ Motor de Procesamiento Cognitivo (IA Flota)")
st.divider()

# 🎛️ CONFIGURACIÓN DE MODELOS HOMOLOGADOS
col_config1, col_config2 = st.columns(2)
with col_config1:
    modelo_seleccionado = st.selectbox(
        "🧠 Seleccionar Cerebro IA",
        options=["gemini-3.5-flash", "gemini-3.1-pro"],
        help="Use 3.5 Flash por defecto (veloz y eficiente). Use 3.1 Pro para casos de baja legibilidad."
    )
with col_config2:
    reprocesar_fallidos = st.checkbox("🔄 Intentar reprocesar registros con marcas de error previas", value=True)

loop_activo = st.checkbox("🔄 **Modo Escaneo Continuo Automático**", value=False)
iniciar_manual = False if loop_activo else st.button("▶️ Iniciar Extracción Cognitiva Manual", type="primary")

if loop_activo or iniciar_manual:
    with st.spinner("Buscando en cola dedicada PENDIENTES_FLOTA..."):
        datos_cola = leer_hoja_completa("PENDIENTES_FLOTA")
        
    pendientes = [
        f for f in datos_cola[1:] 
        if len(f) >= 7 and (f[6] == "PENDIENTE_FLOTA" or (reprocesar_fallidos and f[6].startswith("ERROR")))
    ]
    
    if not pendientes:
        st.info("✅ No hay documentos de flota esperando procesamiento en este momento.")
    else:
        st.success(f"Encontrados {len(pendientes)} registros listos para lectura usando **{modelo_seleccionado}**. Procesando...")
        barra_general = st.progress(0)
        status_text = st.empty()
        exitosos, fallidos = 0, 0
        
        for i, fila in enumerate(pendientes):
            id_carga, nombre_archivo, link_drive = fila[0], fila[2], fila[4]
            tipo_sugerido = fila[7] if len(fila) > 7 else "TITULO"
            
            status_text.markdown(f"⏳ **Analizando archivo {i+1}/{len(pendientes)}:** {nombre_archivo}")
            
            try:
                id_drive = extraer_id_drive(link_drive)
                file_bytes = descargar_archivo(id_drive)
                
                if not file_bytes: raise Exception("Error al descargar archivo desde Google Drive.")
                
                # Invocación pasando el modelo seleccionado de la lista oficial
                datos_extraidos = procesar_documento_flota_ia(file_bytes, tipo_sugerido, modelo_seleccionado)
                
                actualizar_estado_carga("PENDIENTES_FLOTA", id_carga, "PARA_AUDITAR_FLOTA", json.dumps(datos_extraidos, ensure_ascii=False))
                exitosos += 1
                time.sleep(2)
                
            except Exception as e:
                actualizar_estado_carga("PENDIENTES_FLOTA", id_carga, f"ERROR_IA_FLOTA: {str(e)[:100]}")
                fallidos += 1
                
            barra_general.progress((i + 1) / len(pendientes))
            
        status_text.empty()
        st.markdown("### 📊 Reporte Final del Motor:")
        c1, c2 = st.columns(2)
        c1.metric("✅ Procesados con Éxito", exitosos)
        c2.metric("⚠️ Fallas Registradas", fallidos)
        if fallidos == 0 and exitosos > 0: st.balloons()

    if loop_activo:
        st.write("---")
        reloj = st.empty()
        for count in range(60, 0, -1):
            reloj.info(f"⏱ orphan_ próximo escaneo en: **{count} segundos**...")
            time.sleep(1)
        st.rerun()
