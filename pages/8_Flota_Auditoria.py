import streamlit as st
import json
import re
from datetime import datetime
from utils.conexiones import (leer_hoja_completa, actualizar_estado_carga, escribir_fila, H_PENDIENTES)

st.set_page_config(page_title="DPA | Auditoría de Flota", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

# Estilos idénticos al ecosistema SIMA
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
    # REPLICACIÓN: Leemos la misma hoja PENDIENTES que usa facturación
    datos_cola = leer_hoja_completa("PENDIENTES")

# 🔍 EL FILTRO CRÍTICO: Capturamos el estado específico que configuramos en Ingestión
para_auditar = [f for f in datos_cola[1:] if len(f) >= 7 and f[6] == "PARA_AUDITAR_FLOTA"]

if not para_auditar:
    st.success("🎉 No hay documentos de flota pendientes de visado humano.")
else:
    # Construcción de la bandeja de entrada para el Selectbox
    opciones = {}
    for fila in para_auditar:
        tipo_doc_sugerido = "Documento"
        if len(fila) >= 9 and fila[8]:
            try: tipo_doc_sugerido = json.loads(fila[8]).get("tipo_sugerido", "Documento")
            except: pass
        opciones[fila[0]] = f"📋 {tipo_doc_sugerido} | 📄 {fila[2]} | 📅 {fila[1]}"
        
    carga_seleccionada = st.selectbox("Seleccionar registro a auditar:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
    fila_actual = next(f for f in para_auditar if f[0] == carga_seleccionada)
    
    # Mapeo posicional exacto de columnas de PENDIENTES
    id_carga, fecha_ingreso, nombre_archivo, operador, link_drive, _, estado_actual, _, json_crudo = fila_actual[0:9]
    
    datos_ia = {}
    if json_crudo:
        try: datos_ia = json.loads(json_crudo)
        except: pass

    st.divider()
    
    # 50/50 Split Screen Layout homologado
    col_pdf, col_datos = st.columns([1, 1], gap="medium")
    
    with col_pdf:
        st.markdown("### 📄 Vista Previa del Documento")
        id_drive = extraer_id_drive(link_drive)
        if id_drive:
            url_preview = f"https://drive.google.com/file/d/{id_drive}/preview"
            st.markdown(f'<iframe src="{url_preview}" width="100%" height="800px" style="border: none; border-radius: 8px;"></iframe>', unsafe_allow_html=True)
        else: 
            st.error("No se pudo extraer el ID de Google Drive para la vista previa.")
            st.markdown(f"[🔗 Abrir enlace externo del archivo]({link_drive})")
    
    with col_datos:
        st.markdown("### ✍️ Formulario de Validación e Inyección")
        
        # Precarga inteligente de los datos estructurados que inyectó la Ingestión
        patente_sugerida = str(datos_ia.get("patente", "N/A")).upper().strip()
        tipo_sugerido = str(datos_ia.get("tipo_sugerido", "CEDULA_VERDE")).upper().strip()
        
        with st.form("form_auditoria_flota", clear_on_submit=True):
            st.markdown("#### Datos Extraídos / Sugeridos")
            
            # Inputs para corrección humana
            patente_validada = st.text_input("Patente Homologada (Obligatorio)", value="" if patente_sugerida == "N/A" else patente_sugerida).upper().strip()
            
            tipo_documento = st.selectbox(
                "Tipo de Documento Confirmado", 
                ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"],
                index=["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"].index(tipo_sugerido) if tipo_sugerido in ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"] else 1
            )
            
            titular = st.text_input("Titular del Vehículo (Si aplica)", value=datos_ia.get("titular", ""))
            cuit_cuil = st.text_input("CUIT / CUIL Asociado", value=datos_ia.get("cuit_cuil", ""))
            
            st.write("---")
            st.markdown("#### Acciones")
            
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                btn_aprobar = st.form_submit_button("✅ Aprobar e Inyectar", use_container_width=True)
            with c_btn2:
                btn_descartar = st.form_submit_button("🗑️ Descartar Documento", use_container_width=True)
                
            if btn_aprobar:
                if not patente_validada:
                    st.error("❌ Se requiere una patente válida para procesar el documento en el maestro de flota.")
                else:
                    with st.spinner("Procesando inyección en el módulo correspondiente..."):
                        # REGLA DE NEGOCIO 1: Si es TÍTULO, impacta directo en la base de datos "FLOTA"
                        if tipo_documento == "TITULO":
                            # Estructura maestra: Patente, Tipo, Titular, CUIT, Link Documento, Fecha Registro
                            escribir_fila("FLOTA", [
                                patente_validada, 
                                "ALTA_AUTOMATICA_TITULO", 
                                titular, 
                                cuit_cuil, 
                                link_drive, 
                                datetime.now().strftime("%d/%m/%Y")
                            ])
                            msg_destino = "inyectado en la base maestra FLOTA"
                        
                        # REGLA DE NEGOCIO 2: Si es SEGURO, archiva en "HISTORIAL_SEGUROS"
                        elif tipo_documento == "CERTIFICADO_SEGURO":
                            escribir_fila("HISTORIAL_SEGUROS", [
                                patente_validada, 
                                datetime.now().strftime("%d/%m/%Y"), 
                                link_drive, 
                                titular
                            ])
                            msg_destino = "archivado en HISTORIAL_SEGUROS"
                        
                        # Para otros documentos, se pueden agregar sus respectivas tablas aquí
                        else:
                            escribir_fila("HISTORIAL_GENERAL_FLOTA", [
                                patente_validada, 
                                tipo_documento, 
                                link_drive, 
                                datetime.now().strftime("%d/%m/%Y")
                            ])
                            msg_destino = "registrado en el historial general"
                        
                        # Actualizamos el estado de la cola en PENDIENTES a APROBADA
                        actualizar_estado_carga("PENDIENTES", id_carga, "APROBADA")
                        st.success(f"🎉 Documento {nombre_archivo} procesado e {msg_destino} con éxito.")
                        time.sleep(1)
                        st.rerun()
            
            if btn_descartar:
                actualizar_estado_carga("PENDIENTES", id_carga, "DESCARTADO")
                st.warning("Documento marcado como descartado.")
                time.sleep(0.8)
                st.rerun()
