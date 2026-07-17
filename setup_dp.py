import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN DE CONEXIÓN ---
# Ajustá esto según cómo te estés autenticando actualmente en tu utils/conexiones.py
def obtener_cliente_sheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Asume que tenés los datos de la cuenta de servicio en st.secrets
    credenciales = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    cliente = gspread.authorize(credenciales)
    return cliente

# --- DICCIONARIO MAESTRO DE ESTRUCTURA (ERP COMPLETO) ---
ESTRUCTURA_BD = {
    # 1. MÓDULO DE FACTURACIÓN Y AUDITORÍA
    "GENERAL": ["ID Unico", "Año", "Mes", "Fecha", "CUIT Receptor", "Patentes Involucradas", "CUIT Prov", "Razon Social", "Nro Completo", "Subtotal", "Total Final", "Link PDF", "Notas Administrativas"],
    "DETALLE": ["ID Unico", "Año", "Mes", "Fecha", "CUIT Receptor", "Patente Vehículo", "CUIT Empresa Vehículo", "Gerencia del Gasto", "CUIT Prov", "Razon Social Prov", "Nro Completo", "Nro OT", "Categoría Gasto", "Descripción", "Cantidad", "Precio Neto U.", "Precio Total U."],
    "PENDIENTES": ["ID Carga", "Fecha Subida", "Nombre Archivo", "Usuario", "Link PDF", "Drive ID", "Estado", "Mensaje IA", "JSON Datos"],
    
    # 2. MÓDULO MAESTRO Y FLOTA
    "FLOTA": ["Patente", "Estado", "CUIT Empresa", "Gerencia Actual", "Tipo", "Marca", "Modelo", "Año", "Nro Chasis", "Nro Motor", "Vto VTV", "Link VTV", "Vto Seguro", "Link Cert. Seguro", "Link Póliza General", "Vto RUTA", "Link RUTA", "Vto Tarj. YPF", "Link Tarjeta YPF", "Observaciones"],
    "GERENCIAS": ["Nombre Gerencia", "Estado"],
    "RECEPTORES": ["CUIT", "Razón Social", "Alias", "Fecha Alta"],
    "PROVEEDORES": ["Alias", "Razón Social", "CUIT"],
    "REGLAS_IA": ["CUIT Proveedor", "Razón Social", "Instrucción IA", "Fecha Creación"],
    
    # 3. MÓDULO DE TALLER E INVENTARIO (NUEVO)
    "INV_STOCK": ["Categoría", "Artículo/Medida", "Condición", "Stock Disponible", "Punto de Pedido"],
    "INV_TRAZABLE": ["Categoría", "Artículo/Medida", "Condición", "Nro Serie / ID Interno", "Estado"],
    "INV_MOVIMIENTOS": ["Fecha", "Nro Remito", "Tipo Movimiento", "Responsable", "Receptor", "Patente Destino", "Gerencia", "Detalle Repuestos", "Link PDF Remito"],
    "INV_RESPONSABLES": ["Nombre y Apellido", "Puesto", "Estado"],
    "INV_RECEPTORES": ["Nombre y Apellido", "Email", "Gerencia Habitual", "Última Patente"]
}

def reconstruir_base_de_datos(id_planilla):
    print("Iniciando reconstrucción de la base de datos...")
    try:
        cliente = obtener_cliente_sheets()
        planilla = cliente.open_by_key(id_planilla)
        
        hojas_existentes = [hoja.title for hoja in planilla.worksheets()]
        
        for nombre_hoja, encabezados in ESTRUCTURA_BD.items():
            # 1. Crear la hoja si no existe
            if nombre_hoja not in hojas_existentes:
                print(f"Creando pestaña: {nombre_hoja}...")
                hoja = planilla.add_worksheet(title=nombre_hoja, rows="1000", cols=str(len(encabezados)))
            else:
                print(f"Actualizando pestaña existente: {nombre_hoja}...")
                hoja = planilla.worksheet(nombre_hoja)
            
            # 2. Limpiar todo el contenido de la hoja (¡ACCION DESTRUCTIVA!)
            hoja.clear()
            
            # 3. Escribir los encabezados nuevos en la fila 1
            hoja.update(range_name='A1', values=[encabezados])
            
            # 4. Formato visual básico (Negrita para la cabecera)
            hoja.format('A1:Z1', {'textFormat': {'bold': True}})
            
        print("✅ Base de datos reconstruida y formateada con éxito.")
        
    except Exception as e:
        print(f"❌ Error al reconstruir: {e}")

if __name__ == "__main__":
    # Reemplazá esto por el ID real de tu Google Sheets (lo sacás de la URL del navegador)
    ID_GSHEETS = "TU_ID_DE_PLANILLA_AQUI" 
    
    respuesta = input("⚠️ ATENCIÓN: Esto borrará TODOS los datos de la planilla y escribirá solo los encabezados. ¿Continuar? (S/N): ")
    if respuesta.lower() == 's':
        reconstruir_base_de_datos(ID_GSHEETS)
    else:
        print("Operación cancelada.")
