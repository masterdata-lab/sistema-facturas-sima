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
    obtener_cliente_gemini, escribir_fila, escribir_multiples_filas,
    obtener_valores_columna, subir_archivo, limpiar_nombre, unificar_documentos,
    ID_DRIVE_RAIZ, H_GENERAL, H_DETALLE, H_PROV, H_DUPLI, H_REVIS
)

st.set_page_config(page_title="SIMA ERP | Facturación", page_icon="🧾", layout="wide")

ia_client = obtener_cliente_gemini()

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

def procesar_un_archivo(fac_file, ot_file, modelo_ia, indice, total_archivos):
    # Envolvemos el contenido en un contenedor para que sea visualmente limpio en cargas masivas
    with st.container(border=True):
        st.markdown(f"**📄 Procesando archivo {indice} de {total_archivos}:** `{fac_file.name}`")
        barra_progreso = st.progress(5, text="⏳ Iniciando conversión y preparación...")
        
        fac_bytes = asegurar_pdf(fac_file)
        ot_bytes = asegurar_pdf(ot_file) if ot_file else None
        pdf_final = unificar_documentos(fac_bytes, ot_bytes, False)
        
        barra_progreso.progress(25, text="🧠 Analizando con IA (Gemini)...")
        try:
            datos = extraer_datos_ia(pdf_final, modelo_ia)
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str or "quota" in error_str.lower():
                barra_progreso.empty()
                st.warning("⚠️ Servidores saturados. Esperá unos segundos y reintentá este archivo.")
                return False
                
            id_err = f"ERR_{int(datetime.now().timestamp())}"
            mensaje_limpio = re.sub(r'[^\w\s\-\.\/]', '', error_str)[:100]
            txt_final = f"Error IA: {mensaje_limpio}"
            
            barra_progreso.progress(90, text="📁 Guardando en REVISIÓN...")
            link = subir_archivo(f"ERROR_{id_err}.pdf", pdf_final, ID_DRIVE_RAIZ, "REVISION")
            escribir_fila(H_REVIS, [id_err, "Desc", "S/N", txt_final, link])
            barra_progreso.empty()
            st.error("❌ Documento ilegible. Enviado a pestaña REVISION.")
            return False

        barra_progreso.progress(50, text="🔍 Verificando duplicados...")
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
            barra_progreso.progress(80, text="⚠️ Guardando duplicado...")
            link_nuevo = subir_archivo(f"DUP_{fecha_iso}_{num_completo}.pdf", pdf_final, ID_DRIVE_RAIZ, "DUPLICADOS")
            escribir_fila(H_DUPLI, [id_unico, alias_prov, num_completo, datetime.now().strftime("%d/%m/%Y"), "Comprobante duplicado.", "", link_nuevo])
            barra_progreso.empty()
            st.warning("⚠️ Duplicado detectado y guardado en la pestaña correspondiente.")
            return False

        total_formateado = f"{total:.2f}".replace('.', '_')
        suf = "_OT" if ot_file else ""
        nombre_pdf = f"{fecha_iso}_{num_completo}_{total_formateado}{suf}.pdf"
        
        barra_progreso.progress(75, text="☁️ Subiendo a Google Drive...")
        link_drive = subir_archivo(nombre_pdf, pdf_final, ID_DRIVE_RAIZ, alias_prov)

        barra_progreso.progress(90, text="📝 Registrando contabilidad...")
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

        barra_progreso.empty()
        st.success(f"✅ Guardado con éxito: **{alias_prov}** (${total})")
        return True

# ==========================================
# INTERFAZ (UI)
# ==========================================
st.markdown("## 🧾 Módulo de Facturación")
st.markdown("Carga y procesamiento inteligente de comprobantes.")
st.divider()

col_motor, col_vacia = st.columns([1, 1])
with col_motor:
    opcion_ia = st.selectbox(
        "⚙️ Motor de IA:",
        options=["Gemini 3.5 Flash (Rápido)", "Gemini 3.1 Pro (Avanzado)"],
        label_visibility="collapsed"
    )
motor_elegido = 'gemini-3.5-flash' if "Flash" in opcion_ia else 'gemini-3.1-pro'

st.divider()
st.markdown("### 📤 Carga de Documentos")
st.info("💡 **Tip:** Podés arrastrar una carpeta completa adentro del recuadro para subir todo su contenido de golpe.")

# UX: El toggle (interruptor) es más elegante que pestañas completas
usar_camara = st.toggle("📸 Activar Cámara (Celular)")

archivos_facturas_up = []
archivo_ot_up = None
archivo_fac_cam = None
archivo_ot_cam = None

if usar_camara:
    col_cam1, col_cam2 = st.columns(2)
    with col_cam1:
        archivo_fac_cam = st.camera_input("1. Foto de la Factura (Obligatorio)")
    with col_cam2:
        archivo_ot_cam = st.camera_input("2. Foto de la OT (Opcional)")
else:
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        # 🌟 AHORA ACEPTA MÚLTIPLES ARCHIVOS O CARPETAS ARRASTRADAS
        archivos_facturas_up = st.file_uploader("1. Factura/s *Obligatorio*", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    with col_up2:
        archivo_ot_up = st.file_uploader("2. Orden de Trabajo *Opcional*", type=["pdf", "png", "jpg", "jpeg"])
        if len(archivos_facturas_up) > 1 and archivo_ot_up:
            st.warning("⚠️ Estás subiendo varias facturas a la vez, pero solo una OT. Esta OT se adjuntará **únicamente a la primera factura** de la lista.")

# Armado final de las variables
lista_facturas_final = archivos_facturas_up if not usar_camara else ([archivo_fac_cam] if archivo_fac_cam else [])
ot_final = archivo_ot_up if not usar_camara else archivo_ot_cam

st.divider()
st.warning("⚠️ **IMPORTANTE:** Durante el procesamiento, NO bloquees la pantalla ni cierres el navegador web.")

if st.button("🚀 Procesar Comprobantes", type="primary", use_container_width=True):
    total_archivos = len(lista_facturas_final)
    
    if total_archivos == 0:
        st.error("❌ Debes subir al menos una factura para continuar.")
    else:
        procesados_ok = 0
        for i, fac_file in enumerate(lista_facturas_final):
            # Solo pasamos la OT al primer archivo para evitar mezclar documentos en cargas masivas
            ot_para_enviar = ot_final if i == 0 else None 
            
            exito = procesar_un_archivo(fac_file, ot_para_enviar, motor_elegido, i + 1, total_archivos)
            if exito: procesados_ok += 1
            
        st.write("---")
        st.success(f"🎉 Resumen: Se procesaron correctamente {procesados_ok} de {total_archivos} archivo/s.")
