import streamlit as st
import requests
import base64
import re
import io
from PIL import Image
import PyPDF2
from google import genai

# 🔑 Constantes del Sistema (Cargadas desde los Secrets de Streamlit)
ID_GSHEET = st.secrets["ID_GOOGLE_SHEETS"]
ID_DRIVE_RAIZ = st.secrets["ID_CARPETA_RAIZ_DRIVE"]
URL_SCRIPT = st.secrets["URL_APPS_SCRIPT"]

H_GENERAL = st.secrets["HOJA_GENERAL"]
H_DETALLE = st.secrets["HOJA_DETALLE"]
H_PROV = st.secrets["HOJA_PROVEEDORES"]
H_DUPLI = st.secrets["HOJA_DUPLICADOS"]
H_REVIS = st.secrets["HOJA_REVISION"]

# 🤖 Inicialización del Cliente IA (Soporta cache para no recrearlo siempre)
@st.cache_resource
def obtener_cliente_gemini():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# 🌉 Conexión con Google Apps Script (El Puente)
def llamar_puente(payload):
    headers = {'Content-Type': 'application/json'}
    try:
        payload["token"] = st.secrets["TOKEN_SEGURIDAD"]
    except Exception:
        raise Exception("Falta configurar TOKEN_SEGURIDAD en los Secrets.")
        
    sesion = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    sesion.mount('https://', adapter)
    
    req = requests.Request('POST', URL_SCRIPT, json=payload, headers=headers)
    prepared = sesion.prepare_request(req)
    respuesta = sesion.send(prepared, allow_redirects=True)
    
    try:
        datos = respuesta.json()
        if datos.get("status") == "success": 
            return datos
        else: 
            raise Exception(datos.get("message"))
    except ValueError:
        raise Exception("Google rechazó la conexión. Revisá haber hecho una 'Nueva Implementación' en Apps Script.")

# 📝 Escritura y Lectura de Google Sheets
def escribir_fila(hoja_nombre, fila):
    llamar_puente({
        "accion": "escribir_sheet", 
        "sheetId": ID_GSHEET, 
        "hojaNombre": hoja_nombre, 
        "filaDatos": fila
    })

def escribir_multiples_filas(hoja_nombre, filas):
    llamar_puente({
        "accion": "escribir_multiples_sheets", 
        "sheetId": ID_GSHEET, 
        "hojaNombre": hoja_nombre, 
        "filasDatos": filas
    })

def obtener_valores_columna(hoja_nombre, columna_index):
    res = llamar_puente({
        "accion": "leer_columna", 
        "sheetId": ID_GSHEET, 
        "hojaNombre": hoja_nombre, 
        "columnaIndex": columna_index
    })
    return res.get("valores", [])

# 📁 Subida de Archivos con Carpetas Dinámicas
def subir_archivo(nombre, bytes_data, carpeta_id, subcarpeta_prov=None):
    b64_data = base64.b64encode(bytes_data).decode('utf-8')
    payload = {
        "accion": "subir_pdf", 
        "folderId": carpeta_id, 
        "filename": nombre, 
        "fileData": b64_data
    }
    if subcarpeta_prov:
        payload["subcarpetaProveedor"] = subcarpeta_prov
        
    res = llamar_puente(payload)
    return res["link"]

# 📁 Unificación de PDF y Órdenes de Trabajo (Imágenes o PDFs)
def unificar_documentos(pdf_fac_bytes, ot_bytes=None, ot_es_imagen=False):
    writer = PyPDF2.PdfMerger()
    writer.append(io.BytesIO(pdf_fac_bytes))
    
    if ot_bytes:
        if ot_es_imagen:
            img = Image.open(io.BytesIO(ot_bytes))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            pdf_temp = io.BytesIO()
            img.save(pdf_temp, format="PDF")
            pdf_temp.seek(0)
            writer.append(pdf_temp)
        else:
            writer.append(io.BytesIO(ot_bytes))
            
    output = io.BytesIO()
    writer.write(output)
    writer.close()
    return output.getvalue()

# 🧼 Limpieza de nombres para carpetas de Drive
def limpiar_nombre(texto):
    limpio = re.sub(r'[^a-zA-Z0-9\s]', '', str(texto))
    return " ".join(limpio.split())[:30].upper()
