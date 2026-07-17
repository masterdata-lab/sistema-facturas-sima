import streamlit as st
from utils.conexiones import leer_hoja_completa

# 1. FORZAR BARRA CERRADA
st.set_page_config(page_title="SIMA ERP | Inicio", page_icon="🏢", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS PARA COMPACTAR, RESALTAR MENÚ Y EMBELLECER TARJETAS
st.markdown("""
<style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255, 75, 75, 0.8); }
    div[data-testid="stMetricValue"] { font-size: 2.5rem !important; color: #ff4b4b; }
</style>
""", unsafe_allow_html=True)

try: H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except: H_PENDIENTES = "PENDIENTES"

# Obtenemos estadísticas rápidas para el tablero
pendientes_ia = 0
pendientes_auditoria = 0

try:
    datos = leer_hoja_completa(H_PENDIENTES)
    for fila in datos[1:]:
        if len(fila) >= 7:
            if fila[6] == "PENDIENTE": pendientes_ia += 1
            elif fila[6] == "PARA_AUDITAR" or fila[6].startswith("ERROR"): pendientes_auditoria += 1
except:
    pass # Si hay error al leer, quedan en 0 para no romper el inicio

st.title("🏢 Grupo SIMA - ERP Inteligente")
st.markdown("Sistema integral de procesamiento de facturas, órdenes de trabajo y reportes financieros.")
st.divider()

st.subheader("Tablero de Control - Flujo de Trabajo")
st.write("") # Espaciador

col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.markdown("### ⚡ Carga Rápida")
        st.markdown("Subí facturas y órdenes de trabajo desde tu PC o escaneá con la cámara de tu celular.")
        st.write("")
        # Usamos page_link que es un botón nativo para cambiar de página
        st.page_link("pages/1_Facturacion.py", label="Ir a Cargar Documentos", icon="📤", use_container_width=True)

with col2:
    with st.container(border=True):
        st.markdown("### ⚙️ Motor IA")
        st.metric("Facturas en cola", f"{pendientes_ia}")
        st.markdown("Dejá que Gemini extraiga todos los datos de forma automática.")
        st.page_link("pages/2_Motor_Procesamiento.py", label="Ir a Procesar", icon="🤖", use_container_width=True)

with col3:
    with st.container(border=True):
        st.markdown("### ⚖️ Auditoría")
        st.metric("Esperando revisión", f"{pendientes_auditoria}")
        st.markdown("Revisá pantalla dividida, validá patentes y aprobá hacia la contabilidad.")
        st.page_link("pages/3_Auditoria.py", label="Ir a Auditar", icon="✅", use_container_width=True)

st.divider()

st.subheader("Análisis Financiero y Reportes")
with st.container(border=True):
    col_rep1, col_rep2 = st.columns([3, 1])
    with col_rep1:
        st.markdown("### 📊 Buscador y Tableros Dinámicos")
        st.markdown("Filtrá gastos por empresa de Grupo SIMA, por patente, por rango de fechas o categoría. Exportá tablas y visualizá en gráficos el destino de tus fondos.")
    with col_rep2:
        st.write("")
        st.write("")
        st.button("Módulo en Construcción 🚧", disabled=True, use_container_width=True)
