import streamlit as st
import pandas as pd
import re
from datetime import datetime
from utils.conexiones import leer_hoja_completa, H_GENERAL, H_DETALLE

st.set_page_config(page_title="DPA | Buscador", page_icon="🔍", layout="wide", initial_sidebar_state="collapsed")

st.markdown('''
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255,75,75,0.8); }
    ::-webkit-scrollbar { width: 10px !important; height: 10px !important; background-color: #f1f1f1 !important; }
    ::-webkit-scrollbar-thumb { background-color: #c1c1c1 !important; border-radius: 5px !important; }
    .firma-flotante { position: fixed; bottom: 8px; right: 15px; font-size: 10.5px; color: rgba(128, 128, 128, 0.6); z-index: 99999; pointer-events: none; font-family: monospace; }
</style>
<div class="firma-flotante">Software DPA | Creado por Serrano Cristian</div>
''', unsafe_allow_html=True)

st.markdown("## 🔍 DPA | Bandeja de Archivos y Reportes (Inbox)")
st.divider()

@st.cache_data(ttl=300)
def cargar_bases():
    d_gen = leer_hoja_completa(H_GENERAL)
    d_det = leer_hoja_completa(H_DETALLE)
    df_gen = pd.DataFrame(d_gen[1:], columns=d_gen[0]) if len(d_gen) > 1 else pd.DataFrame()
    df_det = pd.DataFrame(d_det[1:], columns=d_det[0]) if len(d_det) > 1 else pd.DataFrame()
    
    if not df_gen.empty:
        df_gen['Total Final'] = pd.to_numeric(df_gen['Total Final'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
    if not df_det.empty:
        df_det['Precio Total U.'] = pd.to_numeric(df_det['Precio Total U.'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
    return df_gen, df_det

def extraer_url(texto):
    if not texto: return ""
    match = re.search(r'(https?://[^\s",]+)', str(texto))
    return match.group(1) if match else str(texto)

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

with st.spinner("Conectando con bases de datos relacionales..."):
    df_gen, df_det = cargar_bases()

if df_gen.empty or df_det.empty:
    st.info("Aún no hay facturas aprobadas para analizar.")
else:
    # 🌟 NUEVA VISTA TIPO "BANDEJA DE ENTRADA (INBOX)"
    col_lista, col_visor = st.columns([1, 1], gap="medium")
    
    with col_lista:
        st.markdown("### 📥 Facturas Aprobadas")
        
        # Acciones Masivas
        st.markdown("**Acciones con las facturas:**")
        ca1, ca2, ca3 = st.columns(3)
        if ca1.button("⬇️ Descargar", use_container_width=True): st.toast("🚧 Módulo de Exportación Local en desarrollo.")
        if ca2.button("🖨️ Imprimir", use_container_width=True): st.toast("🚧 Cola de impresión en desarrollo.")
        if ca3.button("✉️ Enviar (Mail)", use_container_width=True): st.toast("🚧 Conexión SMTP pendiente de configuración.")
        
        st.write("")
        df_gen_visual = df_gen.copy()
        
        # Checkbox simulado para la tabla
        df_gen_visual.insert(0, "Sel", False)
        
        # Mostramos una tabla interactiva
        df_editado = st.data_editor(
            df_gen_visual[['Sel', 'Fecha', 'Razón Social Proveedor', 'Total Final', 'ID Unico']],
            hide_index=True, use_container_width=True,
            column_config={"Sel": st.column_config.CheckboxColumn("Sel", default=False)}
        )
        
        # Filtramos cual está seleccionada
        seleccionadas = df_editado[df_editado['Sel'] == True]['ID Unico'].tolist()
        
    with col_visor:
        st.markdown("### 📄 Visor Documental")
        if not seleccionadas:
            st.info("👈 Seleccioná una factura de la lista para ver su PDF original y detalles.")
        else:
            id_sel = seleccionadas[-1] # Muestra la última clickeada
            fila_info = df_gen[df_gen['ID Unico'] == id_sel].iloc[0]
            link_crudo = extraer_url(fila_info.get('Link PDF', ''))
            
            st.markdown(f"**Proveedor:** {fila_info.get('Razón Social Proveedor', '')} | **Nro:** {fila_info.get('Nro Completo', '')}")
            
            id_drive = extraer_id_drive(link_crudo)
            if id_drive:
                url_preview = f"https://drive.google.com/file/d/{id_drive}/preview"
                st.markdown(f'<iframe src="{url_preview}" width="100%" height="600px" style="border: none; border-radius: 8px;"></iframe>', unsafe_allow_html=True)
            else:
                st.warning("El link no es un archivo de Google Drive válido.")
                if link_crudo: st.markdown(f"[Abrir Link Externo]({link_crudo})")
                
            notas = fila_info.get('Notas Administrativas', '')
            if str(notas).strip() and str(notas).lower() != "none":
                st.warning(f"📝 **Notas Administrativas:** {notas}")
                
    st.divider()
    
    # 🌟 VISTA ANALÍTICA (KPIS Y REPORTES)
    st.markdown("### 📊 Análisis Analítico (Basado en Patentes y Gerencias)")
    
    with st.expander("⚙️ Filtros para Reportes", expanded=False):
        f1, f2, f3 = st.columns(3)
        with f1: filtro_ger = st.multiselect("Gerencia", df_det['Gerencia del Gasto'].unique())
        with f2: filtro_pat = st.multiselect("Patente", df_det['Patente Vehículo'].unique())
        with f3: filtro_cat = st.multiselect("Categoría", df_det['Categoría Gasto'].unique())
        
    df_rep = df_det.copy()
    if filtro_ger: df_rep = df_rep[df_rep['Gerencia del Gasto'].isin(filtro_ger)]
    if filtro_pat: df_rep = df_rep[df_rep['Patente Vehículo'].isin(filtro_pat)]
    if filtro_cat: df_rep = df_rep[df_rep['Categoría Gasto'].isin(filtro_cat)]
    
    c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
    c_kpi1.metric("Gasto Total (Periodo/Filtro)", f"${df_rep['Precio Total U.'].sum():,.2f}")
    c_kpi2.metric("Ítems Aprobados", len(df_rep))
    c_kpi3.metric("Patentes Implicadas", df_rep['Patente Vehículo'].nunique())
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("**Gasto por Gerencia**")
        st.bar_chart(df_rep.groupby('Gerencia del Gasto')['Precio Total U.'].sum())
    with col_g2:
        st.markdown("**Gasto por Categoría**")
        st.bar_chart(df_rep.groupby('Categoría Gasto')['Precio Total U.'].sum())
