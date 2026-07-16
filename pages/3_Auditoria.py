import streamlit as st
import json
import re
import io
from PIL import Image
from datetime import datetime

# Importaciones de la sala de máquinas
from utils.conexiones import (
    leer_hoja_completa, descargar_archivo, actualizar_estado_carga,
    escribir_fila, escribir_multiples_filas, obtener_valores_columna, limpiar_nombre, subir_archivo,
    ID_DRIVE_RAIZ, H_GENERAL, H_DETALLE, H_PROV
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

# Función de seguridad para convertir números aunque estén vacíos
def safe_float(valor, por_defecto=0.0):
    try:
        if valor is None or str(valor).strip().lower() == "none" or str(valor).strip() == "":
            return por_defecto
        return float(valor)
    except:
        return por_defecto

st.markdown("## ⚖️ Módulo de Auditoría Humana")
st.markdown("Revisá los comprobantes procesados, corregí los datos si es necesario y aprobalos para la contabilidad final.")
st.divider()

with st.spinner("Buscando facturas pendientes de auditoría..."):
    datos_cola = leer_hoja_completa(H_PENDIENTES)

para_auditar = [fila for fila in datos_cola[1:] if len(fila) >= 9 and fila[6] == "PARA_AUDITAR"]

if not para_auditar:
    st.success("🎉 ¡Excelente trabajo! No hay facturas pendientes de auditoría en este momento.")
else:
    st.info(f"📌 Tenés {len(para_auditar)} factura/s esperando revisión.")
    
    opciones = {fila[0]: f"{fila[1]} - {fila[2]}" for fila in para_auditar}
    carga_seleccionada = st.selectbox("Seleccionar comprobante a auditar:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
    
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
    
    col_pdf, col_datos = st.columns([1, 1], gap="large")
    
    with col_pdf:
        st.markdown("### 📄 Documento Original")
        id_drive = extraer_id_drive(link_fac)
        if id_drive:
            url_preview = f"https://drive.google.com/file/d/{id_drive}/preview"
            st.markdown(f'<iframe src="{url_preview}" width="100%" height="800px" style="border: none; border-radius: 8px;"></iframe>', unsafe_allow_html=True)
            
            with st.expander("¿Problemas para ver el documento?"):
                pdf_bytes_rescate = descargar_archivo(id_drive)
                if pdf_bytes_rescate:
                    st.download_button("⬇️ Descargar Archivo Físico", data=pdf_bytes_rescate, file_name="comprobante.pdf", mime="application/pdf")
        else:
            st.error("No se pudo obtener el enlace al PDF.")
    
    with col_datos:
        st.markdown("### 📝 Formulario de Validación")
        
        if st.button("🔄 Restablecer Datos Originales (IA)", help="Borra tus ediciones y vuelve a cargar los datos que leyó la IA."):
            st.rerun()
            
        st.markdown("#### Datos del Proveedor")
        col_cuit, col_rs = st.columns([1, 2])
        with col_cuit:
            cuit = st.text_input("CUIT", value=datos_ia.get("cuit_proveedor", ""))
        with col_rs:
            razon_social = st.text_input("Razón Social", value=datos_ia.get("razon_social", ""))
        
        st.markdown("#### Datos del Comprobante")
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha = st.text_input("Fecha (DD/MM/YYYY)", value=datos_ia.get("fecha", ""))
        with col2:
            pv = st.text_input("Punto de Venta", value=str(datos_ia.get("punto_venta", "0")))
        with col3:
            num = st.text_input("Nro Factura", value=str(datos_ia.get("nro_factura", "0")))
        
        # Procesamos la patente general para inyectarla en los ítems
        patente_ia = datos_ia.get("patente", "")
        if not patente_ia or patente_ia.upper() == "SIN_PATENTE":
            patente_ia = "DPA"
            
        st.markdown("#### 🔗 Orden de Trabajo")
        nro_ot = st.text_input("Nro de OT (General)", value=datos_ia.get("nro_ot", ""))
        nueva_ot = st.file_uploader("📎 Adjuntar archivo de OT (Si faltó subirla)", type=["pdf", "png", "jpg", "jpeg"])
        
        st.markdown("#### Ítems de la Factura (Patentes y Montos)")
        st.caption("Podés asignar una patente distinta a cada ítem si corresponde.")
        
        # Preparamos los ítems inyectándoles la patente de la IA si no la tienen
        items_precargados = datos_ia.get("items", [])
        if not items_precargados:
            items_precargados = [{"patente": patente_ia.upper(), "descripcion": "", "cantidad": 1, "precio_unitario": 0.0}]
        else:
            for it in items_precargados:
                if "patente" not in it or not it["patente"]:
                    it["patente"] = patente_ia.upper()

        items_editados = st.data_editor(items_precargados, num_rows="dynamic")
        
        # 🌟 MATEMÁTICA BLINDADA
        suma_items = 0.0
        for item in items_editados:
            desc = str(item.get("descripcion", "")).strip()
            if not desc or desc.lower() == "none":
                continue # Ignora filas vacías en el cálculo
            cant = safe_float(item.get("cantidad"), 1.0)
            precio = safe_float(item.get("precio_unitario"), 0.0)
            suma_items += cant * precio
            
        st.success(f"🧮 **Sumatoria automática de los ítems de arriba:** ${suma_items:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
        st.markdown("#### Totales Generales (Para asentar contablemente)")
        
        col6, col7 = st.columns(2)
        with col6:
            subtotal = st.number_input("Subtotal (Neto)", value=float(datos_ia.get("subtotal", 0.0)), step=100.0)
        with col7:
            total = st.number_input("Total Final (Con Impuestos)", value=float(datos_ia.get("total", 0.0)), step=100.0)
        
        st.write("---")
        
        if st.button("✅ Confirmar y Aprobar Factura", type="primary", use_container_width=True):
            with st.spinner("Guardando en la contabilidad definitiva..."):
                alias_prov = limpiar_nombre(razon_social)
                num_completo = f"{str(pv).zfill(5)}-{str(num).zfill(8)}"
                id_unico = f"{cuit}_{pv}_{num}"
                
                if nueva_ot:
                    ot_bytes = asegurar_pdf(nueva_ot)
                    link_nueva_ot = subir_archivo(f"{num_completo}_OT.pdf", ot_bytes, ID_DRIVE_RAIZ, alias_prov)
                
                try:
                    fecha_dt = datetime.strptime(fecha, "%d/%m/%Y")
                    mes_txt = f"{str(fecha_dt.month).zfill(2)}-{['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'][fecha_dt.month-1]}"
                    anio = fecha_dt.year
                except:
                    mes_txt, anio = "00-IND", datetime.now().year

                # 🌟 PROCESAMIENTO DE ÍTEMS Y LIMPIEZA DE FILAS FANTASMAS
                filas_detalle = []
                patentes_usadas = set()
                
                for item in items_editados:
                    desc = str(item.get("descripcion", "")).strip()
                    if not desc or desc.lower() == "none":
                        continue # Elimina filas basura para no ensuciar Google Sheets
                        
                    cant = int(safe_float(item.get("cantidad"), 1.0))
                    precio_u = safe_float(item.get("precio_unitario"), 0.0)
                    
                    pat_item = str(item.get("patente", patente_ia)).strip().upper()
                    if not pat_item or pat_item == "NONE":
                        pat_item = "DPA"
                    patentes_usadas.add(pat_item)
                    
                    for _ in range(cant): 
                        filas_detalle.append([id_unico, anio, mes_txt, fecha, alias_prov, razon_social, num_completo, nro_ot, pat_item, "", desc, 1, precio_u, precio_u, f'=HYPERLINK("{link_fac}", "Ver PDF")'])
                
                # Armamos un resumen de patentes para la hoja general
                patente_general_resumen = " / ".join(patentes_usadas) if patentes_usadas else "DPA"

                escribir_fila(H_GENERAL, [id_unico, anio, mes_txt, fecha, patente_general_resumen, alias_prov, razon_social, pv, num, num_completo, subtotal, total, f'=HYPERLINK("{link_fac}", "Ver PDF")'])
                
                if filas_detalle: 
                    escribir_multiples_filas(H_DETALLE, filas_detalle)

                cuits_historico = obtener_valores_columna(H_PROV, 3)
                if str(cuit) not in cuits_historico:
                    escribir_fila(H_PROV, [alias_prov, razon_social, cuit])
                
                actualizar_estado_carga(H_PENDIENTES, id_carga, "APROBADA")
                
                st.success("✅ ¡Factura aprobada y registrada en contabilidad exitosamente!")
                st.rerun()
