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

# Leemos la configuración global desde secrets
HOJA_PENDIENTES = st.secrets.get("HOJA_PENDIENTES_FLOTA", "PENDIENTES_FLOTA")
HOJA_FLOTA = st.secrets.get("HOJA_FLOTA", "FLOTA")
MOTOR_IA = st.secrets.get("MODELO_PRIMARIO", "Gemini")

# IDs de Carpetas Destino (Deberás agregarlos a tu secrets.toml)
CARPETA_CERTIFICADOS = st.secrets.get("ID_CARPETA_CERTIFICADOS", "ID_SIMULADO")
CARPETA_POLIZAS_MADRE = st.secrets.get("ID_CARPETA_POLIZAS_MADRE", "ID_SIMULADO")

st.title("⚖️ Auditoría de Documentos (Flota)")
st.markdown(f"**Motor activo:** `{MOTOR_IA}` | **Bandeja:** `{HOJA_PENDIENTES}`")
st.divider()

# 1. Leer datos reales de la hoja de pendientes
with st.spinner("Buscando documentos procesados en la base de datos..."):
    try:
        datos_cola = leer_hoja_completa(HOJA_PENDIENTES)
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        st.stop()

# Filtramos solo los que ya pasaron por la IA (PROCESADO) o que vienen de Carga Manual
# Columnas esperadas: [0]ID_CARGA, [1]FECHA, [2]ARCHIVO, [3]ORIGEN, [4]LINK, [5]LINK_MADRE, [6]ESTADO, [7]TIPO, [8]JSON
lote_auditar = []
for fila in datos_cola[1:]:
    if len(fila) > 8 and str(fila[6]).strip().upper() == "PROCESADO":
        try:
            datos_ia = json.loads(fila[8])
            # Construimos la fila para la visualización del usuario
            lote_auditar.append({
                "ID_CARGA": fila[0],
                "ARCHIVO_ORIGINAL": fila[2],
                "PATENTE": datos_ia.get("patente", "N/A"),
                "TIPO_DOC": datos_ia.get("tipo_sugerido", fila[7]),
                "VENCIMIENTO": datos_ia.get("vencimiento", "S/D"), # Placeholder si la IA no lo extrae aún
                "LINK_TEMP": fila[4],
                "ESTADO_IA": "🟢 Éxito"
            })
        except Exception:
            pass

if not lote_auditar:
    st.info("✅ Bandeja limpia. No hay lotes pendientes de auditoría en este momento.")
    st.stop()

# Lo convertimos a DataFrame para mostrarlo lindo en pantalla
df_lote = pd.DataFrame(lote_auditar)
cantidad_docs = len(df_lote)

st.subheader(f"📦 Lote Pendiente ({cantidad_docs} documentos listos para revisión)")
st.caption("Estos archivos ya fueron procesados por el motor cognitivo. Revisá que las patentes sean correctas antes de aprobar.")

# Grilla interactiva
df_editado = st.data_editor(
    df_lote[["PATENTE", "TIPO_DOC", "VENCIMIENTO", "ESTADO_IA", "ARCHIVO_ORIGINAL"]],
    use_container_width=True,
    hide_index=True,
    disabled=["ESTADO_IA", "ARCHIVO_ORIGINAL"] # Bloqueamos edición de columnas del sistema
)

st.write("")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    if st.button(f"✅ Aprobar Lote Completo ({cantidad_docs} Archivos)", type="primary", use_container_width=True):
        with st.status("Procesando ruteo de archivos y actualizando bases...", expanded=True) as status:
            
            exitos = 0
            for idx, row in df_lote.iterrows():
                id_carga = row["ID_CARGA"]
                patente = str(df_editado.at[idx, "PATENTE"]).strip().upper()
                tipo_doc = str(df_editado.at[idx, "TIPO_DOC"]).strip().upper()
                vencimiento = str(df_editado.at[idx, "VENCIMIENTO"]).strip()
                link_temp = row["LINK_TEMP"]
                id_drive_temp = extraer_id_drive(link_temp)
                
                status.write(f"🔄 Tratando {patente} ({tipo_doc})...")
                
                try:
                    # A. Mover archivo a su carpeta final
                    nuevo_nombre = f"{patente}_{tipo_doc}.pdf"
                    link_definitivo = mover_y_renombrar_archivo(id_drive_temp, CARPETA_CERTIFICADOS, nuevo_nombre)
                    
                    # B. Actualizar Maestro de Flota (Mapeamos la columna a actualizar según el tipo de documento)
                    columna_destino_link = "LINK_CERTIFICADO_SEGURO"
                    if tipo_doc == "TITULO": columna_destino_link = "LINK_TITULO"
                    elif tipo_doc == "VTV": columna_destino_link = "LINK_VTV"
                    elif tipo_doc == "CEDULA_VERDE": columna_destino_link = "LINK_CEDULA"
                        
                    nuevos_datos = {
                        columna_destino_link: link_definitivo,
                        # "SEGURO_VTO": vencimiento # Descomentar cuando la hoja FLOTA tenga estas columnas exactas
                    }
                    
                    actualizar_fila(HOJA_FLOTA, "PATENTE", patente, nuevos_datos)
                    
                    # C. Eliminar de la bandeja temporal
                    eliminar_fila(HOJA_PENDIENTES, id_carga)
                    
                    exitos += 1
                except Exception as e:
                    status.write(f"❌ Error con {patente}: {str(e)}")
            
            status.update(label=f"¡Lote procesado! ({exitos}/{cantidad_docs} completados)", state="complete")
        
        if exitos > 0:
            st.success("¡Base de datos actualizada y archivos organizados en Google Drive!")
            st.rerun()

with col2:
    if st.button("⚠️ Rechazar Lote", use_container_width=True):
        # Opcional: Lógica para cambiar el estado a "RECHAZADO"
        st.error("Funcionalidad de rechazo en desarrollo.")

with col3:
    st.button("📑 Ver Póliza Madre", use_container_width=True, help="Abre el contrato general original")
