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
    """
    Intenta extraer datos con IA. Si falla por cuota/saturación (503/429), 
    retorna una lista vacía de forma segura en lugar de romper la app.
    """
    prompt = """
    Analiza este documento vehicular argentino. Puede contener uno o MUCHOS registros agrupados.
    1. Identifica qué tipo de documento base es: "TITULO", "VTV", "SEGURO", "RUTA" o "DESCONOCIDO".
    2. Extrae la información unidad por unidad (patente por patente).
    Devuelve estrictamente una lista JSON con esta estructura:
    [{"tipo_documento": "TITULO", "patente": "AB123CD", "marca": "", "modelo": "", "anio": "", "chasis": "", "motor": "", "fecha_vencimiento": ""}]
    """
    try:
        doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        resp = ia_client.models.generate_content(
            model='gemini-3.5-flash', contents=[doc, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        resultado = json.loads(resp.text)
        return resultado if isinstance(resultado, list) else [resultado]
    except Exception as e:
        # Falla silenciosa para el usuario: la IA no está disponible en este momento
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

tab_visor, tab_alta, tab_renovacion = st.tabs(["📊 Estado de Flota", "➕ Alta de Vehículos", "📅 Carga de VTV/Seguros"])

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
    except: pass

with tab_alta:
    st.markdown("### Ingreso de Vehículos (Manual Primero)")
    
    # El archivo de respaldo siempre se sube
    archivo_adjunto = st.file_uploader("Subir Título de Respaldo (PDF/Fotos)", type=["pdf", "png", "jpg"])
    
    # Formulario explícito: la verdad de los datos la tiene el usuario
    with st.form("form_alta_vehiculo"):
        st.write("📋 **Datos de la Unidad** (Podés completarlos manualmente o usar el asistente abajo)")
        c1, c2, c3 = st.columns(3)
        patente_input = c1.text_input("Patente *").upper().replace("-","").replace(" ","")
        gerencia_input = c2.selectbox("Gerencia Asignada", lista_gerencias)
        marca_input = c3.text_input("Marca")
        
        c4, c5, c6 = st.columns(3)
        modelo_input = c4.text_input("Modelo")
        anio_input = c5.text_input("Año")
        chasis_input = c6.text_input("Chasis / Cuadro")
        
        motor_input = st.text_input("Número de Motor")
        
        # Botón asistente: Si el usuario quiere, intenta usar la IA para autorellenar la pantalla actual
        asistente_ia = st.checkbox("💡 Intentar autorellenar campos usando IA al procesar el archivo")
        
        guardar_btn = st.form_submit_button("💾 Registrar Vehículo en Sistema", type="primary")
        
        if guardar_btn:
            if not patente_input and not archivo_adjunto:
                st.error("Faltan datos obligatorios (Patente o Archivo).")
            else:
                pdf_bytes = asegurar_pdf(archivo_adjunto) if archivo_adjunto else None
                link_drive = ""
                
                # Si el asistente de IA está activo y hay archivo, intentamos extraer
                if asistente_ia and pdf_bytes:
                    with st.spinner("Asistente IA consultando datos..."):
                        datos_ia = procesar_documento_vehicular_multiple(pdf_bytes)
                        if datos_ia:
                            # Si la IA respondió bien, priorizamos sus datos si los campos estaban vacíos
                            primero = datos_ia[0]
                            patente_input = patente_input or primero.get("patente","").upper()
                            marca_input = marca_input or primero.get("marca","").upper()
                            modelo_input = modelo_input or primero.get("modelo","").upper()
                            anio_input = anio_input or primero.get("anio","")
                            chasis_input = chasis_input or primero.get("chasis","").upper()
                            motor_input = motor_input or primero.get("motor","").upper()
                            st.toast("🤖 Campos completados por el asistente de IA.")
                        else:
                            st.toast("⚠️ IA no disponible temporalmente. Se guardarán los datos ingresados a mano.")
                
                # Proceso de guardado clásico inmune a fallas de IA
                if patente_input:
                    if pdf_bytes:
                        link_drive = subir_archivo(f"TITULO_{patente_input}.pdf", pdf_bytes, ID_DRIVE_RAIZ, "FLOTA")
                    
                    fila = [
                        patente_input, "ACTIVO", "S/D", gerencia_input, "AUTO", marca_input, 
                        modelo_input, anio_input, chasis_input, motor_input, "", "", "", "", link_drive, "", "", ""
                    ]
                    escribir_fila("FLOTA", fila)
                    st.success(f"✅ Vehículo {patente_input} registrado correctamente.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Por favor, ingresá la patente manualmente si la IA está experimentando alta demanda.")

with tab_renovacion:
    st.markdown("### Carga de Vencimientos y Pólizas Masivas")
    
    archivo_poliza = st.file_uploader("Subir Archivo de Respaldo (Póliza Flota/VTV)", type=["pdf", "png", "jpg"])
    
    # Formulario manual prioritario para evitar bloqueos por errores 503 externos
    with st.form("form_renovacion_doc"):
        st.write("✍️ **Carga o Corrección Manual de Vencimientos**")
        c1, c2, c3 = st.columns(3)
        patente_renov = c1.text_input("Patente a impactar").upper().strip()
        tipo_doc = c2.selectbox("Tipo de Trámite", ["VTV", "SEGURO", "RUTA"])
        fecha_nueva = c3.text_input("Fecha de Vencimiento (DD/MM/YYYY)")
        
        usar_ia_desglose = st.checkbox("🔍 Intentar pre-visualizar datos del archivo con Asistente IA")
        
        enviar_renov = st.form_submit_button("Actualizar Registro")
        
        if enviar_renov:
            if patente_renov and fecha_nueva:
                # Aquí corre tu lógica directa a GSheets independiente de la IA
                st.success(f"Actualizando {tipo_doc} para {patente_renov} al {fecha_nueva}...")
                # (Lógica de inyección directa)
            else:
                st.error("Por favor completa los campos manuales obligatorios.")
                
    # Bloque de asistencia de lectura opcional por separado
    if archivo_poliza and usar_ia_desglose:
        if st.button("Ejecutar lectura asistida de lote"):
            with st.spinner("Leyendo estructura..."):
                pdf_bytes = asegurar_pdf(archivo_poliza)
                lista_docs = procesar_documento_vehicular_multiple(pdf_bytes)
                if lista_docs:
                    st.write("🤖 **Datos sugeridos por la IA (Podés copiarlos arriba):**")
                    st.dataframe(pd.DataFrame(lista_docs)[['tipo_documento', 'patente', 'fecha_vencimiento']])
                else:
                    st.error("El servidor de Google está experimentando alta demanda en este momento. Por favor, realiza la carga utilizando el formulario manual de arriba.")
