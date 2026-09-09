"""
Script de inicialización: crea (si no existe) el Google Sheet que usará la
app, con todas las pestañas y encabezados definidos en config.py.

Uso:
    python setup_sheet.py tu_correo@gmail.com

Requisitos previos:
    1. Haber creado un proyecto en Google Cloud y una cuenta de servicio,
       con la Google Sheets API y Google Drive API habilitadas.
    2. Haber descargado el archivo JSON de la cuenta de servicio y
       guardarlo en esta misma carpeta como "credentials.json".
    Ver README.md para el paso a paso detallado.

Qué hace este script:
    - Si el Google Sheet "TiendaAbarrotes_DB" no existe, lo crea (queda
      en el Drive de la cuenta de servicio).
    - Lo comparte como "editor" con el correo de Gmail que le pases como
      argumento, para que tú puedas verlo y abrirlo desde tu propia cuenta
      de Google.
    - Crea todas las pestañas (Usuarios, Inventario, Ventas, etc.) con sus
      encabezados, si todavía no existen.
"""

import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

from config import HOJAS, NOMBRE_SPREADSHEET

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")


def main():
    if len(sys.argv) < 2:
        print("Uso: python setup_sheet.py tu_correo@gmail.com")
        sys.exit(1)
    correo_usuario = sys.argv[1]

    if not os.path.exists(CREDENTIALS_FILE):
        print(
            f"No se encontró {CREDENTIALS_FILE}.\n"
            "Descarga el JSON de tu cuenta de servicio de Google Cloud y "
            "guárdalo en esta carpeta como 'credentials.json'. Ver README.md."
        )
        sys.exit(1)

    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        info = json.load(f)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)

    try:
        sh = client.open(NOMBRE_SPREADSHEET)
        print(f"El Google Sheet '{NOMBRE_SPREADSHEET}' ya existe. Continuando...")
    except gspread.SpreadsheetNotFound:
        print(f"Creando el Google Sheet '{NOMBRE_SPREADSHEET}'...")
        sh = client.create(NOMBRE_SPREADSHEET)

    print(f"Compartiendo el Sheet con {correo_usuario} como editor...")
    sh.share(correo_usuario, perm_type="user", role="writer")

    hojas_existentes = {ws.title for ws in sh.worksheets()}

    for nombre_hoja, columnas in HOJAS.items():
        if nombre_hoja in hojas_existentes:
            print(f"  - Pestaña '{nombre_hoja}' ya existe, se deja igual.")
            continue
        print(f"  - Creando pestaña '{nombre_hoja}'...")
        ws = sh.add_worksheet(title=nombre_hoja, rows=1000, cols=len(columnas) + 2)
        ws.append_row(columnas)

    # Elimina la hoja "Sheet1" / "Hoja 1" por defecto si quedó vacía y ya
    # existen las demás pestañas.
    for nombre_default in ("Sheet1", "Hoja 1", "Hoja1"):
        try:
            hoja_default = sh.worksheet(nombre_default)
            if hoja_default.title not in HOJAS:
                sh.del_worksheet(hoja_default)
                print(f"  - Pestaña por defecto '{nombre_default}' eliminada.")
        except gspread.WorksheetNotFound:
            pass

    print("\n✅ Listo. Abre tu Google Drive con la cuenta "
          f"{correo_usuario} y busca el archivo '{NOMBRE_SPREADSHEET}'.")
    print(f"URL del Sheet: {sh.url}")


if __name__ == "__main__":
    main()
