"""Módulo de Ventas diarias: arma un carrito con varios productos (por
escáner o buscando manualmente), y hasta el final se confirma la venta
completa: se elige el método de pago y, si es efectivo, se calcula el
cambio exacto a entregar. Al confirmar, se registra una fila por producto
(todas con el mismo id_venta, como líneas de un mismo ticket) y se
descuenta automáticamente el inventario. Alimenta el Corte de Caja."""

from datetime import datetime

import pandas as pd
import streamlit as st

from config import METODOS_PAGO
from sheets_connector import (
    leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id, timestamp_hoy,
)
from auth import usuario_actual


# ---------------------------------------------------------------------------
# Carrito de la venta actual (vive en session_state mientras se arma el
# ticket; se vacía en cuanto se confirma o se cancela la venta).
# ---------------------------------------------------------------------------

def _carrito() -> list:
    if "carrito_venta" not in st.session_state:
        st.session_state["carrito_venta"] = []
    return st.session_state["carrito_venta"]


def _cantidad_en_carrito(id_producto) -> float:
    """Cuánto de este producto ya está en el carrito (para no dejar agregar
    más de lo que realmente hay en existencia entre varias líneas del mismo
    producto)."""
    return sum(item["cantidad"] for item in _carrito() if item["id_producto"] == id_producto)


def _agregar_al_carrito(fila_producto: dict, seccion: str, cantidad: float, precio_unitario: float):
    costo_unitario = float(pd.to_numeric(fila_producto.get("costo_unitario", 0), errors="coerce") or 0)
    _carrito().append({
        "id_producto": fila_producto["id_producto"],
        "nombre_producto": fila_producto["nombre_producto"],
        "seccion": seccion,
        "cantidad": cantidad,
        "precio_unitario": precio_unitario,
        "costo_unitario": costo_unitario,
        "subtotal": precio_unitario * cantidad,
    })


def _total_carrito() -> float:
    return sum(item["subtotal"] for item in _carrito())


def _registrar_venta_carrito(metodo_pago: str) -> str:
    """Escribe una fila en 'Ventas' por cada producto del carrito, todas con
    el mismo id_venta (como líneas de un mismo ticket), descuenta el
    inventario y vacía el carrito. Devuelve el id_venta generado."""
    carrito = _carrito()
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
            "turno": "",
            "costo_unitario": item["costo_unitario"],
            "ganancia": ganancia,
        })

    # Un solo ajuste de stock por producto (sumando cantidades si el mismo
    # producto quedó en más de una línea del carrito).
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

    st.session_state["carrito_venta"] = []
    return id_venta


# ---------------------------------------------------------------------------
# Agregar productos al carrito: por escáner o buscando manualmente.
# ---------------------------------------------------------------------------

def _render_venta_por_escaner(inventario: pd.DataFrame):
    st.caption("Coloca el cursor en el siguiente campo y escanea el código de barras del producto.")

    if "codigo_barras" not in inventario.columns:
        st.warning("Todavía no hay productos con código de barras registrado. Agrégalo desde el módulo de Inventario.")
        return

    with st.form("form_escanear_codigo", clear_on_submit=True):
        codigo = st.text_input("Código de barras", key="input_codigo_barras")
        buscar = st.form_submit_button("Buscar")

    if buscar:
        codigo = (codigo or "").strip()
        if not codigo:
            st.warning("Escanea o escribe un código antes de buscar.")
        else:
            coincidencias = inventario[inventario["codigo_barras"].astype(str).str.strip() == codigo]
            if coincidencias.empty:
                st.error(f"No se encontró ningún producto con el código '{codigo}'.")
                st.session_state.pop("producto_escaneado", None)
            else:
                st.session_state["producto_escaneado"] = coincidencias.iloc[0].to_dict()

    producto = st.session_state.get("producto_escaneado")
    if not producto:
        return

    stock_disp = float(pd.to_numeric(producto.get("stock_actual", 0), errors="coerce") or 0)
    stock_disp -= _cantidad_en_carrito(producto["id_producto"])
    precio_unitario = float(pd.to_numeric(producto.get("precio_venta", 0), errors="coerce") or 0)

    if stock_disp <= 0:
        st.error(f"'{producto['nombre_producto']}' ya no tiene stock disponible (o ya agregaste todo lo que había al carrito).")
        return

    st.success(f"Producto encontrado: **{producto['nombre_producto']}** — Sección: {producto['seccion']} — Stock disponible: {stock_disp:g}")

    with st.form("form_agregar_carrito_escaner", clear_on_submit=True):
        colc1, colc2, colc3 = st.columns(3)
        with colc1:
            cantidad = st.number_input("Cantidad", min_value=0.0, max_value=stock_disp, step=1.0, value=1.0)
        with colc2:
            st.metric("Precio unitario", f"${precio_unitario:,.2f}")
        with colc3:
            st.metric("Subtotal", f"${precio_unitario * cantidad:,.2f}")

        agregar = st.form_submit_button("➕ Agregar al carrito")

        if agregar:
            if cantidad <= 0:
                st.error("La cantidad debe ser mayor a cero.")
            elif cantidad > stock_disp:
                st.error("No hay suficiente stock para esa cantidad.")
            else:
                _agregar_al_carrito(producto, producto["seccion"], cantidad, precio_unitario)
                st.session_state.pop("producto_escaneado", None)
                st.toast(f"{cantidad:g} x {producto['nombre_producto']} agregado al carrito.", icon="🛒")
                st.rerun()

    if st.button("Cancelar / escanear otro producto", key="cancelar_escaneo"):
        st.session_state.pop("producto_escaneado", None)
        st.rerun()


def _render_venta_manual(inventario: pd.DataFrame):
    secciones = sorted(inventario["seccion"].dropna().unique().tolist())
    col1, col2 = st.columns(2)
    with col1:
        seccion_sel = st.selectbox("Sección", secciones, key="seccion_manual")
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
        seleccion = st.selectbox("Producto", opciones_producto, key="producto_manual")
    nombre_producto = seleccion.split(" (stock:")[0]
    fila_producto = productos_disponibles[productos_disponibles["nombre_producto"] == nombre_producto].iloc[0]

    precio_unitario = float(fila_producto["precio_venta"] or 0)
    stock_disp = float(fila_producto["stock_actual_num"]) - _cantidad_en_carrito(fila_producto["id_producto"])

    if stock_disp <= 0:
        st.warning(f"Ya agregaste al carrito todo el stock disponible de '{nombre_producto}'.")
        return

    with st.form("form_agregar_carrito_manual", clear_on_submit=True):
        colc1, colc2, colc3 = st.columns(3)
        with colc1:
            cantidad = st.number_input("Cantidad", min_value=0.0, max_value=stock_disp, step=1.0, value=1.0)
        with colc2:
            st.metric("Precio unitario", f"${precio_unitario:,.2f}")
        with colc3:
            st.metric("Subtotal", f"${precio_unitario * cantidad:,.2f}")

        agregar = st.form_submit_button("➕ Agregar al carrito")

        if agregar:
            if cantidad <= 0:
                st.error("La cantidad debe ser mayor a cero.")
            elif cantidad > stock_disp:
                st.error("No hay suficiente stock para esa cantidad.")
            else:
                _agregar_al_carrito(fila_producto, seccion_sel, cantidad, precio_unitario)
                st.toast(f"{cantidad:g} x {nombre_producto} agregado al carrito.", icon="🛒")
                st.rerun()


# ---------------------------------------------------------------------------
# Carrito + confirmación de la venta (método de pago y cambio si es efectivo)
# ---------------------------------------------------------------------------

def _render_confirmacion_venta(total: float):
    st.markdown("#### Confirmar venta")

    metodo_pago = st.radio(
        "Método de pago", METODOS_PAGO, horizontal=True, key="metodo_pago_carrito",
    )

    cambio = None
    recibido = 0.0
    if metodo_pago == "Efectivo":
        recibido = st.number_input(
            "¿Cuánto dinero te dio el cliente?",
            min_value=0.0, step=10.0, format="%.2f", key="recibido_efectivo",
        )
        cambio = recibido - total
        if recibido == 0:
            st.caption("Escribe el monto recibido para calcular el cambio.")
        elif cambio < 0:
            st.error(f"Faltan ${abs(cambio):,.2f} — lo recibido es menor al total (${total:,.2f}).")
        else:
            st.success(f"💰 Cambio a entregar: ${cambio:,.2f}")

    col_a, col_b = st.columns(2)
    confirmar = col_a.button("✅ Confirmar y registrar venta", type="primary", key="btn_registrar_venta_final")
    cancelar = col_b.button("Cancelar", key="btn_cancelar_venta_final")

    if cancelar:
        st.session_state["mostrar_confirmacion_venta"] = False
        st.rerun()

    if confirmar:
        if metodo_pago == "Efectivo" and recibido < total:
            st.error("El monto recibido debe cubrir el total antes de confirmar.")
        else:
            id_venta = _registrar_venta_carrito(metodo_pago)
            st.session_state["mostrar_confirmacion_venta"] = False
            st.session_state.pop("recibido_efectivo", None)
            mensaje = f"Venta {id_venta} registrada por ${total:,.2f} ({metodo_pago})."
            if cambio is not None and cambio >= 0:
                mensaje += f" Cambio: ${cambio:,.2f}."
            st.toast(mensaje, icon="✅")
            st.rerun()


def _render_carrito():
    carrito = _carrito()
    st.subheader("🛒 Carrito de la venta actual")

    if not carrito:
        st.info("Todavía no has agregado productos a esta venta (usa el escáner o la búsqueda manual de arriba).")
        return

    for i, item in enumerate(carrito):
        col_desc, col_quitar = st.columns([6, 1])
        col_desc.write(f"**{item['cantidad']:g}** x {item['nombre_producto']} — ${item['subtotal']:,.2f}")
        if col_quitar.button("❌", key=f"quitar_carrito_{i}", help="Quitar del carrito"):
            carrito.pop(i)
            st.rerun()

    total = _total_carrito()
    col_total, col_vaciar = st.columns([3, 1])
    col_total.metric("Total a cobrar", f"${total:,.2f}")
    if col_vaciar.button("🗑️ Vaciar carrito"):
        st.session_state["carrito_venta"] = []
        st.session_state["mostrar_confirmacion_venta"] = False
        st.rerun()

    if not st.session_state.get("mostrar_confirmacion_venta"):
        if st.button("💵 Confirmar venta", type="primary", key="btn_abrir_confirmacion"):
            st.session_state["mostrar_confirmacion_venta"] = True
            st.rerun()
    else:
        st.divider()
        _render_confirmacion_venta(total)


def render():
    st.header("🧾 Ventas diarias")

    inventario = leer_hoja("Inventario")
    if inventario.empty:
        st.info("Primero registra productos en el módulo de Inventario.")
        return

    inventario["stock_actual_num"] = pd.to_numeric(inventario["stock_actual"], errors="coerce").fillna(0)

    tab_escaner, tab_manual = st.tabs(["📷 Escanear código de barras", "🔍 Buscar manualmente"])
    with tab_escaner:
        _render_venta_por_escaner(inventario)
    with tab_manual:
        _render_venta_manual(inventario)

    st.divider()
    _render_carrito()

    st.divider()
    st.subheader("Ventas de hoy")
    ventas = leer_hoja("Ventas")
    fecha_hoy, _ = timestamp_hoy()
    ventas_hoy = ventas[ventas["fecha"] == fecha_hoy].copy()

    if ventas_hoy.empty:
        st.info("Aún no hay ventas registradas hoy.")
    else:
        ventas_hoy["total_num"] = pd.to_numeric(ventas_hoy["total"], errors="coerce").fillna(0)
        ventas_hoy["ganancia_num"] = pd.to_numeric(ventas_hoy["ganancia"], errors="coerce").fillna(0)
        total_dia = ventas_hoy["total_num"].sum()
        ganancia_dia = ventas_hoy["ganancia_num"].sum()
        resumen = ventas_hoy.groupby("metodo_pago")["total_num"].sum().reindex(METODOS_PAGO, fill_value=0)

        colr1, colr2, colr3, colr4, colr5 = st.columns(5)
        colr1.metric("Total del día", f"${total_dia:,.2f}")
        for col, metodo in zip((colr2, colr3, colr4), METODOS_PAGO):
            col.metric(metodo, f"${resumen.get(metodo, 0):,.2f}")
        colr5.metric("Ganancia estimada", f"${ganancia_dia:,.2f}")

        st.dataframe(
            ventas_hoy[["id_venta", "hora", "usuario", "seccion", "producto", "cantidad", "precio_unitario", "total", "metodo_pago", "ganancia"]],
            use_container_width=True,
            hide_index=True,
        )
