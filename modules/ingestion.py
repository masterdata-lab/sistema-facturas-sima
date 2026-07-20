import streamlit as st
import time
from core.processor import segmentar_pdf_en_memoria

def render():
    st.title("📥 Ingestión de Documentos de Flota")
    st.markdown("Subí lotes de archivos mixtos. El sistema los clasificará y enviará a auditoría.")

    # Inicializar bandera de cancelación
    st.session_state.abortar_proceso = False

    # Layout de carga: 2 columnas para separar Automático de Manual
    col_auto, col_manual = st.columns([2, 1])

    with col_auto:
        st.subheader("Modo Automático Asistido por IA")
        archivos_cargados = st.file_uploader(
            "Arrastrá tus PDFs o fotos aquí", 
            type=["pdf", "jpg", "png"], 
            accept_multiple_files=True,
            key="uploader_auto"
        )
        
        if archivos_cargados:
            col_btn1, col_btn2 = st.columns(2)
            procesar = col_btn1.button("⚡ Iniciar Procesamiento Masivo", use_container_width=True)
            if col_btn2.button("⚠️ Cancelar Procesamiento", use_container_width=True):
                st.session_state.abortar_proceso = True
                st.warning("Petición de parada enviada...")

            if procesar:
                # Contenedor dinámico único para evitar pilas largas de UI
                status_container = st.empty()
                progress_bar = st.progress(0)
                
                total_archivos = len(archivos_cargados)
                
                for idx, archivo in enumerate(archivos_cargados):
                    if st.session_state.abortar_proceso:
                        st.error("⛔ Procesamiento cancelado por el usuario.")
                        break
                    
                    # Actualización compacta de progreso
                    porcentaje = int((idx + 1) / total_archivos * 100)
                    progress_bar.progress(porcentaje)
                    status_container.info(f"⏳ Procesando archivo {idx+1} de {total_archivos}: **{archivo.name}**")
                    
                    try:
                        # 1. Segmentar si es PDF
                        if archivo.name.endswith(".pdf"):
                            paginas = segmentar_pdf_en_memoria(archivo)
                        else:
                            paginas = [{"nombre_origen": archivo.name, "stream": archivo}]
                        
                        for pag in paginas:
                            # 2. Simulación de llamada al ai_engine (Próximo módulo)
                            # Aquí se llamará a la IA para clasificar y extraer
                            time.sleep(0.5) # Simulación de delay de API
                            
                            # Ejemplo de mock de datos extraídos por la IA
                            datos_extraidos = {
                                "id_interno": f"tmp_{time.time()}",
                                "origen": pag["nombre_origen"],
                                "tipo_sugerido": "CERTIFICADO_SEGURO",
                                "patente": "AA192BQ",
                                "cuit_cuil": "30-76543210-9",
                                "titular_nombre": "GRUPO SIMA S.A.",
                                "aseguradora": "Federacion Patronal",
                                "numero_poliza": "987654",
                                "fecha_vencimiento": "01/08/2026",
                                "es_duplicado": False # Lógica que chequeará contra la BD
                            }
                            
                            st.session_state.bandeja_auditoria.append(datos_extraidos)
                            
                    except Exception as e:
                        # Los errores se apilan de forma fija en la sesión
                        st.session_state.logs_errores.append(f"Error en {archivo.name}: {str(e)}")
                
                status_container.success("🎉 Procesamiento del lote finalizado. Revisá la Mesa de Auditoría.")

    with col_manual:
        st.subheader("Bypass Manual Directo")
        st.markdown("Si la IA falla o el archivo es ilegible, envialo directo a auditoría vacío.")
        
        with st.form("carga_manual_form", clear_on_submit=True):
            doc_manual = st.file_uploader("Adjuntar Documento", type=["pdf", "jpg", "png"], key="manual_file")
            tipo_manual = st.selectbox("Tipo de Documento", ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "RTO", "YPF"])
            patente_manual = st.text_input("Patente (Opcional)").upper().strip()
            
            enviar_a_auditoria = st.form_submit_button("📥 Enviar Directo a Auditoría", use_container_width=True)
            
            if enviar_a_auditoria:
                if doc_manual is not None:
                    datos_manual = {
                        "id_interno": f"manual_{time.time()}",
                        "origen": doc_manual.name,
                        "tipo_sugerido": tipo_manual,
                        "patente": patente_manual if patente_manual else "VERIFICAR",
                        "cuit_cuil": "",
                        "titular_nombre": "",
                        "aseguradora": "",
                        "numero_poliza": "",
                        "fecha_vencimiento": "",
                        "es_duplicado": False
                    }
                    st.session_state.bandeja_auditoria.append(datos_manual)
                    st.success(f"Documento enviado a la mesa de control sin lectura de IA.")
                else:
                    st.error("Debes adjuntar un archivo para el bypass manual.")

    # --- ZONA DE LOGS DE ERROR PERSISTENTES ---
    st.markdown("---")
    st.subheader("⚠️ Alertas del Lote (Errores de lectura)")
    
    if st.session_state.logs_errores:
        for error in st.session_state.logs_errores:
            st.error(error)
        if st.button("🗑️ Limpiar Historial de Errores"):
            st.session_state.logs_errores = []
            st.rerun()
    else:
        st.caption("No se registraron fallas de lectura en este lote.")
