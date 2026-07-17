import streamlit as st
from streamlit_drawable_canvas import st_canvas
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Taller e Inventario", page_icon="🔧", layout="wide")
st.title("🔧 Gestión de Pañol e Inventario")

# --- PESTAÑAS DEL MÓDULO ---
tab_remito, tab_stock, tab_historial = st.tabs([
    "📝 Emitir Remito de Salida", 
    "📦 Consultar Stock", 
    "📋 Historial de Movimientos"
])

# --- PESTAÑA 1: EMITIR REMITO ---
with tab_remito:
    st.markdown("### Nuevo Remito de Entrega")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Datos del Responsable (Quien entrega)**")
        # Esto luego lo leeremos de tu pestaña INV_RESPONSABLES
        responsable = st.selectbox("Seleccionar Pañolero/Responsable:", ["Juan Pañolero", "Carlos Taller", "Otro"])
        
        st.markdown("*Firma del Responsable:*")
        firma_responsable = st_canvas(
            stroke_width=2,
            stroke_color="#000000",
            background_color="#EEEEEE",
            height=150,
            width=300,
            drawing_mode="freedraw",
            key="canvas_responsable",
        )

    with col2:
        st.markdown("**Datos del Receptor (Quien retira)**")
        # Esto luego buscará en INV_RECEPTORES para autocompletar
        receptor_nombre = st.text_input("Nombre del Receptor:")
        receptor_mail = st.text_input("Email del Receptor (Para enviar PDF):")
        
        st.markdown("*Firma del Receptor:*")
        firma_receptor = st_canvas(
            stroke_width=2,
            stroke_color="#000000",
            background_color="#EEEEEE",
            height=150,
            width=300,
            drawing_mode="freedraw",
            key="canvas_receptor",
        )
        
    st.divider()
    st.markdown("### Detalle de Repuestos")
    # Aquí irá el selector dinámico para descontar stock
    repuesto = st.text_input("Repuesto/Artículo:")
    cantidad = st.number_input("Cantidad", min_value=1, step=1)
    
    if st.button("💾 Guardar Remito y Enviar por Correo", type="primary"):
        st.info("Generando PDF y conectando con masterdata@gruposima.ar... (Próximamente)")

# --- PESTAÑA 2: STOCK ---
with tab_stock:
    st.markdown("### Estado actual del Pañol")
    st.write("Aquí visualizaremos los datos de la pestaña **INV_STOCK** e **INV_TRAZABLE**.")

# --- PESTAÑA 3: HISTORIAL ---
with tab_historial:
    st.markdown("### Historial de Remitos Emitidos")
    st.write("Aquí veremos la tabla de **INV_MOVIMIENTOS** con links a los PDFs generados.")
