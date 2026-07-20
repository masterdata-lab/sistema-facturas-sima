import streamlit as st
from utils.conexiones import leer_hoja_completa  # Usando tu conector

st.title("🔍 Buscador Avanzado de Flota e Historial")
st.markdown("Consulta el estado documental de un vehículo y descarga pólizas vigentes o históricas.")
st.divider()

# 1. Input de búsqueda centralizado
patente_buscada = st.text_input("Ingrese la Patente a consultar (Ej: AA192BQ o A162ABP)", "").upper().strip().replace(" ", "")

if patente_buscada:
    # --- MOCK DE BASE DE DATOS (Simulación hasta conectar tu Sheets) ---
    # Esto simula lo que el sistema traerá de la hoja FLOTA y de HISTORIAL_SEGUROS
    vehiculo_existe = True  
    
    if vehiculo_existe:
        st.subheader(f"🚘 Ficha del Vehículo: {patente_buscada}")
        
        # --- 1. SEMÁFORO DOCUMENTAL ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cédula Verde", "🟢 Válida", help="Sin vencimiento restrictivo por ley")
        c2.metric("VTV / RTO", "🟢 Vigente", delta="Vence: 14/11/2026")
        c3.metric("Tarjeta YPF", "🔴 Vencida", delta="-60 días", delta_color="inverse")
        c4.metric("Seguro Actual", "🟡 Alerta", delta="-12 días", delta_color="normal")
        
        st.markdown("---")
        
        # --- 2. SELECTOR DE PÓLIZAS HISTÓRICAS ---
        st.subheader("📄 Historial de Coberturas de Seguros")
        st.markdown("Seleccione una póliza para auditar el contrato o descargar el comprobante legal de ese período:")
        
        # Diccionario simulando los registros de la hoja HISTORIAL_SEGUROS
        polizas_historial = {
            "Póliza Nº 987654 - Federación Patronal (Vigente)": {
                "nro": "987654", "aseg": "Federación Patronal Seguros S.A.", 
                "tomador": "GRUPO SIMA S.A. (CUIT 30-76543210-9)", "desde": "01/02/2026", "hasta": "01/08/2026",
                "tipo": "Todo Riesgo con Franquicia", "url": "#"
            },
            "Póliza Nº 543210 - Federación Patronal (Vencida - Período 2025/2026)": {
                "nro": "543210", "aseg": "Federación Patronal Seguros S.A.", 
                "tomador": "GRUPO SIMA S.A. (CUIT 30-76543210-9)", "desde": "01/08/2025", "hasta": "01/02/2026",
                "tipo": "Todo Riesgo con Franquicia", "url": "#"
            },
            "Póliza Nº 112233 - La Caja (Vencida - Período 2024/2025)": {
                "nro": "112233", "aseg": "La Caja de Ahorro y Seguro", 
                "tomador": "PEREZ JUAN RAMON (CUIT 20-34567890-9)", "desde": "01/08/2024", "hasta": "01/08/2025",
                "tipo": "Terceros Completo", "url": "#"
            }
        }
        
        # El desplegable que cambia la pantalla en caliente
        seleccion = st.selectbox("Seleccione la póliza requerida:", list(polizas_historial.keys()))
        
        # --- 3. FICHA EXTENDIDA DE LA PÓLIZA SELECCIONADA ---
        if seleccion:
            info = polizas_historial[seleccion]
            with st.container(border=True):
                st.markdown(f"### Detalle Técnico: {seleccion}")
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.write(f"**Compañía Aseguradora:** {info['aseg']}")
                    st.write(f"**Número de Póliza:** {info['nro']}")
                    st.write(f"**Tomador / Asegurado:** {info['tomador']}")
                with sc2:
                    st.write(f"**Vigencia:** Desde {info['desde']} hasta {info['hasta']}")
                    st.write(f"**Tipo de Cobertura:** {info['tipo']}")
                
                st.write("")
                # Botón de descarga apuntando al archivo renombrado humanamente
                st.link_button(f"💾 Descargar PDF Original ({info['nro']})", url=info['url'], use_container_width=True)
        
        # --- 4. REPOSITORIO DE ARCHIVOS VIGENTES ---
        st.markdown("---")
        st.subheader("📂 Documentación General del Vehículo")
        col_files = st.columns(3)
        col_files.link_button("📄 Ver Título Digital", "#", use_container_width=True)
        col_files.link_button("📄 Ver Cédula Verde (Frente/Dorso)", "#", use_container_width=True)
        col_files.link_button("📄 Ver Última VTV", "#", use_container_width=True)
        
    else:
        st.error(f"La patente {patente_buscada} no se encuentra cargada en la base de datos de la empresa.")
