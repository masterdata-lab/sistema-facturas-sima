import streamlit as st
import json
import base64
import re
from datetime import datetime

# Importaciones de la sala de máquinas
from utils.conexiones import (
    leer_hoja_completa, descargar_archivo, actualizar_estado_carga,
    escribir_fila, escribir_multiples_filas, obtener_valores_columna, limpiar_nombre,
    H_GENERAL, H_DETALLE, H_PROV
)

st.set_page_config(page_title="SIMA ERP | Auditoría", page_icon="⚖️", layout="wide")

try:
    H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except:
    H_PENDIENTES = "PENDIENTES"

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

def mostrar_pdf(base64_pdf):
    # Incrusta el visor de PDF nativo del navegador
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

st.markdown("## ⚖️ Módulo de Auditoría Humana")
st.markdown("Revisá los comprobantes procesados por la IA, corregí los datos si es necesario y aprobalos para la contabilidad final.")
st.divider()

with st.spinner("Buscando facturas pendientes de auditoría..."):
    datos_cola = leer_hoja_completa(H_PENDIENTES)

# Filtramos los que están listos para auditar (Tienen que tener estado PARA_AUDITAR y datos en la col 9)
para_auditar = [fila for fila in datos_cola[1:] if len(fila) >= 9 and fila[6] == "PARA_AUDITAR"]

if not para_auditar:
    st.success("🎉 ¡Excelente trabajo! No hay facturas pendientes de auditoría en este momento.")
else:
    st.info(f"📌 Tenés {len(para_auditar)} factura/s esperando revisión.")
    
    # Selector de factura a auditar
    opciones = {fila[0]: f"{fila[1]} - {fila[2]}" for fila in para_auditar}
    carga_seleccionada = st.selectbox("Seleccionar comprobante a auditar:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
    
    # Obtener los datos de la fila seleccionada
    fila_actual = next(f for f in para_auditar if f[0] == carga_seleccionada)
    id_carga = fila_actual[0]
    link_fac = fila_actual[4]
    json_crudo = fila_actual[8]
    
    try:
        datos_ia = json.loads(json_crudo)
    except:
        datos_ia = {}
        st.error("Error al leer los datos de la IA. Revisá manualmente.")

    st.divider()
    
    # 🌟 PANTALLA DIVIDIDA
    col_pdf, col_datos = st.columns([1, 1], gap="large")
    
    with col_pdf:
        st.markdown("### 📄 Documento Original")
        id_drive = extraer_id_drive(link_fac)
        if id_drive:
            with st.spinner("Cargando documento..."):
                pdf_bytes = descargar_archivo(id_drive)
                if pdf_bytes:
                    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                    mostrar_pdf(base64_pdf)
                else:
                    st.error("No se pudo descargar el PDF de Google Drive.")
    
    with col_datos:
        st.markdown("### 📝 Formulario de Validación")
        with st.form("form_auditoria"):
            
            st.markdown("#### Datos del Proveedor")
            cuit = st.text_input("CUIT Proveedor", value=datos_ia.get("cuit_proveedor", ""))
            razon_social = st.text_input("Razón Social", value=datos_ia.get("razon_social", ""))
            
            st.markdown("#### Datos del Comprobante")
            col1, col2, col3 = st.columns(3)
            with col1:
                fecha = st.text_input("Fecha (DD/MM/YYYY)", value=datos_ia.get("fecha", ""))
            with col2:
                pv = st.text_input("Punto de Venta", value=str(datos_ia.get("punto_venta", "0")))
            with col3:
                num = st.text_input("Nro Factura", value=str(datos_ia.get("nro_factura", "0")))
            
            # Regla de Negocio: Si la patente está vacía o dice SIN_PATENTE, ponemos DPA
            patente_ia = datos_ia.get("patente", "")
            if not patente_ia or patente_ia.upper() == "SIN_PATENTE":
                patente_ia = "DPA"
                
            col4, col5 = st.columns(2)
            with col4:
                patente = st.text_input("Patente asignada", value=patente_ia.upper())
            with col5:
                nro_ot = st.text_input("Nro de OT", value=datos_ia.get("nro_ot", ""))
            
            st.markdown("#### Ítems de la Factura (Editables)")
            # st.data_editor permite modificar la tabla directamente en pantalla
            items_editados = st.data_editor(datos_ia.get("items", [{"descripcion": "", "cantidad": 1, "precio_unitario": 0.0}]), num_rows="dynamic", use_container_width=True)
            
            st.markdown("#### Totales Generales")
            col6, col7 = st.columns(2)
            with col6:
                subtotal = st.number_input("Subtotal (Neto)", value=float(datos_ia.get("subtotal", 0.0)), step=100.0)
            with col7:
                total = st.number_input("Total Final (Con Impuestos)", value=float(datos_ia.get("total", 0.0)), step=100.0)
            
            st.info("💡 **Recordatorio matemático:** Si hay una discrepancia entre la suma de los ítems y los totales generales, el sistema guardará exactamente lo que dejes escrito en estas casillas.")
            
            # Botón de aprobación final
            aprobado = st.form_submit_button("✅ Confirmar y Aprobar Factura", type="primary", use_container_width=True)
            
        if aprobado:
            with st.spinner("Guardando en la contabilidad definitiva..."):
                # 1. Armamos las variables limpias
                alias_prov = limpiar_nombre(razon_social)
                num_completo = f"{str(pv).zfill(5)}-{str(num).zfill(8)}"
                id_unico = f"{cuit}_{pv}_{num}"
                
                try:
                    fecha_dt = datetime.strptime(fecha, "%d/%m/%Y")
                    mes_txt = f"{str(fecha_dt.month).zfill(2)}-{['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'][fecha_dt.month-1]}"
                    anio = fecha_dt.year
                except:
                    mes_txt, anio = "00-IND", datetime.now().year

                # 2. Guardamos en GENERAL
                escribir_fila(H_GENERAL, [id_unico, anio, mes_txt, fecha, patente, alias_prov, razon_social, pv, num, num_completo, subtotal, total, f'=HYPERLINK("{link_fac}", "Ver PDF")'])
                
                # 3. Guardamos los ítems en DETALLE
                filas_detalle = []
                for item in items_editados:
                    cant = int(item.get("cantidad", 1))
                    precio_u = float(item.get("precio_unitario", 0))
                    for _ in range(cant): 
                        filas_detalle.append([id_unico, anio, mes_txt, fecha, alias_prov, razon_social, num_completo, nro_ot, patente, "", item.get("descripcion", ""), 1, precio_u, precio_u, f'=HYPERLINK("{link_fac}", "Ver PDF")'])
                if filas_detalle: 
                    escribir_multiples_filas(H_DETALLE, filas_detalle)

                # 4. Guardamos Proveedor si es nuevo
                cuits_historico = obtener_valores_columna(H_PROV, 3)
                if str(cuit) not in cuits_historico:
                    escribir_fila(H_PROV, [alias_prov, razon_social, cuit])
                
                # 5. Cambiamos el estado en PENDIENTES
                actualizar_estado_carga(H_PENDIENTES, id_carga, "APROBADA")
                
                st.success("✅ ¡Factura aprobada y registrada en contabilidad exitosamente!")
                st.rerun() # Recarga la página para mostrar la siguiente factura
