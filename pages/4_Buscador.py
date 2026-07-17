import streamlit as st
import pandas as pd
from datetime import datetime
from utils.conexiones import leer_hoja_completa, H_GENERAL, H_DETALLE

# 1. CONFIGURACIÓN DPA Y BARRA CERRADA
st.set_page_config(page_title="DPA | Buscador", page_icon="🔍", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS COMPACTO Y FIRMA
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255,75,75,0.8); }
    .firma { text-align: right; font-size: 12px; color: gray; margin-top: 50px; }
</style>
""", unsafe_allow_html=True)

st.markdown("## 🔍 DPA | Buscador y Reportes Financieros")
st.divider()

# --- CARGA DE DATOS CON CACHÉ ---
# Guardamos los datos en memoria por 5 minutos para que la página sea ultrarrápida al filtrar
@st.cache_data(ttl=300)
def cargar_bases():
    d_gen = leer_hoja_completa(H_GENERAL)
    d_det = leer_hoja_completa(H_DETALLE)
    
    # Convertimos a DataFrames de Pandas (Tablas inteligentes)
    df_gen = pd.DataFrame(d_gen[1:], columns=d_gen[0]) if len(d_gen) > 1 else pd.DataFrame()
    df_det = pd.DataFrame(d_det[1:], columns=d_det[0]) if len(d_det) > 1 else pd.DataFrame()
    
    # Limpieza de montos para poder sumar (sacar signos $ y comas)
    if not df_gen.empty:
        df_gen['Total'] = pd.to_numeric(df_gen['Total'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
    if not df_det.empty:
        df_det['Precio Total Unitario'] = pd.to_numeric(df_det['Precio Total Unitario'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
        
    return df_gen, df_det

with st.spinner("Conectando con la base de datos DPA..."):
    df_gen, df_det = cargar_bases()

if df_gen.empty or df_det.empty:
    st.info("Aún no hay facturas aprobadas en la base de datos para analizar.")
else:
    # --- ZONA DE FILTROS GLOBALES ---
    with st.expander("⚙️ Filtros de Búsqueda (Hacé clic para abrir)", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            empresas_unicas = df_det['Empresa SIMA'].dropna().unique().tolist()
            filtro_empresa = st.multiselect("🏢 Empresa SIMA", options=empresas_unicas)
        with f2:
            patentes_unicas = df_det['Patente'].dropna().unique().tolist()
            filtro_patente = st.multiselect("🚗 Patente", options=patentes_unicas)
        with f3:
            cats_unicas = df_det['Categoría Gasto'].dropna().unique().tolist()
            filtro_cat = st.multiselect("🏷️ Tipo de Gasto", options=cats_unicas)
        with f4:
            provs_unicos = df_gen['Razón Social Proveedor'].dropna().unique().tolist()
            filtro_prov = st.multiselect("🏭 Proveedor", options=provs_unicos)

    # Aplicar filtros a los DataFrames
    df_det_filtrado = df_det.copy()
    df_gen_filtrado = df_gen.copy()

    if filtro_empresa:
        df_det_filtrado = df_det_filtrado[df_det_filtrado['Empresa SIMA'].isin(filtro_empresa)]
        df_gen_filtrado = df_gen_filtrado[df_gen_filtrado['Empresa SIMA'].isin(filtro_empresa)]
    if filtro_patente:
        df_det_filtrado = df_det_filtrado[df_det_filtrado['Patente'].isin(filtro_patente)]
        # Para la general, buscamos si la patente está incluida en el resumen
        df_gen_filtrado = df_gen_filtrado[df_gen_filtrado['Patente'].str.contains('|'.join(filtro_patente), na=False)]
    if filtro_cat:
        df_det_filtrado = df_det_filtrado[df_det_filtrado['Categoría Gasto'].isin(filtro_cat)]
        # La general no tiene categoría, filtramos por los IDs que sobrevivieron en el detalle
        ids_validos = df_det_filtrado['ID Unico'].unique()
        df_gen_filtrado = df_gen_filtrado[df_gen_filtrado['ID Unico'].isin(ids_validos)]
    if filtro_prov:
        df_det_filtrado = df_det_filtrado[df_det_filtrado['Razón Social Proveedor'].isin(filtro_prov)]
        df_gen_filtrado = df_gen_filtrado[df_gen_filtrado['Razón Social Proveedor'].isin(filtro_prov)]

    # --- PESTAÑAS DE VISTA ---
    tab_reporte, tab_facturas = st.tabs(["📊 Tablero de Gastos (Por Ítem)", "📄 Buscador de Facturas (General)"])

    with tab_reporte:
        st.markdown("### Resumen de Gastos Filtrados")
        gasto_total = df_det_filtrado['Precio Total Unitario'].sum()
        
        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
        c_kpi1.metric("Gasto Total (Con Impuestos)", f"${gasto_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c_kpi2.metric("Cantidad de Ítems Comprados", len(df_det_filtrado))
        c_kpi3.metric("Patentes Involucradas", df_det_filtrado['Patente'].nunique())
        
        st.write("---")
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.markdown("**Gasto por Categoría**")
            if not df_det_filtrado.empty:
                gasto_cat = df_det_filtrado.groupby('Categoría Gasto')['Precio Total Unitario'].sum().reset_index()
                st.bar_chart(gasto_cat, x='Categoría Gasto', y='Precio Total Unitario')
                
        with col_graf2:
            st.markdown("**Gasto por Patente**")
            if not df_det_filtrado.empty:
                gasto_pat = df_det_filtrado.groupby('Patente')['Precio Total Unitario'].sum().reset_index()
                st.bar_chart(gasto_pat, x='Patente', y='Precio Total Unitario')

        st.markdown("**Base de Datos Detallada**")
        st.dataframe(df_det_filtrado, use_container_width=True, hide_index=True)

    with tab_facturas:
        st.markdown("### Facturas Registradas")
        
        # Resaltar si tiene Notas (Agregamos un emoji visual)
        if 'Notas y Observaciones' in df_gen_filtrado.columns:
            df_gen_filtrado['Tiene Nota'] = df_gen_filtrado['Notas y Observaciones'].apply(lambda x: "📝 Sí" if str(x).strip() and str(x).strip() != 'None' else "")
        
        # Mostramos la tabla completa
        st.dataframe(df_gen_filtrado, use_container_width=True, hide_index=True)

# 3. FIRMA CREADOR
st.markdown('<div class="firma">Creado por Serrano Cristian</div>', unsafe_allow_html=True)
