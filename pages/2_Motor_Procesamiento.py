import streamlit as st
import re
import json
import time
from datetime import datetime
from google.genai import types

from utils.conexiones import (
    obtener_cliente_gemini, leer_hoja_completa, descargar_archivo,
    actualizar_estado_carga, unificar_documentos, H_REVIS
)

st.set_page_config(page_title="SIMA ERP | Motor IA", page_icon="⚙️", layout="wide")

try:
    H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except:
    H_PENDIENTES = "PENDIENTES"

ia_client = obtener_cliente_gemini()

def extraer_id_drive(url_drive):
    # 🌟 Busca el ID soportando múltiples formatos de Google Drive (/d/ o ?id=)
    if not url_drive or url_drive == "N/A":
        return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

def procesar_con_ia_y_reintentos(pdf_bytes, modelo_elegido, max_reintentos=5):
    prompt = """
    Extraé los datos de esta factura/OT y devolvelos en JSON estricto.
    Formato JSON:
    {
        "cuit_proveedor": "0000", "razon_social": "Nombre", "cuit_cliente": "000",
        "fecha": "DD/MM/YYYY", "punto_venta": 0, "nro_factura": 0, "patente": "",
        "subtotal": 0.0, "total": 0.0, "nro_ot": "",
        "items": [{"descripcion": "Texto", "cantidad": 0.0, "precio_unitario": 0.0}]
    }
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
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str or "quota" in error_str.lower():
                if intento < max_reintentos - 1:
                    time.sleep(10) # Espera 10 segundos en silencio y reintenta
                    continue
            raise e # Si no es error de servidor o agotó intentos, explota

st.markdown("## ⚙️ Motor de Procesamiento (IA)")
st.markdown("Este módulo lee la cola de archivos pendientes, procesa los datos con Gemini y los prepara para la auditoría humana.")
st.divider()

if st.button("▶️ Iniciar Procesamiento Automático", type="primary"):
    with st.spinner("Buscando facturas en la cola..."):
        datos_cola = leer_hoja_completa(H_PENDIENTES)
    
    # Filtramos omitiendo la cabecera
    pendientes = [fila for fila in datos_cola[1:] if len(fila) >= 7 and fila[6] == "PENDIENTE"]
    
    if not pendientes:
        st.info("✅ No hay facturas pendientes en la cola.")
    else:
        st.success(f"Encontradas {len(pendientes)} facturas pendientes. Iniciando motor...")
        
        # Barra de progreso general
        barra_general = st.progress(0)
        status_text = st.empty()
        
        for i, fila in enumerate(pendientes):
            id_carga = fila[0]
            nombre_fac = fila[2]
            link_fac = fila[4]
            link_ot = fila[5]
            motor_ia = fila[7] if len(fila) > 7 else 'gemini-3.5-flash'
            
            status_text.markdown(f"⏳ **Procesando {i+1}/{len(pendientes)}:** {nombre_fac}")
            
            try:
                # 1. Descargar PDFs
                id_fac = extraer_id_drive(link_fac)
                id_ot = extraer_id_drive(link_ot) if "N/A" not in link_ot else None
                
                fac_bytes = descargar_archivo(id_fac)
                ot_bytes = descargar_archivo(id_ot) if id_ot else None
                
                if not fac_bytes:
                    actualizar_estado_carga(H_PENDIENTES, id_carga, "ERROR: No se pudo descargar")
                    continue
                    
                # 2. Unificar y llamar a IA (con reintentos automáticos)
                pdf_final = unificar_documentos(fac_bytes, ot_bytes, False)
                datos_ia = procesar_con_ia_y_reintentos(pdf_final, motor_ia)
                
                # 3. Guardar JSON y marcar como PARA_AUDITAR
                json_string = json.dumps(datos_ia, ensure_ascii=False)
                actualizar_estado_carga(H_PENDIENTES, id_carga, "PARA_AUDITAR", json_string)
                
            except Exception as e:
                # Si falló del todo, lo marcamos con error
                actualizar_estado_carga(H_PENDIENTES, id_carga, f"ERROR_IA: {str(e)[:50]}")
                
            barra_general.progress((i + 1) / len(pendientes))
            
        status_text.markdown("✅ **¡Lote procesado por completo!**")
        st.balloons()
