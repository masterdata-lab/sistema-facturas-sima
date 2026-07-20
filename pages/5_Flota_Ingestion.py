import streamlit as st
import time
import uuid
import json
from utils.conexiones import escribir_fila, subir_archivo, ID_DRIVE_RAIZ

st.set_page_config(page_title="DPA | Ingestión Flota", page_icon="📥", layout="wide")

st.title("📥 Gestión de Flota: Ingestión de Documentos")
st.markdown("Carga de archivos en lote para procesamiento cognitivo y posterior auditoría.")
st.divider()

# Inicialización segura de logs de errores
if "logs_errores" not in st.session_state: 
    st.session_state.logs_errores = []

# Muestra de errores en la parte superior si los hubiere
if st.session_state.logs_errores:
    with st.expander("⚠️ Alertas e Incidencias en la Carga", expanded=True):
        for err in st.session_state.logs_errores:
            st.error(err)
        if st.button("Limpiar historial de alertas"):
            st.session_state.logs_errores = []
            st.rerun()

col_ia, col_manual = st.columns([2, 1], gap="medium")

with col_ia:
    st.subheader("⚡ Carga en Lote / Asistida")
    archivos_cargados = st.file_uploader(
        "Arrastrá aquí PDFs multipágina, pólizas, imágenes de cédulas o VTV",
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
                status_placeholder.info(f"⏳ Subiendo e indexando en Drive ({idx+1}/{total}): **{archivo.name}**")
                
                try:
                    # --- FIRMA CORREGIDA: Leemos los bytes del archivo y pasamos la carpeta destino ---
                    bytes_crudos = archivo.read()
                    link_drive = subir_archivo(bytes_crudos, ID_DRIVE_RAIZ)
                    
                    if not link_drive or link_drive == "N/A":
                        raise ValueError("Google Drive no retornó un enlace de acceso válido.")
                    
                    id_carga = f"FLOTA_{uuid.uuid4().hex[:8].upper()}"
                    
                    nombre_minuscula = archivo.name.lower()
                    if "titulo" in nombre_minuscula:
                        tipo_sugerido = "TITULO"
                    elif "seguro" in nombre_minuscula or "poliza" in nombre_minuscula:
                        tipo_sugerido = "CERTIFICADO_SEGURO"
                    elif "vtv" in nombre_minuscula:
                        tipo_sugerido = "VTV"
                    elif "ypf" in nombre_minuscula:
                        tipo_sugerido = "YPF"
                    else:
                        tipo_sugerido = "CEDULA_VERDE"
                        
                    datos_predichos = {
                        "patente": "N/A", 
                        "tipo_sugerido": tipo_sugerido, 
                        "origen": archivo.name,
                        "titular": "",
                        "cuit_cuil": ""
                    }
                    
                    escribir_fila("PENDIENTES", [
                        id_carga, 
                        time.strftime("%d/%m/%Y"), 
                        archivo.name, 
                        "OPERADOR_FLOTA", 
                        link_drive, 
                        id_carga, 
                        "PARA_AUDITAR_FLOTA", 
                        "Subida correcta. Esperando visado humano.", 
                        json.dumps(datos_predichos)
                    ])
                    
                except Exception as e:
                    st.session_state.logs_errores.append(f"❌ Error crítico en {archivo.name}: {str(e)}")
            
            status_placeholder.success("🎉 Lote procesado. Los documentos esperan en la Mesa de Auditoría.")
            time.sleep(1.2)
            st.rerun()
        else:
            st.warning("Por favor, selecciona al menos un archivo para subir.")

with col_manual:
    st.subheader("✍️ Registro Manual Directo")
    with st.form("form_alta_directa", clear_on_submit=True):
        patente_m = st.text_input("Patente sugerida / provisoria").upper().strip()
        tipo_m = st.selectbox("Tipo Documento", ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"])
        archivo_m = st.file_uploader("Adjuntar archivo físico", type=["pdf", "png", "jpg"])
        
        if st.form_submit_button("📥 Enviar a Cola de Control", use_container_width=True):
            if archivo_m:
                try:
                    # --- FIRMA CORREGIDA EN CARGA MANUAL ---
                    bytes_crudos_m = archivo_m.read()
                    link_drive_m = subir_archivo(bytes_crudos_m, ID_DRIVE_RAIZ)
                    
                    if not link_drive_m or link_drive_m == "N/A":
                        raise ValueError("No se pudo obtener enlace de Drive en la carga manual.")
                        
                    id_carga_m = f"FLOTA_{uuid.uuid4().hex[:8].upper()}"
                    datos_m = {"patente": patente_m if patente_m else "N/A", "tipo_sugerido": tipo_m, "origen": archivo_m.name}
                    
                    escribir_fila("PENDIENTES", [
                        id_carga_m, 
                        time.strftime("%d/%m/%Y"), 
                        archivo_m.name, 
                        "MANUAL", 
                        link_drive_m, 
                        id_carga_m, 
                        "PARA_AUDITAR_FLOTA", 
                        "Ingreso manual directo.", 
                        json.dumps(datos_m)
                    ])
                    st.success("¡Enviado a la cola de revisión!")
                    time.sleep(0.8)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error en carga manual: {e}")
            else:
                st.error("Debes adjuntar el archivo para poder enviarlo a control.")
