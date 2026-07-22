import streamlit as st
import pandas as pd

st.set_page_config(page_title="Auditoría de Flota", page_icon="⚖️", layout="wide")

# Leemos la configuración global (centralizada en secrets)
HOJA_PENDIENTES = st.secrets["HOJA_PENDIENTES_FLOTA"]
MOTOR_IA = st.secrets["MODELO_PRIMARIO"]

st.title("⚖️ Auditoría de Documentos (Flota)")
st.markdown(f"**Motor activo:** `{MOTOR_IA}` | **Bandeja:** `{HOJA_PENDIENTES}`")
st.divider()

# --- DATOS SIMULADOS (Hasta que conectemos la lectura real de Google Sheets) ---
# Simulamos que la IA ya procesó un lote (ID_CARGA: LOTE-889) con 3 certificados exitosos
datos_lote = pd.DataFrame({
    "PATENTE": ["AB123CD", "EF456GH", "IJ789KL"],
    "EMPRESA": ["LA BIZANTINA", "LA BIZANTINA", "LA BIZANTINA"],
    "TIPO_DOC": ["CERT. COBERTURA", "CERT. COBERTURA", "CERT. COBERTURA"],
    "VENCIMIENTO": ["2026-12-31", "2026-12-31", "2026-12-31"],
    "ESTADO_IA": ["🟢 Éxito", "🟢 Éxito", "🟢 Éxito"]
})

st.subheader("📦 Lote Pendiente: Póliza La Bizantina (LOTE-889)")
st.caption("Subido el 22/07/2026 - 70 páginas procesadas.")

# Mostramos el resumen de lo que la IA entendió para revisión humana rápida
st.dataframe(
    datos_lote,
    use_container_width=True,
    hide_index=True
)

st.write("")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    # El botón gigante anti-fatiga
    if st.button("✅ Aprobar Lote Completo (65 Certificados)", type="primary", use_container_width=True):
        # Aquí irá la lógica que impacta la hoja FLOTA y limpia PENDIENTES_FLOTA
        st.success("¡Lote aprobado! Los 65 vehículos fueron actualizados en la base de datos.")
        
with col2:
    if st.button("⚠️ Rechazar Lote", use_container_width=True):
        st.error("Lote rechazado y eliminado de la bandeja.")

with col3:
    # La botonera universal para PDFs
    st.button("📑 Ver Póliza Madre", use_container_width=True, help="Abre el contrato general original")
