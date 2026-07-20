import streamlit as st
import time
import uuid
import json
import io
from datetime import datetime
from utils.conexiones import escribir_fila, subir_archivo, ID_DRIVE_RAIZ

# Buscamos la librería de manipulación de PDFs integrada en el entorno
try:
    import pypdf
except ImportError:
    try:
        import PyPDF2 as pypdf
    except ImportError:
        pypdf = None

st.set_page_config(page_title="DPA | Ingestión Flota", page_icon="📥", layout="wide")

st.title("📥 Gestión de Flota: Ingestión de Documentos")
st.markdown("Portal de carga optimizado para flota. Los PDFs multipágina se segmentan automáticamente.")
st.divider()

if "logs_errores" not in st.session_state: 
    st.session_state.logs_errores = []

if st.session_state.logs_errores:
    with st.expander("⚠️ Alertas de Procesamiento", expanded=True):
        for err in st.session_state.logs_errores:
            st.error(err)
        if st.button("Limpiar Alertas"):
            st.session_state.logs_errores = []
            st.rerun()

col_ia, col_manual = st.columns([2, 1], gap="medium")

with col_ia:
    st.subheader("⚡ Carga Asistida en Lote")
    archivos_cargados = st.file_uploader(
        "Arrastrá aquí PDFs multipágina, títulos, pólizas o VTV",
        type=["pdf", "png", "jpg"], accept_multiple_files=True, key="uploader_flota"
    )
    
    if st.button("Procesar y Enviar a Auditoría", use_container_width=True, type="primary"):
        if archivos_cargados:
            status_placeholder = st.empty()
            progreso_bar = st.progress(0)
            total = len(archivos_cargados)
            
            for idx, archivo in enumerate(archivos_cargados):
                porcentaje = int((idx + 1) / total * 100)
                progreso_bar.progress(porcentaje)
                
                try:
                    archivo_bytes = archivo.getvalue()
                    nombre_original = archivo.name
                    
                    # ✂️ SEGMENTACIÓN MULTIPÁGINA EN MEMORIA
                    if nombre_original.lower().endswith('.pdf') and pypdf is not None:
                        status_placeholder.info(f"🔍 Analizando páginas de: {nombre_original}")
                        pdf_reader = pypdf.PdfReader(io.BytesIO(archivo_bytes))
                        total_paginas = len(pdf_reader.pages)
                        
                        if total_paginas > 1:
                            status_placeholder.warning(f"✂️ Separando {total_paginas} páginas independientes...")
                            
                            for p_idx in range(total_paginas):
                                pdf_writer = pypdf.PdfWriter()
                                pdf_writer.add_page(pdf_reader.pages[p_idx])
                                
                                output_buffer = io.BytesIO()
                                pdf_writer.write(output_buffer)
                                bytes_pagina = output_buffer.getvalue()
                                
                                id_carga = f"FLOTA_{uuid.uuid4().hex[:8].upper()}"
                                fecha_ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                                
                                nombre_pagina = f"PAG_{p_idx+1}_DE_{total_paginas}_{nombre_original}"
                                nombre_destino_drive = f"PENDIENTE_{id_carga}_{nombre_pagina}"
                                
                                link_drive = subir_archivo(nombre_destino_drive, bytes_pagina, ID_DRIVE_RAIZ)
                                
                                nombre_minuscula = nombre_original.lower()
                                tipo_sugerido = "TITULO" if "titulo" in nombre_minuscula else "CEDULA_VERDE"
                                
                                datos_predichos = {
                                    "patente": "N/A", 
                                    "tipo_sugerido": tipo_sugerido, 
                                    "origen": nombre_pagina,
                                    "titular": "",
                                    "cuit_cuil": ""
                                }
                                
                                escribir_fila("PENDIENTES", [
                                    id_carga, fecha_ahora, nombre_pagina, "OPERADOR_FLOTA", 
                                    link_drive, "N/A", "PARA_AUDITAR_FLOTA", 
                                    f"Segmento {p_idx+1}/{total_paginas} extraído.", 
                                    json.dumps(datos_predichos, ensure_ascii=False)
                                ])
                            continue
                    
                    # CARGA ESTÁNDAR (Individual / Imágenes)
                    status_placeholder.info(f"⏳ Subiendo a Drive: {nombre_original}")
                    id_carga = f"FLOTA_{uuid.uuid4().hex[:8].upper()}"
                    fecha_ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    nombre_destino_drive = f"PENDIENTE_{id_carga}_{nombre_original}"
                    
                    link_drive = subir_archivo(nombre_destino_drive, archivo_bytes, ID_DRIVE_RAIZ)
                    
                    nombre_minuscula = nombre_original.lower()
                    if "titulo" in nombre_minuscula: tipo_sugerido = "TITULO"
                    elif "seguro" in nombre_minuscula or "poliza" in nombre_minuscula: tipo_sugerido = "CERTIFICADO_SEGURO"
                    elif "vtv" in nombre_minuscula: tipo_sugerido = "VTV"
                    else: tipo_sugerido = "CEDULA_VERDE"
                        
                    datos_predichos = {
                        "patente": "N/A", "tipo_sugerido": tipo_sugerido, "origen": nombre_original, "titular": "", "cuit_cuil": ""
                    }
                    
                    escribir_fila("PENDIENTES", [
                        id_carga, fecha_ahora, nombre_original, "OPERADOR_FLOTA", 
                        link_drive, "N/A", "PARA_AUDITAR_FLOTA", 
                        "Listo para auditoría.", 
                        json.dumps(datos_predichos, ensure_ascii=False)
                    ])
                    
                except Exception as e:
                    st.session_state.logs_errores.append(f"❌ Error en {archivo.name}: {str(e)}")
            
            status_placeholder.success("🎉 Carga y división completada exitosamente.")
            time.sleep(1.2)
            st.rerun()

with col_manual:
    st.subheader("✍️ Carga Manual Directa")
    with st.form("form_alta_directa", clear_on_submit=True):
        patente_m = st.text_input("Patente (Provisoria)").upper().strip()
        tipo_m = st.selectbox("Tipo Documento", ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"])
        archivo_m = st.file_uploader("Archivo", type=["pdf", "png", "jpg"])
        
        if st.form_submit_button("📥 Enviar a Control", use_container_width=True):
            if archivo_m:
                try:
                    id_carga_m = f"FLOTA_{uuid.uuid4().hex[:8].upper()}"
                    fecha_ahora_m = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    
                    link_drive_m = subir_archivo(f"MANUAL_{id_carga_m}_{archivo_m.name}", archivo_m.getvalue(), ID_DRIVE_RAIZ)
                    
                    datos_m = {"patente": patente_m if patente_m else "N/A", "tipo_sugerido": tipo_m, "origen": archivo_m.name}
                    
                    escribir_fila("PENDIENTES", [
                        id_carga_m, fecha_ahora_m, archivo_m.name, "MANUAL", 
                        link_drive_m, "N/A", "PARA_AUDITAR_FLOTA", 
                        "Carga manual.", json.dumps(datos_m, ensure_ascii=False)
                    ])
                    st.success("Enviado a revisión.")
                    time.sleep(0.8)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
