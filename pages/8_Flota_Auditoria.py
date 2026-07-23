import streamlit as st
import pandas as pd
import json
from utils.conexiones import (
    leer_hoja_completa, 
    mover_y_renombrar_archivo, 
    actualizar_fila, 
    eliminar_fila,
    extraer_id_drive
)

st.set_page_config(page_title="Auditoría de Flota", page_icon="⚖️", layout="wide")

HOJA_PENDIENTES = st.secrets.get("HOJA_PENDIENTES_FLOTA", "PENDIENTES_FLOTA")
HOJA_FLOTA = st.secrets.get("HOJA_FLOTA", "FLOTA")
MOTOR_IA = st.secrets.get("MODELO_PRIMARIO", "Gemini")

CARPETA_CERTIFICADOS = st.secrets.get("ID_CARPETA_CERTIFICADOS", "ID_SIMULADO")
CARPETA_POLIZAS_MADRE = st.secrets.get("ID_CARPETA_POLIZAS_MADRE", "ID_SIMULADO")

st.markdown('''
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 98%; }
    ::-webkit-scrollbar { width: 8px !important; height: 8px !important; }
    ::-webkit-scrollbar-thumb { background-color: #c1c1c1 !important; border-radius: 4px !important; }
</style>
''', unsafe_allow_html=True)

st.title("⚖️ Auditoría de Documentos (Flota)")
st.markdown(f"**Bandeja:** `{HOJA_PENDIENTES}` | Filtrá, previsualizá y aprobá los documentos.")
st.divider()

with st.spinner("Buscando documentos procesados en la base de datos..."):
    try:
        datos_cola = leer_hoja_completa(HOJA_PENDIENTES)
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        st.stop()

lote_auditar = []
for fila in datos_cola[1:]:
    if len(fila) > 8 and str(fila[6]).strip().upper() == "PROCESADO":
        try:
            datos_ia = json.loads(fila[8])
            lote_auditar.append({
                "ID_CARGA": fila[0],
                "PATENTE": datos_ia.get("patente", "N/A").upper(),
                "TIPO_DOC": datos_ia.get("tipo_sugerido", fila[7]).upper(),
                "VENCIMIENTO": datos_ia.get("vencimiento", "S/D"), 
                "LINK_TEMP": fila[4],
                "LINK_MADRE": fila[5] if len(fila) > 5 else "N/A"
            })
        except Exception:
            pass

if not lote_auditar:
    st.info("✅ Bandeja limpia. No hay lotes pendientes de auditoría en este momento.")
    st.stop()

df_lote = pd.DataFrame(lote_auditar)

# 🌟 LAYOUT EN 3 COLUMNAS: Lista (30%) - Visor (45%) - Auditoría (25%)
col_lista, col_visor, col_auditoria = st.columns([1.2, 1.8, 1.0], gap="large")

with col_lista:
    st.subheader("📋 Lote Pendiente")
    st.caption("Cíclic para seleccionar. Shift/Ctrl para múltiples.")
    
    # Tabla nativa con selección de filas activada
    evento = st.dataframe(
        df_lote[["PATENTE", "TIPO_DOC", "VENCIMIENTO"]],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row"
    )
    
    seleccionados_idx = evento.selection.rows
    cant_sel = len(seleccionados_idx)

with col_visor:
    st.subheader("👁️ Visor de Documento")
    if cant_sel > 0:
        idx_mostrar = seleccionados_idx[-1] # Muestra siempre el último seleccionado
        link_temp_visor = df_lote.at[idx_mostrar, "LINK_TEMP"]
        id_drive_visor = extraer_id_drive(link_temp_visor)
        
        if id_drive_visor:
            url_visor = f"https://drive.google.com/file/d/{id_drive_visor}/preview"
            st.components.v1.iframe(url_visor, height=650)
        else:
            st.warning("Link de Drive inválido para la vista previa.")
    else:
        st.info("👈 Seleccioná un documento de la lista para previsualizarlo aquí.")

with col_auditoria:
    st.subheader("🛠️ Mesa de Auditoría")
    
    if cant_sel == 0:
        st.warning("Esperando selección...")
        
    elif cant_sel == 1:
        st.markdown("**Control Individual**")
        st.write("Si la IA cometió un error, podés corregir los datos antes de aprobar:")
        
        idx = seleccionados_idx[0]
        id_carga_actual = df_lote.at[idx, "ID_CARGA"]
        link_temp_actual = df_lote.at[idx, "LINK_TEMP"]
        
        # Formularios para corrección manual
        patente_corregida = st.text_input("Patente", value=df_lote.at[idx, "PATENTE"]).strip().upper()
        
        opciones_tipo = ["CERTIFICADO_SEGURO", "TITULO", "CEDULA_VERDE", "VTV", "POLIZA_MADRE"]
        tipo_actual = df_lote.at[idx, "TIPO_DOC"]
        idx_tipo = opciones_tipo.index(tipo_actual) if tipo_actual in opciones_tipo else 0
        tipo_corregido = st.selectbox("Tipo de Documento", opciones_tipo, index=idx_tipo)
        
        st.write("")
        if st.button("✅ Aprobar Archivo", type="primary", use_container_width=True):
            with st.spinner("Guardando..."):
                try:
                    nuevo_nombre = f"{patente_corregida}_{tipo_corregido}.pdf"
                    id_drive_temp = extraer_id_drive(link_temp_actual)
                    link_definitivo = mover_y_renombrar_archivo(id_drive_temp, CARPETA_CERTIFICADOS, nuevo_nombre)
                    
                    columna_destino = "LINK_CERTIFICADO_SEGURO"
                    if tipo_corregido == "TITULO": columna_destino = "LINK_TITULO"
                    elif tipo_corregido == "VTV": columna_destino = "LINK_VTV"
                    elif tipo_corregido == "CEDULA_VERDE": columna_destino = "LINK_CEDULA"
                        
                    actualizar_fila(HOJA_FLOTA, "PATENTE", patente_corregida, {columna_destino: link_definitivo})
                    eliminar_fila(HOJA_PENDIENTES, id_carga_actual)
                    
                    st.success("¡Aprobado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        if st.button("🗑️ Descartar / Borrar", use_container_width=True):
            eliminar_fila(HOJA_PENDIENTES, id_carga_actual)
            st.rerun()

    else:
        st.markdown("**Modo Lote (Múltiple)**")
        st.info(f"Vas a procesar **{cant_sel} documentos** al mismo tiempo. Se usarán las patentes detectadas por la IA.")
        
        if st.button(f"🚀 Aprobar Lote ({cant_sel})", type="primary", use_container_width=True):
            with st.status(f"Procesando {cant_sel} archivos...", expanded=True) as status:
                exitos = 0
                for idx in seleccionados_idx:
                    id_carga = df_lote.at[idx, "ID_CARGA"]
                    patente = df_lote.at[idx, "PATENTE"]
                    tipo_doc = df_lote.at[idx, "TIPO_DOC"]
                    link_temp = df_lote.at[idx, "LINK_TEMP"]
                    id_drive_temp = extraer_id_drive(link_temp)
                    
                    status.write(f"🔄 Moviendo {patente}...")
                    try:
                        nuevo_nombre = f"{patente}_{tipo_doc}.pdf"
                        link_definitivo = mover_y_renombrar_archivo(id_drive_temp, CARPETA_CERTIFICADOS, nuevo_nombre)
                        
                        columna_destino = "LINK_CERTIFICADO_SEGURO"
                        if tipo_doc == "TITULO": columna_destino = "LINK_TITULO"
                        elif tipo_doc == "VTV": columna_destino = "LINK_VTV"
                        elif tipo_doc == "CEDULA_VERDE": columna_destino = "LINK_CEDULA"
                            
                        actualizar_fila(HOJA_FLOTA, "PATENTE", patente, {columna_destino: link_definitivo})
                        eliminar_fila(HOJA_PENDIENTES, id_carga)
                        exitos += 1
                    except Exception as e:
                        status.write(f"❌ Error con {patente}: {str(e)}")
                
                status.update(label=f"¡Completado! ({exitos}/{cant_sel})", state="complete")
            if exitos > 0:
                st.rerun()

    st.divider()
    
    # Botón Póliza Madre (Usa el primer seleccionado, o el primer registro si no hay selección)
    idx_referencia = seleccionados_idx[0] if cant_sel > 0 else 0
    link_madre = df_lote.at[idx_referencia, "LINK_MADRE"]
    
    if link_madre and link_madre != "N/A" and "http" in link_madre:
        st.link_button("📑 Abrir Póliza Madre Original", url=link_madre, use_container_width=True)
    else:
        st.button("📑 Póliza Madre Original", disabled=True, use_container_width=True, help="El documento seleccionado no forma parte de un lote general.")
