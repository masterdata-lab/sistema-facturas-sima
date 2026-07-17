import streamlit as st

# 1. FORZAMOS EL CIERRE DE LA BARRA LATERAL EN EL ARRANQUE
st.set_page_config(page_title="DPA | ERP", page_icon="🏢", layout="wide", initial_sidebar_state="collapsed")

# 2. DEFINICIÓN DEL MENÚ CORPORATIVO (SECCIONES)
# Asegurate de que los nombres de los archivos coincidan con los tuyos
pg = st.navigation({
    "🏠 Principal": [
        st.Page("Inicio.py", title="Tablero de Control", icon="🏢") # Reemplazá Inicio.py por el nombre real de este archivo si se llama distinto
    ],
    "🧾 Facturación": [
        st.Page("pages/1_Facturacion.py", title="Carga Rápida", icon="⚡"),
        st.Page("pages/2_Motor_Procesamiento.py", title="Motor IA", icon="🤖"),
        st.Page("pages/3_Auditoria.py", title="Auditoría Humana", icon="⚖️")
    ],
    "📊 Reportes": [
        st.Page("pages/4_Buscador.py", title="Buscador y Tableros", icon="🔍")
    ],
    "🔧 Mantenimiento": [
        # st.Page("pages/5_Taller.py", title="Gestión de OT Taller", icon="⚙️") # Lo dejamos comentado hasta que lo creemos
    ]
})

# Ejecutamos la navegación
pg.run()
