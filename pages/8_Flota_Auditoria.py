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

# Inicializamos el estado de la selección para el "Árbol"
if "audit_sel" not in st.session_state: st.session_state.audit_sel = []
if "audit_prev" not in st.session_state: st.session_state.audit_prev = None

st.markdown('''
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 98%; }
    .stButton>button { text-align: left; border: none; background-color: transparent; padding: 0.2rem 0.5rem; font-size: 14px; }
    .stButton>button:hover { background-color: #f0f2f6; border-radius: 4px; color: #ff4b4b;}
    ::-webkit-scrollbar { width: 8px !important; height: 8px !important; }
    ::-webkit-scrollbar-thumb { background-color: #c1c1c1 !important; border-radius: 4px !important; }
</style>
''', unsafe_allow_html=True)

st.title("⚖️ Auditoría de Documentos (Flota)")
st.markdown(f"**Bandeja:** `{HOJA_PENDIENTES}` | Menú de árbol: Seleccioná lotes completos o revisá uno por uno.")
st.divider()

with st.spinner("Buscando documentos procesados..."):
    try:
        datos_cola = leer_hoja_completa(HOJA_PENDIENTES)
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        st.stop()

lote_auditar = []
for fila in datos_cola[1:]:
    estado = str(fila[6]).strip().upper()
    tipo = str(fila[7]).strip().upper()
    
    # Traemos los individuales procesados y también las Pólizas Madre que la IA ya desglosó
    if (estado == "PROCESADO") or (estado == "PROCESADO_DESGLOSADO" and tipo == "POLIZA_MADRE"):
        try:
            datos_ia = json.loads(fila[8]) if len(fila) > 8 and fila[8] else {}
            link_madre = fila[5] if len(fila) > 5 else "N/A"
            id_madre = extraer_id_drive(link_madre) if link_madre != "N/A" else "INDEPENDIENTE"
            
            lote_auditar.append({
                "ID_CARGA": fila[0],
                "PATENTE": datos_ia.get("patente", "S_D").upper(),
                "TIPO_DOC": tipo,
                "VENCIMIENTO": datos_ia.get("vencimiento", "S/D"), 
                "LINK_TEMP": fila[4],
                "LINK_MADRE": link_madre,
                "ID_MADRE_GRUPO": id_madre,
                "ESTADO": estado
            })
        except Exception:
            pass

if not lote_auditar:
    st.info("✅ Bandeja limpia. No hay lotes pendientes de auditoría en este momento.")
    st.stop()

df_lote = pd.DataFrame(lote_auditar)

# 🌟 LAYOUT EN 3 COLUMNAS: Árbol (25%) - Visor (50%) - Auditoría (25%)
col_arbol, col_visor, col_auditoria = st.columns([1.2, 2.2, 1.2], gap="large")

with col_arbol:
    st.markdown("### 📂 Bandeja de Entrada")
    
    # --- GRUPO 1: SEGUROS (Madres y Certificados) ---
    st.markdown("#### 🛡️ SEGUROS")
    df_seguros = df_lote[df_lote["TIPO_DOC"].isin(["POLIZA_MADRE", "CERTIFICADO_SEGURO"])]
    
    madres = df_seguros[df_seguros["TIPO_DOC"] == "POLIZA_MADRE"]
    certificados = df_seguros[df_seguros["TIPO_DOC"] == "CERTIFICADO_SEGURO"]
    
    st.markdown("**➡️ PÓLIZAS ENTERAS (ORIGINALES)**")
    if madres.empty:
        st.caption("No hay pólizas originales pendientes.")
    else:
        for _, row in madres.iterrows():
            icono = "👉" if row["ID_CARGA"] in st.session_state.audit_sel else "📄"
            if st.button(f"{icono} Póliza {row['ID_MADRE_GRUPO'][:8]}", key=f"btn_madre_{row['ID_CARGA']}"):
                st.session_state.audit_sel = [row["ID_CARGA"]]
                st.session_state.audit_prev = row["ID_CARGA"]
                st.rerun()

    st.markdown("**➡️ CERTIFICADOS INDIVIDUALES**")
    if certificados.empty:
        st.caption("No hay certificados segmentados pendientes.")
    else:
        grupos_cert = certificados.groupby("ID_MADRE_GRUPO")
        for id_grupo, grupo in grupos_cert:
            nombre_lote = f"PÓLIZA {id_grupo[:8]}" if id_grupo != "INDEPENDIENTE" else "SIN AGRUPAR"
            
            # Botón del Lote Padre
            if st.button(f"📁 LOTE: {nombre_lote} ({len(grupo)} docs)", key=f"btn_lote_{id_grupo}"):
                st.session_state.audit_sel = grupo["ID_CARGA"].tolist()
                st.session_state.audit_prev = grupo.iloc[0]["ID_CARGA"]
                st.rerun()
                
            # Botones de los Hijos (Patentes)
            for _, row in grupo.iterrows():
                c_espacio, c_btn = st.columns([0.15, 0.85])
                with c_btn:
                    icono = "👉" if row["ID_CARGA"] in st.session_state.audit_sel else "↳ 📄"
                    if st.button(f"{icono} {row['PATENTE']}", key=f"btn_hijo_{row['ID_CARGA']}"):
                        st.session_state.audit_sel = [row["ID_CARGA"]]
                        st.session_state.audit_prev = row["ID_CARGA"]
                        st.rerun()

    # --- GRUPO 2: OTROS DOCUMENTOS (VTV, Cédulas, etc.) ---
    st.write("---")
    st.markdown("#### 🟩 OTROS DOCUMENTOS")
    df_otros = df_lote[~df_lote["TIPO_DOC"].isin(["POLIZA_MADRE", "CERTIFICADO_SEGURO"])]
    
    if df_otros.empty:
        st.caption("No hay otros documentos pendientes.")
    else:
        grupos_otros = df_otros.groupby("TIPO_DOC")
        for tipo, grupo in grupos_otros:
            if st.button(f"📁 LOTE: {tipo} ({len(grupo)} docs)", key=f"btn_lote_{tipo}"):
                st.session_state.audit_sel = grupo["ID_CARGA"].tolist()
                st.session_state.audit_prev = grupo.iloc[0]["ID_CARGA"]
                st.rerun()
                
            for _, row in grupo.iterrows():
                c_espacio, c_btn = st.columns([0.15, 0.85])
                with c_btn:
                    icono = "👉" if row["ID_CARGA"] in st.session_state.audit_sel else "↳ 📄"
                    if st.button(f"{icono} {row['PATENTE']}", key=f"btn_hijo_{row['ID_CARGA']}"):
                        st.session_state.audit_sel = [row["ID_CARGA"]]
                        st.session_state.audit_prev = row["ID_CARGA"]
                        st.rerun()

with col_visor:
    st.markdown("### 👁️ Visor de Documento")
    if st.session_state.audit_prev:
        try:
            # Buscamos el documento actual en el DataFrame
            fila_visor = df_lote[df_lote["ID_CARGA"] == st.session_state.audit_prev].iloc[0]
            link_visor = fila_visor["LINK_TEMP"]
            pat_visor = fila_visor["PATENTE"]
            tipo_visor = fila_visor["TIPO_DOC"]
            
            st.info(f"**Viendo ahora:** `{pat_visor}` | **Documento:** `{tipo_visor}`")
            
            id_drive = extraer_id_drive(link_visor)
            if id_drive:
                url_visor = f"https://drive.google.com/file/d/{id_drive}/preview"
                st.components.v1.iframe(url_visor, height=700)
            else:
                st.warning("Link de Drive inválido.")
        except IndexError:
            st.warning("El documento seleccionado ya fue procesado.")
            st.session_state.audit_prev = None
    else:
        st.info("👈 Hacé clic en un documento o lote del menú izquierdo para visualizarlo.")

with col_auditoria:
    st.markdown("### 🛠️ Mesa de Trabajo")
    
    cant_sel = len(st.session_state.audit_sel)
    
    if cant_sel == 0:
        st.warning("Esperando selección desde el árbol...")
        
    elif cant_sel == 1:
        # MODO INDIVIDUAL
        id_actual = st.session_state.audit_sel[0]
        fila_actual = df_lote[df_lote["ID_CARGA"] == id_actual].iloc[0]
        
        st.markdown("**Control Individual**")
        st.write("Podés corregir los datos antes de enviar a la base de datos:")
        
        patente_corregida = st.text_input("Patente", value=fila_actual["PATENTE"]).strip().upper()
        
        opciones_tipo = ["CERTIFICADO_SEGURO", "TITULO", "CEDULA_VERDE", "VTV", "POLIZA_MADRE"]
        tipo_actual = fila_actual["TIPO_DOC"]
        idx_tipo = opciones_tipo.index(tipo_actual) if tipo_actual in opciones_tipo else 0
        tipo_corregido = st.selectbox("Clasificación", opciones_tipo, index=idx_tipo)
        
        st.write("")
        if st.button("✅ Aprobar y Guardar", type="primary", use_container_width=True):
            with st.spinner("Moviendo a carpeta definitiva..."):
                try:
                    nuevo_nombre = f"{patente_corregida}_{tipo_corregido}.pdf"
                    id_drive_temp = extraer_id_drive(fila_actual["LINK_TEMP"])
                    link_definitivo = mover_y_renombrar_archivo(id_drive_temp, CARPETA_CERTIFICADOS, nuevo_nombre)
                    
                    if tipo_corregido != "POLIZA_MADRE":
                        columna_destino = "LINK_CERTIFICADO_SEGURO"
                        if tipo_corregido == "TITULO": columna_destino = "LINK_TITULO"
                        elif tipo_corregido == "VTV": columna_destino = "LINK_VTV"
                        elif tipo_corregido == "CEDULA_VERDE": columna_destino = "LINK_CEDULA"
                            
                        actualizar_fila(HOJA_FLOTA, "PATENTE", patente_corregida, {columna_destino: link_definitivo})
                    
                    eliminar_fila(HOJA_PENDIENTES, id_actual)
                    
                    # Limpiamos selección post-aprobación
                    st.session_state.audit_sel = []
                    st.session_state.audit_prev = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        if st.button("🗑️ Eliminar Registro", use_container_width=True):
            eliminar_fila(HOJA_PENDIENTES, id_actual)
            st.session_state.audit_sel = []
            st.session_state.audit_prev = None
            st.rerun()

    else:
        # MODO LOTE
        st.markdown("**Aprobación Masiva**")
        st.info(f"Seleccionaste un lote de **{cant_sel} documentos**.")
        st.write("Se organizarán en Drive y actualizarán la base usando las patentes extraídas por la IA.")
        
        if st.button(f"🚀 Aprobar Lote Completo", type="primary", use_container_width=True):
            with st.status(f"Procesando {cant_sel} archivos...", expanded=True) as status:
                exitos = 0
                for id_carga in st.session_state.audit_sel:
                    try:
                        fila_lote = df_lote[df_lote["ID_CARGA"] == id_carga].iloc[0]
                        patente = fila_lote["PATENTE"]
                        tipo_doc = fila_lote["TIPO_DOC"]
                        
                        status.write(f"🔄 Ruteando {patente}...")
                        
                        nuevo_nombre = f"{patente}_{tipo_doc}.pdf"
                        id_drive_temp = extraer_id_drive(fila_lote["LINK_TEMP"])
                        link_definitivo = mover_y_renombrar_archivo(id_drive_temp, CARPETA_CERTIFICADOS, nuevo_nombre)
                        
                        if tipo_doc != "POLIZA_MADRE":
                            columna_destino = "LINK_CERTIFICADO_SEGURO"
                            if tipo_doc == "TITULO": columna_destino = "LINK_TITULO"
                            elif tipo_doc == "VTV": columna_destino = "LINK_VTV"
                            elif tipo_doc == "CEDULA_VERDE": columna_destino = "LINK_CEDULA"
                                
                            actualizar_fila(HOJA_FLOTA, "PATENTE", patente, {columna_destino: link_definitivo})
                            
                        eliminar_fila(HOJA_PENDIENTES, id_carga)
                        exitos += 1
                    except Exception as e:
                        status.write(f"❌ Error con {patente}: {str(e)}")
                
                status.update(label=f"¡Lote finalizado! ({exitos}/{cant_sel})", state="complete")
                
            if exitos > 0:
                st.session_state.audit_sel = []
                st.session_state.audit_prev = None
                st.rerun()
