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

st.title("⚖️ Auditoría de Documentos (Flota)")
st.markdown(f"**Motor activo:** `{MOTOR_IA}` | **Bandeja:** `{HOJA_PENDIENTES}`")
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
                "ARCHIVO_ORIGINAL": fila[2],
                "PATENTE": datos_ia.get("patente", "N/A"),
                "TIPO_DOC": datos_ia.get("tipo_sugerido", fila[7]),
                "VENCIMIENTO": datos_ia.get("vencimiento", "S/D"), 
                "LINK_TEMP": fila[4],
                "LINK_MADRE": fila[5] if len(fila) > 5 else "N/A", # Agregado para el botón
                "ESTADO_IA": "🟢 Éxito"
            })
        except Exception:
            pass

if not lote_auditar:
    st.info("✅ Bandeja limpia. No hay lotes pendientes de auditoría en este momento.")
    st.stop()

df_lote = pd.DataFrame(lote_auditar)
cantidad_docs = len(df_lote)

st.subheader(f"📦 Lote Pendiente ({cantidad_docs} documentos listos para revisión)")
st.caption("Revisá que las patentes extraídas coincidan con los PDFs antes de procesar el lote completo.")

df_editado = st.data_editor(
    df_lote[["PATENTE", "TIPO_DOC", "VENCIMIENTO", "ESTADO_IA", "ARCHIVO_ORIGINAL"]],
    use_container_width=True,
    hide_index=True,
    disabled=["ESTADO_IA", "ARCHIVO_ORIGINAL"] 
)

st.divider()

# Dividimos la pantalla: Controles a la izquierda, Visor a la derecha
col_controles, col_visor = st.columns([1, 1.5], gap="large")

with col_controles:
    st.subheader("🛠️ Acciones de Lote")
    
    if st.button(f"✅ Aprobar Lote Completo ({cantidad_docs} Archivos)", type="primary", use_container_width=True):
        with st.status("Procesando ruteo de archivos y actualizando bases...", expanded=True) as status:
            exitos = 0
            for idx, row in df_lote.iterrows():
                id_carga = row["ID_CARGA"]
                patente = str(df_editado.at[idx, "PATENTE"]).strip().upper()
                tipo_doc = str(df_editado.at[idx, "TIPO_DOC"]).strip().upper()
                link_temp = row["LINK_TEMP"]
                id_drive_temp = extraer_id_drive(link_temp)
                
                status.write(f"🔄 Tratando {patente} ({tipo_doc})...")
                
                try:
                    nuevo_nombre = f"{patente}_{tipo_doc}.pdf"
                    link_definitivo = mover_y_renombrar_archivo(id_drive_temp, CARPETA_CERTIFICADOS, nuevo_nombre)
                    
                    columna_destino_link = "LINK_CERTIFICADO_SEGURO"
                    if tipo_doc == "TITULO": columna_destino_link = "LINK_TITULO"
                    elif tipo_doc == "VTV": columna_destino_link = "LINK_VTV"
                    elif tipo_doc == "CEDULA_VERDE": columna_destino_link = "LINK_CEDULA"
                        
                    nuevos_datos = {columna_destino_link: link_definitivo}
                    actualizar_fila(HOJA_FLOTA, "PATENTE", patente, nuevos_datos)
                    eliminar_fila(HOJA_PENDIENTES, id_carga)
                    
                    exitos += 1
                except Exception as e:
                    status.write(f"❌ Error con {patente}: {str(e)}")
            
            status.update(label=f"¡Lote procesado! ({exitos}/{cantidad_docs} completados)", state="complete")
        
        if exitos > 0:
            st.success("¡Base de datos actualizada y archivos organizados en Google Drive!")
            st.rerun()

    if st.button("⚠️ Rechazar Lote", use_container_width=True):
        st.error("Funcionalidad de rechazo en desarrollo.")
        
    st.write("---")
    
    # Lógica corregida para el botón de Póliza Madre
    link_madre_ejemplo = df_lote["LINK_MADRE"].iloc[0]
    if link_madre_ejemplo and link_madre_ejemplo != "N/A" and "http" in link_madre_ejemplo:
        st.link_button("📑 Ver Póliza Madre Original", url=link_madre_ejemplo, use_container_width=True)
    else:
        st.button("📑 Póliza Madre no disponible", disabled=True, use_container_width=True)

with col_visor:
    st.subheader("👁️ Vista Previa del Certificado")
    
    # Selector para elegir qué certificado del lote previsualizar
    opciones_preview = {row["ID_CARGA"]: f"{row['PATENTE']} - {row['TIPO_DOC']}" for _, row in df_lote.iterrows()}
    seleccion_preview = st.selectbox("Seleccionar archivo para ver:", options=list(opciones_preview.keys()), format_func=lambda x: opciones_preview[x])
    
    if seleccion_preview:
        link_temp_visor = df_lote[df_lote["ID_CARGA"] == seleccion_preview].iloc[0]["LINK_TEMP"]
        id_drive_visor = extraer_id_drive(link_temp_visor)
        
        if id_drive_visor:
            url_visor = f"https://drive.google.com/file/d/{id_drive_visor}/preview"
            st.components.v1.iframe(url_visor, height=550)
        else:
            st.warning("No se puede generar la vista previa. Link inválido.")
