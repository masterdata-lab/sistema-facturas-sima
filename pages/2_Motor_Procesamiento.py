import streamlit as st
import re
import json
import time
from datetime import datetime
from google.genai import types

from utils.conexiones import (
    obtener_cliente_gemini, leer_hoja_completa, descargar_archivo,
    actualizar_estado_carga, unificar_documentos, H_REVIS
)

st.set_page_config(page_title="SIMA ERP | Motor IA", page_icon="⚙️", layout="wide")

try:
    H_PENDIENTES = st.secrets["HOJA_PENDIENTES"]
except:
    H_PENDIENTES = "PENDIENTES"

# 🌟 DEFINÍ LAS 4 EMPRESAS DE TU GRUPO Y SUS CUITS AQUÍ:
MAPEO_CUITS_SIMA = {
    "30111111111": "SIMA S.A.",
    "30222222222": "SIMA LOGISTICA SRL",
    "30333333333": "SIMA SERVICIOS",
    "30444444444": "SIMA AGRO"
}

CATEGORIAS_GASTO = [
    "BATERIAS", "CHAP PINT", "DOCUMENTACION", "EXTINTORES", "FILTROS Y FLUIDOS", 
    "GOMERIA", "MANTENIMIENTO CORRECTIVO", "MANTENIMIENTO PREVENTIVO", "NEUMATICOS", 
    "PLOTEO", "RASTREO GPS", "REPUESTOS", "VARIOS", "VTV", "PEAJE", "LAVADO", 
    "ESTACIONAMIENTO", "CAJA CHICA S.F."
]

ia_client = obtener_cliente_gemini()

def extraer_id_drive(url_drive):
    if not url_drive or url_drive == "N/A": return None
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url_drive)
    return match.group(1) if match else None

def procesar_con_ia_y_reintentos(pdf_bytes, modelo_elegido, max_reintentos=5):
    # 🌟 EL PROMPT AHORA EXTRAE EL CUIT DEL RECEPTOR (CLIENTE)
    prompt = f"""
    Extraé los datos de esta factura/OT y devolvelos en JSON estricto.
    Identificá quién es el CLIENTE (receptor de la factura) y extraé su CUIT (cuit_cliente).
    Para cada ítem, asigná obligatoriamente un "tipo_gasto" de esta lista: {CATEGORIAS_GASTO}.
    Calculá el precio unitario sin impuestos y con impuestos por ítem.
    Formato JSON:
    {{
        "cuit_proveedor": "0000", "razon_social": "Nombre", "cuit_cliente": "00000000000", "razon_social_cliente": "Nombre Sima",
        "fecha": "DD/MM/YYYY", "punto_venta": 0, "nro_factura": 0, "patente": "",
        "subtotal": 0.0, "total": 0.0, "nro_ot": "",
        "items": [
            {{
                "descripcion": "Texto", 
                "cantidad": 1.0, 
                "precio_sin_impuestos": 0.0, 
                "precio_con_impuestos": 0.0,
                "tipo_gasto": "VARIOS"
            }}
        ]
    }}
    """
    doc = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    
    for intento in range(max_reintentos):
        try:
            resp = ia_client.models.generate_content(
                model=modelo_elegido,
                contents=[doc, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(resp.text)
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "429" in error_str or "UNAVAILABLE" in error_str or "quota" in error_str.lower():
                if intento < max_reintentos - 1:
                    tiempo_espera = 30 if "429" in error_str or "quota" in error_str.lower() else 10
                    time.sleep(tiempo_espera)
                    continue
            raise e

st.markdown("## ⚙️ Motor de Procesamiento (IA)")
st.markdown("Este módulo lee la cola de archivos pendientes, procesa los datos con Gemini y los prepara para la auditoría.")
st.divider()

reprocesar_fallidos = st.checkbox("🔄 Intentar reprocesar también los archivos que dieron error anteriormente", value=True)
loop_activo = st.checkbox("🔄 **Modo Loop Automático (Procesar continuamente cada 5 minutos)**", value=False)

# Contenedor para el botón de disparo manual o el loop activo
disparar_motor = st.button("▶️ Iniciar Procesamiento", type="primary")

# Si el loop activo está tildado, disparamos el proceso directamente sin esperar clic
if loop_activo or disparar_motor:
    with st.spinner("Buscando facturas en la cola..."):
        datos_cola = leer_hoja_completa(H_PENDIENTES)
    
    pendientes = []
    for fila in datos_cola[1:]:
        if len(fila) >= 7:
            estado = fila[6]
            if estado == "PENDIENTE" or (reprocesar_fallidos and estado.startswith("ERROR_IA")):
                pendientes.append(fila)
    
    if not pendientes:
        st.info("✅ No hay facturas pendientes de procesamiento en este momento.")
    else:
        st.success(f"Encontradas {len(pendientes)} facturas para procesar. Iniciando motor...")
        
        barra_general = st.progress(0)
        status_text = st.empty()
        
        # 🌟 CONTADORES DE ESTADÍSTICAS
        exitosos = 0
        fallidos = 0
        
        for i, fila in enumerate(pendientes):
            id_carga = fila[0]
            nombre_fac = fila[2]
            link_fac = fila[4]
            link_ot = fila[5]
            motor_ia = fila[7] if len(fila) > 7 else 'gemini-3.5-flash'
            
            status_text.markdown(f"⏳ **Procesando {i+1}/{len(pendientes)}:** {nombre_fac}")
            
            try:
                id_fac = extraer_id_drive(link_fac)
                id_ot = extraer_id_drive(link_ot) if "N/A" not in link_ot else None
                
                fac_bytes = descargar_archivo(id_fac)
                ot_bytes = descargar_archivo(id_ot) if id_ot else None
                
                if not fac_bytes:
                    actualizar_estado_carga(H_PENDIENTES, id_carga, "ERROR: No se pudo descargar")
                    fallidos += 1
                    continue
                    
                pdf_final = unificar_documentos(fac_bytes, ot_bytes, False)
                datos_ia = procesar_con_ia_y_reintentos(pdf_final, motor_ia)
                
                json_string = json.dumps(datos_ia, ensure_ascii=False)
                actualizar_estado_carga(H_PENDIENTES, id_carga, "PARA_AUDITAR", json_string)
                exitosos += 1
                
            except Exception as e:
                actualizar_estado_carga(H_PENDIENTES, id_carga, f"ERROR_IA: {str(e)[:100]}")
                fallidos += 1
                
            barra_general.progress((i + 1) / len(pendientes))
            
        status_text.empty()
        
        # 🌟 PRESENTACIÓN DE RESULTADOS
        st.markdown("### 📊 Resumen del Procesamiento:")
        col_ok, col_err = st.columns(2)
        with col_ok:
            st.metric("✅ Procesados con éxito (Listos para auditar)", exitosos)
        with col_err:
            st.metric("⚠️ Con errores de API (Reintentables)", fallidos)
            
        if fallidos > 0:
            st.warning("💡 Los archivos con errores quedaron marcados para volver a intentarse en la próxima vuelta.")
        else:
            st.balloons()

    # 🌟 LÓGICA DEL LOOP DE 5 MINUTOS
    if loop_activo:
        st.write("---")
        segundos = 300
        reloj = st.empty()
        for i in range(segundos, 0, -1):
            reloj.info(f"⏱️ Modo Continuo Activo. Próximo escaneo automático en: **{i} segundos**... No cierres esta pestaña.")
            time.sleep(1)
        st.rerun()
