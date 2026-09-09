"""Módulo de Ventas diarias: registra ventas por sección/producto (o
escaneando el código de barras) y descuenta automáticamente el inventario.
Alimenta el Corte de Caja."""

from datetime import datetime

import pandas as pd
import streamlit as st

from config import METODOS_PAGO
from sheets_connector import (
    leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id, timestamp_hoy,
)
from auth import usuario_actual


def _registrar_venta(fila_producto: dict, seccion: str, cantidad: float, precio_unitario: float, metodo_pago: str):
    fecha, hora = timestamp_hoy()
    id_venta = siguiente_id("Ventas", "id_venta", prefijo="V")
    total = precio_unitario * cantidad
    costo_unitario = float(pd.to_numeric(fila_producto.get("costo_unitario", 0), errors="coerce") or 0)
    ganancia = (precio_unitario - costo_unitario) * cantidad
    agregar_fila("Ventas", {
        "id_venta": id_venta,
        "fecha": fecha,
        "hora": hora,
        "usuario": usuario_actual(),
        "seccion": seccion,
        "id_producto": fila_producto["id_producto"],
        "producto": fila_producto["nombre_producto"],
        "cantidad": cantidad,
        "precio_unitario": precio_unitario,
        "total": total,
        "metodo_pago": metodo_pago,
        "turno": "",
        "costo_unitario": costo_unitario,
        "ganancia": ganancia,
    })
    stock_actual = pd.to_numeric(fila_producto.get("stock_actual", 0), errors="coerce") or 0
    nuevo_stock = float(stock_actual) - cantidad
    actualizar_fila_por_id("Inventario", "id_producto", fila_producto["id_producto"], {
        "stock_actual": nuevo_stock,
        "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return total


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
    precio_unitario = float(pd.to_numeric(producto.get("precio_venta", 0), errors="coerce") or 0)

    if stock_disp <= 0:
        st.error(f"'{producto['nombre_producto']}' no tiene stock disponible.")
        return

    st.success(f"Producto encontrado: **{producto['nombre_producto']}** — Sección: {producto['seccion']} — Stock disponible: {stock_disp:g}")

    with st.form("form_confirmar_venta_escaner"):
        colc1, colc2, colc3 = st.columns(3)
        with colc1:
            cantidad = st.number_input("Cantidad", min_value=0.0, max_value=stock_disp, step=1.0, value=1.0)
        with colc2:
            st.metric("Precio unitario", f"${precio_unitario:,.2f}")
        with colc3:
            st.metric("Total", f"${precio_unitario * cantidad:,.2f}")

        metodo_pago = st.radio("Método de pago", METODOS_PAGO, horizontal=True, key="metodo_pago_escaner")
        confirmar = st.form_submit_button("✅ Registrar venta")

        if confirmar:
            if cantidad <= 0:
                st.error("La cantidad debe ser mayor a cero.")
            elif cantidad > stock_disp:
                st.error("No hay suficiente stock para esa cantidad.")
            else:
                total = _registrar_venta(producto, producto["seccion"], cantidad, precio_unitario, metodo_pago)
                st.session_state.pop("producto_escaneado", None)
                st.success(f"Venta registrada: {cantidad:g} x {producto['nombre_producto']} = ${total:,.2f} ({metodo_pago})")
                st.rerun()

    if st.button("Cancelar / escanear otro producto"):
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
    stock_disp = float(fila_producto["stock_actual_num"])

    with st.form("form_registrar_venta_manual", clear_on_submit=True):
        colc1, colc2, colc3 = st.columns(3)
        with colc1:
            cantidad = st.number_input("Cantidad", min_value=0.0, max_value=stock_disp, step=1.0, value=1.0)
        with colc2:
            st.metric("Precio unitario", f"${precio_unitario:,.2f}")
        with colc3:
            st.metric("Total", f"${precio_unitario * cantidad:,.2f}")

        metodo_pago = st.radio("Método de pago", METODOS_PAGO, horizontal=True, key="metodo_pago_manual")
        vender = st.form_submit_button("✅ Registrar venta")

        if vender:
            if cantidad <= 0:
                st.error("La cantidad debe ser mayor a cero.")
            elif cantidad > stock_disp:
                st.error("No hay suficiente stock para esa cantidad.")
            else:
                total = _registrar_venta(fila_producto, seccion_sel, cantidad, precio_unitario, metodo_pago)
                st.success(f"Venta registrada: {cantidad:g} x {nombre_producto} = ${total:,.2f} ({metodo_pago})")
                st.rerun()


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
            ventas_hoy[["hora", "usuario", "seccion", "producto", "cantidad", "precio_unitario", "total", "metodo_pago", "ganancia"]],
            use_container_width=True,
            hide_index=True,
        )
