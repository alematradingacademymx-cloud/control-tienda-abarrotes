"""Módulo de Ventas diarias: registra ventas por sección/producto y
descuenta automáticamente el inventario. Alimenta el Corte de Caja."""

from datetime import datetime

import pandas as pd
import streamlit as st

from config import METODOS_PAGO
from sheets_connector import (
    leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id, timestamp_hoy,
)
from auth import usuario_actual


def render():
    st.header("🧾 Ventas diarias")

    inventario = leer_hoja("Inventario")
    if inventario.empty:
        st.info("Primero registra productos en el módulo de Inventario.")
        return

    inventario["stock_actual_num"] = pd.to_numeric(inventario["stock_actual"], errors="coerce").fillna(0)

    st.subheader("Registrar venta")
    secciones = sorted(inventario["seccion"].dropna().unique().tolist())
    col1, col2 = st.columns(2)
    with col1:
        seccion_sel = st.selectbox("Sección", secciones)
    productos_seccion = inventario[inventario["seccion"] == seccion_sel]
    productos_disponibles = productos_seccion[productos_seccion["stock_actual_num"] > 0]

    if productos_disponibles.empty:
        st.warning("No hay productos con stock disponible en esta sección.")
    else:
        with col2:
            opciones_producto = (
                productos_disponibles["nombre_producto"]
                + " (stock: " + productos_disponibles["stock_actual_num"].astype(str) + ")"
            )
            seleccion = st.selectbox("Producto", opciones_producto)
        nombre_producto = seleccion.split(" (stock:")[0]
        fila_producto = productos_disponibles[productos_disponibles["nombre_producto"] == nombre_producto].iloc[0]

        precio_unitario = float(fila_producto["precio_venta"] or 0)
        stock_disp = float(fila_producto["stock_actual_num"])

        with st.form("form_registrar_venta", clear_on_submit=True):
            colc1, colc2, colc3 = st.columns(3)
            with colc1:
                cantidad = st.number_input("Cantidad", min_value=0.0, max_value=stock_disp, step=1.0, value=1.0)
            with colc2:
                st.metric("Precio unitario", f"${precio_unitario:,.2f}")
            with colc3:
                st.metric("Total", f"${precio_unitario * cantidad:,.2f}")

            metodo_pago = st.radio("Método de pago", METODOS_PAGO, horizontal=True)
            vender = st.form_submit_button("✅ Registrar venta")

            if vender:
                if cantidad <= 0:
                    st.error("La cantidad debe ser mayor a cero.")
                elif cantidad > stock_disp:
                    st.error("No hay suficiente stock para esa cantidad.")
                else:
                    fecha, hora = timestamp_hoy()
                    id_venta = siguiente_id("Ventas", "id_venta", prefijo="V")
                    total = precio_unitario * cantidad
                    agregar_fila("Ventas", {
                        "id_venta": id_venta,
                        "fecha": fecha,
                        "hora": hora,
                        "usuario": usuario_actual(),
                        "seccion": seccion_sel,
                        "id_producto": fila_producto["id_producto"],
                        "producto": nombre_producto,
                        "cantidad": cantidad,
                        "precio_unitario": precio_unitario,
                        "total": total,
                        "metodo_pago": metodo_pago,
                        "turno": "",
                    })
                    nuevo_stock = stock_disp - cantidad
                    actualizar_fila_por_id("Inventario", "id_producto", fila_producto["id_producto"], {
                        "stock_actual": nuevo_stock,
                        "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    st.success(f"Venta registrada: {cantidad} x {nombre_producto} = ${total:,.2f} ({metodo_pago})")
                    st.rerun()

    st.divider()
    st.subheader("Ventas de hoy")
    ventas = leer_hoja("Ventas")
    fecha_hoy, _ = timestamp_hoy()
    ventas_hoy = ventas[ventas["fecha"] == fecha_hoy].copy()

    if ventas_hoy.empty:
        st.info("Aún no hay ventas registradas hoy.")
    else:
        ventas_hoy["total_num"] = pd.to_numeric(ventas_hoy["total"], errors="coerce").fillna(0)
        total_dia = ventas_hoy["total_num"].sum()
        resumen = ventas_hoy.groupby("metodo_pago")["total_num"].sum().reindex(METODOS_PAGO, fill_value=0)

        colr1, colr2, colr3, colr4 = st.columns(4)
        colr1.metric("Total del día", f"${total_dia:,.2f}")
        for col, metodo in zip((colr2, colr3, colr4), METODOS_PAGO):
            col.metric(metodo, f"${resumen.get(metodo, 0):,.2f}")

        st.dataframe(
            ventas_hoy[["hora", "usuario", "seccion", "producto", "cantidad", "precio_unitario", "total", "metodo_pago"]],
            use_container_width=True,
            hide_index=True,
        )
