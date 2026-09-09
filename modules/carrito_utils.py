"""Utilidades de carrito de productos, compartidas entre Ventas diarias
(venta de mostrador) y Mensajería (venta a domicilio) — así ambas registran
la venta exactamente de la misma forma: se arma un carrito con uno o varios
productos (por escáner o buscando manualmente) y al confirmar se escribe una
fila por producto en 'Ventas' (todas con el mismo id_venta) y se descuenta
el inventario.

Cada pantalla que use este módulo debe pasar una `clave` distinta (el
nombre de la llave en session_state) para que sus carritos no se mezclen, y
un `key_prefix` distinto para que los widgets de Streamlit no choquen entre
pantallas."""

from datetime import datetime

import pandas as pd
import streamlit as st

from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id, timestamp_hoy
from auth import usuario_actual


def obtener_carrito(clave: str) -> list:
    if clave not in st.session_state:
        st.session_state[clave] = []
    return st.session_state[clave]


def cantidad_en_carrito(clave: str, id_producto) -> float:
    return sum(item["cantidad"] for item in obtener_carrito(clave) if item["id_producto"] == id_producto)


def agregar_al_carrito(clave: str, fila_producto: dict, seccion: str, cantidad: float, precio_unitario: float):
    costo_unitario = float(pd.to_numeric(fila_producto.get("costo_unitario", 0), errors="coerce") or 0)
    obtener_carrito(clave).append({
        "id_producto": fila_producto["id_producto"],
        "nombre_producto": fila_producto["nombre_producto"],
        "seccion": seccion,
        "cantidad": cantidad,
        "precio_unitario": precio_unitario,
        "costo_unitario": costo_unitario,
        "subtotal": precio_unitario * cantidad,
    })


def quitar_del_carrito(clave: str, indice: int):
    carrito = obtener_carrito(clave)
    if 0 <= indice < len(carrito):
        carrito.pop(indice)


def vaciar_carrito(clave: str):
    st.session_state[clave] = []


def total_carrito(clave: str) -> float:
    return sum(item["subtotal"] for item in obtener_carrito(clave))


def registrar_venta_carrito(clave: str, metodo_pago: str, turno: str = "") -> str:
    """Escribe una fila en 'Ventas' por cada producto del carrito indicado
    (mismo id_venta para todas, como líneas de un mismo ticket), descuenta
    el inventario, vacía el carrito y devuelve el id_venta generado.
    Si el carrito está vacío, no escribe nada y devuelve ''."""
    carrito = obtener_carrito(clave)
    if not carrito:
        return ""

    fecha, hora = timestamp_hoy()
    id_venta = siguiente_id("Ventas", "id_venta", prefijo="V")
    usuario = usuario_actual()

    for item in carrito:
        ganancia = (item["precio_unitario"] - item["costo_unitario"]) * item["cantidad"]
        agregar_fila("Ventas", {
            "id_venta": id_venta,
            "fecha": fecha,
            "hora": hora,
            "usuario": usuario,
            "seccion": item["seccion"],
            "id_producto": item["id_producto"],
            "producto": item["nombre_producto"],
            "cantidad": item["cantidad"],
            "precio_unitario": item["precio_unitario"],
            "total": item["subtotal"],
            "metodo_pago": metodo_pago,
            "turno": turno,
            "costo_unitario": item["costo_unitario"],
            "ganancia": ganancia,
        })

    cantidades_por_producto = {}
    for item in carrito:
        cantidades_por_producto[item["id_producto"]] = (
            cantidades_por_producto.get(item["id_producto"], 0) + item["cantidad"]
        )

    inventario_actual = leer_hoja("Inventario")
    for id_producto, cantidad_vendida in cantidades_por_producto.items():
        fila_inv = inventario_actual[inventario_actual["id_producto"] == id_producto]
        if fila_inv.empty:
            continue
        stock_actual = pd.to_numeric(fila_inv.iloc[0].get("stock_actual", 0), errors="coerce")
        stock_actual = float(stock_actual) if pd.notna(stock_actual) else 0.0
        actualizar_fila_por_id("Inventario", "id_producto", id_producto, {
            "stock_actual": stock_actual - cantidad_vendida,
            "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    vaciar_carrito(clave)
    return id_venta


def render_agregar_por_escaner(clave: str, inventario: pd.DataFrame, key_prefix: str):
    """Widget de escaneo de código de barras para agregar productos al
    carrito `clave`."""
    st.caption("Coloca el cursor en el siguiente campo y escanea el código de barras del producto.")

    if "codigo_barras" not in inventario.columns:
        st.warning("Todavía no hay productos con código de barras registrado. Agrégalo desde el módulo de Inventario.")
        return

    estado_key = f"{key_prefix}_producto_escaneado"

    with st.form(f"{key_prefix}_form_escanear_codigo", clear_on_submit=True):
        codigo = st.text_input("Código de barras", key=f"{key_prefix}_input_codigo_barras")
        buscar = st.form_submit_button("Buscar")

    if buscar:
        codigo = (codigo or "").strip()
        if not codigo:
            st.warning("Escanea o escribe un código antes de buscar.")
        else:
            coincidencias = inventario[inventario["codigo_barras"].astype(str).str.strip() == codigo]
            if coincidencias.empty:
                st.error(f"No se encontró ningún producto con el código '{codigo}'.")
                st.session_state.pop(estado_key, None)
            else:
                st.session_state[estado_key] = coincidencias.iloc[0].to_dict()

    producto = st.session_state.get(estado_key)
    if not producto:
        return

    stock_disp = float(pd.to_numeric(producto.get("stock_actual", 0), errors="coerce") or 0)
    stock_disp -= cantidad_en_carrito(clave, producto["id_producto"])
    precio_unitario = float(pd.to_numeric(producto.get("precio_venta", 0), errors="coerce") or 0)

    if stock_disp <= 0:
        st.error(f"'{producto['nombre_producto']}' ya no tiene stock disponible (o ya lo agregaste todo al carrito).")
        return

    st.success(f"Producto encontrado: **{producto['nombre_producto']}** — Sección: {producto['seccion']} — Stock disponible: {stock_disp:g}")

    # Fuera de un form: así el subtotal se recalcula al instante mientras
    # cambias la cantidad, en vez de quedarse fijo hasta que envíes el form.
    cantidad_key = f"{key_prefix}_cantidad_escaner"
    colc1, colc2, colc3 = st.columns(3)
    with colc1:
        cantidad = st.number_input("Cantidad", min_value=0.0, max_value=stock_disp, step=1.0, value=1.0, key=cantidad_key)
    with colc2:
        st.metric("Precio unitario", f"${precio_unitario:,.2f}")
    with colc3:
        st.metric("Subtotal", f"${precio_unitario * cantidad:,.2f}")

    if st.button("➕ Agregar al carrito", key=f"{key_prefix}_btn_agregar_escaner"):
        if cantidad <= 0:
            st.error("La cantidad debe ser mayor a cero.")
        elif cantidad > stock_disp:
            st.error("No hay suficiente stock para esa cantidad.")
        else:
            agregar_al_carrito(clave, producto, producto["seccion"], cantidad, precio_unitario)
            st.session_state.pop(estado_key, None)
            st.session_state.pop(cantidad_key, None)
            st.toast(f"{cantidad:g} x {producto['nombre_producto']} agregado al carrito.", icon="🛒")
            st.rerun()

    if st.button("Cancelar / escanear otro producto", key=f"{key_prefix}_cancelar_escaneo"):
        st.session_state.pop(estado_key, None)
        st.rerun()


def render_agregar_manual(clave: str, inventario: pd.DataFrame, key_prefix: str):
    """Widget de búsqueda manual (sección + producto) para agregar productos
    al carrito `clave`."""
    secciones = sorted(inventario["seccion"].dropna().unique().tolist())
    col1, col2 = st.columns(2)
    with col1:
        seccion_sel = st.selectbox("Sección", secciones, key=f"{key_prefix}_seccion_manual")
    productos_seccion = inventario[inventario["seccion"] == seccion_sel]
    productos_disponibles = productos_seccion[productos_seccion["stock_actual_num"] > 0]

    if productos_disponibles.empty:
        st.warning("No hay productos con stock disponible en esta sección.")
        return

    with col2:
        opciones_producto = (
            productos_disponibles["nombre_producto"]
            + " (stock: " + productos_disponibles["stock_actual_num"].astype(str) + ")"
        )
        seleccion = st.selectbox("Producto", opciones_producto, key=f"{key_prefix}_producto_manual")
    nombre_producto = seleccion.split(" (stock:")[0]
    fila_producto = productos_disponibles[productos_disponibles["nombre_producto"] == nombre_producto].iloc[0]

    precio_unitario = float(fila_producto["precio_venta"] or 0)
    stock_disp = float(fila_producto["stock_actual_num"]) - cantidad_en_carrito(clave, fila_producto["id_producto"])

    if stock_disp <= 0:
        st.warning(f"Ya agregaste al carrito todo el stock disponible de '{nombre_producto}'.")
        return

    # Fuera de un form: así el subtotal se recalcula al instante mientras
    # cambias la cantidad, en vez de quedarse fijo hasta que envíes el form.
    cantidad_key = f"{key_prefix}_cantidad_manual"
    colc1, colc2, colc3 = st.columns(3)
    with colc1:
        cantidad = st.number_input("Cantidad", min_value=0.0, max_value=stock_disp, step=1.0, value=1.0, key=cantidad_key)
    with colc2:
        st.metric("Precio unitario", f"${precio_unitario:,.2f}")
    with colc3:
        st.metric("Subtotal", f"${precio_unitario * cantidad:,.2f}")

    if st.button("➕ Agregar al carrito", key=f"{key_prefix}_btn_agregar_manual"):
        if cantidad <= 0:
            st.error("La cantidad debe ser mayor a cero.")
        elif cantidad > stock_disp:
            st.error("No hay suficiente stock para esa cantidad.")
        else:
            agregar_al_carrito(clave, fila_producto, seccion_sel, cantidad, precio_unitario)
            st.session_state.pop(cantidad_key, None)
            st.toast(f"{cantidad:g} x {nombre_producto} agregado al carrito.", icon="🛒")
            st.rerun()


def render_lista_carrito(clave: str, key_prefix: str) -> float:
    """Muestra los productos ya agregados con un botón para quitar cada uno,
    y el total. Devuelve el total actual (0.0 si el carrito está vacío)."""
    carrito = obtener_carrito(clave)
    if not carrito:
        st.info("Todavía no has agregado productos (usa el escáner o la búsqueda manual de arriba).")
        return 0.0

    for i, item in enumerate(carrito):
        col_desc, col_quitar = st.columns([6, 1])
        col_desc.write(f"**{item['cantidad']:g}** x {item['nombre_producto']} — ${item['subtotal']:,.2f}")
        if col_quitar.button("❌", key=f"{key_prefix}_quitar_{i}", help="Quitar del carrito"):
            quitar_del_carrito(clave, i)
            st.rerun()

    total = total_carrito(clave)
    st.metric("Total de productos", f"${total:,.2f}")
    return total
