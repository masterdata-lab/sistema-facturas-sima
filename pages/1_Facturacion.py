import streamlit as st
import re
import json
import io
import time
from PIL import Image
from datetime import datetime
from google.genai import types

# Importaciones de la sala de máquinas
from utils.conexiones import (
    obtener_cliente_gemini,
    escribir_fila,
    escribir_multiples_filas,
    obtener_valores_columna,
    subir_archivo,
    limpiar_nombre,
    unificar_documentos,
    ID_DRIVE_RAIZ,
    H_GENERAL,
    H_DETALLE,
    H_PROV,
    H_DUPLI,
    H_REVIS
)

st.set_page_config(page_title="SIMA ERP | Facturación", page_icon="🧾", layout="wide")

ia_client = obtener_cliente_gemini()

# Función para asegurar que las fotos de la cámara se conviertan a PDF
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

def extraer_datos_ia(pdf_bytes, modelo_elegido):
    prompt = """
    Extraé los datos de esta factura/OT y devolvelos en JSON estricto.
    Formato JSON:
    {
        "cuit_proveedor": "0000", "razon_social": "Nombre", "cuit_cliente": "000",
        "fecha": "DD/MM/YYYY", "punto_venta": 0, "nro_factura": 0, "patente": "",
        "subtotal": 0.0, "total": 0.0, "nro_ot": "",
        "items": [{"descripcion": "Texto", "cantidad": 0.0, "precio_unitario": 0.0}]
    }
    """
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    resp = ia_client.models.generate_content(
        model=modelo_elegido,
        contents=[doc, prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return json.loads(resp.text)

def procesar_archivos(fac_file, ot_file, modelo_ia):
    barra_progreso = st.progress(5, text="⏳ Iniciando procesamiento. Por favor, no apagues la pantalla...")
    
    # 1. Conversión a PDF de las fotos
    fac_bytes = asegurar_pdf(fac_file)
    ot_bytes = asegurar_pdf(ot_file) if ot_file else None
    
    # Como ya son PDFs, no mandamos bandera de imagen a unificar_documentos
    pdf_final = unificar_documentos(fac_bytes, ot_bytes, False)
    
    barra_progreso.progress(25, text="🧠 Analizando el documento con Inteligencia Artificial...")
    try:
        datos = extraer_datos_ia(pdf_final, modelo_ia)
    except Exception as e:
        error_str = str(e)
        # 🌟 FILTRO INTELIGENTE PARA EL 503 O QUOTA
        if "503" in error_str or "UNAVAILABLE" in error_str or "quota" in error_str.lower():
            barra_progreso.empty()
            st.warning("⚠️ Los servidores de IA están temporalmente saturados por alta demanda. Esperá 10 segundos y volvé a intentarlo.")
            return
            
        # Si es un error real de lectura, va a revisión
        id_err = f"ERR_{int(datetime.now().timestamp())}"
        mensaje_limpio = re.sub(r'[^\w\s\-\.\/]', '', error_str)[:100]
        txt_final = f"Error IA: {mensaje_limpio}"
        
        barra_progreso.progress(90, text="📁 Guardando documento ilegible en REVISIÓN...")
        link = subir_archivo(f"ERROR_{id_err}.pdf", pdf_final, ID_DRIVE_RAIZ, "REVISION")
        escribir_fila(H_REVIS, [id_err, "Desc", "S/N", txt_final, link])
        barra_progreso.empty()
        st.error("❌ Documento ilegible. Fue enviado a la pestaña REVISION para auditoría manual.")
        return

    barra_progreso.progress(50, text="🔍 Cruzando datos con la base de Google Sheets...")
    cuit_prov = datos.get("cuit_proveedor", "000")
    pv = str(datos.get("punto_venta", "0"))
    num = str(datos.get("nro_factura", "0"))
    id_unico = f"{cuit_prov}_{pv}_{num}"
    total = float(datos.get("total", 0.0))
    patente = datos.get("patente", "SIN_PATENTE")
    nro_ot = datos.get("nro_ot", "")
    alias_prov = limpiar_nombre(datos.get("razon_social", "DESCONOCIDO"))
    num_completo = f"{pv.zfill(5)}-{num.zfill(8)}"
    
    try:
        fecha_dt = datetime.strptime(datos.get("fecha", "01/01/2000"), "%d/%m/%Y")
        fecha_iso = fecha_dt.strftime("%Y-%m-%d")
        mes_txt = f"{str(fecha_dt.month).zfill(2)}-{['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'][fecha_dt.month-1]}"
        anio = fecha_dt.year
    except:
        fecha_iso, mes_txt, anio = "0000-00-00", "00-IND", datetime.now().year

    ids_general = obtener_valores_columna(H_GENERAL, 1)
        
    if id_unico in ids_general:
        barra_progreso.progress(80, text="⚠️ Duplicado detectado. Moviendo a cuarentena...")
        link_nuevo = subir_archivo(f"DUP_{fecha_iso}_{num_completo}.pdf", pdf_final, ID_DRIVE_RAIZ, "DUPLICADOS")
        escribir_fila(H_DUPLI, [id_unico, alias_prov, num_completo, datetime.now().strftime("%d/%m/%Y"), "Comprobante duplicado.", "", link_nuevo])
        barra_progreso.empty()
        st.warning("⚠️ Comprobante duplicado detectado. Fue registrado en la pestaña DUPLICADOS.")
        return

    total_formateado = f"{total:.2f}".replace('.', '_')
    suf = "_OT" if ot_file else ""
    nombre_pdf = f"{fecha_iso}_{num_completo}_{total_formateado}{suf}.pdf"
    
    barra_progreso.progress(75, text="☁️ Subiendo comprobante a la carpeta del proveedor en Drive...")
    link_drive = subir_archivo(nombre_pdf, pdf_final, ID_DRIVE_RAIZ, alias_prov)

    barra_progreso.progress(90, text="📝 Escribiendo filas en la base de datos contable...")
    escribir_fila(H_GENERAL, [id_unico, anio, mes_txt, datos.get("fecha"), patente, alias_prov, datos.get("razon_social"), pv, num, num_completo, datos.get("subtotal", 0), total, f'=HYPERLINK("{link_drive}", "Ver PDF")'])
    
    filas_detalle = []
    for item in datos.get("items", []):
        cant = int(item.get("cantidad", 1))
        precio_u = float(item.get("precio_unitario", 0))
        for _ in range(cant): 
            filas_detalle.append([id_unico, anio, mes_txt, datos.get("fecha"), alias_prov, datos.get("razon_social"), num_completo, nro_ot, patente, "", item.get("descripcion"), 1, precio_u, precio_u, f'=HYPERLINK("{link_drive}", "Ver PDF")'])
    if filas_detalle: 
        escribir_multiples_filas(H_DETALLE, filas_detalle)

    cuits_historico = obtener_valores_columna(H_PROV, 3)
    if cuit_prov not in cuits_historico:
        escribir_fila(H_PROV, [alias_prov, datos.get("razon_social"), cuit_prov])

    barra_progreso.progress(100, text="✅ ¡Proceso completado exitosamente!")
    time.sleep(1) # Pequeña pausa para que el usuario lea que terminó
    barra_progreso.empty()
    st.success(f"✅ ¡Factura de **{alias_prov}** procesada y guardada con éxito!")

# ==========================================
# INTERFAZ (UI)
# ==========================================
st.markdown("## 🧾 Módulo de Facturación")
st.markdown("Procesamiento inteligente de comprobantes con Gemini IA.")
st.divider()

st.markdown("### ⚙️ Configuración del Motor")
opcion_ia = st.selectbox(
    "Seleccionar Inteligencia Artificial:",
    options=[
        "Gemini 3.5 Flash (Modelo actual, gratuito y rápido)",
        "Gemini 3.1 Pro (Modelo avanzado)"
    ],
    label_visibility="collapsed"
)
motor_elegido = 'gemini-3.5-flash' if "Flash" in opcion_ia else 'gemini-3.1-pro'

st.divider()
st.markdown("### 📤 Carga de Documentos")

# Pestañas para elegir entre subir archivo de la PC o usar la cámara del celular
tab_upload, tab_camera = st.tabs(["📁 Subir Archivo", "📸 Usar Cámara (Celular)"])

with tab_upload:
    col1, col2 = st.columns(2)
    with col1:
        archivo_fac_up = st.file_uploader("1. Factura (PDF o Imagen) *Obligatorio*", type=["pdf", "png", "jpg", "jpeg"], key="fac_up")
    with col2:
        archivo_ot_up = st.file_uploader("2. Orden de Trabajo *Opcional*", type=["pdf", "png", "jpg", "jpeg"], key="ot_up")

with tab_camera:
    col3, col4 = st.columns(2)
    with col3:
        archivo_fac_cam = st.camera_input("1. Tomar foto de la Factura", key="fac_cam")
    with col4:
        archivo_ot_cam = st.camera_input("2. Tomar foto de la OT (Opcional)", key="ot_cam")

# El sistema detecta qué método usó el usuario
archivo_factura_final = archivo_fac_up or archivo_fac_cam
archivo_ot_final = archivo_ot_up or archivo_ot_cam

st.write("") # Espaciador
if st.button("🚀 Procesar Comprobantes", type="primary", use_container_width=True):
    if not archivo_factura_final:
        st.error("❌ Debes subir o capturar al menos la factura para continuar.")
    else:
        procesar_archivos(archivo_factura_final, archivo_ot_final, motor_elegido)
