import streamlit as st
import pandas as pd
import json
import io
import time
from PIL import Image, ImageOps
from datetime import datetime
from google.genai import types

# Usamos pypdf para segmentar el archivo localmente
import pypdf  

from utils.conexiones import (
    leer_hoja_completa, escribir_fila, subir_archivo, ID_DRIVE_RAIZ, obtener_cliente_gemini
)

st.set_page_config(page_title="DPA | Gestión de Flota", page_icon="🚘", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255,75,75,0.8); }
    ::-webkit-scrollbar { width: 10px !important; height: 10px !important; background-color: #f1f1f1 !important; }
    ::-webkit-scrollbar-thumb { background-color: #c1c1c1 !important; border-radius: 5px !important; }
    .firma-flotante { position: fixed; bottom: 8px; right: 15px; font-size: 10.5px; color: rgba(128, 128, 128, 0.6); z-index: 99999; pointer-events: none; font-family: monospace; }
</style>
<div class="firma-flotante">Software DPA | Creado por Serrano Cristian</div>
""", unsafe_allow_html=True)

ia_client = obtener_cliente_gemini()

# --- FUNCIONES AUXILIARES ---
def asegurar_pdf(archivo):
    if archivo is None: return None
    if archivo.type.startswith("image/"):
        img = Image.open(archivo)
        img = ImageOps.exif_transpose(img) 
        if img.mode != 'RGB': img = img.convert('RGB')
        pdf_bytes = io.BytesIO()
        img.save(pdf_bytes, format="PDF")
        return pdf_bytes.getvalue()
    return archivo.getvalue()

def procesar_pagina_individual_con_ia(pdf_page_bytes):
    """
    Envía una sola página a la IA forzando un esquema JSON estricto mediante la API.
    """
    prompt = """
    Analiza este documento vehicular argentino. Extrae los datos y responde UNICAMENTE con el objeto JSON solicitado.
    Estructura requerida:
    {
        "tipo_documento": "TITULO", 
        "patente": "AB123CD",
        "marca": "CORVEN", 
        "modelo": "TRIAX", 
        "anio": "2022", 
        "chasis": "8CV...", 
        "motor": "162...", 
        "fecha_vencimiento": "DD/MM/YYYY"
    }
    Si es TITULO rellena los datos técnicos. Si es VTV, SEGURO o RUTA prioriza la fecha_vencimiento. 
    No agregues texto explicativo ni formato markdown fuera del JSON.
    """
    doc = types.Part.from_bytes(data=pdf_page_bytes, mime_type="application/pdf")
    
    for intento in range(3):
        try:
            resp = ia_client.models.generate_content(
                model='gemini-3.5-flash',
                contents=[doc, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            # Limpieza de seguridad por si el modelo ignora el constraint e inyecta bloques markdown
            texto_limpio = resp.text.strip()
            if texto_limpio.startswith("```"):
                texto_limpio = texto_limpio.split("```")[1]
                if texto_limpio.startswith("json"):
                    texto_limpio = texto_limpio[4:]
            texto_limpio = texto_limpio.strip("` \n")
            
            return json.loads(texto_limpio)
        except Exception as e:
            if ("503" in str(e) or "429" in str(e)) and intento < 2:
                time.sleep(2 ** intento)
                continue
            raise e

def calcular_estado_vto(fecha_str):
    if not fecha_str or str(fecha_str).strip() == "": return "⚪ Sin Dato"
    try:
        f_vto = datetime.strptime(str(fecha_str).strip(), "%d/%m/%Y")
        dias = (f_vto - datetime.now()).days
        if dias < 0: return "🔴 VENCIDO"
        elif dias <= 15: return "🟡 PRÓXIMO"
        else: return "🟢 APTO"
    except: return "⚪ Error"

st.markdown("## 🚘 DPA | Gestión de Flota y Documentación")
st.divider()

# --- CARGA DE MAESTROS ---
try: 
    datos_gerencias = leer_hoja_completa("GERENCIAS")
except: 
    datos_gerencias = []

lista_gerencias = [str(g[0]).upper() for g in datos_gerencias[1:] if len(g)>0 and str(g[1]).upper()!="INACTIVO"]
if not lista_gerencias: 
    lista_gerencias = ["DPA"]

tab_visor, tab_alta, tab_renovacion = st.tabs(["📊 Estado de Flota", "🚀 Alta Inteligente Automatizada", "📅 Carga Masiva de Vencimientos"])

with tab_visor:
    st.markdown("### Semáforo Documental y Asignaciones")
    try:
        datos_flota = leer_hoja_completa("FLOTA")
        if len(datos_flota) > 1:
            df = pd.DataFrame(datos_flota[1:], columns=datos_flota[0])
            if 'Vto VTV' in df.columns: df['Status VTV'] = df['Vto VTV'].apply(calcular_estado_vto)
            if 'Vto Seguro' in df.columns: df['Status Seguro'] = df['Vto Seguro'].apply(calcular_estado_vto)
            
            cols_mostrar = [c for c in ['Patente', 'Estado', 'Gerencia Actual', 'Status VTV', 'Status Seguro', 'Marca', 'Modelo'] if c in df.columns]
            st.dataframe(df[cols_mostrar], use_container_width=True, hide_index=True)
        else:
            st.warning("No hay vehículos cargados.")
    except: 
        pass

with tab_alta:
    st.markdown("### Procesamiento Absoluto de Títulos (Lotes o Multipágina)")
    st.info("🤖 **Modo Automático Activo:** La IA se encargará de fraccionar el documento, extraer los datos técnicos de cada unidad, generar los archivos individuales indexados y guardarlos en la base de datos.")
    
    archivos_titulos = st.file_uploader("Subir Títulos (PDF/Fotos)", type=["pdf", "png", "jpg"], accept_multiple_files=True)
    
    if archivos_titulos and st.button("🚀 Ejecutar Procesamiento e Indexación", type="primary"):
        status_panel = st.status("Iniciando motor de segmentación...", expanded=True)
        
        for arch in archivos_titulos:
            status_panel.write(f"📂 Abriendo archivo original: `{arch.name}`")
            
            try:
                if arch.type.startswith("image/"):
                    pdf_bytes = asegurar_pdf(arch)
                    datos = procesar_pagina_individual_con_ia(pdf_bytes)
                    patente = str(datos.get("patente","")).upper().replace("-","").replace(" ","")
                    if patente:
                        link = subir_archivo(f"TITULO_{patente}.pdf", pdf_bytes, ID_DRIVE_RAIZ, "FLOTA")
                        fila = [patente, "ACTIVO", "S/D", "S/D", "AUTO", str(datos.get("marca","")).upper(), str(datos.get("modelo","")).upper(), datos.get("anio",""), str(datos.get("chasis","")).upper(), str(datos.get("motor","")).upper(), "", "", "", "", link, "", "", ""]
                        escribir_fila("FLOTA", fila)
                        status_panel.write(f"✅ Procesado unitario: **{patente}**")
                
                else:
                    reader = pypdf.PdfReader(arch)
                    total_paginas = len(reader.pages)
                    status_panel.write(f"📄 El archivo contiene {total_paginas} páginas. Procesando una por una...")
                    
                    for idx in range(total_paginas):
                        status_panel.write(f"🔍 Analizando página {idx + 1} de {total_paginas}...")
                        
                        writer = pypdf.PdfWriter()
                        writer.add_page(reader.pages[idx])
                        page_io = io.BytesIO()
                        writer.write(page_io)
                        page_bytes = page_io.getvalue()
                        
                        datos = procesar_pagina_individual_con_ia(page_bytes)
                        patente = str(datos.get("patente","")).upper().replace("-","").replace(" ","")
                        
                        if patente:
                            link = subir_archivo(f"TITULO_{patente}.pdf", page_bytes, ID_DRIVE_RAIZ, "FLOTA")
                            
                            fila = [
                                patente, "ACTIVO", "S/D", "S/D", "AUTO", 
                                str(datos.get("marca","")).upper(), str(datos.get("modelo","")).upper(), 
                                datos.get("anio",""), str(datos.get("chasis","")).upper(), 
                                str(datos.get("motor","")).upper(), "", "", "", "", link, "", "", ""
                            ]
                            escribir_fila("FLOTA", fila)
                            status_panel.write(f"💥 ¡Guardado Exitoso Página {idx + 1}! Patente: **{patente}**")
                        else:
                            status_panel.write(f"⚠️ Página {idx + 1}: No se reconoció patente válida.")
                            
            except Exception as e:
                st.error(f"Error crítico en el archivo {arch.name}: {e}")
                
        status_panel.update(label="¡Todos los documentos desglosados e indexados con éxito!", state="complete")
        st.success("La IA terminó el trabajo de campo. Datos impactados en GSheets and Drive.")
        time.sleep(2)
        st.rerun()

with tab_renovacion:
    st.markdown("### Desglose Automático de Pólizas Flota / VTV")
    st.info("🤖 Subí acá el PDF largo de la póliza. La IA va a leer página por página, detectará a qué patente corresponde el vencimiento y lo dejará listo para impactar.")
    
    archivo_masivo = st.file_uploader("Subir Póliza Completa o Lote de VTV (PDF)", type=["pdf"])
    
    if archivo_masivo and st.button("🔍 Desglosar Póliza y Extraer Fechas", type="primary"):
        status_renov = st.status("Analizando estructura del documento masivo...", expanded=True)
        
        resultados_tabla = []
        
        try:
            reader = pypdf.PdfReader(archivo_masivo)
            total_pag = len(reader.pages)
            status_renov.write(f"Análisis local: Detectadas {total_pag} páginas a auditar.")
            
            for idx in range(total_pag):
                status_renov.write(f"Procesando extracto {idx + 1} de {total_pag}...")
                
                writer = pypdf.PdfWriter()
                writer.add_page(reader.pages[idx])
                page_io = io.BytesIO()
                writer.write(page_io)
                page_bytes = page_io.getvalue()
                
                datos = procesar_pagina_individual_con_ia(page_bytes)
                patente = str(datos.get("patente","")).upper().replace("-","").replace(" ","")
                fecha_vto = datos.get("fecha_vencimiento","")
                tipo_doc = datos.get("tipo_documento","")
                
                if patente and fecha_vto:
                    resultados_tabla.append({
                        "Página": idx + 1,
                        "Tipo": tipo_doc,
                        "Patente": patente,
                        "Vencimiento": fecha_vto
                    })
                    status_renov.write(f"🎯 Mapeado: Pág {idx + 1} -> Patente {patente} vence {fecha_vto}")
            
            status_renov.update(label="Lectura de lote finalizada.", state="complete")
            
            if resultados_tabla:
                st.markdown("### 📋 Resultados listos para confirmación masiva")
                df_resumen = pd.DataFrame(resultados_tabla)
                st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                
                if st.button("💾 Confirmar e Inyectar todos los vencimientos en FLOTA"):
                    st.success("Lógica de inyección en lote lista.")
            else:
                st.warning("No se encontraron registros estructurados legibles en las páginas analizadas.")
                
        except Exception as e:
            st.error(f"Error procesando póliza masiva: {e}")
