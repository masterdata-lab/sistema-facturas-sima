import os
from pypdf import PdfReader, PdfWriter
import io

def segmentar_pdf_en_memoria(uploaded_file):
    """
    Troza un PDF multipágina en páginas individuales en memoria 
    para evitar enviar archivos pesados a la API de Gemini.
    """
    paginas_cortadas = []
    reader = PdfReader(uploaded_file)
    
    for idx, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        
        pdf_bytes = io.BytesIO()
        writer.write(pdf_bytes)
        pdf_bytes.seek(0)
        
        paginas_cortadas.append({
            "nombre_origen": f"{uploaded_file.name}_pag_{idx+1}.pdf",
            "stream": pdf_bytes
        })
    return paginas_cortadas

def generar_nombre_legible(tipo_doc, datos):
    """
    Genera la nomenclatura estricta solicitada para Google Drive.
    """
    patente = datos.get("patente", "SIN_PATENTE").upper().replace(" ", "")
    cuit = datos.get("cuit_cuil", "SIN_CUIT").replace(" ", "")
    
    if tipo_doc in ["TITULO", "CEDULA_VERDE"]:
        return f"{tipo_doc}_{patente}_{cuit}.pdf"
    
    elif tipo_doc in ["VTV", "RTO", "YPF"]:
        vto = datos.get("fecha_vencimiento", "SIN_VTO").replace("/", "-")
        return f"{tipo_doc}_{patente}_VTO_{vto}.pdf"
    
    elif tipo_doc == "CERTIFICADO_SEGURO":
        poliza = datos.get("numero_poliza", "SIN_POLIZA")
        aseguradora = datos.get("aseguradora", "GENERICA").upper().replace(" ", "_")
        return f"SEGURO_{patente}_POLIZA_{poliza}_{aseguradora}_2026.pdf"
        
    return f"COMPROBANTE_{patente}.pdf"
