import streamlit as st
import io
from PIL import Image
from datetime import datetime

# Importaciones de la sala de máquinas
from utils.conexiones import (
    subir_archivo, escribir_fila, ID_DRIVE_RAIZ
)

st.set_page_config(page_title="SIMA ERP | Carga Rápida", page_icon="⚡", layout="wide")

try:
    H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except:
    H_PENDIENTES = "PENDIENTES"

# 🌟 SISTEMA DE RESETEO SEGURO
# Usamos session_state para obligar a Streamlit a limpiar las cajitas después de enviar
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0

# Si venimos de un envío exitoso, mostramos el mensaje y lo borramos de la memoria
if "mensaje_exito" in st.session_state:
    st.success(st.session_state.mensaje_exito)
    del st.session_state.mensaje_exito

def asegurar_pdf(archivo):
    if archivo is None: return None
    if archivo.type.startswith("image/"):
        img = Image.open(archivo)
        if img.mode != 'RGB': 
            img = img.convert('RGB')
        pdf_bytes = io.BytesIO()
        img.save(pdf_bytes, format="PDF")
        return pdf_bytes.getvalue()
    return archivo.getvalue()

def subir_a_bandeja(fac_file, ot_file, motor_ia, indice, total_archivos):
    with st.container(border=True):
        st.markdown(f"**📄 Enviando {indice}/{total_archivos}:** `{fac_file.name if hasattr(fac_file, 'name') else 'Foto'}`")
        barra_progreso = st.progress(10, text="⏳ Preparando archivos...")
        
        fac_bytes = asegurar_pdf(fac_file)
        ot_bytes = asegurar_pdf(ot_file) if ot_file else None
        
        id_carga = f"Q_{int(datetime.now().timestamp())}_{indice}"
        fecha_ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        nombre_fac = fac_file.name if hasattr(fac_file, 'name') else "Foto_Factura.pdf"
        nombre_ot = ot_file.name if (ot_file and hasattr(ot_file, 'name')) else ("Foto_OT.pdf" if ot_file else "SIN OT")

        barra_progreso.progress(40, text="☁️ Subiendo Factura a la Bandeja de Drive...")
        link_fac = subir_archivo(f"PENDIENTE_FAC_{id_carga}.pdf", fac_bytes, ID_DRIVE_RAIZ, "1_BANDEJA_ENTRADA")

        link_ot = ""
        if ot_bytes:
            barra_progreso.progress(70, text="☁️ Subiendo OT a la Bandeja de Drive...")
            link_ot = subir_archivo(f"PENDIENTE_OT_{id_carga}.pdf", ot_bytes, ID_DRIVE_RAIZ, "1_BANDEJA_ENTRADA")

        barra_progreso.progress(90, text="📝 Registrando en la cola de procesamiento...")
        fila_pendiente = [
            id_carga, fecha_ahora, nombre_fac, nombre_ot,
            link_fac, link_ot if link_ot else "N/A", "PENDIENTE", motor_ia
        ]
        escribir_fila(H_PENDIENTES, fila_pendiente)

        barra_progreso.empty()
        return True

# ==========================================
# INTERFAZ (UI)
# ==========================================
st.markdown("## ⚡ Carga Rápida de Comprobantes")
st.markdown("Los archivos se enviarán a la bandeja de entrada para su procesamiento automático.")
st.divider()

col_motor, col_vacia = st.columns([1, 1])
with col_motor:
    opcion_ia = st.selectbox(
        "⚙️ Preferencia de Motor IA (Se usará en el procesamiento):",
        options=["Gemini 3.5 Flash (Rápido)", "Gemini 3.1 Pro (Avanzado)"],
        label_visibility="collapsed"
    )
motor_elegido = 'gemini-3.5-flash' if "Flash" in opcion_ia else 'gemini-3.1-pro'

st.divider()
st.info("💡 **Tip:** Podés arrastrar carpetas enteras o seleccionar múltiples archivos.")

usar_camara = st.toggle("📸 Activar Cámara (Celular)")

if usar_camara:
    # 🌟 MODO CÁMARA BLINDADO
    # Solo mostramos la cámara de la OT si el usuario lo pide explícitamente
    archivo_fac_cam = st.camera_input("1. Foto de la Factura (Obligatorio)", key=f"cam_fac_{st.session_state.reset_key}")
    
    con_ot = st.checkbox("📎 Quiero adjuntar además una foto de la Orden de Trabajo")
    archivo_ot_cam = None
    if con_ot:
        archivo_ot_cam = st.camera_input("2. Foto de la OT", key=f"cam_ot_{st.session_state.reset_key}")
        
    st.write("")
    if st.button("🚀 Enviar a la Bandeja", type="primary", use_container_width=True):
        if not archivo_fac_cam:
            st.error("❌ Debes tomar la foto de la factura para continuar.")
        else:
            subir_a_bandeja(archivo_fac_cam, archivo_ot_cam, motor_elegido, 1, 1)
            # Guardamos el mensaje, recargamos y limpiamos las cámaras
            st.session_state.mensaje_exito = "✅ ¡Foto enviada a la bandeja exitosamente!"
            st.session_state.reset_key += 1
            st.rerun()

else:
    # 🌟 MODO CARGA MASIVA BLINDADO
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        archivos_facturas_up = st.file_uploader(
            "1. Factura/s *Obligatorio*", 
            type=["pdf", "png", "jpg", "jpeg"], 
            accept_multiple_files=True,
            key=f"up_fac_{st.session_state.reset_key}"
        )
    with col_up2:
        archivos_ots_up = st.file_uploader(
            "2. Orden/es de Trabajo *Opcional*", 
            type=["pdf", "png", "jpg", "jpeg"], 
            accept_multiple_files=True,
            key=f"up_ot_{st.session_state.reset_key}"
        )

    if archivos_facturas_up:
        st.markdown("#### 🔗 Vincular Órdenes de Trabajo")
        st.write("Seleccioná qué OT le corresponde a cada factura. Si no lleva, dejalo en 'Ninguna'.")
        
        opciones_ot = ["Ninguna"]
        dict_ots = {}
        if archivos_ots_up:
            for ot in archivos_ots_up:
                opciones_ot.append(ot.name)
                dict_ots[ot.name] = ot

        mapeo_archivos = []
        for i, fac in enumerate(archivos_facturas_up):
            col_f, col_o = st.columns([6, 4])
            with col_f:
                st.write(f"📄 **{fac.name}**")
            with col_o:
                ot_elegida = st.selectbox(
                    "OT Correspondiente",
                    options=opciones_ot,
                    key=f"match_{st.session_state.reset_key}_{i}_{fac.name}",
                    label_visibility="collapsed"
                )
                ot_final = dict_ots.get(ot_elegida)
                mapeo_archivos.append((fac, ot_final))
        
        st.divider()

        if st.button("🚀 Enviar Lote a la Bandeja", type="primary", use_container_width=True):
            procesados_ok = 0
            total_archivos = len(mapeo_archivos)
            for i, (fac_file, ot_file) in enumerate(mapeo_archivos):
                exito = subir_a_bandeja(fac_file, ot_file, motor_elegido, i + 1, total_archivos)
                if exito: procesados_ok += 1
                
            # Guardamos el mensaje, recargamos y limpiamos las cajitas de carga
            st.session_state.mensaje_exito = f"🎉 ¡Listo! Se enviaron {procesados_ok} comprobantes a la cola de procesamiento."
            st.session_state.reset_key += 1
            st.rerun()
