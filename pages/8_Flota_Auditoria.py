import streamlit as st
import json
import re
import time
from utils.conexiones import leer_hoja_completa, escribir_fila, actualizar_estado_carga # Usando tus conectores

st.set_page_config(page_title="DPA | Auditoría Flota", page_icon="⚖️", layout="wide")

# CSS para scrolls e iframe adaptativo
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    iframe { border: 1px solid #c1c1c1; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

def extraer_id_drive(url_drive):
    if not url_drive: return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

# Cargar maestro de patentes existentes para la alerta relacional
try: datos_flota = leer_hoja_completa("FLOTA")
except: datos_flota = []
patentes_existentes = [str(f[0]).strip().upper() for f in datos_flota[1:] if f]

st.title("⚖️ Mesa de Auditoría: Documentación de Flota")
st.divider()

# Leer cola de pendientes
try: cola_pendientes = leer_hoja_completa("PENDIENTES")
except: cola_pendientes = []

# Filtramos solo lo que pertenezca al flujo documental de flota
registros_flota = [f for f in cola_pendientes[1:] if len(f) >= 7 and f[6] == "PARA_AUDITAR_FLOTA"]

if not registros_flota:
    st.success("🎉 No hay documentación de flota pendiente de auditoría humana.")
else:
    # Selector indexado de archivos en cola
    opciones = {}
    for r in registros_flota:
        try: sugerido = json.loads(r[8]).get("tipo_sugerido", "DOC")
        except: sugerido = "DOC"
        opciones[r[0]] = f"📄 {sugerido} | Archivo: {r[2]} | Cargado: {r[1]}"
        
    seleccion = st.selectbox("Seleccionar archivo para auditar:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
    
    fila_actual = next(f for f in registros_flota if f[0] == seleccion)
    id_carga, url_pdf, json_crudo = fila_actual[0], fila_actual[4], fila_actual[8]
    
    datos_ia = {}
    if json_crudo:
        try: datos_ia = json.loads(json_crudo)
        except: pass

    # PANTALLA DIVIDIDA: 50% Visualizador | 50% Formulario de Veracidad
    col_visor, col_datos = st.columns([1, 1], gap="medium")
    
    with col_visor:
        st.subheader("👀 Copia Fiel del Documento")
        id_drive = extraer_id_drive(url_pdf)
        if id_drive:
            url_preview = f"https://drive.google.com/file/d/{id_drive}/preview"
            st.markdown(f'<iframe src="{url_preview}" width="100%" height="800px"></iframe>', unsafe_allow_html=True)
        else:
            st.error("No se puede renderizar la vista previa de Google Drive.")
            
    with col_datos:
        st.subheader("📝 Formulario de Validación y Cruce")
        
        # Corrección de tipo dinámica en pantalla
        tipo_documento = st.selectbox(
            "Tipo de Documento Correcto", 
            ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"],
            index=["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"].index(datos_ia.get("tipo_sugerido", "CEDULA_VERDE"))
        )
        
        patente = st.text_input("Patente del Vehículo (Sin espacios)", value=datos_ia.get("patente", "N/A")).upper().strip()
        
        # --- REGLA DE NEGOCIO INTEGRADA: ALTA POR TÍTULO ---
        es_alta_nueva = False
        if patente not in patentes_existentes:
            if tipo_documento == "TITULO":
                st.info("ℹ️ **Modo Alta de Vehículo Activo:** Esta patente no existe en el sistema. Al confirmar el Título, el auto se registrará de forma automática en el maestro FLOTA.")
                es_alta_nueva = True
            else:
                st.error("⚠️ La patente ingresada NO figura en el maestro FLOTA. Para cargar este documento primero debes dar de alta el auto mediante su TITULO o agregarlo al listado maestro.")
        
        st.markdown("---")
        st.markdown("#### Datos de Control Operativo")
        c1, c2 = st.columns(2)
        with c1: titular = st.text_input("Titular / Tomador", value=datos_ia.get("titular", ""))
        with c2: cuit_cuil = st.text_input("CUIT / CUIL Vinculado", value=datos_ia.get("cuit_cuil", ""))
        
        # Habilitación de campos específicos condicionales
        vencimiento = ""
        if tipo_documento == "CERTIFICADO_SEGURO":
            c3, c4 = st.columns(2)
            with c3: aseguradora = st.text_input("Compañía Aseguradora")
            with c4: poliza = st.text_input("Número de Póliza")
            vencimiento = st.text_input("Fecha Vencimiento Póliza (DD/MM/YYYY)")
            
        elif tipo_documento != "CEDULA_VERDE":
            # Recordá: Cédula verde no lleva control de vencimiento restrictivo
            vencimiento = st.text_input("Fecha Vencimiento del Documento (DD/MM/YYYY)")
            
        st.markdown("---")
        b_aprobar, b_descartar = st.columns(2)
        
        if b_aprobar.button("✅ Aprobar e Inyectar a Producción", type="primary", use_container_width=True, disabled=(patente not in patentes_existentes and not es_alta_nueva)):
            with st.spinner("Guardando en base de datos..."):
                hoy = time.strftime("%d/%m/%Y")
                
                # Acciones si es un auto nuevo vía Título
                if es_alta_nueva and tipo_documento == "TITULO":
                    # Estructura FLOTA: ["Patente", "Estado", "CUIT Empresa", ...]
                    escribir_fila("FLOTA", [patente, "ACTIVO", cuit_cuil, "DPA", "AUTO", "", "", "", "", "", "", "", "", "", "", "", "", "", "", f"Alta automática por auditoría de título el {hoy}"])
                
                # Si es un seguro va directo al historial retroactivo permanente
                if tipo_documento == "CERTIFICADO_SEGURO":
                    # Estructura HISTORIAL_SEGUROS
                    escribir_fila("HISTORIAL_SEGUROS", [patente, aseguradora, poliza, hoy, vencimiento, titular, cuit_cuil, url_pdf, hoy])
                
                # Cambiamos estado en la cola para sacarla de la vista
                actualizar_estado_carga("PENDIENTES", id_carga, "APROBADO_FLOTA")
                st.success("¡Documento procesado correctamente!")
                time.sleep(0.8)
                st.rerun()
                
        if b_descartar.button("🗑️ Descartar Archivo", use_container_width=True):
            actualizar_estado_carga("PENDIENTES", id_carga, "DESCARTADO_FLOTA")
            st.warning("El documento fue removido de la mesa.")
            time.sleep(0.5)
            st.rerun()
