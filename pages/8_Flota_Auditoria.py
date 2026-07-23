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
                "Sel": False, # Agregamos el Checkbox por defecto desmarcado
                "ID_CARGA": fila[0],
                "ARCHIVO_ORIGINAL": fila[2],
                "PATENTE": datos_ia.get("patente", "N/A"),
                "TIPO_DOC": datos_ia.get("tipo_sugerido", fila[7]),
                "VENCIMIENTO": datos_ia.get("vencimiento", "S/D"), 
                "LINK_TEMP": fila[4],
                "LINK_MADRE": fila[5] if len(fila) > 5 else "N/A",
                "ESTADO_IA": "🟢 Éxito"
            })
        except Exception:
            pass

if not lote_auditar:
    st.info("✅ Bandeja limpia. No hay lotes pendientes de auditoría en este momento.")
    st.stop()

df_lote = pd.DataFrame(lote_auditar)

# Dividimos la pantalla: Visor a la izquierda (más grande), Controles a la derecha
col_visor, col_controles = st.columns([1.5, 1], gap="large")

with col_controles:
    st.subheader("📋 Lista de Certificados")
    st.write("Tildá los archivos que quieras revisar y aprobar.")

    # Mostramos la tabla interactiva
    df_editado = st.data_editor(
        df_lote[["Sel", "PATENTE", "TIPO_DOC", "VENCIMIENTO", "ESTADO_IA"]],
        column_config={
            "Sel": st.column_config.CheckboxColumn("✅", default=False)
        },
        use_container_width=True,
        hide_index=True,
        disabled=["ESTADO_IA"] # Evitamos que editen el estado
    )

    # Filtramos para saber cuáles tildó el usuario
    seleccionados_idx = df_editado.index[df_editado["Sel"] == True].tolist()
    cant_sel = len(seleccionados_idx)

    st.markdown("### 🛠️ Acciones")
    
    if cant_sel == 0:
        st.info("👈 Seleccioná al menos un documento en la tabla para aprobar o rechazar.")
    else:
        if st.button(f"✅ Aprobar Seleccionados ({cant_sel})", type="primary", use_container_width=True):
            with st.status(f"Procesando {cant_sel} archivos...", expanded=True) as status:
                exitos = 0
                for idx in seleccionados_idx:
                    id_carga = df_lote.at[idx, "ID_CARGA"]
                    link_temp = df_lote.at[idx, "LINK_TEMP"]
                    
                    # Tomamos los datos de df_editado por si el usuario corrigió la patente a mano
                    patente = str(df_editado.at[idx, "PATENTE"]).strip().upper()
                    tipo_doc = str(df_editado.at[idx, "TIPO_DOC"]).strip().upper()
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
                
                status.update(label=f"¡Lote procesado! ({exitos}/{cant_sel} completados)", state="complete")
            
            if exitos > 0:
                st.success("¡Base de datos actualizada y archivos organizados en Google Drive!")
                st.rerun()

        if st.button(f"⚠️ Rechazar Seleccionados ({cant_sel})", use_container_width=True):
            st.error("Funcionalidad de rechazo en desarrollo.")
            
    st.write("---")
    
    # Botón de Póliza Madre (Toma la póliza del primer registro)
    link_madre_ejemplo = df_lote["LINK_MADRE"].iloc[0]
    if link_madre_ejemplo and link_madre_ejemplo != "N/A" and "http" in link_madre_ejemplo:
        st.link_button("📑 Ver Póliza Madre Original", url=link_madre_ejemplo, use_container_width=True)
    else:
        st.button("📑 Póliza Madre no disponible", disabled=True, use_container_width=True)

with col_visor:
    st.subheader("👁️ Visor de Documento")
    
    if cant_sel > 0:
        # Mostramos en el visor el ÚLTIMO documento que el usuario tildó
        idx_mostrar = seleccionados_idx[-1]
        link_temp_visor = df_lote.at[idx_mostrar, "LINK_TEMP"]
        patente_visor = df_editado.at[idx_mostrar, "PATENTE"]
        tipo_visor = df_editado.at[idx_mostrar, "TIPO_DOC"]
        
        st.markdown(f"**Viendo:** `{patente_visor}` - `{tipo_visor}`")
        
        id_drive_visor = extraer_id_drive(link_temp_visor)
        if id_drive_visor:
            url_visor = f"https://drive.google.com/file/d/{id_drive_visor}/preview"
            st.components.v1.iframe(url_visor, height=750)
        else:
            st.warning("No se puede generar la vista previa. Link inválido.")
    else:
        # Mensaje por defecto cuando no hay nada tildado
        st.info("Tildá un documento en la lista de la derecha para previsualizarlo aquí.")
