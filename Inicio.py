import streamlit as st
from utils.conexiones import leer_hoja_completa

# 1. SETUP INICIAL DE LA PÁGINA
st.set_page_config(page_title="DPA | ERP", page_icon="🏢", layout="wide", initial_sidebar_state="collapsed")

def tablero_principal():
    # 🌟 CSS GLOBAL REFORZADO (Afecta a todas las páginas)
    st.markdown("""
    <style>
        /* 1. Achicar márgenes superiores gigantes */
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        
        /* 2. Resaltar botón de menú */
        [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255, 75, 75, 0.8); }
        
        /* 3. Métricas llamativas */
        div[data-testid="stMetricValue"] { font-size: 2.5rem !important; color: #ff4b4b; }
        
        /* 4. ANULAR SCROLLBARS TRANSPARENTES (Solución definitiva) */
        ::-webkit-scrollbar {
            width: 10px !important;
            height: 10px !important;
            background-color: #f1f1f1 !important;
        }
        ::-webkit-scrollbar-thumb {
            background-color: #c1c1c1 !important;
            border-radius: 5px !important;
        }
        ::-webkit-scrollbar-thumb:hover {
            background-color: #a8a8a8 !important;
        }
        
        .firma { text-align: right; font-size: 12px; color: gray; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

    try: H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
    except: H_PENDIENTES = "PENDIENTES"

    pendientes_ia = 0
    pendientes_auditoria = 0

    try:
        datos = leer_hoja_completa(H_PENDIENTES)
        for fila in datos[1:]:
            if len(fila) >= 7:
                if fila[6] == "PENDIENTE": pendientes_ia += 1
                elif fila[6] == "PARA_AUDITAR" or fila[6].startswith("ERROR"): pendientes_auditoria += 1
    except:
        pass 

    st.title("🏢 DPA - Software de Gestión")
    st.markdown("Sistema integral de procesamiento de comprobantes, flotas y reportes financieros.")
    st.divider()

    st.subheader("Tablero de Control - Flujo de Trabajo")
    st.write("") 

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.markdown("### ⚡ Carga Rápida")
            st.markdown("Subí facturas desde tu PC o celular con opción de Ingreso Manual.")
            st.write("")
            st.page_link("pages/1_Facturacion.py", label="Ir a Cargar Documentos", icon="📤", use_container_width=True)

    with col2:
        with st.container(border=True):
            st.markdown("### 🤖 Motor IA")
            st.metric("Facturas en cola", f"{pendientes_ia}")
            st.markdown("Procesamiento automático de comprobantes.")
            st.page_link("pages/2_Motor_Procesamiento.py", label="Ir a Procesar", icon="🤖", use_container_width=True)

    with col3:
        with st.container(border=True):
            st.markdown("### ⚖️ Auditoría")
            st.metric("Esperando revisión", f"{pendientes_auditoria}")
            st.markdown("Validación inteligente cruzada con base de Patentes.")
            st.page_link("pages/3_Auditoria.py", label="Ir a Auditar", icon="✅", use_container_width=True)

    st.markdown('<div class="firma">Software DPA | Creado por Serrano Cristian</div>', unsafe_allow_html=True)

# 3. DEFINICIÓN DEL MENÚ LATERAL AGRUPADO
pg = st.navigation({
    "🏠 Principal": [
        st.Page(tablero_principal, title="Tablero de Control", icon="🏢")
    ],
    "🧾 Facturación": [
        st.Page("pages/1_Facturacion.py", title="Carga Rápida", icon="⚡"),
        st.Page("pages/2_Motor_Procesamiento.py", title="Motor IA", icon="🤖"),
        st.Page("pages/3_Auditoria.py", title="Auditoría Humana", icon="⚖️"),
        st.Page("pages/4_Buscador.py", title="Buscador y Tableros", icon="🔍")
    ],
    "🔧 Configuración": [
        # st.Page("pages/5_Configuracion.py", title="Bases Maestras", icon="⚙️") # Lo activaremos pronto
    ]
})

pg.run()
