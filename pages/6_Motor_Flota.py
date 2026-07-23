import streamlit as st
import time
import json
import re
import io
import uuid
from datetime import datetime
import concurrent.futures
from google.genai import types

try:
    import pypdf
except ImportError:
    try:
        import PyPDF2 as pypdf
    except ImportError:
        pypdf = None

from utils.conexiones import (
    obtener_cliente_gemini, 
    leer_hoja_completa, 
    descargar_archivo, 
    actualizar_estado_carga,
    subir_archivo,
    escribir_fila,
    ID_DRIVE_RAIZ
)

st.set_page_config(page_title="Motor de Extracción - Flota", page_icon="🧠", layout="wide")

st.title("🧠 Motor de Extracción Cognitiva Real (Flota)")
st.markdown("---")

try:
    HOJA_FLOTA = st.secrets.get("HOJA_PENDIENTES_FLOTA", "PENDIENTES_FLOTA") 
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
    st.info("🧠 Enrutador de IA Activo: 3.1-Flash-Lite ➡️ Failover a 3.5-Flash")
with col_opts_2:
    reprocesar_errores = st.checkbox("🔄 Intentar reprocesar registros con error", value=True)
    loop_activo = st.checkbox("🔄 Modo Loop Automático (Procesar cada 60 seg)", value=False)

def procesar_documento_flota_ia(pdf_bytes, tipo_sugerido, status_text_ui, contexto_ui):
    plantilla_prompt = """
    Actúa como un auditor experto en seguros de flota automotor de Argentina. Tu tarea es analizar TODO el documento proporcionado y extraer la información clave.

    REGLAS ESTRICTAS DE EXTRACCIÓN:
    1. IGNORAR BASURA: Ignora las páginas de "Condiciones Generales", "Índice", o texto legal continuo al buscar vehículos, PERO utiliza las primeras páginas (Frente de Póliza) para extraer los DATOS GENERALES (Asegurado, CUIT, N° Póliza, Vigencia).
    2. IDENTIFICAR CERTIFICADOS: Una página SOLO es un certificado individual válido si contiene un Dominio/Patente de un vehículo.
    3. FORMATO DE PATENTE: Busca únicamente patentes argentinas (ej. AE896KP, OUI123).
    4. RESTRICCIÓN DE PÁGINAS: Si una página no menciona explícitamente un Dominio/Patente, no la incluyas en la lista de vehículos.
    5. NORMALIZACIÓN DE FECHAS: Todas las fechas (vigencias, vencimientos) DEBEN convertirse obligatoriamente al formato estricto DD/MM/AAAA (ejemplo: si dice "12 Ago 26", debes devolver "12/08/2026"). Si no hay fecha, devuelve "S/D".
    
    Devuelve estrictamente un JSON con este formato (y NADA MÁS que el JSON):
    {
        "es_multiple": true_o_false,
        "datos_generales": {
            "asegurado": "Razón social o S/D",
            "cuit": "Número de CUIT o S/D",
            "num_poliza": "Número de póliza o S/D",
            "vigencia_desde": "DD/MM/AAAA o S/D",
            "vigencia_hasta": "DD/MM/AAAA o S/D"
        },
        "vehiculos": [
            {
                "patente": "Patente sin espacios",
                "tipo_sugerido": "CERTIFICADO_SEGURO", 
                "pagina_pdf": 1,
                "vencimiento": "DD/MM/AAAA o S/D",
                "marca_modelo": "Solo si está disponible o S/D"
            }
        ]
    }
    """
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
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
                        contents=[doc, plantilla_prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    resp = future.result(timeout=60)
                    
                texto_limpio = resp.text.strip()
                if texto_limpio.startswith("```"): texto_limpio = texto_limpio.split("\n", 1)[1]
                return json.loads(texto_limpio.rstrip("`").strip())
            except Exception as e:
                if intento == max_intentos_por_modelo - 1 and modelo == modelos_disponibles[-1]: raise e
                time.sleep(2)
    raise Exception("TIMEOUT_GLOBAL")

COL_ID, COL_FECHA, COL_ARCHIVO = 0, 1, 2
COL_TIPO, COL_LINK, COL_ESTADO = 7, 4, 6     

st.markdown("---")
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    btn_iniciar = st.button("▶️ Iniciar Procesamiento", type="primary", disabled=loop_activo)
with col_btn2:
    if st.button("⏹️ Detener / Cancelar Proceso"): st.stop()
st.markdown("---")

if btn_iniciar or loop_activo:
    with st.spinner(f"Buscando documentos..."):
        try: datos_cola = leer_hoja_completa(HOJA_FLOTA)
        except Exception as e: st.stop()
    
    pendientes = [f for f in datos_cola[1:] if len(f) > COL_ESTADO and (str(f[COL_ESTADO]).strip().upper() == "PENDIENTE_FLOTA" or (reprocesar_errores and "ERROR_IA" in str(f[COL_ESTADO]).strip().upper()))]

    if not pendientes:
        st.info("✅ No se encontraron documentos en cola.")
    else:
        st.success(f"🚀 Encontrados {len(pendientes)} documentos.")
        barra_general = st.progress(0)
        status_text = st.empty()
        exitos, fallas = 0, 0
        
        for i, fila in enumerate(pendientes):
            id_carga = fila[COL_ID]
            nombre_archivo = fila[COL_ARCHIVO]
            link_drive_original = fila[COL_LINK]
            tipo_doc = fila[COL_TIPO]
            contexto = f"{i+1}/{len(pendientes)}: {nombre_archivo}"
            
            try:
                id_drive = extraer_id_drive(link_drive_original)
                if not id_drive: raise Exception("Link Drive inválido.")
                    
                status_text.markdown(f"⏳ **{contexto}** | Descargando PDF...")
                pdf_bytes = descargar_archivo(id_drive)
                
                resultado_ia = procesar_documento_flota_ia(pdf_bytes, tipo_doc, status_text, contexto)
                
                if resultado_ia.get("es_multiple") and tipo_doc == "POLIZA_MADRE":
                    status_text.markdown(f"✂️ **{contexto}** | Cortando y subiendo certificados individuales...")
                    pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                    
                    for vehiculo in resultado_ia.get("vehiculos", []):
                        pag_num = int(vehiculo.get("pagina_pdf", 1)) - 1 
                        patente = vehiculo.get("patente", "S_D")
                        
                        if 0 <= pag_num < len(pdf_reader.pages):
                            pdf_writer = pypdf.PdfWriter()
                            pdf_writer.add_page(pdf_reader.pages[pag_num])
                            output_buffer = io.BytesIO()
                            pdf_writer.write(output_buffer)
                            
                            nuevo_id = f"CERT_{uuid.uuid4().hex[:6].upper()}"
                            link_cortado = subir_archivo(f"TEMP_{patente}_CERT.pdf", output_buffer.getvalue(), ID_DRIVE_RAIZ)
                            
                            escribir_fila(HOJA_FLOTA, [
                                nuevo_id, fila[COL_FECHA], f"Recorte_{patente}.pdf", "IA_MOTOR", 
                                link_cortado, link_drive_original, "PROCESADO", "CERTIFICADO_SEGURO", json.dumps(vehiculo)
                            ])
                            
                    datos_madre = resultado_ia.get("datos_generales", {})
                    datos_madre["notas"] = "Desglosada en certificados individuales."
                    actualizar_estado_carga(HOJA_FLOTA, id_carga, "PROCESADO_DESGLOSADO", json.dumps(datos_madre))
                else:
                    vehiculo = resultado_ia.get("vehiculos", [{}])[0]
                    actualizar_estado_carga(HOJA_FLOTA, id_carga, "PROCESADO", json.dumps(vehiculo))
                
                exitos += 1
            except Exception as e:
                actualizar_estado_carga(HOJA_FLOTA, id_carga, f"ERROR_IA_FLOTA: {str(e)[:150]}")
                fallas += 1
                
            barra_general.progress((i + 1) / len(pendientes))
            time.sleep(1) 
            
        status_text.empty()
        st.subheader("📊 Resumen del Proceso:")
        col_r1, col_r2 = st.columns(2)
        col_r1.metric("✅ Procesados con Éxito", exitos)
        col_r2.metric("⚠️ Fallas Registradas", fallas)

    if loop_activo:
        st.write("---")
        reloj = st.empty()
        for i in range(60, 0, -1):
            reloj.info(f"⏱️ Próximo escaneo en: **{i} segundos**...")
            time.sleep(1)
        st.rerun()
