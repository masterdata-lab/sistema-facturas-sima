import streamlit as st
import io
from PIL import Image
from datetime import datetime

# Importaciones de la sala de máquinas
from utils.conexiones import (subir_archivo, escribir_fila, ID_DRIVE_RAIZ)

# 1. FORZAR BARRA LATERAL CERRADA
st.set_page_config(page_title="SIMA ERP | Carga Rápida", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

# 2. CSS PARA COMPACTAR Y RESALTAR EL MENÚ
st.markdown("""
<style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255, 75, 75, 0.8); }
</style>
""", unsafe_allow_html=True)

try:
    H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except:
    H_PENDIENTES = "PENDIENTES"

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

def subir_a_bandeja(fac_file, ot_file, motor_ia, indice, total_archivos):
    with st.container(border=True):
        st.markdown(f"**📄 Enviando {indice}/{total_archivos}:** `{fac_file.name}`")
        barra_progreso = st.progress(10, text="⏳ Preparando archivos...")
        
        fac_bytes = asegurar_pdf(fac_file)
        ot_bytes = asegurar_pdf(ot_file) if ot_file else None
        
        id_carga = f"Q_{int(datetime.now().timestamp())}_{indice}"
        fecha_ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        barra_progreso.progress(40, text="☁️ Subiendo Factura...")
        link_fac = subir_archivo(f"PENDIENTE_FAC_{id_carga}.pdf", fac_bytes, ID_DRIVE_RAIZ, "1_BANDEJA_ENTRADA")

        link_ot = ""
        if ot_bytes:
            barra_progreso.progress(70, text="☁️ Subiendo OT...")
            link_ot = subir_archivo(f"PENDIENTE_OT_{id_carga}.pdf", ot_bytes, ID_DRIVE_RAIZ, "1_BANDEJA_ENTRADA")

        barra_progreso.progress(90, text="📝 Registrando...")
        escribir_fila(H_PENDIENTES, [id_carga, fecha_ahora, fac_file.name, ot_file.name if ot_file else "SIN OT", link_fac, link_ot if link_ot else "N/A", "PENDIENTE", motor_ia])
        
        barra_progreso.empty()
        return True

st.markdown("## ⚡ Carga Rápida de Comprobantes")
st.divider()

col_motor, col_vacia = st.columns([1, 1])
with col_motor:
    opcion_ia = st.selectbox("⚙️ Preferencia de Motor IA:", options=["Gemini 3.5 Flash (Rápido)", "Gemini 3.1 Pro (Avanzado)"], label_visibility="collapsed")
motor_elegido = 'gemini-3.5-flash' if "Flash" in opcion_ia else 'gemini-3.1-pro'

st.info("💡 **Instrucciones:** Desde PC arrastrá los archivos. Desde el celular, tocá 'Browse files' para abrir tu cámara de fotos nativa.")

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
    if st.button("🚀 Enviar Lote a la Bandeja", type="primary", use_container_width=True):
        procesados_ok = 0
        total = len(mapeo_archivos)
        
        # 🌟 UN SOLO MENSAJE DE PROGRESO QUE SE ACTUALIZA
        panel_progreso = st.status(f"Procesando 0 de {total} archivos...", expanded=True)
        
        for i, (fac_file, ot_file) in enumerate(mapeo_archivos):
            panel_progreso.update(label=f"Procesando {i+1} de {total}: {fac_file.name}", state="running")
            exito = subir_a_bandeja(fac_file, ot_file, motor_elegido, i + 1, total)
            if exito: procesados_ok += 1
            
        panel_progreso.update(label="¡Envío completado!", state="complete")
            
        st.session_state.mensaje_exito = f"🎉 ¡Listo! Se enviaron {procesados_ok} comprobantes a la cola."
        st.session_state.reset_key += 1
        st.rerun()

# FIRMA DPA
st.markdown('<div style="text-align: right; font-size: 12px; color: gray; margin-top: 50px;">Software DPA | Creado por Serrano Cristian</div>', unsafe_allow_html=True)
