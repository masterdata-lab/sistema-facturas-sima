import streamlit as st
from core.connection import inicializar_estados
from modules import dashboard, ingestion, auditoria, buscador

# Configuración de página obligatoria al inicio
st.set_page_config(page_title="Módulo de Flota ERP", layout="wide")

# Inicializar estados de sesión persistentes
inicializar_estados()

st.sidebar.title("🗂️ Gestión de Flota SIMA")
st.sidebar.markdown("---")

opcion = st.sidebar.radio(
    "Menú de Operaciones",
    ["📊 Semáforo de Control", "📥 Ingestión de Documentos", "⚖️ Mesa de Auditoría", "🔍 Buscador Avanzado"]
)

st.sidebar.markdown("---")
st.sidebar.caption("Versión 2.0 - Manual-First Architecture (2026)")

# Enrutador de módulos
if opcion == "📊 Semáforo de Control":
    dashboard.render()
elif opcion == "📥 Ingestión de Documentos":
    ingestion.render()
elif opcion == "⚖️ Mesa de Auditoría":
    auditoria.render()
elif opcion == "🔍 Buscador Avanzado":
    buscador.render()
