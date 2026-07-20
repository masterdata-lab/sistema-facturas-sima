import streamlit as st
import datetime
# Asumimos que estas funciones existen en tu utils/conexiones.py para interactuar con las APIs
# Si tus funciones tienen otros nombres (ej. escribir_fila, actualizar_celda), adaptalas aquí.
from utils.conexiones import leer_hoja_completa 

def inyectar_documento_flota(item, cliente_sheets=None, cliente_drive=None):
    """
    Aplica las reglas de negocio del ERP para Flota:
    1. Guarda el archivo en Google Drive dentro de [Patente]/[Tipo_Doc] o [HISTORIAL_SEGUROS]
    2. Si es SEGURO: Inyecta fila en HISTORIAL_SEGUROS y actualiza "Vto Seguro" en FLOTA.
    3. Si es CÉDULA VERDE: Guarda el link en FLOTA pero ignora alertas de vencimiento.
    4. Para otros (VTV, Título): Pisa el registro único de esa Patente en la hoja FLOTA.
    """
    patente = item["patente"]
    tipo = item["tipo_sugerido"]
    
    # --- FASE 1: SIMULACIÓN/PROCESAMIENTO DE DRIVE ---
    # Aquí irá tu lógica para subir el archivo binario a Drive
    # Por ahora generamos un link ficticio basado en la estructura jerárquica solicitada
    link_drive_simulado = f"https://drive.google.com/drive/folders/{patente}/{tipo}_{item['origen']}"
    
    # --- FASE 2: IMPACTO EN GOOGLE SHEETS ---
    hoy = datetime.date.today().strftime("%d/%m/%Y")
    
    try:
        # REGLA DE NEGOCIO 1: EXCEPCIÓN DE SEGUROS (HISTORIAL PERMANENTE)
        if tipo == "CERTIFICADO_SEGURO":
            # 1. Armamos la fila para la hoja HISTORIAL_SEGUROS
            # Columnas: ["Patente", "Aseguradora", "Nro Poliza", "Fecha Emision", "Fecha Vencimiento", "Titular / Tomador", "CUIT / CUIL", "Link Drive PDF", "Fecha Ingestión"]
            nueva_fila_seguro = [
                patente,
                item.get("aseguradora", "No especificado"),
                item.get("numero_poliza", "No especificado"),
                hoy, # Fecha Emision ficticia o de hoy
                item.get("fecha_vencimiento", ""),
                item.get("titular_nombre", ""),
                item.get("cuit_cuil", ""),
                link_drive_simulado,
                hoy
            ]
            
            # TODO: Ejecutar la inserción real en HISTORIAL_SEGUROS vía gspread
            # ejemplo: cliente_sheets.open_by_key(...).worksheet("HISTORIAL_SEGUROS").append_row(nueva_fila_seguro)
            
            st.toast(f"Póliza {item['numero_poliza']} añadida al historial de {patente}.", icon="📄")
            
        # REGLA DE NEGOCIO 2: REGISTRO ÚNICO (FLOTA GENERAL)
        else:
            # Para TITULO, CEDULA_VERDE, VTV, RTO, YPF se busca la fila de la patente y se actualiza la celda correspondiente
            # TODO: Buscar la fila que matchee con la 'patente' en la hoja "FLOTA"
            # Si la patente existe, se actualizan sus columnas de Links y Vencimientos
            st.toast(f"Documento {tipo} actualizado para la patente {patente}.", icon="🚘")
            
        return True, link_drive_simulado
        
    except Exception as e:
        return False, f"Error al inyectar en la base de datos: {str(e)}"
