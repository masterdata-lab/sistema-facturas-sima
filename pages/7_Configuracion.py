import streamlit as st

st.title("⚙️ Parámetros Globales del Sistema")
st.markdown("Centralización de tokens de API, identificadores de bases de datos y rutas de almacenamiento legal.")
st.divider()

# Inicializamos las variables en session_state para que estén disponibles en toda la app
if "id_sheet_flota" not in st.session_state:
    st.session_state.id_sheet_flota = st.secrets.get("SPREADSHEET_ID", "1abc123_ID_DE_TU_SHEET_DE_FLOTA")
if "id_folder_drive" not in st.session_state:
    st.session_state.id_folder_drive = st.secrets.get("DRIVE_FOLDER_ID", "1xyz789_ID_CARPETA_RAIZ_DRIVE")

tab_sheets, tab_drive, tab_ia = st.tabs(["📊 Google Sheets", "📁 Google Drive", "🤖 Configuración IA"])

with tab_sheets:
    st.subheader("Conexión a Bases de Datos (Planillas)")
    st.session_state.id_sheet_flota = st.text_input(
        "ID del Spreadsheet (Google Sheets)", 
        value=st.session_state.id_sheet_flota,
        help="El string largo que aparece en la URL de tu hoja de cálculo."
    )
    
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.text_input("Nombre Hoja Principal Flota", value="FLOTA", disabled=True)
    with col_h2:
        st.text_input("Nombre Hoja Historial Seguros", value="HISTORIAL_SEGUROS", disabled=True)

with tab_drive:
    st.subheader("Repositorio de Archivos Legibles")
    st.markdown("Todos los archivos aprobados en la mesa de auditoría se renombrarán y guardarán bajo este directorio jerárquico.")
    st.session_state.id_folder_drive = st.text_input(
        "ID de la Carpeta Raíz en Google Drive", 
        value=st.session_state.id_folder_drive
    )
    st.caption("⚠️ Nota: La cuenta de servicio (Service Account) configurada en la app debe tener permisos de Editor en esta carpeta.")

with tab_ia:
    st.subheader("Motor de Extracción Cognitiva")
    st.selectbox("Modelo Seleccionado", ["Gemini 1.5 Flash (Recomendado)", "Gemini 1.5 Pro (Alta Precisión)"], index=0)
    st.checkbox("Forzar validación estricta de CUIT/CUIL en documentos extraídos", value=True)

st.write("")
if st.button("💾 Guardar Parámetros en Sesión", type="primary", use_container_width=True):
    st.success("¡Configuración actualizada en caliente para los módulos de Ingestión y Búsqueda!")
    st.toast("Parámetros guardados correctamente.", icon="⚙️")
