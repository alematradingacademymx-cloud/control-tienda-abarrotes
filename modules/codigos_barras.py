"""Generador de códigos de barras internos para productos que no traen uno
de fábrica (por ejemplo cigarros sueltos, dulces a granel, bolsitas de algún
material, etc.). Para esos productos se genera un código interno (se
reutiliza el id_producto, que ya es único) y se arma una hoja en PDF con
varias etiquetas listas para imprimir, recortar y pegar físicamente cerca
de la caja o del producto — así, al escanear esa etiqueta, la venta se
registra igual que cualquier otro producto y ya no se puede "olvidar" cobrar
algo suelto por no tener código."""

import io
import textwrap

import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128

from sheets_connector import actualizar_fila_por_id

MM = 2.83464567  # 1 mm en puntos (unidad que usa reportlab)

# Layout de la hoja: 3 columnas x 6 filas = 18 etiquetas por página tamaño carta.
COLUMNAS = 3
FILAS = 6
MARGEN = 0.5 * 72  # 0.5 pulgadas
ANCHO_PAGINA, ALTO_PAGINA = letter


def _codigo_interno(id_producto: str) -> str:
    """El código interno es simplemente el id_producto (ej. 'P0007'), que ya
    es único en el inventario y nunca choca con un código de barras real de
    fábrica (esos son siempre numéricos)."""
    return str(id_producto)


def asegurar_codigos_internos(productos_seleccionados: list) -> list:
    """Para cada producto de la lista (dicts con al menos id_producto,
    nombre_producto, codigo_barras, precio_venta) que no tenga ya un código
    de barras, le asigna uno interno y lo guarda en Inventario. Devuelve la
    misma lista con 'codigo_barras' ya actualizado en cada dict."""
    for producto in productos_seleccionados:
        codigo_actual = str(producto.get("codigo_barras", "") or "").strip()
        if not codigo_actual:
            nuevo_codigo = _codigo_interno(producto["id_producto"])
            actualizar_fila_por_id("Inventario", "id_producto", producto["id_producto"], {
                "codigo_barras": nuevo_codigo,
            })
            producto["codigo_barras"] = nuevo_codigo
    return productos_seleccionados


def _dibujar_etiqueta(c: canvas.Canvas, x: float, y: float, ancho: float, alto: float, producto: dict):
    """Dibuja una etiqueta (nombre + código de barras) dentro de la caja
    definida por (x, y) como esquina inferior izquierda, con el tamaño dado.
    Incluye un recuadro punteado para poder recortarla a mano."""
    c.setDash(2, 2)
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.rect(x, y, ancho, alto, stroke=1, fill=0)
    c.setDash()

    # Nombre del producto, envuelto a máximo 2 líneas.
    nombre = str(producto.get("nombre_producto", "")).strip()
    c.setFont("Helvetica-Bold", 8)
    lineas = textwrap.wrap(nombre, width=26)[:2]
    y_texto = y + alto - 12
    for linea in lineas:
        c.drawCentredString(x + ancho / 2, y_texto, linea)
        y_texto -= 10

    # Precio (si existe), chiquito, debajo del nombre.
    precio = pd.to_numeric(producto.get("precio_venta", 0), errors="coerce")
    if pd.notna(precio) and precio > 0:
        c.setFont("Helvetica", 7)
        c.drawCentredString(x + ancho / 2, y_texto - 2, f"${float(precio):,.2f}")
        y_texto -= 10

    # Código de barras, centrado en el espacio restante de la etiqueta.
    codigo = str(producto.get("codigo_barras", "")).strip()
    if not codigo:
        return
    barra = code128.Code128(codigo, barHeight=12 * MM, barWidth=0.35 * MM, humanReadable=True)
    bx = x + (ancho - barra.width) / 2
    by = y + 12
    barra.drawOn(c, bx, by)


def generar_pdf_etiquetas(productos: list) -> bytes:
    """Genera un PDF tamaño carta con una cuadrícula de etiquetas (nombre +
    código de barras) listas para imprimir y recortar. `productos` es una
    lista de dicts con id_producto, nombre_producto, codigo_barras y
    precio_venta."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    ancho_util = ANCHO_PAGINA - 2 * MARGEN
    alto_util = ALTO_PAGINA - 2 * MARGEN
    ancho_celda = ancho_util / COLUMNAS
    alto_celda = alto_util / FILAS
    por_pagina = COLUMNAS * FILAS

    for i, producto in enumerate(productos):
        pos_en_pagina = i % por_pagina
        if pos_en_pagina == 0 and i > 0:
            c.showPage()
        fila = pos_en_pagina // COLUMNAS
        col = pos_en_pagina % COLUMNAS
        x = MARGEN + col * ancho_celda
        y = ALTO_PAGINA - MARGEN - (fila + 1) * alto_celda
        _dibujar_etiqueta(c, x, y, ancho_celda, alto_celda, producto)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def render_tab(df: pd.DataFrame):
    st.caption(
        "Para productos que se venden sueltos y no traen código de fábrica "
        "(cigarros sueltos, dulces a granel, etc.), genera aquí un código de "
        "barras interno y descarga una hoja para imprimir, recortar y pegar "
        "cerca de la caja o del producto. Así, al escanearlo, la venta se "
        "registra igual que cualquier otro producto — ya no se puede pasar "
        "por alto."
    )

    if df.empty:
        st.info("Todavía no hay productos registrados en Inventario.")
        return

    solo_sin_codigo = st.checkbox("Mostrar solo productos sin código de barras", value=True)
    df_disponible = df.copy()
    if solo_sin_codigo:
        df_disponible = df_disponible[df_disponible["codigo_barras"].astype(str).str.strip() == ""]

    if df_disponible.empty:
        st.success("Todos tus productos ya tienen un código de barras asignado. ✅" if solo_sin_codigo else "No hay productos.")
        return

    opciones = (df_disponible["id_producto"] + " — " + df_disponible["nombre_producto"]).tolist()
    seleccionados = st.multiselect(
        "Selecciona los productos para generar/reimprimir su etiqueta",
        opciones,
        default=opciones if len(opciones) <= 18 else [],
        help="Se acomodan hasta 18 etiquetas por hoja tamaño carta.",
    )

    if not seleccionados:
        st.info("Selecciona al menos un producto para generar la hoja de etiquetas.")
        return

    ids_sel = [s.split(" — ")[0] for s in seleccionados]
    productos_sel = df_disponible[df_disponible["id_producto"].isin(ids_sel)].to_dict("records")

    num_paginas = -(-len(productos_sel) // 18)  # redondeo hacia arriba
    st.caption(f"Se generará {'1 hoja' if num_paginas == 1 else f'{num_paginas} hojas'} con {len(productos_sel)} etiqueta(s).")

    if st.button("🏷️ Generar códigos y preparar hoja para imprimir", type="primary"):
        with st.spinner("Generando códigos de barras..."):
            productos_sel = asegurar_codigos_internos(productos_sel)
            pdf_bytes = generar_pdf_etiquetas(productos_sel)
        st.session_state["pdf_etiquetas_generado"] = pdf_bytes
        st.toast(f"{len(productos_sel)} código(s) de barras listo(s).", icon="🏷️")

    if st.session_state.get("pdf_etiquetas_generado"):
        st.download_button(
            "⬇️ Descargar hoja de etiquetas (PDF)",
            data=st.session_state["pdf_etiquetas_generado"],
            file_name="codigos_de_barras.pdf",
            mime="application/pdf",
        )
