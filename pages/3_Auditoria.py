import streamlit as st
import json
import re
import io
from PIL import Image, ImageOps
from datetime import datetime
from utils.conexiones import (leer_hoja_completa, actualizar_estado_carga, escribir_fila, escribir_multiples_filas, obtener_valores_columna, limpiar_nombre, subir_archivo, ID_DRIVE_RAIZ, H_GENERAL, H_DETALLE)

st.set_page_config(page_title="DPA | Auditoría", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

# CSS Local y Marca de Agua
st.markdown('''
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    [data-testid="collapsedControl"] { border: 2px solid #ff4b4b; border-radius: 50%; box-shadow: 0px 0px 5px rgba(255,75,75,0.8); }
    .stAlert { padding: 0.5rem; }
    ::-webkit-scrollbar { width: 10px !important; height: 10px !important; background-color: #f1f1f1 !important; }
    ::-webkit-scrollbar-thumb { background-color: #c1c1c1 !important; border-radius: 5px !important; }
    .firma-flotante { position: fixed; bottom: 8px; right: 15px; font-size: 10.5px; color: rgba(128, 128, 128, 0.6); z-index: 99999; pointer-events: none; font-family: monospace; }
</style>
<div class="firma-flotante">Software DPA | Creado por Serrano Cristian</div>
''', unsafe_allow_html=True)

try: H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except: H_PENDIENTES = "PENDIENTES"
try: H_PROV = st.secrets.get("HOJA_PROVEEDORES", "PROVEEDORES")
except: H_PROV = "PROVEEDORES"

CATEGORIAS_GASTO = ["BATERIAS", "CHAP PINT", "DOCUMENTACION", "EXTINTORES", "FILTROS Y FLUIDOS", "GOMERIA", "MANTENIMIENTO CORRECTIVO", "MANTENIMIENTO PREVENTIVO", "NEUMATICOS", "PLOTEO", "RASTREO GPS", "REPUESTOS", "VARIOS", "VTV", "PEAJE", "LAVADO", "ESTACIONAMIENTO", "CAJA CHICA S.F."]

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

def safe_float(valor, por_defecto=0.0):
    try:
        if valor is None or str(valor).strip().lower() == "none" or str(valor).strip() == "": return por_defecto
        return float(valor)
    except: return por_defecto

# --- CARGAR BASES MAESTRAS ---
try: datos_flota = leer_hoja_completa("FLOTA")
except: datos_flota = []
dict_flota = {}
for f in datos_flota[1:]:
    if len(f) >= 4: dict_flota[str(f[0]).strip().upper()] = {"cuit_empresa": str(f[2]).strip(), "gerencia": str(f[3]).strip().upper()}

try: datos_receptores = leer_hoja_completa("RECEPTORES")
except: datos_receptores = []
dict_receptores = {str(r[0]).strip(): str(r[2]).strip().upper() for r in datos_receptores[1:] if len(r) >= 3}

try: datos_gerencias = leer_hoja_completa("GERENCIAS")
except: datos_gerencias = []
lista_gerencias = [str(g[0]).strip().upper() for g in datos_gerencias[1:] if len(g) > 0 and str(g[1]).strip().upper() != "INACTIVO"]
if not lista_gerencias: lista_gerencias = ["DPA"]

st.markdown("## ⚖️ Módulo de Auditoría Humana")
st.divider()

with st.spinner("Buscando facturas..."):
    datos_cola = leer_hoja_completa(H_PENDIENTES)

para_auditar = [f for f in datos_cola[1:] if len(f) >= 7 and (f[6] == "PARA_AUDITAR" or f[6].startswith("ERROR_IA") or f[6] == "CARGA_MANUAL_DIRECTA")]

if not para_auditar:
    st.success("🎉 No hay facturas pendientes de auditoría.")
else:
    opciones = {}
    for fila in para_auditar:
        prov = "Desconocido"
        if len(fila) >= 9 and fila[8]:
            try: prov = json.loads(fila[8]).get("razon_social", "Desconocido")
            except: pass
        estado_ico = "⚠️ ERROR" if fila[6].startswith("ERROR") else "✍️ MANUAL" if fila[6] == "CARGA_MANUAL_DIRECTA" else "✅"
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
        else: st.error("No se pudo obtener el PDF.")
    
    with col_datos:
        if estado_actual.startswith("ERROR_IA"): st.warning(f"⚠️ IA falló ({estado_actual}). Cargá manual.")
        elif estado_actual == "CARGA_MANUAL_DIRECTA": st.info("✍️ Modo de Ingreso Manual Activo.")
            
        if st.button("🔄 Restablecer Datos Originales", help="Borra tus ediciones."): st.rerun()
            
        st.markdown("#### Datos del Proveedor")
        c1, c2 = st.columns(2)
        with c1: cuit = st.text_input("CUIT Proveedor (Solo Números)", value=str(datos_ia.get("cuit_proveedor", "")).replace("-", ""))
        with c2: razon_social = st.text_input("Razón Social Proveedor", value=datos_ia.get("razon_social", ""))
        
        with st.expander("🤖 Enseñar a la IA sobre este proveedor"):
            instruccion_ia = st.text_area("Instrucción futura para la IA:", value="", height=68)
            
        st.markdown("#### Destinatario de Factura")
        cuit_cli_leido = str(datos_ia.get("cuit_cliente", "")).replace("-", "").strip()
        c3, c4 = st.columns(2)
        with c3: cuit_receptor = st.text_input("CUIT Receptor", value=cuit_cli_leido)
        with c4:
            alias_conocido = dict_receptores.get(cuit_receptor, "")
            alias_receptor = st.text_input("Alias Receptor", value=alias_conocido, help="Si es nuevo, escribí cómo llamarlo.")
        
        st.markdown("#### Datos del Comprobante")
        c5, c6, c7 = st.columns(3)
        with c5: fecha = st.text_input("Fecha (DD/MM/YYYY)", value=datos_ia.get("fecha", ""))
        with c6: pv = st.text_input("Punto de Venta", value=str(datos_ia.get("punto_venta", "0")))
        with c7: num = st.text_input("Nro Factura", value=str(datos_ia.get("nro_factura", "0")))
        
        c8, c9 = st.columns(2)
        with c8: nro_ot = st.text_input("Nro OT (General)", value=datos_ia.get("nro_ot", ""))
        with c9: st.write("El Link al PDF general se guarda automáticamente.")

        # --- ITEMS Y CRUCE CON FLOTA ---
        st.markdown("#### Ítems y Asignación por Patente")
        items_precargados = datos_ia.get("items", [])
        if not items_precargados: items_precargados = [{"patente": "", "descripcion": "", "cantidad": 1, "precio_sin_impuestos": 0.0, "precio_con_impuestos": 0.0, "tipo_gasto": "VARIOS"}]
        for it in items_precargados:
            if "precio_sin_impuestos" not in it: it["precio_sin_impuestos"] = safe_float(it.get("precio_unitario", 0.0))
            if "precio_con_impuestos" not in it: it["precio_con_impuestos"] = safe_float(it.get("precio_unitario", 0.0))
            if "tipo_gasto" not in it: it["tipo_gasto"] = "VARIOS"

        items_editados = st.data_editor(
            items_precargados, num_rows="dynamic", use_container_width=True,
            column_config={
                "tipo_gasto": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS_GASTO, required=True, default="VARIOS"),
                "descripcion": st.column_config.TextColumn("Descripción", width="large")
            }
        )
        
        suma_neto, suma_total_con_imp = 0.0, 0.0
        patentes_vistas = set()
        patente_no_registrada = False
        
        for item in items_editados:
            desc = str(item.get("descripcion", "")).strip()
            pat = str(item.get("patente", "")).strip().upper()
            if pat and pat != "NONE": 
                patentes_vistas.add(pat)
                if pat not in dict_flota: patente_no_registrada = True
            
            if not desc or desc.lower() == "none": continue
            cant = safe_float(item.get("cantidad"), 1.0)
            suma_neto += cant * safe_float(item.get("precio_sin_impuestos"), 0.0)
            suma_total_con_imp += cant * safe_float(item.get("precio_con_impuestos"), 0.0)
            
        if patente_no_registrada:
            st.error("⚠️ Atención: Una de las patentes ingresadas NO existe en la base de datos FLOTA. Deberás registrarla en la página 'Gestión de Flota' para que los KPIs sean precisos.")
            
        st.success(f"🧮 **Subtotal calculado:** ${suma_neto:,.2f} | **Total calculado:** ${suma_total_con_imp:,.2f}")
            
        c10, c11 = st.columns(2)
        with c10: subtotal = st.number_input("Subtotal (Neto)", value=float(suma_neto), step=100.0, key=f"sub_{suma_neto}")
        with c11: total = st.number_input("Total (C/Impuestos)", value=float(suma_total_con_imp), step=100.0, key=f"tot_{suma_total_con_imp}")
        
        notas_proveedor = st.text_area("📝 Notas u Observaciones administrativas", value="", height=68)
        
        st.write("---")
        b1, b2, b3 = st.columns(3)
        with b1: btn_aprobar = st.button("✅ Confirmar y Aprobar", type="primary", use_container_width=True)
        with b2: btn_reprocesar = st.button("🔄 IA leyó mal (Reprocesar)", type="secondary", use_container_width=True)
        with b3: btn_descartar = st.button("🗑️ Descartar", type="secondary", use_container_width=True)
        
        if btn_reprocesar:
            actualizar_estado_carga(H_PENDIENTES, id_carga, "PENDIENTE")
            st.rerun()

        if btn_aprobar:
            with st.spinner("Guardando en bases maestras..."):
                cuit_f = str(cuit).strip().replace("-", "")
                razon_social_f = str(razon_social).strip().upper()
                alias_prov = limpiar_nombre(razon_social_f)
                
                alias_receptor_f = str(alias_receptor).strip().upper() if str(alias_receptor).strip() else "DESCONOCIDO"
                cuit_receptor_f = str(cuit_receptor).strip().replace("-", "")
                
                nro_ot_f = str(nro_ot).strip().upper()
                notas_f = str(notas_proveedor).strip().upper()
                instruccion_ia_f = str(instruccion_ia).strip().upper()

                num_completo = f"{str(pv).zfill(5)}-{str(num).zfill(8)}"
                id_unico = f"{cuit_f}_{pv}_{num}"
                
                try: 
                    fecha_dt = datetime.strptime(fecha, "%d/%m/%Y")
                    mes_txt = f"{str(fecha_dt.month).zfill(2)}-{['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'][fecha_dt.month-1]}"
                    anio = fecha_dt.year
                except: mes_txt, anio = "00-IND", datetime.now().year

                filas_detalle = []
                
                for item in items_editados:
                    desc = str(item.get("descripcion", "")).strip().upper()
                    if not desc or desc == "NONE": continue
                    cant = int(safe_float(item.get("cantidad"), 1.0))
                    precio_neto_u = safe_float(item.get("precio_sin_impuestos"), 0.0)
                    precio_total_u = safe_float(item.get("precio_con_impuestos"), 0.0)
                    tipo_gasto_final = str(item.get("tipo_gasto", "VARIOS")).strip().upper()
                    
                    pat_item = str(item.get("patente", "")).strip().upper()
                    if not pat_item or pat_item == "NONE": pat_item = "DPA"
                    
                    # MAGIA RELACIONAL: Extraer gerencia y empresa real de cada patente
                    info_patente = dict_flota.get(pat_item, {"cuit_empresa": "S/D", "gerencia": "DPA"})
                    
                    for _ in range(cant): 
                        # DETALLE: ID Unico, Año, Mes, Fecha, CUIT Receptor, Patente, CUIT Empresa Vehículo, Gerencia Gasto, CUIT Prov, Razon Social Prov, Nro Completo, Nro OT, Cat, Desc, Cant, P.Neto, P.Total
                        filas_detalle.append([
                            id_unico, anio, mes_txt, fecha, cuit_receptor_f, pat_item, 
                            info_patente["cuit_empresa"], info_patente["gerencia"], cuit_f, razon_social_f, 
                            num_completo, nro_ot_f, tipo_gasto_final, desc, 1, precio_neto_u, precio_total_u
                        ])
                
                patente_general_resumen = " / ".join(list(patentes_vistas)) if patentes_vistas else "DPA"

                # GENERAL: ID Unico, Año, Mes, Fecha, CUIT Receptor, Patentes Involucradas, CUIT Prov, Razon Social, Nro Completo, Subtotal, Total, Link, Notas
                escribir_fila(H_GENERAL, [id_unico, anio, mes_txt, fecha, cuit_receptor_f, patente_general_resumen, cuit_f, razon_social_f, num_completo, subtotal, total, link_fac, notas_f])
                
                if filas_detalle: escribir_multiples_filas(H_DETALLE, filas_detalle)

                cuits_historico = obtener_valores_columna(H_PROV, 3)
                if cuit_f not in cuits_historico: escribir_fila(H_PROV, [alias_prov, razon_social_f, cuit_f])
                if instruccion_ia_f.strip() and cuit_f: escribir_fila("REGLAS_IA", [cuit_f, razon_social_f, instruccion_ia_f, datetime.now().strftime("%d/%m/%Y %H:%M:%S")])
                if cuit_receptor_f and cuit_receptor_f not in dict_receptores: escribir_fila("RECEPTORES", [cuit_receptor_f, razon_social_f, alias_receptor_f, datetime.now().strftime("%d/%m/%Y")])
                
                actualizar_estado_carga(H_PENDIENTES, id_carga, "APROBADA")
                st.rerun()

        if btn_descartar:
            actualizar_estado_carga(H_PENDIENTES, id_carga, "DESCARTADO")
            st.rerun()
