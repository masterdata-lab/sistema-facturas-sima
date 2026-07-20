import streamlit as st
import time
import uuid
from utils.conexiones import escribir_fila, subir_archivo # Usando tus conectores

st.title("📥 Gestión de Flota: Ingestión de Documentos")
st.markdown("Carga de archivos en lote para procesamiento cognitivo y posterior auditoría.")
st.divider()

if "logs_errores" not in st.session_state: st.session_state.logs_errores = []

col_ia, col_manual = st.columns([2, 1])

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
                progreso_bar.progress(int((idx + 1) / total * 100))
                status_placeholder.info(f"⏳ Subiendo {idx+1}/{total}: **{archivo.name}**")
                
                try:
                    # 1. Se sube el archivo físico a tu Drive temporal/raíz (Igual que en facturas)
                    # link_drive = subir_archivo(archivo) 
                    link_drive = "https://drive.google.com/file/d/1abc123_MOCK_ID/preview" 
                    id_carga = f"FLOTA_{uuid.uuid4().hex[:8].upper()}"
                    
                    # 2. IA Engine Mock (Simula lectura inicial, luego lo corregimos en el visor)
                    tipo_sugerido = "TITULO" if "titulo" in archivo.name.lower() else "CEDULA_VERDE"
                    datos_predichos = {"patente": "N/A", "tipo_sugerido": tipo_sugerido, "origen": archivo.name}
                    
                    import json
                    # Inyectamos en la hoja PENDIENTES de tu estructura maestro
                    escribir_fila("PENDIENTES", [
                        id_carga, 
                        time.strftime("%d/%m/%Y"), 
                        archivo.name, 
                        "OPERADOR_FLOTA", 
                        link_drive, 
                        "DRIVE_ID_MOCK", 
                        "PARA_AUDITAR_FLOTA", 
                        "Pendiente revisión humana", 
                        json.dumps(datos_predichos)
                    ])
                except Exception as e:
                    st.session_state.logs_errores.append(f"Falla en {archivo.name}: {str(e)}")
            
            status_placeholder.success("🎉 Lote procesado. Los documentos esperan en la Mesa de Auditoría.")
            time.sleep(1)
            st.rerun()

with col_manual:
    st.subheader("✍️ Registro Manual Directo")
    with st.form("form_alta_directa", clear_on_submit=True):
        patente_m = st.text_input("Patente sugerida / provisoria").upper().strip()
        tipo_m = st.selectbox("Tipo Documento", ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"])
        archivo_m = st.file_uploader("Adjuntar archivo", type=["pdf", "png", "jpg"])
        
        if st.form_submit_button("📥 Enviar a Cola de Control", use_container_width=True):
            if archivo_m:
                id_carga = f"FLOTA_{uuid.uuid4().hex[:8].upper()}"
                import json
                datos_m = {"patente": patente_m if patente_m else "N/A", "tipo_sugerido": tipo_m, "origen": archivo_m.name}
                escribir_fila("PENDIENTES", [
                    id_carga, time.strftime("%d/%m/%Y"), archivo_m.name, "MANUAL", 
                    "https://drive.google.com/file/d/1abc123_MOCK_ID/preview", "DRIVE_ID", 
                    "PARA_AUDITAR_FLOTA", "Ingreso manual", json.dumps(datos_m)
                ])
                st.success("Enviado a revisión.")
