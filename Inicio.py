import streamlit as st
from utils.conexiones import leer_hoja_completa

st.set_page_config(page_title="DPA | ERP", page_icon="🏢", layout="wide", initial_sidebar_state="collapsed")

def tablero_principal():
    st.markdown("""
    <style>
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255, 75, 75, 0.8); }
        div[data-testid="stMetricValue"] { font-size: 2.5rem !important; color: #ff4b4b; }
        ::-webkit-scrollbar { width: 10px !important; height: 10px !important; background-color: #f1f1f1 !important; }
        ::-webkit-scrollbar-thumb { background-color: #c1c1c1 !important; border-radius: 5px !important; }
        ::-webkit-scrollbar-thumb:hover { background-color: #a8a8a8 !important; }
        .firma-flotante { position: fixed; bottom: 8px; right: 15px; font-size: 10.5px; color: rgba(128, 128, 128, 0.6); z-index: 99999; pointer-events: none; font-family: monospace; }
    </style>
    <div class="firma-flotante">Software DPA | Creado por Serrano Cristian</div>
    """, unsafe_allow_html=True)

    try: H_PENDIENTES = st.secrets.get("HOJA_PENDIENTES", "PENDIENTES")
    except: H_PENDIENTES = "PENDIENTES"

    pendientes_ia, pendientes_auditoria = 0, 0
    try:
        datos = leer_hoja_completa(H_PENDIENTES)
        for fila in datos[1:]:
            if len(fila) >= 7:
                if fila[6] == "PENDIENTE": pendientes_ia += 1
                elif fila[6] in ["PARA_AUDITAR", "CARGA_MANUAL_DIRECTA"] or str(fila[6]).startswith("ERROR"): pendientes_auditoria += 1
    except: pass 

    st.title("🏢 DPA - Software de Gestión")
    st.markdown("Sistema integral de procesamiento de comprobantes, flotas y reportes financieros.")
    st.divider()

    st.subheader("Tablero de Control - Flujo de Trabajo")
    st.write("") 

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.markdown("### ⚡ Carga Rápida")
            st.markdown("Subí facturas desde tu PC o celular con opción manual.")
            st.write(""); st.page_link("pages/1_Facturacion.py", label="Ir a Cargar", icon="📤", use_container_width=True)
    with col2:
        with st.container(border=True):
            st.markdown("### 🤖 Motor IA")
            st.metric("Facturas en cola", f"{pendientes_ia}")
            st.markdown("Procesamiento automático de datos.")
            st.page_link("pages/2_Motor_Procesamiento.py", label="Ir a Procesar", icon="🤖", use_container_width=True)
    with col3:
        with st.container(border=True):
            st.markdown("### ⚖️ Auditoría")
            st.metric("Esperando revisión", f"{pendientes_auditoria}")
            st.markdown("Validación inteligente por Patente y CUIT.")
            st.page_link("pages/3_Auditoria.py", label="Ir a Auditar", icon="✅", use_container_width=True)

pg = st.navigation({
    "🏠 Principal": [
        st.Page(tablero_principal, title="Tablero de Control", icon="🏢")
    ],
    "🧾 Facturación y Reportes": [
        st.Page("pages/1_Facturacion.py", title="Carga Rápida", icon="⚡"),
        st.Page("pages/2_Motor_Procesamiento.py", title="Motor IA", icon="🤖"),
        st.Page("pages/3_Auditoria.py", title="Auditoría Humana", icon="⚖️"),
        st.Page("pages/4_Buscador.py", title="Buscador DPA", icon="🔍")
    ],
   "🚘 Control de Flota (Manual-First)": [
        st.Page("pages/5_Flota_Ingestion.py", title="Ingestión de Archivos", icon="📥"),
        st.Page("pages/6_Motor_Flota.py", title="Motor de Procesamiento Flota", icon="⚙️"),
        st.Page("pages/8_Flota_Auditoria.py", title="Mesa de Auditoría Flota", icon="⚖️"),
        st.Page("pages/6_Flota_Buscador.py", title="Consulta por Patente", icon="🔍")
    ],
    "🔧 Maestros y Configuración": [
        # Si tenías datos aquí los conservás, o reubicás tu maestro de flota antiguo
        st.Page("pages/7_Configuracion.py", title="Parámetros Globales", icon="⚙️")
    ]
})
pg.run()
