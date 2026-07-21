import streamlit as st
import time
import json
import re
import concurrent.futures
from google.genai import types

from utils.conexiones import (
    obtener_cliente_gemini, 
    leer_hoja_completa, 
    descargar_archivo, 
    actualizar_estado_carga
)

st.set_page_config(page_title="Motor de Extracción - Flota", page_icon="🧠", layout="wide")

st.title("🧠 Motor de Extracción Cognitiva Real (Flota)")
st.markdown("---")

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
    # Mensaje actualizado a la nueva prioridad
    st.info("🧠 Enrutador de IA Activo: 3.1-Flash-Lite ➡️ Failover a 3.5-Flash")
with col_opts_2:
    reprocesar_errores = st.checkbox("🔄 Intentar reprocesar registros con error", value=True)
    loop_activo = st.checkbox("🔄 Modo Loop Automático (Procesar cada 60 seg)", value=False)

def procesar_documento_flota_ia(pdf_bytes, tipo_sugerido, status_text_ui, contexto_ui):
    plantilla_prompt = """
    Actúa como un auditor experto en documentación automotriz de Argentina. Analiza el documento proporcionado.
    Extrae los datos solicitados. 
    
    REGLA VITAL PARA 'tipo_sugerido': Debes deducir leyendo el documento a qué categoría pertenece. 
    Responde ÚNICAMENTE con una de estas 5 opciones exactas: TITULO, CEDULA_VERDE, CERTIFICADO_SEGURO, VTV, YPF.
    
    Para 'tipo_vehiculo', transcribe EXACTAMENTE la categoría o tipo que figura impreso en el documento oficial (ej: SEDAN 4 PUERTAS, PICK-UP, FURGON, CAMION, MOTOVEHICULO, etc.). 
    Para 'anio_inscripcion' busca específicamente el año de inscripción inicial o patentamiento.
    
    Devuelve estrictamente un objeto JSON estructurado con este formato exacto.
    NO envuelvas la respuesta en bloques de código markdown (```json ... ```). Devuelve solo el texto plano del JSON:
    {
        "patente": "Patente limpia sin espacios ni guiones",
        "tipo_sugerido": "TITULO", 
        "titular": "Nombre completo del titular registral",
        "cuit_cuil": "CUIT del titular sin guiones",
        "tipo_vehiculo": "Transcribir tipo textual y literal del documento",
        "lugar_radicacion": "Localidad y/o provincia de radicación",
        "marca": "Solo la marca del vehículo",
        "modelo": "Solo el modelo del vehículo",
        "anio_inscripcion": "Año de inscripción inicial",
        "nro_chasis": "Número de chasis largo",
        "nro_motor": "Número de motor completo"
    }
    """
    prompt = plantilla_prompt
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    
    # NUEVO ORDEN DE PRIORIDAD
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
                    status_text_ui.error(f"⚠️ {modelo} falló por Timeout. Saltando a modelo de emergencia...")
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

COL_ID, COL_ARCHIVO, COL_TIPO, COL_LINK, COL_ESTADO = 0, 2, 3, 4, 6     

st.markdown("---")
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    btn_iniciar = st.button("▶️ Iniciar Procesamiento", type="primary", disabled=loop_activo)
with col_btn2:
    if st.button("⏹️ Detener / Cancelar Proceso"):
        st.warning("🛑 Proceso detenido por el usuario.")
        st.stop()
st.markdown("---")

if btn_iniciar or loop_activo:
    with st.spinner(f"Buscando documentos en hoja '{HOJA_FLOTA}'..."):
        try:
            datos_cola = leer_hoja_completa(HOJA_FLOTA)
        except Exception as e:
            st.error(f"No se pudo leer la hoja. Error: {e}")
            st.stop()
    
    pendientes = []
    for fila in datos_cola[1:]:
        if len(fila) > COL_ESTADO:
            estado_actual = str(fila[COL_ESTADO]).strip().upper()
            if estado_actual == "PENDIENTE_FLOTA" or (reprocesar_errores and "ERROR_IA" in estado_actual):
                pendientes.append(fila)

    if not pendientes:
        st.info(f"✅ No se encontraron documentos 'PENDIENTE_FLOTA' en la hoja {HOJA_FLOTA}.")
    else:
        st.success(f"🚀 Encontrados {len(pendientes)} documentos en cola.")
        barra_general = st.progress(0)
        status_text = st.empty()
        exitos, fallas = 0, 0
        
        for i, fila in enumerate(pendientes):
            id_carga = fila[COL_ID]
            nombre_archivo = fila[COL_ARCHIVO] if len(fila) > COL_ARCHIVO else f"Fila_{i+1}"
            link_drive = fila[COL_LINK] if len(fila) > COL_LINK else ""
            tipo_doc = fila[COL_TIPO] if len(fila) > COL_TIPO else "Título Digital"
            contexto = f"{i+1}/{len(pendientes)}: {nombre_archivo}"
            
            try:
                id_drive = extraer_id_drive(link_drive)
                if not id_drive: raise Exception("Link Drive vacío/inválido.")
                    
                status_text.markdown(f"⏳ **{contexto}** | Descargando PDF de Drive...")
                pdf_bytes = descargar_archivo(id_drive)
                if not pdf_bytes: raise Exception("Error al descargar el archivo.")
                    
                resultado_json = procesar_documento_flota_ia(pdf_bytes, tipo_doc, status_text, contexto)
                
                json_str = json.dumps(resultado_json, ensure_ascii=False)
                actualizar_estado_carga(HOJA_FLOTA, id_carga, "PROCESADO", json_str)
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
        if fallas == 0: st.balloons()

    if loop_activo:
        st.write("---")
        reloj = st.empty()
        for i in range(60, 0, -1):
            reloj.info(f"⏱️ Próximo escaneo en: **{i} segundos**... (Usá el botón ⏹️ Detener para cancelar)")
            time.sleep(1)
        st.rerun()

st.markdown('<div style="text-align: right; font-size: 12px; color: gray; margin-top: 50px;">Motor Flota | Sistema SIMA</div>', unsafe_allow_html=True)
