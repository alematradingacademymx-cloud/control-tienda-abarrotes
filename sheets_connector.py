"""
Conector a Google Sheets. Toda la app lee y escribe datos a través de este
módulo, para no repetir lógica de conexión en cada página.

Requiere credenciales de una cuenta de servicio de Google Cloud con acceso
a la Google Sheets API y Google Drive API. Ver README.md para el paso a
paso de configuración.

Las credenciales se leen, en este orden:
  1. st.secrets["gcp_service_account"]  (recomendado para Streamlit Cloud)
  2. archivo local "credentials.json" junto a este script (para pruebas locales)
"""

import json
import os
from datetime import datetime

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from config import HOJAS, NOMBRE_SPREADSHEET

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")


def _cargar_credenciales() -> Credentials:
    if "gcp_service_account" in st.secrets:
        info = dict(st.secrets["gcp_service_account"])
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            info = json.load(f)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    raise RuntimeError(
        "No se encontraron credenciales de Google. Configura "
        "'gcp_service_account' en secrets.toml o coloca un archivo "
        "credentials.json junto a la app. Consulta el README."
    )


@st.cache_resource(show_spinner=False)
def _get_client() -> gspread.Client:
    creds = _cargar_credenciales()
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _get_spreadsheet():
    client = _get_client()
    try:
        return client.open(NOMBRE_SPREADSHEET)
    except gspread.SpreadsheetNotFound as exc:
        raise RuntimeError(
            f"No se encontró el Google Sheet '{NOMBRE_SPREADSHEET}'. "
            "Créalo, compártelo con el correo de la cuenta de servicio, "
            "y corre setup_sheet.py para inicializar las pestañas."
        ) from exc


def get_or_create_worksheet(nombre_hoja: str):
    """Devuelve la pestaña; si no existe, la crea con los encabezados de config.py."""
    sh = _get_spreadsheet()
    try:
        return sh.worksheet(nombre_hoja)
    except gspread.WorksheetNotFound:
        columnas = HOJAS[nombre_hoja]
        ws = sh.add_worksheet(title=nombre_hoja, rows=1000, cols=len(columnas) + 2)
        ws.append_row(columnas)
        return ws


def _limpiar_cache_datos():
    leer_hoja.clear()


@st.cache_data(ttl=30, show_spinner=False)
def leer_hoja(nombre_hoja: str) -> pd.DataFrame:
    """Lee una pestaña completa como DataFrame (cacheado 30s para no saturar la API)."""
    ws = get_or_create_worksheet(nombre_hoja)
    registros = ws.get_all_records()
    columnas = HOJAS[nombre_hoja]
    if not registros:
        return pd.DataFrame(columns=columnas)
    df = pd.DataFrame(registros)
    for col in columnas:
        if col not in df.columns:
            df[col] = ""
    return df[columnas]


def agregar_fila(nombre_hoja: str, datos: dict):
    """Agrega una fila nueva. `datos` debe traer (al menos) las columnas clave."""
    ws = get_or_create_worksheet(nombre_hoja)
    columnas = HOJAS[nombre_hoja]
    fila = [datos.get(col, "") for col in columnas]
    # RAW evita que Google Sheets reformatee automáticamente fechas o IDs
    # (por ejemplo, convirtiendo "2026-09-09" a otro formato de fecha según
    # la configuración regional de la hoja).
    ws.append_row(fila, value_input_option="RAW")
    _limpiar_cache_datos()


def actualizar_fila_por_id(nombre_hoja: str, columna_id: str, valor_id, cambios: dict) -> bool:
    """Actualiza la primera fila cuya `columna_id` coincida con `valor_id`.
    Devuelve True si encontró y actualizó la fila, False si no la encontró."""
    ws = get_or_create_worksheet(nombre_hoja)
    columnas = HOJAS[nombre_hoja]
    idx_col_id = columnas.index(columna_id) + 1  # 1-indexed para gspread
    celdas = ws.col_values(idx_col_id)
    fila_objetivo = None
    for i, valor in enumerate(celdas[1:], start=2):  # fila 1 = encabezados
        if str(valor) == str(valor_id):
            fila_objetivo = i
            break
    if fila_objetivo is None:
        return False
    for col, val in cambios.items():
        if col in columnas:
            idx_col = columnas.index(col) + 1
            ws.update_cell(fila_objetivo, idx_col, val)
    _limpiar_cache_datos()
    return True


def eliminar_fila_por_id(nombre_hoja: str, columna_id: str, valor_id) -> bool:
    ws = get_or_create_worksheet(nombre_hoja)
    columnas = HOJAS[nombre_hoja]
    idx_col_id = columnas.index(columna_id) + 1
    celdas = ws.col_values(idx_col_id)
    for i, valor in enumerate(celdas[1:], start=2):
        if str(valor) == str(valor_id):
            ws.delete_rows(i)
            _limpiar_cache_datos()
            return True
    return False


def siguiente_id(nombre_hoja: str, columna_id: str, prefijo: str = "") -> str:
    """Genera un ID incremental simple: PREFIJO0001, PREFIJO0002, ..."""
    df = leer_hoja(nombre_hoja)
    if df.empty:
        numero = 1
    else:
        numeros = []
        for v in df[columna_id]:
            v = str(v).replace(prefijo, "")
            if v.isdigit():
                numeros.append(int(v))
        numero = (max(numeros) + 1) if numeros else 1
    return f"{prefijo}{numero:04d}"


def timestamp_hoy():
    ahora = datetime.now()
    return ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S")
