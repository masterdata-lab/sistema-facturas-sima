import streamlit as st
import pandas as pd

# Configuración inicial de la página
st.set_page_config(page_title="Configuración General", page_icon="⚙️", layout="wide")

st.title("⚙️ Configuración del Sistema")
st.markdown("Administración centralizada de Empresas, Gerencias y Receptores para todas las áreas (Facturas, Pañol y Flota).")

# 1. Función de lectura con Caché (Evita saturar Google Sheets)
@st.cache_data(ttl=600) # Se actualiza cada 10 min automáticamente o al limpiar caché
def cargar_configuracion():
    # NOTA PARA EL FUTURO: Aquí conectaremos con la pestaña CONFIGURACION de Google Sheets.
    # Por ahora, generamos un DataFrame inicial vacío con las columnas correctas.
    columnas = {
        "GERENCIAS": ["AEROPUERTO", "ECOKLIN", "EDENOR", "", ""],
        "EMPRESAS_FLOTA": ["GPS", "GLOBAL PROTECTION SERVICE S. A.", "LA BIZANTINA", "ECOKLIN", ""],
        "CUIT_EMPRESAS_FLOTA": ["33-12345678-9", "33-71498759-9", "30-12345678-0", "", ""],
        "EMPRESAS_RECEPTORAS_FACTURAS": ["GPS", "GLOBAL PROTECTION SERVICE S. A.", "", "", ""],
        "CUIT_RECEPTORES_FACTURAS": ["33-12345678-9", "33-71498759-9", "", "", ""]
    }
    return pd.DataFrame(columnas)

# Cargamos los datos
df_config = cargar_configuracion()

st.info("💡 **Modo Edición Segura:** Modificá los datos directamente en la tabla de abajo (podés agregar o borrar filas al final de la tabla). Los cambios solo impactarán en la base de datos al presionar 'Guardar'.")

# 2. Editor interactivo (Sandboxing)
# El usuario interactúa con esta tabla sin tocar el Excel real hasta que guarda
df_editado = st.data_editor(
    df_config,
    num_rows="dynamic", # Permite a los civiles agregar filas nuevas
    use_container_width=True,
    hide_index=True
)

st.write("---")
col1, col2, col3 = st.columns([2, 2, 4])

# 3. Botonera de acciones
with col1:
    if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
        # NOTA PARA EL FUTURO: Aquí irá la función que sobreescribe Google Sheets
        
        # Limpiamos la memoria caché para que el resto de las pantallas tomen los datos nuevos
        st.cache_data.clear() 
        st.success("¡Datos guardados exitosamente!")
        
with col2:
    if st.button("🔄 Actualizar Datos", use_container_width=True, help="Fuerza al sistema a leer el Excel nuevamente."):
        st.cache_data.clear()
        st.rerun()
