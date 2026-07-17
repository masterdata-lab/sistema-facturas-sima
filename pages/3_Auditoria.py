import streamlit as st
import json
import re
import io
import time
from PIL import Image, ImageOps
from datetime import datetime
from utils.conexiones import (leer_hoja_completa, descargar_archivo, actualizar_estado_carga, escribir_fila, escribir_multiples_filas, obtener_valores_columna, limpiar_nombre, subir_archivo, ID_DRIVE_RAIZ, H_GENERAL, H_DETALLE, H_PROV)

st.set_page_config(page_title="SIMA ERP | Auditoría", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255,75,75,0.8); }
    .stAlert { padding: 0.5rem; }
</style>
""", unsafe_allow_html=True)

try: H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except: H_PENDIENTES = "PENDIENTES"

EMPRESAS_GRUPO = ["SIMA S.A.", "SIMA LOGISTICA SRL", "SIMA SERVICIOS", "SIMA AGRO"]
MAPEO_CUITS_SIMA = {"30111111111": "SIMA S.A.", "30222222222": "SIMA LOGISTICA SRL", "30333333333": "SIMA SERVICIOS", "30444444444": "SIMA AGRO"}
CATEGORIAS_GASTO = ["BATERIAS", "CHAP PINT", "DOCUMENTACION", "EXTINTORES", "FILTROS Y FLUIDOS", "GOMERIA", "MANTENIMIENTO CORRECTIVO", "MANTENIMIENTO PREVENTIVO", "NEUMATICOS", "PLOTEO", "RASTREO GPS", "REPUESTOS", "VARIOS", "VTV", "PEAJE", "LAVADO", "ESTACIONAMIENTO", "CAJA CHICA S.F."]

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

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

def safe_float(valor, por_defecto=0.0):
    try:
        if valor is None or str(valor).strip().lower() == "none" or str(valor).strip() == "": return por_defecto
        return float(valor)
    except: return por_defecto

st.markdown("## ⚖️ Módulo de Auditoría Humana")
st.divider()

with st.spinner("Buscando facturas..."):
    datos_cola = leer_hoja_completa(H_PENDIENTES)

para_auditar = [f for f in datos_cola[1:] if len(f) >= 7 and (f[6] == "PARA_AUDITAR" or f[6].startswith("ERROR_IA"))]

if not para_auditar:
    st.success("🎉 No hay facturas pendientes de auditoría.")
else:
    opciones = {}
    for fila in para_auditar:
        prov = "Desconocido"
        if len(fila) >= 9 and fila[8]:
            try: prov = json.loads(fila[8]).get("razon_social", "Desconocido")
            except: pass
        estado_ico = "⚠️ ERROR" if fila[6].startswith("ERROR") else "✅"
        opciones[fila[0]] = f"{estado_ico} | 🏢 {str(prov)[:20]}... | 📄 {fila[2]} | 📅 {fila[1]}"
        
    carga_seleccionada = st.selectbox("Seleccionar comprobante a auditar:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
    
    fila_actual = next(f for f in para_auditar if f[0] == carga_seleccionada)
    id_carga, link_fac, estado_actual = fila_actual[0], fila_actual[4], fila_actual[6]
    json_crudo = fila_actual[8] if len(fila_actual) >= 9 else ""
    
    datos_ia = {}
    if json_crudo:
        try: datos_ia = json.loads(json_crudo)
        except: pass

    st.divider()
    col_pdf, col_datos = st.columns([1, 1], gap="medium")
    
    with col_pdf:
        id_drive = extraer_id_drive(link_fac)
        if id_drive:
            url_preview = f"https://drive.google.com/file/d/{id_drive}/preview"
            st.markdown(f'<iframe src="{url_preview}" width="100%" height="900px" style="border: none; border-radius: 8px;"></iframe>', unsafe_allow_html=True)
        else:
            st.error("No se pudo obtener el PDF.")
    
    with col_datos:
        if estado_actual.startswith("ERROR_IA"):
            st.warning(f"⚠️ La IA no pudo procesarlo. Código: {estado_actual}. Cargá manual.")
        if datos_ia.get("ot_incluida_en_pdf", False):
            st.info("📌 **La IA detectó hojas de Orden de Trabajo adjuntas en este mismo documento.**")
            
        st.markdown("#### Datos del Proveedor")
        c1, c2 = st.columns(2)
        with c1: cuit = st.text_input("CUIT Proveedor", value=datos_ia.get("cuit_proveedor", ""))
        with c2: razon_social = st.text_input("Razón Social Proveedor", value=datos_ia.get("razon_social", ""))
        
        # 🌟 NUEVO: FEEDBACK DIRECTO PARA LA IA
        with st.expander("🤖 Enseñar a la IA sobre este proveedor (Opcional)"):
            st.caption("Si la IA se equivocó leyendo este documento, dejale una regla clara acá. La próxima vez que procese un archivo de este CUIT, tendrá en cuenta tu instrucción.")
            instruccion_ia = st.text_area("Ejemplo: 'El Nro de OT está siempre escrito a mano arriba a la derecha' o 'El subtotal tomalo del valor que dice Gravado 21%'.", value="", height=68)
        
        st.markdown("#### Empresa del Grupo Facturada")
        cuit_cli_extraido = str(datos_ia.get("cuit_cliente", "")).replace("-", "").strip()
        empresa_detectada = MAPEO_CUITS_SIMA.get(cuit_cli_extraido, "SIMA S.A.")
        empresa_sima = st.selectbox("Seleccionar Empresa:", options=EMPRESAS_GRUPO, index=EMPRESAS_GRUPO.index(empresa_detectada) if empresa_detectada in EMPRESAS_GRUPO else 0, label_visibility="collapsed")
        
        st.markdown("#### Datos del Comprobante")
        c3, c4, c5 = st.columns(3)
        with c3: fecha = st.text_input("Fecha (DD/MM/YYYY)", value=datos_ia.get("fecha", ""))
        with c4: pv = st.text_input("Punto de Venta", value=str(datos_ia.get("punto_venta", "0")))
        with c5: num = st.text_input("Nro Factura", value=str(datos_ia.get("nro_factura", "0")))
        
        patente_ia = datos_ia.get("patente", "DPA") if datos_ia.get("patente") else "DPA"
        
        c6, c7 = st.columns(2)
        with c6: nro_ot = st.text_input("Nro OT (General)", value=datos_ia.get("nro_ot", ""))
        with c7: nueva_ot = st.file_uploader("📎 Adjuntar OT separada", type=["pdf", "png", "jpg", "jpeg"])
        
        items_precargados = datos_ia.get("items", [{"patente": patente_ia.upper(), "descripcion": "", "cantidad": 1, "precio_sin_impuestos": 0.0, "precio_con_impuestos": 0.0, "tipo_gasto": "VARIOS"}])
        for it in items_precargados:
            if "patente" not in it or not it["patente"]: it["patente"] = patente_ia.upper()
            if "precio_sin_impuestos" not in it: it["precio_sin_impuestos"] = safe_float(it.get("precio_unitario", 0.0))
            if "precio_con_impuestos" not in it: it["precio_con_impuestos"] = safe_float(it.get("precio_unitario", 0.0))
            if "tipo_gasto" not in it: it["tipo_gasto"] = "VARIOS"

        st.markdown("#### Ítems")
        items_editados = st.data_editor(
            items_precargados, num_rows="dynamic",
            column_config={"tipo_gasto": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS_GASTO, required=True, default="VARIOS")}
        )
        
        suma_neto, suma_total_con_imp = 0.0, 0.0
        for item in items_editados:
            desc = str(item.get("descripcion", "")).strip()
            if not desc or desc.lower() == "none": continue
            cant = safe_float(item.get("cantidad"), 1.0)
            suma_neto += cant * safe_float(item.get("precio_sin_impuestos"), 0.0)
            suma_total_con_imp += cant * safe_float(item.get("precio_con_impuestos"), 0.0)
            
        c8, c9 = st.columns(2)
        with c8: subtotal = st.number_input("Subtotal (Neto)", value=float(datos_ia.get("subtotal", suma_neto)), step=100.0)
        with c9: total = st.number_input("Total (C/Impuestos)", value=float(datos_ia.get("total", suma_total_con_imp)), step=100.0)
        
        notas_proveedor = st.text_area("📝 Notas u Observaciones contables (Ej: Chequear retenciones, falta firma)", value="", height=68)
        
        st.write("---")
        
        b1, b2, b3 = st.columns(3)
        with b1: btn_aprobar = st.button("✅ Confirmar y Aprobar", type="primary", use_container_width=True)
        with b2: btn_reprocesar = st.button("🔄 IA leyó mal (Reprocesar)", type="secondary", use_container_width=True)
        with b3: btn_descartar = st.button("🗑️ Descartar", type="secondary", use_container_width=True)
        
        if btn_reprocesar:
            actualizar_estado_carga(H_PENDIENTES, id_carga, "PENDIENTE")
            st.toast("Enviado nuevamente a la cola del motor.", icon="🔄")
            time.sleep(1)
            st.rerun()

        if btn_aprobar:
            with st.spinner("Guardando..."):
                alias_prov = limpiar_nombre(razon_social)
                num_completo = f"{str(pv).zfill(5)}-{str(num).zfill(8)}"
                id_unico = f"{cuit}_{pv}_{num}"
                
                if nueva_ot:
                    link_nueva_ot = subir_archivo(f"{num_completo}_OT.pdf", asegurar_pdf(nueva_ot), ID_DRIVE_RAIZ, alias_prov)
                
                try: fecha_dt = datetime.strptime(fecha, "%d/%m/%Y"); mes_txt = f"{str(fecha_dt.month).zfill(2)}-{['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'][fecha_dt.month-1]}"; anio = fecha_dt.year
                except: mes_txt, anio = "00-IND", datetime.now().year

                filas_detalle = []
                patentes_usadas = set()
                
                for item in items_editados:
                    desc = str(item.get("descripcion", "")).strip()
                    if not desc or desc.lower() == "none": continue
                    cant = int(safe_float(item.get("cantidad"), 1.0))
                    precio_neto_u = safe_float(item.get("precio_sin_impuestos"), 0.0)
                    precio_total_u = safe_float(item.get("precio_con_impuestos"), 0.0)
                    tipo_gasto_final = str(item.get("tipo_gasto", "VARIOS")).strip().upper()
                    
                    pat_item = str(item.get("patente", patente_ia)).strip().upper()
                    if not pat_item or pat_item == "NONE": pat_item = "DPA"
                    patentes_usadas.add(pat_item)
                    
                    for _ in range(cant): 
                        filas_detalle.append([id_unico, anio, mes_txt, fecha, empresa_sima, alias_prov, razon_social, num_completo, nro_ot, pat_item, tipo_gasto_final, desc, 1, precio_neto_u, precio_total_u, f'=HYPERLINK("{link_fac}", "Ver PDF")'])
                
                patente_general_resumen = " / ".join(patentes_usadas) if patentes_usadas else "DPA"

                # Guardamos contabilidad
                escribir_fila(H_GENERAL, [id_unico, anio, mes_txt, fecha, empresa_sima, patente_general_resumen, alias_prov, razon_social, pv, num, num_completo, subtotal, total, f'=HYPERLINK("{link_fac}", "Ver PDF")', notas_proveedor])
                if filas_detalle: escribir_multiples_filas(H_DETALLE, filas_detalle)

                # Actualizamos Histórico Proveedores
                cuits_historico = obtener_valores_columna(H_PROV, 3)
                if str(cuit) not in cuits_historico: escribir_fila(H_PROV, [alias_prov, razon_social, cuit])

                # 🌟 GUARDAMOS LA REGLA PARA LA IA (SI SE ESCRIBIÓ ALGO)
                if instruccion_ia.strip() and cuit:
                    fecha_regla = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    escribir_fila("REGLAS_IA", [cuit, razon_social, instruccion_ia.strip(), fecha_regla])
                
                actualizar_estado_carga(H_PENDIENTES, id_carga, "APROBADA")
                st.success("✅ ¡Factura aprobada!")
                time.sleep(1)
                st.rerun()

        if btn_descartar:
            actualizar_estado_carga(H_PENDIENTES, id_carga, "DESCARTADO")
            st.toast("Comprobante descartado.", icon="🗑️")
            time.sleep(1)
            st.rerun()
