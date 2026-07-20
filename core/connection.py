import streamlit as st
# Nota: Suponiendo el uso de gsheets-connection o la API oficial de Google
# Para mantener el ejemplo limpio, centralizamos la simulación de acceso robusto

def get_sheets_client():
    """Retorna la instancia de conexión activa a Google Sheets."""
    if "sheets_client" not in st.session_state:
        # Aquí va tu lógica de autenticación actual con service_account
        st.session_state.sheets_client = "Instancia_Sheets"
    return st.session_state.sheets_client

def get_drive_client():
    """Retorna la instancia de conexión activa a Google Drive."""
    if "drive_client" not in st.session_state:
        st.session_state.drive_client = "Instancia_Drive"
    return st.session_state.drive_client

def inicializar_estados():
    """Inicializa las variables de estado globales para evitar pérdidas de datos en reruns."""
    if "bandeja_auditoria" not in st.session_state:
        st.session_state.bandeja_auditoria = []
    if "logs_errores" not in st.session_state:
        st.session_state.logs_errores = []
    if "abortar_proceso" not in st.session_state:
        st.session_state.abortar_proceso = False
