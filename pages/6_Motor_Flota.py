import streamlit as st
import re
import json
import time
from datetime import datetime
from google.genai import types
from utils.conexiones import (obtener_cliente_gemini, leer_hoja_completa, descargar_archivo, actualizar_estado_carga)

st.set_page_config(page_title="SIMA ERP | Motor IA Flota", page_icon="⚙️", layout="wide", initial_sidebar_state="collapsed")

try: H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except: H_PENDIENTES = "PENDIENTES"

ia_client = obtener_cliente_gemini()

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

def procesar_documento_flota_ia(pdf_bytes, tipo_sugerido, modelo_elegido='gemini-2.5-flash', max_reintentos=5):
    prompt = f"""
    Actúa como un auditor experto en documentación de flota pesada y vehicular.
    Analiza este documento cuyo tipo sugerido es: {tipo_sugerido}.
    
    Debes extraer de forma extremadamente precisa la información. Si es un Título de Propiedad o Cédula, lee con atención el dominio (patente), los datos del titular, y las especificaciones técnicas.
    
    Devuelve estrictamente un objeto JSON con el siguiente formato:
    {{
        "patente": "Escribe la patente/dominio aquí limpia, sin espacios ni guiones",
        "tipo_sugerido": "{tipo_sugerido}",
        "titular": "Nombre completo del dueño o empresa titular que figura en el documento",
        "cuit_cuil": "CUIT o CUIL del titular sin guiones",
        "marca_modelo": "Marca y Modelo exacto del vehículo",
        "anio": "Año de fabricación o año modelo",
        "nro_chasis": "Número de chasis o cuadro largo alfanumérico",
        "nro_motor": "Número de motor completo"
    }}
    """
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    
    for intento in range(max_reintentos):
        try:
            resp = ia_client.models.generate_content(
                model=modelo_elegido, 
                contents=[doc, prompt], 
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(resp.text)
        except Exception as e:
            if "503" in str(e) or "429" in str(e) or "quota" in str(e).lower():
                if intento < max_reintentos - 1:
                    time.sleep(15)
                    continue
            raise e

st.markdown("## ⚙️ Motor de Procesamiento Cognitivo (IA Flota)")
st.divider()

loop_activo = st.checkbox("🔄 **Modo Escaneo Continuo Automático (Cada 5 minutos)**", value=False)
iniciar_manual = False if loop_activo else st.button("▶️ Iniciar Extracción Cognitiva Manual", type="primary")

if loop_activo or iniciar_manual:
    with st.spinner("Buscando archivos pendientes de flota..."):
        datos_cola = leer_hoja_completa(H_PENDIENTES)
        
    # Buscamos de la hoja general solo las filas con la marca específica de flota
    pendientes = [f for f in datos_cola[1:] if len(f) >= 7 and f[6] == "PENDIENTE_FLOTA"]
    
    if not pendientes:
        st.info("✅ No hay documentos de flota pendientes en la cola del Motor IA.")
    else:
        st.success(f"Encontrados {len(pendientes)} documentos para lectura cognitiva. Procesando...")
        barra_general = st.progress(0)
        status_text = st.empty()
        exitosos, fallidos = 0, 0
        
        for i, fila in enumerate(pendientes):
            id_carga, nombre_archivo, link_drive = fila[0], fila[2], fila[4]
            tipo_sugerido = fila[7] if len(fila) > 7 else "TITULO"
            
            status_text.markdown(f"⏳ **Leyendo archivo {i+1}/{len(pendientes)}:** {nombre_archivo}")
            
            try:
                id_drive = extraer_id_drive(link_drive)
                file_bytes = descargar_archivo(id_drive)
                
                if not file_bytes:
                    raise Exception("No se pudo descargar el archivo segmentado desde Drive.")
                
                # Invocación directa al modelo de Gemini configurado en tu ERP
                datos_extraidos = procesar_documento_flota_ia(file_bytes, tipo_sugerido)
                
                # Movemos a la bandeja de auditoría cambiando el estado a PARA_AUDITAR_FLOTA e inyectando el JSON
                actualizar_estado_carga(H_PENDIENTES, id_carga, "PARA_AUDITAR_FLOTA", json.dumps(datos_extraidos, ensure_ascii=False))
                exitosos += 1
                
                # Freno inteligente para cuidar la cuota de la API
                time.sleep(2)
                
            except Exception as e:
                actualizar_estado_carga(H_PENDIENTES, id_carga, f"ERROR_IA_FLOTA: {str(e)[:100]}")
                fallidos += 1
                
            barra_general.progress((i + 1) / len(pendientes))
            
        status_text.empty()
        st.markdown("### 📊 Reporte de Extracción:")
        c1, c2 = st.columns(2)
        c1.metric("✅ Lecturas Exitosas", exitosos)
        c2.metric("⚠️ Fallas", fallidos)
        if fallidos == 0: st.balloons()

    if loop_activo:
        st.write("---")
        reloj = st.empty()
        for count in range(60, 0, -1):
            reloj.info(f"⏱️ Siguiente barrido cognitivo en: **{count} segundos**... No cierres esta pestaña.")
            time.sleep(1)
        st.rerun()
