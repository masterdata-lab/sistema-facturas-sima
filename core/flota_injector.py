import streamlit as st
import datetime
import time

def inyectar_documento_flota(item):
    """
    Procesa el documento aprobado en la mesa de auditoría:
    1. Simula/Carga en la carpeta jerárquica de Google Drive.
    2. Aplica reglas de negocio en Google Sheets según el tipo de documento.
    """
    patente = item["patente"]
    tipo = item["tipo_sugerido"]
    hoy = datetime.date.today().strftime("%d/%m/%Y")
    
    # 1. Recuperamos el ID de la planilla guardado en la configuración
    id_planilla = st.session_state.get("id_sheet_flota", "")
    if not id_planilla:
        return False, "Falta configurar el ID de la planilla en Parámetros Globales."
    
    # 2. Construcción del path jerárquico simulado para Drive
    # Formato: [Patente]/[HISTORIAL_SEGUROS]/[FILENAME] o [Patente]/[TIPO]/[FILENAME]
    subcarpeta = "HISTORIAL_SEGUROS" if tipo == "CERTIFICADO_SEGURO" else tipo
    link_drive_final = f"https://drive.google.com/drive/folders/{patente}/{subcarpeta}/{item['origen']}"
    
    try:
        # --- REGLA DE NEGOCIO A: EXCEPCIÓN DE SEGUROS (HISTORIAL COMPLETO) ---
        if tipo == "CERTIFICADO_SEGURO":
            # Estructura: ["Patente", "Aseguradora", "Nro Poliza", "Fecha Emision", "Fecha Vencimiento", "Titular / Tomador", "CUIT / CUIL", "Link Drive PDF", "Fecha Ingestión"]
            nueva_fila_seguro = [
                patente,
                item.get("aseguradora", "No especificado"),
                item.get("numero_poliza", "No especificado"),
                hoy,
                item.get("fecha_vencimiento", "No especifica"),
                item.get("titular_nombre", ""),
                item.get("cuit_cuil", ""),
                link_drive_final,
                hoy
            ]
            
            # Aquí se ejecutará el append_row real a la pestaña HISTORIAL_SEGUROS
            # conector.append_row(id_planilla, "HISTORIAL_SEGUROS", nueva_fila_seguro)
            st.toast(f"Póliza Nº {item['numero_poliza']} guardada en el historial de {patente}.", icon="📄")
            
        # --- REGLA DE NEGOCIO B: UNICIDAD DOCUMENTAL (FLOTA GENERAL) ---
        else:
            # Para TITULO, CEDULA_VERDE, VTV, RTO, YPF se busca la patente en 'FLOTA' y se actualiza su celda específica
            # Si es CEDULA_VERDE, recordá que ignoramos las alertas de vencimiento en los semáforos del buscador
            st.toast(f"Módulo Maestro: Registro {tipo} actualizado para la patente {patente}.", icon="🚘")
            
        return True, link_drive_final
        
    except Exception as e:
        return False, str(e)
