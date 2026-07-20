import streamlit as st
import time
import uuid
import json
from utils.conexiones import escribir_fila, subir_archivo, ID_DRIVE_RAIZ

st.set_page_config(page_title="DPA | Ingestión Flota", page_icon="📥", layout="wide")

st.title("📥 Gestión de Flota: Ingestión de Documentos")
st.markdown("Carga de archivos en lote para procesamiento cognitivo y posterior auditoría.")
st.divider()

if "logs_errores" not in st.session_state: 
    st.session_state.logs_errores = []

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
                    # Guardamos el nombre plano en una variable string aislada
                    nombre_archivo_plano = str(archivo.name)
                    bytes_crudos = archivo.read()
                    
                    # Subida a Drive exitosa
                    link_drive = subir_archivo(archivo, bytes_crudos, ID_DRIVE_RAIZ)
                    
                    if not link_drive or link_drive == "N/A":
                        raise ValueError("Google Drive no retornó un enlace de acceso válido.")
                    
                    id_carga = f"FLOTA_{uuid.uuid4().hex[:8].upper()}"
                    
                    nombre_minuscula = nombre_archivo_plano.lower()
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
                        
                    # Aislamos el diccionario garantizando que son solo STRINGS nativos de Python
                    datos_predichos = {
                        "patente": "N/A", 
                        "tipo_sugerido": str(tipo_sugerido), 
                        "origen": nombre_archivo_plano,
                        "titular": "",
                        "cuit_cuil": ""
                    }
                    
                    payload_json = json.dumps(datos_predichos, ensure_ascii=False)
                    
                    escribir_fila("PENDIENTES", [
                        str(id_carga), 
                        str(time.strftime("%d/%m/%Y")), 
                        nombre_archivo_plano, 
                        "OPERADOR_FLOTA", 
                        str(link_drive), 
                        str(id_carga), 
                        "PARA_AUDITAR_FLOTA", 
                        "Subida correcta. Esperando visado humano.", 
                        payload_json
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
                    nombre_manual_plano = str(archivo_m.name)
                    bytes_crudos_m = archivo_m.read()
                    
                    link_drive_m = subir_archivo(archivo_m, bytes_crudos_m, ID_DRIVE_RAIZ)
                    
                    if not link_drive_m or link_drive_m == "N/A":
                        raise ValueError("No se pudo obtener enlace de Drive en la carga manual.")
                        
                    id_carga_m = f"FLOTA_{uuid.uuid4().hex[:8].upper()}"
                    
                    datos_m = {
                        "patente": str(patente_m) if patente_m else "N/A", 
                        "tipo_sugerido": str(tipo_m), 
                        "origen": nombre_manual_plano
                    }
                    
                    payload_json_m = json.dumps(datos_m, ensure_ascii=False)
                    
                    escribir_fila("PENDIENTES", [
                        str(id_carga_m), 
                        str(time.strftime("%d/%m/%Y")), 
                        nombre_manual_plano, 
                        "MANUAL", 
                        str(link_drive_m), 
                        str(id_carga_m), 
                        "PARA_AUDITAR_FLOTA", 
                        "Ingreso manual directo.", 
                        payload_json_m
                    ])
                    st.success("¡Enviado a la cola de revisión!")
                    time.sleep(0.8)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error en carga manual: {e}")
            else:
                st.error("Debes adjuntar el archivo para poder enviarlo a control.")
