import streamlit as st
import json
import re
import time
from datetime import datetime
from utils.conexiones import leer_hoja_completa, actualizar_estado_carga, escribir_fila

try: 
    H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except: 
    H_PENDIENTES = "PENDIENTES"

st.set_page_config(page_title="DPA | Auditoría de Flota", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

st.markdown('''
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255,75,75,0.8); }
    .stAlert { padding: 0.5rem; }
    ::-webkit-scrollbar { width: 10px !important; height: 10px !important; background-color: #f1f1f1 !important; }
    ::-webkit-scrollbar-thumb { background-color: #c1c1c1 !important; border-radius: 5px !important; }
    .firma-flotante { position: fixed; bottom: 8px; right: 15px; font-size: 10.5px; color: rgba(128, 128, 128, 0.6); z-index: 99999; pointer-events: none; font-family: monospace; }
</style>
<div class="firma-flotante">Software DPA | Creado por Serrano Cristian</div>
''', unsafe_allow_html=True)

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

st.markdown("## ⚖️ Módulo de Auditoría Humana: Control de Flota")
st.divider()

with st.spinner("Buscando documentos de flota pendientes..."):
    datos_cola = leer_hoja_completa(H_PENDIENTES)

# Captura estricta del estado del pipeline de flota
para_auditar = [f for f in datos_cola[1:] if len(f) >= 7 and f[6] == "PARA_AUDITAR_FLOTA"]

if not para_auditar:
    st.success("🎉 No hay documentos de flota pendientes de visado humano.")
else:
    opciones = {}
    for fila in para_auditar:
        tipo_doc_sugerido = "Documento"
        if len(fila) >= 9 and fila[8]:
            try: tipo_doc_sugerido = json.loads(fila[8]).get("tipo_sugerido", "Documento")
            except: pass
        opciones[fila[0]] = f"📋 {tipo_doc_sugerido} | 📄 {fila[2]} | 📅 {fila[1]}"
        
    carga_seleccionada = st.selectbox("Seleccionar registro a auditar:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
    fila_actual = next(f for f in para_auditar if f[0] == carga_seleccionada)
    
    id_carga, fecha_ingreso, nombre_archivo, operador, link_drive, _, estado_actual, _, json_crudo = fila_actual[0:9]
    
    datos_flota_json = {}
    if json_crudo:
        try: datos_flota_json = json.loads(json_crudo)
        except: pass

    st.divider()
    col_pdf, col_datos = st.columns([1, 1], gap="medium")
    
    with col_pdf:
        st.markdown("### 📄 Vista Previa del Documento Extraído")
        id_drive = extraer_id_drive(link_drive)
        if id_drive:
            url_preview = f"https://drive.google.com/file/d/{id_drive}/preview"
            st.markdown(f'<iframe src="{url_preview}" width="100%" height="800px" style="border: none; border-radius: 8px;"></iframe>', unsafe_allow_html=True)
        else: 
            st.error("Archivo sin vista previa disponible.")
            st.markdown(f"[🔗 Enlace Directo a Drive]({link_drive})")
    
    with col_datos:
        st.markdown("### ✍️ Validación Humana de Datos")
        
        patente_sugerida = str(datos_flota_json.get("patente", "N/A")).upper().strip()
        tipo_sugerido = str(datos_flota_json.get("tipo_sugerido", "CEDULA_VERDE")).upper().strip()
        
        with st.form("form_auditoria_flota", clear_on_submit=True):
            patente_validada = st.text_input("Patente Definitiva (Obligatorio)", value="" if patente_sugerida == "N/A" else patente_sugerida).upper().strip()
            
            tipo_documento = st.selectbox(
                "Tipo Documento Confirmado", 
                ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"],
                index=["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"].index(tipo_sugerido) if tipo_sugerido in ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"] else 1
            )
            
            titular = st.text_input("Titular Registral", value=datos_flota_json.get("titular", ""))
            cuit_cuil = st.text_input("CUIT / CUIL", value=datos_flota_json.get("cuit_cuil", ""))
            
            st.write("---")
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                btn_aprobar = st.form_submit_button("✅ Aprobar e Inyectar", use_container_width=True)
            with c_btn2:
                btn_descartar = st.form_submit_button("🗑️ Descartar", use_container_width=True)
                
            if btn_aprobar:
                if not patente_validada:
                    st.error("❌ La patente es un dato obligatorio.")
                else:
                    with st.spinner("Ejecutando inyección indexada..."):
                        
                        # 🌟 LÓGICA DE DERIVACIÓN RELACIONAL CONDICIONAL
                        if tipo_documento == "TITULO":
                            escribir_fila("FLOTA", [
                                patente_validada, "ALTA_POR_TITULO", titular, cuit_cuil, 
                                link_drive, datetime.now().strftime("%d/%m/%Y")
                            ])
                            destino = "inyectado en Base Maestra FLOTA"
                        
                        elif tipo_documento == "CERTIFICADO_SEGURO":
                            escribir_fila("HISTORIAL_SEGUROS", [
                                patente_validada, datetime.now().strftime("%d/%m/%Y"), 
                                link_drive, titular
                            ])
                            destino = "registrado en HISTORIAL_SEGUROS"
                        
                        else:
                            escribir_fila("HISTORIAL_GENERAL_FLOTA", [
                                patente_validada, tipo_documento, link_drive, 
                                datetime.now().strftime("%d/%m/%Y")
                            ])
                            destino = "archivado en Historial General de Flota"
                        
                        actualizar_estado_carga(H_PENDIENTES, id_carga, "APROBADA")
                        st.success(f"🎉 Registro procesado y {destino}.")
                        time.sleep(1)
                        st.rerun()
            
            if btn_descartar:
                actualizar_estado_carga(H_PENDIENTES, id_carga, "DESCARTADO")
                st.warning("Documento descartado de la cola.")
                time.sleep(0.8)
                st.rerun()
