import streamlit as st
import time
# Importamos tus módulos del core
from core.processor import segmentar_pdf_en_memoria, generar_nombre_legible
from utils.conexiones import leer_hoja_completa  # Usando tu conector existente

# Estilos específicos para la Mesa de Control
st.markdown("""
<style>
    .card-duplicado { border: 2px solid #ff4b4b; background-color: rgba(255,75,75,0.05); padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    .card-normal { border: 1px solid #c1c1c1; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("📥 Gestión de Flota: Ingestión y Mesa de Auditoría")
st.markdown("Carga unificada de documentación con validación manual estricta antes de impactar en las bases de datos.")
st.divider()

# --- VALIDACIÓN BASE DE DATOS LOCAL EN TIEMPO REAL ---
# Traemos las patentes activas en la hoja FLOTA para validar que el auto exista
@st.cache_data(ttl=60)
def obtener_patentes_validas():
    try:
        # Reemplazar "FLOTA" por el nombre exacto de tu pestaña principal
        datos_flota = leer_hoja_completa("FLOTA")
        # Asumimos que la columna 0 es 'Patente'
        return [str(fila[0]).upper().strip() for fila in datos_flota[1:] if fila]
    except:
        return []

patentes_existentes = obtener_patentes_validas()

# --- FASE 1: PANEL DE INGESTIÓN (CARGA AUTOMÁTICA & MANUAL) ---
col_ia, col_manual = st.columns([2, 1])

with col_ia:
    st.subheader("⚡ Carga Asistida por IA (Lotes Mixtos)")
    archivos_cargados = st.file_uploader(
        "Arrastrá aquí PDFs multipágina, pólizas extensas, imágenes de cédulas o VTV",
        type=["pdf", "png", "jpg"],
        accept_multiple_files=True,
        key="uploader_flota_ia"
    )
    
    col_b1, col_b2 = st.columns(2)
    if col_b1.button("Procesar Documentos", use_container_width=True, type="primary"):
        if archivos_cargados:
            st.session_state.abortar_proceso = False
            status_placeholder = st.empty()
            progreso_bar = st.progress(0)
            
            total = len(archivos_cargados)
            for idx, archivo in enumerate(archivos_cargados):
                if st.session_state.abortar_proceso:
                    st.error("⛔ Operación cancelada por el usuario.")
                    break
                
                # Barra de progreso limpia sin apilar elementos visuales
                progreso_bar.progress(int((idx + 1) / total * 100))
                status_placeholder.info(f"⏳ Procesando {idx+1}/{total}: **{archivo.name}**")
                
                try:
                    # Segmentación local vía pypdf para evitar timeouts
                    if archivo.name.endswith(".pdf"):
                        paginas = segmentar_pdf_en_memoria(archivo)
                    else:
                        paginas = [{"nombre_origen": archivo.name, "stream": archivo}]
                    
                    for p in paginas:
                        time.sleep(0.4)  # Simulación de llamada a Gemini 3.5-flash
                        
                        # Simulación de respuesta estructurada JSON de la IA
                        # En el siguiente paso integraremos el archivo core/ai_engine.py real
                        tipo_detectado = "CERTIFICADO_SEGURO" if "seguro" in p["nombre_origen"].lower() else "CEDULA_VERDE"
                        patente_detectada = "AA192BQ"
                        
                        # Verificación de duplicados en la sesión actual
                        existe_duplicado = any(d["patente"] == patente_detectada and d["tipo_sugerido"] == tipo_detectado for d in st.session_state.bandeja_auditoria)
                        
                        st.session_state.bandeja_auditoria.append({
                            "id_interno": f"ia_{time.time()}_{idx}",
                            "origen": p["nombre_origen"],
                            "tipo_sugerido": tipo_detectado,
                            "patente": patente_detectada,
                            "cuit_cuil": "30-76543210-9",
                            "titular_nombre": "GRUPO SIMA S.A.",
                            "aseguradora": "Federación Patronal",
                            "numero_poliza": "987654",
                            "fecha_vencimiento": "01/08/2026",
                            "es_duplicado": existe_duplicado
                        })
                except Exception as e:
                    # Persistencia estricta de errores pedida por requerimiento
                    st.session_state.logs_errores.append(f"Falla crítica en {archivo.name}: {str(e)}")
            
            status_placeholder.success("🎉 ¡Procesamiento finalizado! Datos enviados a la mesa inferior.")
        else:
            st.warning("Por favor, selecciona al menos un archivo.")

    if col_b2.button("⚠️ Cancelar Procesamiento", use_container_width=True):
        st.session_state.abortar_proceso = True

with col_manual:
    st.subheader("✍️ Carga Manual (Bypass de IA)")
    st.markdown("Subí el documento y completá los datos a mano saltando el motor de IA.")
    with st.form("form_bypass_manual", clear_on_submit=True):
        doc_m = st.file_uploader("Archivo", type=["pdf", "png", "jpg"], key="file_manual")
        tipo_m = st.selectbox("Tipo de Documento", ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "RTO", "YPF"])
        patente_m = st.text_input("Patente").upper().strip()
        
        if st.form_submit_button("📥 Enviar Directo a Auditoría", use_container_width=True):
            if doc_m and patente_m:
                st.session_state.bandeja_auditoria.append({
                    "id_interno": f"manual_{time.time()}",
                    "origen": doc_m.name,
                    "tipo_sugerido": tipo_m,
                    "patente": patente_m,
                    "cuit_cuil": "",
                    "titular_nombre": "",
                    "aseguradora": "",
                    "numero_poliza": "",
                    "fecha_vencimiento": "",
                    "es_duplicado": any(d["patente"] == patente_m and d["tipo_sugerido"] == tipo_m for d in st.session_state.bandeja_auditoria)
                })
                st.success(f"Archivo de patente {patente_m} enviado a la cola.")
            else:
                st.error("Faltan campos obligatorios (Archivo y Patente).")

# --- CONTEXTO DE ERRORES FIJOS EN PANTALLA ---
if st.session_state.logs_errores:
    st.markdown("---")
    st.subheader("🚨 Alertas de Lectura de este Lote")
    for err in st.session_state.logs_errores:
        st.error(err)
    if st.button("🗑️ Limpiar Historial de Errores"):
        st.session_state.logs_errores = []
        st.rerun()

# --- FASE 2: MESA DE AUDITORÍA (HUMAN-IN-THE-LOOP) ---
st.markdown("---")
st.subheader("⚖️ Mesa de Auditoría (Pre-visado Manual)")

if not st.session_state.bandeja_auditoria:
    st.info("La mesa de auditoría está vacía. Cargá archivos arriba para empezar a validar.")
else:
    st.caption(f"Tienes {len(st.session_state.bandeja_auditoria)} documentos pendientes de revisión.")
    
    # Iteramos la bandeja en reversa para ver siempre lo último arriba
    for item in list(st.session_state.bandeja_auditoria):
        clase_css = "card-duplicado" if item["es_duplicado"] else "card-normal"
        
        st.markdown(f'<div class="{clase_css}">', unsafe_allow_html=True)
        
        # Alerta visual explícita si el sistema detecta colisión de archivos
        if item["es_duplicado"]:
            st.warning(f"⚠️ **Resolución de Duplicados Activa:** Ya existe un documento tipo '{item['tipo_sugerido']}' cargado en esta sesión para la patente {item['patente']}.")
        
        c1, c2, c3 = st.columns([1, 2, 1])
        
        with c1:
            st.markdown(f"**Origen:** `{item['origen']}`")
            # Selector de tipo de documento que permite corregir la clasificación de la IA
            item["tipo_sugerido"] = st.selectbox("Clasificación Fiel", ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "RTO", "YPF"], index=["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "RTO", "YPF"].index(item["tipo_sugerido"]), key=f"tipo_{item['id_interno']}")
            
            # Validación visual si la patente no matchea con tu maestro real
            item["patente"] = st.text_input("Patente Asociada", value=item["patente"], key=f"pat_{item['id_interno']}").upper().strip()
            if patentes_existentes and item["patente"] not in patentes_existentes:
                st.error("⚠️ Esta patente no se encuentra registrada en la hoja FLOTA principal.")
        
        with c2:
            st.markdown("**Datos Extraídos (Campos Editables):**")
            sub_col1, sub_col2 = st.columns(2)
            
            with sub_col1:
                item["titular_nombre"] = st.text_input("Nombre Titular / Tomador", value=item["titular_nombre"], key=f"nom_{item['id_interno']}")
                item["cuit_cuil"] = st.text_input("CUIT / CUIL Vinculado", value=item["cuit_cuil"], key=f"cuit_{item['id_interno']}")
            
            with sub_col2:
                # Si es seguro habilitamos datos contractuales
                if item["tipo_sugerido"] == "CERTIFICADO_SEGURO":
                    item["aseguradora"] = st.text_input("Aseguradora", value=item["aseguradora"], key=f"aseg_{item['id_interno']}")
                    item["numero_poliza"] = st.text_input("Nº de Póliza", value=item["numero_poliza"], key=f"pol_{item['id_interno']}")
                
                # Gestión del Vencimiento (Exceptuando Cédulas por Ley)
                if item["tipo_sugerido"] != "CEDULA_VERDE":
                    item["fecha_vencimiento"] = st.text_input("Fecha Vencimiento (DD-MM-YYYY)", value=item["fecha_vencimiento"], key=f"vto_{item['id_interno']}")
                else:
                    st.caption("💡 Cédula Verde seleccionada: Por ley no se computará vencimiento restrictivo en los semáforos.")

        with c3:
            st.markdown("**Acciones de Control:**")
            st.write("")
            
            # Procesamiento de nombres estricto y limpio utilizando tu core
            nombre_final_drive = generar_nombre_legible(item["tipo_sugerido"], item)
            st.caption(f"📂 Guardado en Drive como:\n`{nombre_final_drive}`")
            
            # --- BOTÓN DE INYECCIÓN INTEGRADO ---
            if st.button("✅ Validar e Inyectar", key=f"btn_ok_{item['id_interno']}", use_container_width=True, type="primary"):
                from core.flota_injector import inyectar_documento_flota
                
                with st.spinner("Procesando e inyectando en bases de datos..."):
                    exito, resultado = inyectar_documento_flota(item)
                
                if exito:
                    st.success("¡Documento visado e impactado con éxito!")
                    # Remoción limpia del archivo procesado de la lista de auditoría
                    st.session_state.bandeja_auditoria.remove(item)
                    time.sleep(0.6)
                    st.rerun()
                else:
                    st.error(f"Error de consistencia: {resultado}")
                
            # --- BOTÓN DE DESCARTE ---
            if st.button("🗑️ Descartar", key=f"btn_del_{item['id_interno']}", use_container_width=True):
                st.session_state.bandeja_auditoria.remove(item)
                st.warning("Documento eliminado de la bandeja de entrada.")
                time.sleep(0.5)
                st.rerun()
                
        st.markdown('</div>', unsafe_allow_html=True)
