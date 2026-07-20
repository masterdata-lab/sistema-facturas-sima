import streamlit as st
import json
import re
import time
from utils.conexiones import leer_hoja_completa, escribir_fila, actualizar_estado_carga

st.set_page_config(page_title="DPA | Auditoría Flota", page_icon="⚖️", layout="wide")

# Estilos CSS específicos para controlar la estructura visual del ERP
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    iframe { border: 2px solid #e6e9ef; border-radius: 8px; background-color: #fafafa; }
    .stAlert { padding: 0.75rem; }
</style>
""", unsafe_allow_html=True)

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": 
        return None
    # Captura variaciones de URL compartida o de APIs (/d/ o id=)
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    if match:
        return match.group(1)
    # Si la celda contiene directamente el ID crudo sin barras
    if len(url_drive) > 20 and "/" not in url_drive and "=" not in url_drive:
        return url_drive
    return None

# Carga en caliente del maestro de patentes para validación cruzada relacional
try: 
    datos_flota = leer_hoja_completa("FLOTA")
except Exception as e: 
    datos_flota = []
    st.error(f"Error al conectar con la base maestra FLOTA: {e}")

patentes_existentes = [str(f[0]).strip().upper() for f in datos_flota[1:] if f and len(f) > 0]

st.title("⚖️ Mesa de Auditoría: Documentación de Flota")
st.markdown("Verificación humana de consistencia, vigencia y asignaciones vehiculares.")
st.divider()

# Lectura del buzón general descentralizado
try: 
    cola_pendientes = leer_hoja_completa("PENDIENTES")
except: 
    cola_pendientes = []

# Filtrado estricto por flujo documental de flota
registros_flota = [f for f in cola_pendientes[1:] if len(f) >= 7 and f[6] == "PARA_AUDITAR_FLOTA"]

if not registros_flota:
    st.success("🎉 Excelente. No hay documentación de flota pendiente de auditoría humana.")
else:
    # Selector de tareas pendientes
    opciones = {}
    for r in registros_flota:
        try: 
            sugerido = json.loads(r[8]).get("tipo_sugerido", "DOC")
        except: 
            sugerido = "DOC"
        opciones[r[0]] = f"📄 {sugerido} | Archivo: {r[2][:30]}... | Fecha: {r[1]}"
        
    seleccion = st.selectbox("Seleccionar comprobante en cola para auditar:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
    
    fila_actual = next(f for f in registros_flota if f[0] == seleccion)
    id_carga, url_pdf, json_crudo = fila_actual[0], fila_actual[4], fila_actual[8]
    
    datos_ia = {}
    if json_crudo:
        try: 
            datos_ia = json.loads(json_crudo)
        except: 
            pass

    # INTERFAZ SPLIT-SCREEN 50% VISOR DRIVE / 50% VALIDACIÓN HUMANA
    col_visor, col_datos = st.columns([1, 1], gap="large")
    
    with col_visor:
        st.subheader("👀 Copia Fiel del Documento")
        id_drive = extraer_id_drive(url_pdf)
        if id_drive:
            url_preview = f"https://drive.google.com/file/d/{id_drive}/preview"
            st.markdown(f'<iframe src="{url_preview}" width="100%" height="800px" allow="autoplay"></iframe>', unsafe_allow_html=True)
        else:
            st.error("Error estructural: No se puede extraer un ID de Google Drive válido desde el enlace registrado.")
            st.info(f"Enlace crudo en base de datos: {url_pdf}")
            
    with col_datos:
        st.subheader("📝 Formulario de Veracidad e Impacto")
        
        # Corregidor e inyector de tipo dinámico
        tipos_validos = ["TITULO", "CEDULA_VERDE", "CERTIFICADO_SEGURO", "VTV", "YPF"]
        tipo_leido = datos_ia.get("tipo_sugerido", "CEDULA_VERDE")
        idx_defecto = tipos_validos.index(tipo_leido) if tipo_leido in tipos_validos else 1
        
        tipo_documento = st.selectbox("Tipo de Documento Homologado", tipos_validos, index=idx_defecto)
        
        patente = st.text_input("Patente del Vehículo (Formato limpio sin espacios)", value=datos_ia.get("patente", "N/A")).upper().strip()
        
        # --- LÓGICA CORE: ALTA AUTOMÁTICA O VALIDACIÓN DE EXISTENCIA ---
        es_alta_nueva = False
        if patente and patente != "N/A":
            if patente not in patentes_existentes:
                if tipo_documento == "TITULO":
                    st.info("ℹ️ **Modo Alta de Activo Detectado:** Esta patente no se encuentra registrada en el sistema. Al confirmar este Título, el vehículo se incorporará automáticamente a la base maestra FLOTA.")
                    es_alta_nueva = True
                else:
                    st.error("⚠️ Operación bloqueada: La patente no figura en la base maestra FLOTA. Para procesar este documento secundario, primero debés dar de alta la unidad usando su TITULO o ingresarla manualmente en el maestro.")
            else:
                st.success("✅ Vehículo validado en la flota activa corporativa.")
        
        st.markdown("---")
        st.markdown("#### Datos Extraídos del Documento")
        c1, c2 = st.columns(2)
        with c1: 
            titular = st.text_input("Titular / Tomador Registrado", value=datos_ia.get("titular", ""))
        with c2: 
            cuit_cuil = st.text_input("CUIT / CUIL Vinculado", value=datos_ia.get("cuit_cuil", ""))
        
        # Inputs condicionales basados en el negocio
        vencimiento = ""
        if tipo_documento == "CERTIFICADO_SEGURO":
            c3, c4 = st.columns(2)
            with c3: aseguradora = st.text_input("Compañía Aseguradora (Ej: Rivadavia, Sancor)")
            with c4: poliza = st.text_input("Número de Póliza de Seguro")
            vencimiento = st.text_input("Fecha Vencimiento de Póliza (DD/MM/YYYY)")
            
        elif tipo_documento != "CEDULA_VERDE":
            # Las cédulas verdes no disparan alertas restrictivas por diseño conceptual
            vencimiento = st.text_input("Fecha Vencimiento del Documento (DD/MM/YYYY)")
            
        st.markdown("---")
        b_aprobar, b_descartar = st.columns(2)
        
        # El botón de aprobación se deshabilita si la patente no existe y no califica para alta automática por título
        bloqueado = (patente not in patentes_existentes and not es_alta_nueva) or (patente == "N/A")
        
        if b_aprobar.button("✅ Confirmar y Transferir a Producción", type="primary", use_container_width=True, disabled=bloqueado):
            with st.spinner("Realizando transacciones y aplicando reglas de negocio..."):
                hoy = time.strftime("%d/%m/%Y")
                
                # REGLA A: Creación automática del registro físico en la pestaña principal
                if es_alta_nueva and tipo_documento == "TITULO":
                    # Estructura de columnas simulada para calzar en tu hoja maestra FLOTA
                    fila_maestro_flota = [patente, "ACTIVO", cuit_cuil, "DPA", "AUTO", "", "", "", "", "", "", "", "", "", "", "", "", "", "", f"Alta automatizada via auditoría de Título el {hoy}"]
                    escribir_fila("FLOTA", fila_maestro_flota)
                
                # REGLA B: Envío retroactivo permanente para auditoría de Seguros
                if tipo_documento == "CERTIFICADO_SEGURO":
                    fila_historial_seguro = [patente, aseguradora, poliza, hoy, vencimiento, titular, cuit_cuil, url_pdf, hoy]
                    escribir_fila("HISTORIAL_SEGUROS", fila_historial_seguro)
                
                # Cierre y limpieza del registro en pendientes
                actualizar_estado_carga("PENDIENTES", id_carga, "APROBADO_FLOTA")
                st.success("¡Documento visado e impactado en las bases de datos con éxito!")
                time.sleep(0.8)
                st.rerun()
                
        if b_descartar.button("🗑️ Descartar y Quitar de la Cola", use_container_width=True):
            actualizar_estado_carga("PENDIENTES", id_carga, "DESCARTADO_FLOTA")
            st.warning("El archivo ha sido removido de la bandeja operativa.")
            time.sleep(0.5)
            st.rerun()
