import streamlit as st
import json
import re
import time
from datetime import datetime
from utils.conexiones import leer_hoja_completa, actualizar_estado_carga, escribir_fila

try: 
    HOJA_FLOTA = st.secrets.get("HOJA_FLOTA", "PENDIENTES_FLOTA")
except: 
    HOJA_FLOTA = "PENDIENTES_FLOTA"

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

with st.spinner(f"Buscando documentos en {HOJA_FLOTA}..."):
    datos_cola = leer_hoja_completa(HOJA_FLOTA)

para_auditar = [f for f in datos_cola[1:] if len(f) >= 7 and str(f[6]).strip().upper() in ["PARA_AUDITAR_FLOTA", "PROCESADO"]]

if not para_auditar:
    st.success("🎉 No hay documentos de flota pendientes de visado humano.")
else:
    opciones = {}
    for fila in para_auditar:
        tipo_doc_sugerido = "Documento"
        if len(fila) >= 9 and fila[8]:
            try: tipo_doc_sugerido = json.loads(fila[8]).get("tipo_sugerido", "Documento")
            except: pass
        
        nombre = fila[2] if len(fila) > 2 else "Sin Nombre"
        fecha = fila[1] if len(fila) > 1 else "Sin Fecha"
        opciones[fila[0]] = f"📋 {tipo_doc_sugerido} | 📄 {nombre} | 📅 {fecha}"
        
    carga_seleccionada = st.selectbox("Seleccionar registro a auditar:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
    fila_actual = next(f for f in para_auditar if f[0] == carga_seleccionada)
    
    id_carga = fila_actual[0]
    link_drive = fila_actual[4] if len(fila_actual) > 4 else ""
    json_crudo = fila_actual[8] if len(fila_actual) > 8 else "{}"
    
    # 🔍 PARSEO DEL JSON
    datos_flota_json = {}
    if json_crudo:
        try: 
            datos_flota_json = json.loads(json_crudo)
        except: 
            st.error("⚠️ El formato del payload JSON guardado es inválido.")

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
            st.markdown("#### 🚗 Identificación Básica")
            c1, c2 = st.columns(2)
            with c1:
                patente_validada = st.text_input("Patente Definitiva (Obligatorio)", value="" if patente_sugerida == "N/A" else patente_sugerida).upper().strip()
            with c2:
                tipo_documento = st.selectbox(
                    "Tipo Documento Confirmado", 
                    ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"],
                    index=["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"].index(tipo_sugerido) if tipo_sugerido in ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"] else 1,
                    key=f"tipo_doc_{id_carga}" 
                )
            
            st.markdown("#### 📜 Datos de Propiedad y Radicación")
            c3, c4 = st.columns(2)
            with c3:
                titular = st.text_input("Titular Registral", value=datos_flota_json.get("titular", ""))
            with c4:
                cuit_cuil = st.text_input("CUIT / CUIL Empresa (Titular)", value=datos_flota_json.get("cuit_cuil", ""))
            
            lugar_radicacion = st.text_input("Lugar de Radicación", value=datos_flota_json.get("lugar_radicacion", ""))

            st.markdown("#### ⚙️ Ficha Técnica del Vehículo")
            c5, c6 = st.columns(2)
            with c5:
                marca = st.text_input("Marca", value=datos_flota_json.get("marca", datos_flota_json.get("marca_modelo", "")))
                tipo_vehiculo = st.text_input("Formato / Tipo de Vehículo", value=datos_flota_json.get("tipo_vehiculo", ""))
            with c6:
                modelo = st.text_input("Modelo", value=datos_flota_json.get("modelo", ""))
                anio_inscripcion = st.text_input("Año de Inscripción", value=datos_flota_json.get("anio_inscripcion", datos_flota_json.get("anio", "")))

            c7, c8 = st.columns(2)
            with c7:
                nro_chasis = st.text_input("Número de Chasis / Cuadro", value=datos_flota_json.get("nro_chasis", ""))
            with c8:
                nro_motor = st.text_input("Número de Motor", value=datos_flota_json.get("nro_motor", ""))
                
            st.write("---")
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                btn_aprobar = st.form_submit_button("✅ Aprobar e Inyectar en Flota", use_container_width=True)
            with c_btn2:
                btn_descartar = st.form_submit_button("🗑️ Descartar Registro", use_container_width=True)
                
            if btn_aprobar:
                if not patente_validada:
                    st.error("❌ La patente es un dato obligatorio para estructurar la flota.")
                else:
                    with st.spinner("Ejecutando inyección indexada..."):
                        
                        if tipo_documento == "TITULO":
                            # MAPEO A LA NUEVA ESTRUCTURA LIMPIA DE 25 COLUMNAS
                            datos_a_inyectar = [
                                patente_validada,           # 1. Patente
                                "ALTA_POR_TITULO",          # 2. Estado
                                titular,                    # 3. Titular
                                cuit_cuil,                  # 4. CUIT Empresa
                                lugar_radicacion,           # 5. Radicacion
                                "",                         # 6. Gerencia Actual
                                tipo_vehiculo,              # 7. Tipo Vehiculo
                                marca,                      # 8. Marca
                                modelo,                     # 9. Modelo
                                anio_inscripcion,           # 10. Año
                                nro_chasis,                 # 11. Chasis
                                nro_motor,                  # 12. Motor
                                "",                         # 13. Vto VTV
                                "",                         # 14. Status VTV
                                "",                         # 15. Vto Seguro
                                "",                         # 16. Status Seguro
                                "",                         # 17. Vto RUTA
                                "",                         # 18. Vto Tarj YPF
                                link_drive,                 # 19. Link Titulo / Alta
                                "",                         # 20. Link VTV
                                "",                         # 21. Link Cert Seguro
                                "",                         # 22. Link Poliza General
                                "",                         # 23. Link RUTA
                                "",                         # 24. Link Tarj YPF
                                f"Alta Automática: {datetime.now().strftime('%d/%m/%Y')}" # 25. Observaciones
                            ]
                            escribir_fila("FLOTA", datos_a_inyectar)
                            destino = "inyectado en Base Maestra FLOTA (Nueva Estructura)"
                        
                        elif tipo_documento == "CERTIFICADO_SEGURO":
                            escribir_fila("HISTORIAL_SEGUROS", [
                                patente_validada, 
                                datetime.now().strftime("%d/%m/%Y"), 
                                link_drive, 
                                titular
                            ])
                            destino = "registrado en HISTORIAL_SEGUROS"
                        
                        else:
                            escribir_fila("HISTORIAL_GENERAL_FLOTA", [
                                patente_validada, 
                                tipo_documento, 
                                link_drive, 
                                datetime.now().strftime("%d/%m/%Y")
                            ])
                            destino = "archivado en Historial General de Flota"
                        
                        actualizar_estado_carga(HOJA_FLOTA, id_carga, "APROBADA")
                        st.success(f"🎉 Registro procesado y {destino}.")
                        time.sleep(1)
                        st.rerun()
            
            if btn_descartar:
                actualizar_estado_carga(HOJA_FLOTA, id_carga, "DESCARTADO")
                st.warning("Documento descartado de la cola.")
                time.sleep(0.8)
                st.rerun()
