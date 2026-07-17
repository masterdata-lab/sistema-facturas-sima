import streamlit as st
import pandas as pd
from datetime import datetime
from utils.conexiones import leer_hoja_completa, escribir_fila

st.set_page_config(page_title="DPA | Gestión de Flota", page_icon="🚘", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255,75,75,0.8); }
    ::-webkit-scrollbar { width: 10px !important; height: 10px !important; background-color: #f1f1f1 !important; }
    ::-webkit-scrollbar-thumb { background-color: #c1c1c1 !important; border-radius: 5px !important; }
    .firma-flotante { position: fixed; bottom: 8px; right: 15px; font-size: 10.5px; color: rgba(128, 128, 128, 0.6); z-index: 99999; pointer-events: none; font-family: monospace; }
</style>
<div class="firma-flotante">Software DPA | Creado por Serrano Cristian</div>
""", unsafe_allow_html=True)

st.markdown("## 🚘 DPA | Gestión Integral de Flota")
st.divider()

# --- CARGAR DATOS MAESTROS ---
try: datos_receptores = leer_hoja_completa("RECEPTORES")
except: datos_receptores = []
cuits_empresas = [str(r[0]) for r in datos_receptores[1:] if len(r) > 0]
if not cuits_empresas: cuits_empresas = ["30716696867", "33714987599", "30715195549", "30717266532"]

try: datos_gerencias = leer_hoja_completa("GERENCIAS")
except: datos_gerencias = []
lista_gerencias = [str(g[0]).upper() for g in datos_gerencias[1:] if len(g) > 0 and str(g[1]).upper() != "INACTIVO"]
if not lista_gerencias: lista_gerencias = ["DPA"]

# --- FUNCIÓN DE SEMAFORIZACIÓN ---
def calcular_estado_vto(fecha_str):
    if not fecha_str or str(fecha_str).strip() == "": return "⚪ Sin Dato"
    try:
        f_vto = datetime.strptime(str(fecha_str).strip(), "%d/%m/%Y")
        hoy = datetime.now()
        dias_restantes = (f_vto - hoy).days
        if dias_restantes < 0: return "🔴 VENCIDO"
        elif dias_restantes <= 15: return "🟡 PRÓXIMO A VENCER"
        else: return "🟢 APTO"
    except:
        return "⚪ Error Formato"

# --- TABS DE NAVEGACIÓN ---
tab_visor, tab_alta = st.tabs(["📊 Panel de Control y Vencimientos", "➕ Alta de Nuevo Vehículo"])

with tab_visor:
    st.markdown("### Estado Documental de Vehículos")
    try:
        datos_flota = leer_hoja_completa("FLOTA")
        if len(datos_flota) > 1:
            df = pd.DataFrame(datos_flota[1:], columns=datos_flota[0])
            
            # Aplicamos la semaforización en vivo
            df['Status VTV'] = df['Vto VTV'].apply(calcular_estado_vto)
            df['Status Seguro'] = df['Vto Seguro'].apply(calcular_estado_vto)
            df['Status RUTA'] = df['Vto RUTA'].apply(calcular_estado_vto)
            
            # Reorganizamos columnas para mostrarlas lindo
            cols_mostrar = ['Patente', 'Estado', 'CUIT Empresa', 'Gerencia Actual', 'Status VTV', 'Status Seguro', 'Status RUTA', 'Tipo', 'Marca', 'Modelo']
            # Evitamos errores si falta alguna columna en el sheet
            cols_mostrar = [c for c in cols_mostrar if c in df.columns]
            
            st.dataframe(df[cols_mostrar], use_container_width=True, hide_index=True)
        else:
            st.info("No hay vehículos cargados en la flota todavía.")
    except Exception as e:
        st.error(f"Error al leer la hoja FLOTA: {e}")

with tab_alta:
    st.markdown("### Registrar Nuevo Vehículo")
    with st.form("form_alta_vehiculo", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        patente = c1.text_input("Patente (Ej: AB123CD) *").upper().replace(" ", "").replace("-", "")
        estado = c2.selectbox("Estado Operativo", ["ACTIVO", "INACTIVO", "EN TALLER"])
        empresa = c3.selectbox("Empresa Asignada (CUIT)", cuits_empresas)
        gerencia = c4.selectbox("Gerencia Actual", lista_gerencias)
        
        st.markdown("#### Datos Técnicos")
        c5, c6, c7, c8 = st.columns(4)
        tipo = c5.selectbox("Tipo", ["AUTO", "PICKUP", "UTILITARIO", "CAMIÓN", "MOTO", "MÁQUINA"])
        marca = c6.text_input("Marca (Ej: TOYOTA)").upper()
        modelo = c7.text_input("Modelo (Ej: HILUX)").upper()
        anio = c8.text_input("Año")
        
        c9, c10 = st.columns(2)
        chasis = c9.text_input("Nro Chasis (VIN)").upper()
        motor = c10.text_input("Nro Motor").upper()
        
        st.markdown("#### Vencimientos Documentales (DD/MM/YYYY)")
        c11, c12, c13 = st.columns(3)
        vto_vtv = c11.text_input("Vencimiento VTV")
        vto_seguro = c12.text_input("Vencimiento Seguro")
        vto_ruta = c13.text_input("Vencimiento RUTA")
        
        obs = st.text_area("Observaciones", height=68).upper()
        
        submit = st.form_submit_button("💾 Guardar Vehículo en Base de Datos", type="primary")
        
        if submit:
            if not patente:
                st.error("La patente es obligatoria.")
            else:
                fila_nueva = [patente, estado, empresa, gerencia, tipo, marca, modelo, anio, chasis, motor, vto_vtv, vto_seguro, vto_ruta, obs]
                escribir_fila("FLOTA", fila_nueva)
                st.success(f"✅ Vehículo {patente} registrado con éxito en la Flota DPA.")
                st.rerun()
