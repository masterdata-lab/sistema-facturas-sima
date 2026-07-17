import streamlit as st
import io
import json
import time # <-- Agregado para el freno inteligente
from PIL import Image
from datetime import datetime

from utils.conexiones import (subir_archivo, escribir_fila, ID_DRIVE_RAIZ)

try: H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except: H_PENDIENTES = "PENDIENTES"

if "reset_key" not in st.session_state: st.session_state.reset_key = 0
if "mensaje_exito" in st.session_state:
    st.success(st.session_state.mensaje_exito)
    del st.session_state.mensaje_exito

def asegurar_pdf(archivo):
    if archivo is None: return None
    if archivo.type.startswith("image/"):
        img = Image.open(archivo)
        if img.mode != 'RGB': img = img.convert('RGB')
        pdf_bytes = io.BytesIO()
        img.save(pdf_bytes, format="PDF")
        return pdf_bytes.getvalue()
    return archivo.getvalue()

def subir_a_bandeja(fac_file, ot_file, motor_ia, indice, total_archivos, es_carga_manual):
    fac_bytes = asegurar_pdf(fac_file)
    ot_bytes = asegurar_pdf(ot_file) if ot_file else None
    
    id_carga = f"Q_{int(datetime.now().timestamp())}_{indice}"
    fecha_ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    link_fac = subir_archivo(f"PENDIENTE_FAC_{id_carga}.pdf", fac_bytes, ID_DRIVE_RAIZ, "1_BANDEJA_ENTRADA")

    link_ot = ""
    if ot_bytes:
        link_ot = subir_archivo(f"PENDIENTE_OT_{id_carga}.pdf", ot_bytes, ID_DRIVE_RAIZ, "1_BANDEJA_ENTRADA")

    # 🌟 LÓGICA DE CARGA MANUAL DIRECTA
    if es_carga_manual:
        estado = "PARA_AUDITAR"
        # Le inyectamos un JSON vacío para que la Auditoría no colapse al leerlo
        json_vacio = json.dumps({"ot_incluida_en_pdf": False, "items": []})
        escribir_fila(H_PENDIENTES, [id_carga, fecha_ahora, fac_file.name, ot_file.name if ot_file else "SIN OT", link_fac, link_ot if link_ot else "N/A", estado, "CARGA_MANUAL_DIRECTA", json_vacio])
    else:
        estado = "PENDIENTE"
        escribir_fila(H_PENDIENTES, [id_carga, fecha_ahora, fac_file.name, ot_file.name if ot_file else "SIN OT", link_fac, link_ot if link_ot else "N/A", estado, motor_ia])
    
    return True

st.markdown("## ⚡ Carga de Comprobantes")
st.divider()

# 🌟 INTERRUPTOR DE CARGA MANUAL
modo_manual = st.toggle("✍️ **Activar Modo de Ingreso Manual Directo**", help="Si activás esto, la IA no procesará el documento. Irá directo a la Auditoría para que cargues todos los datos a mano.")

if modo_manual:
    st.warning("⚠️ **Modo Manual Activado:** Los documentos subidos irán directamente a la bandeja de Auditoría.")
    motor_elegido = "CARGA_MANUAL"
else:
    col_motor, col_vacia = st.columns([1, 1])
    with col_motor:
        opcion_ia = st.selectbox("⚙️ Preferencia de Motor IA:", options=["Gemini 3.5 Flash (Rápido)", "Gemini 3.1 Pro (Avanzado)"], label_visibility="collapsed")
    motor_elegido = 'gemini-3.5-flash' if "Flash" in opcion_ia else 'gemini-3.1-pro'

st.info("💡 **Instrucciones:** Desde PC arrastrá los archivos. Desde el celular, tocá 'Browse files' para abrir tu cámara.")

col_up1, col_up2 = st.columns(2)
with col_up1:
    archivos_facturas_up = st.file_uploader("1. Factura/s *Obligatorio*", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_fac_{st.session_state.reset_key}")
with col_up2:
    archivos_ots_up = st.file_uploader("2. Orden/es de Trabajo *Opcional*", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_ot_{st.session_state.reset_key}")

if archivos_facturas_up:
    st.markdown("#### 🔗 Vincular Órdenes de Trabajo")
    opciones_ot = ["Ninguna"]
    dict_ots = {}
    if archivos_ots_up:
        for ot in archivos_ots_up:
            opciones_ot.append(ot.name)
            dict_ots[ot.name] = ot

    mapeo_archivos = []
    for i, fac in enumerate(archivos_facturas_up):
        col_f, col_o = st.columns([6, 4])
        with col_f: st.write(f"📄 **{fac.name}**")
        with col_o:
            ot_elegida = st.selectbox("OT Correspondiente", options=opciones_ot, key=f"match_{st.session_state.reset_key}_{i}", label_visibility="collapsed")
            mapeo_archivos.append((fac, dict_ots.get(ot_elegida)))
    
    st.divider()
    
    texto_boton = "🚀 Enviar a la Auditoría (Ingreso Manual)" if modo_manual else "🚀 Enviar Lote al Motor IA"
    
    if st.button(texto_boton, type="primary", use_container_width=True):
        procesados_ok = 0
        total = len(mapeo_archivos)
        
        panel_progreso = st.status(f"Subiendo 0 de {total} archivos...", expanded=True)
        
        for i, (fac_file, ot_file) in enumerate(mapeo_archivos):
            try:
                panel_progreso.update(label=f"Procesando {i+1} de {total}: {fac_file.name}", state="running")
                
                exito = subir_a_bandeja(fac_file, ot_file, motor_elegido, i + 1, total, modo_manual)
                if exito: procesados_ok += 1
                
                # --- EL FRENO INTELIGENTE ---
                if i < total - 1:
                    panel_progreso.update(label=f"⏳ Pausa de 15s para no saturar la API de Google...", state="running")
                    time.sleep(15)
                    
            except Exception as e:
                # Si a pesar de la pausa tira error 429, aplicamos freno de emergencia
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    panel_progreso.update(label=f"⚠️ Google saturado. Pausa de emergencia de 30s...", state="running")
                    time.sleep(30)
                else:
                    st.error(f"❌ Error con {fac_file.name}: {e}")
            
        panel_progreso.update(label="¡Envío completado!", state="complete")
        
        if modo_manual:
            st.session_state.mensaje_exito = f"🎉 ¡Listo! Se enviaron {procesados_ok} comprobantes directo a la Auditoría para carga manual."
        else:
            st.session_state.mensaje_exito = f"🎉 ¡Listo! Se enviaron {procesados_ok} comprobantes a la cola del motor IA."
            
        st.session_state.reset_key += 1
        st.rerun()

st.markdown('<div class="firma">Software DPA | Creado por Serrano Cristian</div>', unsafe_allow_html=True)
