import streamlit as st

# 1. Configuración de la página (DEBE SER LA PRIMERA LÍNEA DE CÓDIGO)
st.set_page_config(
    page_title="SIMA ERP | Panel Principal",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Estilos personalizados para darle un look corporativo
st.markdown("""
    <style>
    .titulo-principal {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0px;
    }
    .subtitulo {
        font-size: 1.1rem;
        color: #6B7280;
        margin-bottom: 30px;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Encabezado
st.markdown('<p class="titulo-principal">🏢 Grupo SIMA | Portal de Gestión</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitulo">Seleccione un módulo para comenzar a trabajar</p>', unsafe_allow_html=True)
st.divider()

# 4. Botones de Navegación (Módulos)
col1, col2, col3 = st.columns(3)

with col1:
    st.info("### 🧾 FACTURACIÓN")
    st.write("Carga de comprobantes con IA, auditoría humana y control de duplicados.")
    # st.page_link navega directamente a los archivos de la carpeta pages/
    st.page_link("pages/1_Facturacion.py", label="Ir a Facturación", icon="🚀")

with col2:
    st.success("### 🚛 FLOTA ACTIVA")
    st.write("Gestión de títulos, seguros, cédulas y vinculación de patentes.")
    st.page_link("pages/4_Flota.py", label="Ir a Flota", icon="📋")

with col3:
    st.warning("### 🔧 TALLER Y MANTENIMIENTO")
    st.write("Coordinación de servicios, autorizaciones y seguimiento de reparaciones.")
    st.page_link("pages/5_Taller.py", label="Ir a Taller", icon="🛠️")

st.divider()

# 5. Dashboard / Tablero de Estado (Visualmente atractivo)
st.markdown("### 📊 Estado General del Sistema")
met1, met2, met3, met4 = st.columns(4)

with met1:
    st.metric(label="Facturas Pendientes de Auditoría", value="0", delta="-3 revisadas hoy", delta_color="normal")
with met2:
    st.metric(label="Flota Activa", value="142", delta="2 altas recientes", delta_color="normal")
with met3:
    st.metric(label="Servicios en Taller", value="5", delta="1 por autorizar", delta_color="inverse")
with met4:
    st.metric(label="Estado del Servidor IA", value="🟢 Óptimo", delta="API Conectada")
