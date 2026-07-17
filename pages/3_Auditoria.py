import streamlit as st
import json
import re
import io
import time
from PIL import Image, ImageOps
from datetime import datetime
from utils.conexiones import (leer_hoja_completa, descargar_archivo, actualizar_estado_carga, escribir_fila, escribir_multiples_filas, obtener_valores_columna, limpiar_nombre, subir_archivo, ID_DRIVE_RAIZ, H_GENERAL, H_DETALLE, H_PROV)

st.set_page_config(page_title="SIMA ERP | Auditoría", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")

st.markdown("#### Datos del Proveedor y Destinatario")
        c1, c2 = st.columns(2)
        with c1: cuit = st.text_input("CUIT Proveedor", value=datos_ia.get("cuit_proveedor", ""))
        with c2: razon_social = st.text_input("Razón Social Proveedor", value=datos_ia.get("razon_social", ""))
        
        # Gerencia histórica y Destinatario
        c3, c4 = st.columns(2)
        with c3:
            empresa_facturada = st.text_input("Empresa Receptora (SIMA, CAJA CHICA, etc.)", value=str(datos_ia.get("razon_social_cliente", "")).upper())
        with c4:
            # Esta es la "foto" histórica a la que pertenecía el vehículo al momento del gasto
            gerencia_asignada = st.text_input("Gerencia Asignada (Ej: EDENOR, SEGURIDAD)", value="")

        with st.expander("🤖 Enseñar a la IA sobre este proveedor"):
            instruccion_ia = st.text_area("Instrucción futura para la IA:", value="", height=68)
        
        st.markdown("#### Datos del Comprobante")
        c5, c6, c7 = st.columns(3)
        with c5: fecha = st.text_input("Fecha (DD/MM/YYYY)", value=datos_ia.get("fecha", ""))
        with c6: pv = st.text_input("Punto de Venta", value=str(datos_ia.get("punto_venta", "0")))
        with c7: num = st.text_input("Nro Factura", value=str(datos_ia.get("nro_factura", "0")))
        
        patente_ia = datos_ia.get("patente", "DPA") if datos_ia.get("patente") else "DPA"
        
        c8, c9 = st.columns(2)
        with c8: nro_ot = st.text_input("Nro OT (General)", value=datos_ia.get("nro_ot", ""))
        with c9: nueva_ot = st.file_uploader("📎 Adjuntar OT separada", type=["pdf", "png", "jpg", "jpeg"])
        
        items_precargados = datos_ia.get("items", [{"patente": patente_ia.upper(), "descripcion": "", "cantidad": 1, "precio_sin_impuestos": 0.0, "precio_con_impuestos": 0.0, "tipo_gasto": "VARIOS"}])
        for it in items_precargados:
            if "patente" not in it or not it["patente"]: it["patente"] = patente_ia.upper()
            if "precio_sin_impuestos" not in it: it["precio_sin_impuestos"] = safe_float(it.get("precio_unitario", 0.0))
            if "precio_con_impuestos" not in it: it["precio_con_impuestos"] = safe_float(it.get("precio_unitario", 0.0))
            if "tipo_gasto" not in it: it["tipo_gasto"] = "VARIOS"

        st.markdown("#### Ítems (Cálculo en vivo)")
        # Ajustamos el ancho de las columnas para evitar el scroll horizontal
        items_editados = st.data_editor(
            items_precargados, 
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "tipo_gasto": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS_GASTO, required=True, default="VARIOS"),
                "descripcion": st.column_config.TextColumn("Descripción", width="large")
            }
        )
        
        suma_neto, suma_total_con_imp = 0.0, 0.0
        for item in items_editados:
            desc = str(item.get("descripcion", "")).strip()
            if not desc or desc.lower() == "none": continue
            cant = safe_float(item.get("cantidad"), 1.0)
            suma_neto += cant * safe_float(item.get("precio_sin_impuestos"), 0.0)
            suma_total_con_imp += cant * safe_float(item.get("precio_con_impuestos"), 0.0)
            
        st.success(f"🧮 **Subtotal calculado:** ${suma_neto:,.2f} | **Total calculado:** ${suma_total_con_imp:,.2f}")
            
        st.markdown("#### Totales Definitivos (Se actualizan solos)")
        c10, c11 = st.columns(2)
        with c10: subtotal = st.number_input("Subtotal (Neto)", value=float(suma_neto), step=100.0, key=f"sub_{suma_neto}")
        with c11: total = st.number_input("Total (C/Impuestos)", value=float(suma_total_con_imp), step=100.0, key=f"tot_{suma_total_con_imp}")
        
        notas_proveedor = st.text_area("📝 Notas u Observaciones contables", value="", height=68)
        
        st.write("---")
        
        b1, b2, b3 = st.columns(3)
        with b1: btn_aprobar = st.button("✅ Confirmar y Aprobar", type="primary", use_container_width=True)
        with b2: btn_reprocesar = st.button("🔄 IA leyó mal (Reprocesar)", type="secondary", use_container_width=True)
        with b3: btn_descartar = st.button("🗑️ Descartar", type="secondary", use_container_width=True)
        
        if btn_reprocesar:
            actualizar_estado_carga(H_PENDIENTES, id_carga, "PENDIENTE")
            st.rerun()

        if btn_aprobar:
            with st.spinner("Guardando en la base de datos..."):
                # 🌟 FORZAMOS MAYÚSCULAS EN TODAS LAS VARIABLES DE TEXTO
                alias_prov = limpiar_nombre(str(razon_social).upper())
                cuit_f = str(cuit).upper()
                razon_social_f = str(razon_social).upper()
                empresa_facturada_f = str(empresa_facturada).upper()
                gerencia_asignada_f = str(gerencia_asignada).upper()
                nro_ot_f = str(nro_ot).upper()
                notas_f = str(notas_proveedor).upper()
                instruccion_ia_f = str(instruccion_ia).upper()

                num_completo = f"{str(pv).zfill(5)}-{str(num).zfill(8)}"
                id_unico = f"{cuit_f}_{pv}_{num}"
                
                if nueva_ot: link_nueva_ot = subir_archivo(f"{num_completo}_OT.pdf", asegurar_pdf(nueva_ot), ID_DRIVE_RAIZ, alias_prov)
                
                try: fecha_dt = datetime.strptime(fecha, "%d/%m/%Y"); mes_txt = f"{str(fecha_dt.month).zfill(2)}-{['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'][fecha_dt.month-1]}"; anio = fecha_dt.year
                except: mes_txt, anio = "00-IND", datetime.now().year

                filas_detalle = []
                patentes_usadas = set()
                
                for item in items_editados:
                    desc = str(item.get("descripcion", "")).strip().upper() # MAYUSCULA
                    if not desc or desc == "NONE": continue
                    cant = int(safe_float(item.get("cantidad"), 1.0))
                    precio_neto_u = safe_float(item.get("precio_sin_impuestos"), 0.0)
                    precio_total_u = safe_float(item.get("precio_con_impuestos"), 0.0)
                    tipo_gasto_final = str(item.get("tipo_gasto", "VARIOS")).strip().upper()
                    
                    pat_item = str(item.get("patente", patente_ia)).strip().upper()
                    if not pat_item or pat_item == "NONE": pat_item = "DPA"
                    patentes_usadas.add(pat_item)
                    
                    for _ in range(cant): 
                        # 🌟 AHORA GUARDAMOS LA GERENCIA EN EL DETALLE TAMBIÉN
                        filas_detalle.append([id_unico, anio, mes_txt, fecha, empresa_facturada_f, alias_prov, razon_social_f, num_completo, nro_ot_f, pat_item, tipo_gasto_final, desc, 1, precio_neto_u, precio_total_u, f'=HYPERLINK("{link_fac}", "Ver PDF")', gerencia_asignada_f])
                
                patente_general_resumen = " / ".join(patentes_usadas) if patentes_usadas else "DPA"

                # Guardamos contabilidad (Hemos quitado los time.sleep para ganar 3 segundos)
                escribir_fila(H_GENERAL, [id_unico, anio, mes_txt, fecha, empresa_facturada_f, patente_general_resumen, alias_prov, razon_social_f, pv, num, num_completo, subtotal, total, f'=HYPERLINK("{link_fac}", "Ver PDF")', notas_f, gerencia_asignada_f])
                
                if filas_detalle: escribir_multiples_filas(H_DETALLE, filas_detalle)

                cuits_historico = obtener_valores_columna(H_PROV, 3)
                if cuit_f not in cuits_historico: escribir_fila(H_PROV, [alias_prov, razon_social_f, cuit_f])
                
                if instruccion_ia_f.strip() and cuit_f:
                    escribir_fila("REGLAS_IA", [cuit_f, razon_social_f, instruccion_ia_f, datetime.now().strftime("%d/%m/%Y %H:%M:%S")])
                
                actualizar_estado_carga(H_PENDIENTES, id_carga, "APROBADA")
                st.rerun()

        if btn_descartar:
            actualizar_estado_carga(H_PENDIENTES, id_carga, "DESCARTADO")
            st.rerun()
# FIRMA DPA
st.markdown('<div style="text-align: right; font-size: 12px; color: gray; margin-top: 50px;">Software DPA | Creado por Serrano Cristian</div>', unsafe_allow_html=True)
