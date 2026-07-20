import streamlit as st
import pandas as pd
import json
import io
import time
from PIL import Image, ImageOps
from datetime import datetime
from google.genai import types

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

def procesar_documento_vehicular_multiple(pdf_bytes):
    # ... (resto del código igual) ...
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    
    # CAMBIO AQUÍ: Usamos el modelo estable actual de Google Cloud
    resp = ia_client.models.generate_content(
        model='gemini-3.5-flash',  # <--- Este es el modelo oficial
        contents=[doc, prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    
    try:
        resultado = json.loads(resp.text)
        if isinstance(resultado, list):
            return resultado
        else:
            return [resultado]
    except Exception as e:
        st.error(f"Error al decodificar la respuesta de la IA: {e}")
        return []

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
try: datos_gerencias = leer_hoja_completa("GERENCIAS")
except: datos_gerencias = []
lista_gerencias = [str(g[0]).upper() for g in datos_gerencias[1:] if len(g)>0 and str(g[1]).upper()!="INACTIVO"]
if not lista_gerencias: lista_gerencias = ["DPA"]

tab_visor, tab_alta, tab_renovacion = st.tabs(["📊 Estado de Flota", "➕ Alta de Vehículos (Títulos)", "📅 Carga de VTV/Seguros"])

with tab_visor:
    st.markdown("### Semáforo Documental y Asignaciones")
    st.info("💡 Desde aquí podés ver qué autos están vencidos y a qué gerencia pertenecen.")
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
    except: pass

with tab_alta:
    st.markdown("### Ingreso de Nuevos Vehículos")
    modo_manual = st.toggle("✍️ Carga Manual de Excepción (Sin Título Físico)")
    
    if not modo_manual:
        st.info("🤖 **Modo IA Avanzado:** Arrastrá Títulos (Individuales o archivos multi-título). El sistema extraerá e indexará cada unidad por separado.")
        archivos_titulos = st.file_uploader("Subir Títulos (PDF/Fotos)", type=["pdf", "png", "jpg"], accept_multiple_files=True)
        
        if archivos_titulos and st.button("🚀 Procesar Títulos y Guardar", type="primary"):
            panel = st.status(f"Procesando lote de archivos cargados...", expanded=True)
            
            for arch in archivos_titulos:
                panel.write(f"🔍 Analizando documento completo: `{arch.name}`...")
                try:
                    pdf_bytes = asegurar_pdf(arch)
                    # La IA nos devuelve una lista de vehículos encontrados en este archivo
                    lista_vehiculos = procesar_documento_vehicular_multiple(pdf_bytes)
                    
                    panel.write(f"✨ Se detectaron {len(lista_vehiculos)} vehículos dentro de `{arch.name}`. Guardando registros...")
                    
                    for datos in lista_vehiculos:
                        patente = str(datos.get("patente","")).upper().replace("-","").replace(" ","")
                        if patente:
                            # Subimos el archivo completo indexado con el nombre de la patente correspondiente
                            link = subir_archivo(f"TITULO_{patente}.pdf", pdf_bytes, ID_DRIVE_RAIZ, "FLOTA")
                            fila = [
                                patente, "ACTIVO", "S/D", "S/D", "AUTO", str(datos.get("marca","")).upper(), 
                                str(datos.get("modelo","")).upper(), datos.get("anio",""), str(datos.get("chasis","")).upper(), 
                                str(datos.get("motor","")).upper(), "", "", "", "", link, "", "", ""
                            ]
                            escribir_fila("FLOTA", fila)
                            panel.write(f"✅ Guardado exitoso: **{patente}** ({str(datos.get('marca','')).upper()} {str(datos.get('modelo','')).upper()})")
                except Exception as e:
                    st.error(f"Error procesando el archivo {arch.name}: {e}")
                    
            panel.update(label="¡Lote de títulos procesado con éxito!", state="complete")
            st.success("✅ Todos los vehículos del archivo masivo han sido registrados.")
            time.sleep(2)
            st.rerun()
    else:
        with st.form("form_manual_auto"):
            st.warning("Estás dando de alta un vehículo sin respaldo documental.")
            c1, c2, c3 = st.columns(3)
            pat = c1.text_input("Patente *").upper()
            ger = c2.selectbox("Gerencia", lista_gerencias)
            mar = c3.text_input("Marca").upper()
            if st.form_submit_button("Guardar Manual", type="primary") and pat:
                fila = [pat, "ACTIVO", "S/D", ger, "AUTO", mar, "", "", "", "", "", "", "", "", "", "", "", ""]
                escribir_fila("FLOTA", fila)
                st.success("Guardado.")

with tab_renovacion:
    st.markdown("### Carga de Vencimientos y Pólizas Masivas")
    renov_manual = st.toggle("✍️ Carga Manual de Vencimientos (Sin Documento Físico)")
    
    if not renov_manual:
        st.info("🤖 **Modo IA Avanzado:** Subí el archivo (incluso Pólizas Flota con decenas de unidades). La IA mapeará cada vencimiento a su patente correspondiente.")
        doc_vto = st.file_uploader("Subir Documento (VTV/Seguro/Ruta)", type=["pdf", "png", "jpg"])
        
        if doc_vto and st.button("🔍 Desglosar y Leer Documento"):
            with st.spinner("Procesando documento masivo con IA..."):
                pdf_bytes = asegurar_pdf(doc_vto)
                # Extrae todas las patentes y sus fechas específicas del mismo archivo de póliza
                lista_renovaciones = procesar_documento_vehicular_multiple(pdf_bytes)
                
                if lista_renovaciones:
                    st.success(f"**Análisis Completo:** Se encontraron {len(lista_renovaciones)} registros en el documento.")
                    
                    # Mostrar resumen en una tabla interactiva para que el usuario corrobore
                    df_preview = pd.DataFrame(lista_renovaciones)
                    st.dataframe(df_preview[['tipo_documento', 'patente', 'fecha_vencimiento']], use_container_width=True)
                    
                    st.warning("🚧 *Nota de Arquitectura: La actualización coordinada en celdas de Sheets se ejecutará sobre estas unidades.*")
                else:
                    st.error("No se pudieron extraer registros válidos de este archivo.")
    else:
        with st.form("form_renov_manual"):
            st.write("Actualizar fecha manualmente:")
            c1, c2, c3 = st.columns(3)
            pat_renov = c1.text_input("Patente a actualizar").upper()
            tipo_doc = c2.selectbox("Qué vas a actualizar?", ["VTV", "SEGURO", "RUTA"])
            fecha_nueva = c3.text_input("Nueva Fecha (DD/MM/YYYY)")
            if st.form_submit_button("Actualizar Fecha"):
                st.info("🚧 *En desarrollo: Actualización de celdas específicas en GSheets.*")
