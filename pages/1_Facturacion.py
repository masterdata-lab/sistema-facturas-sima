import streamlit as st
import re
import json
from datetime import datetime
from google.genai import types

# 🌟 IMPORTANTE: Traemos todas las conexiones de la sala de máquinas
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

# 1. Configuración visual de la página
st.set_page_config(
    page_title="SIMA ERP | Facturación",
    page_icon="🧾",
    layout="wide"
)

# Inicializar cliente de IA utilizando la función centralizada
ia_client = obtener_cliente_gemini()

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
    ot_bytes = ot_file.getvalue() if ot_file else None
    ot_img = ot_file.type.startswith("image/") if ot_file else False
    pdf_final = unificar_documentos(fac_file.getvalue(), ot_bytes, ot_img)
    
    with st.spinner("Analizando documento con IA..."):
        try:
            datos = extraer_datos_ia(pdf_final, modelo_ia)
        except Exception as e:
            id_err = f"ERR_{int(datetime.now().timestamp())}"
            mensaje_limpio = re.sub(r'[^\w\s\-\.\/]', '', str(e))[:100]
            txt_final = f"Error IA: {mensaje_limpio}"
            
            # Lo manda directo a la subcarpeta REVISION en Drive
            link = subir_archivo(f"ERROR_{id_err}.pdf", pdf_final, ID_DRIVE_RAIZ, "REVISION")
            escribir_fila(H_REVIS, [id_err, "Desc", "S/N", txt_final, link])
            st.error("Error de lectura o servidor saturado. Enviado a la pestaña REVISION.")
            return

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

    with st.spinner("Comprobando duplicados en la base de datos..."):
        ids_general = obtener_valores_columna(H_GENERAL, 1)
        
    if id_unico in ids_general:
        st.warning("Comprobante duplicado detectado. Registrando...")
        link_nuevo = subir_archivo(f"DUP_{fecha_iso}_{num_completo}.pdf", pdf_final, ID_DRIVE_RAIZ, "DUPLICADOS")
        escribir_fila(H_DUPLI, [id_unico, alias_prov, num_completo, datetime.now().strftime("%d/%m/%Y"), "Comprobante duplicado.", "", link_nuevo])
        st.warning("Registrado en pestaña DUPLICADOS.")
        return

    # Nomenclatura limpia acordada: sin $, centavos con guion bajo (_)
    total_formateado = f"{total:.2f}".replace('.', '_')
    suf = "_OT" if ot_file else ""
    nombre_pdf = f"{fecha_iso}_{num_completo}_{total_formateado}{suf}.pdf"
    
    with st.spinner("Subiendo PDF unificado a Google Drive..."):
        link_drive = subir_archivo(nombre_pdf, pdf_final, ID_DRIVE_RAIZ, alias_prov)

    with st.spinner("Registrando datos en las hojas de cálculo..."):
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

    st.success(f"¡Factura de {alias_prov} procesada y guardada con éxito!")

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
    ]
)

if "Flash" in opcion_ia:
    motor_elegido = 'gemini-3.5-flash'
else:
    motor_elegido = 'gemini-3.1-pro'

st.divider()

st.markdown("### 📤 Carga de Documentos")
col1, col2 = st.columns(2)
with col1:
    archivo_factura = st.file_uploader("1. Factura (PDF) *Obligatorio*", type=["pdf"])
with col2:
    archivo_ot = st.file_uploader("2. Orden de Trabajo / Remito *Opcional*", type=["pdf", "png", "jpg", "jpeg"])

if st.button("🚀 Procesar Comprobantes", type="primary"):
    if not archivo_factura:
        st.error("Debes subir al menos la factura para continuar.")
    else:
        procesar_archivos(archivo_factura, archivo_ot, motor_elegido)
