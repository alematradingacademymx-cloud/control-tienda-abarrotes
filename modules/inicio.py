"""Módulo de Inicio: panel resumen con lo más importante del día."""

import pandas as pd
import streamlit as st

from sheets_connector import leer_hoja, timestamp_hoy
from auth import nombre_actual, rol_actual


def render():
    st.header(f"👋 Hola, {nombre_actual()}")
    st.caption(f"Rol: {rol_actual()}")

    fecha_hoy, _ = timestamp_hoy()

    inventario = leer_hoja("Inventario")
    ventas = leer_hoja("Ventas")

    col1, col2, col3, col4 = st.columns(4)

    if not ventas.empty:
        ventas["total_num"] = pd.to_numeric(ventas["total"], errors="coerce").fillna(0)
        ventas_hoy = ventas[ventas["fecha"] == fecha_hoy]
        col1.metric("Ventas de hoy", f"${ventas_hoy['total_num'].sum():,.2f}")
        col2.metric("Tickets hoy", len(ventas_hoy))
    else:
        col1.metric("Ventas de hoy", "$0.00")
        col2.metric("Tickets hoy", 0)

    if not inventario.empty:
        inventario["stock_actual_num"] = pd.to_numeric(inventario["stock_actual"], errors="coerce").fillna(0)
        inventario["stock_minimo_num"] = pd.to_numeric(inventario["stock_minimo"], errors="coerce").fillna(0)
        bajo_stock = inventario[inventario["stock_actual_num"] <= inventario["stock_minimo_num"]]
        col3.metric("Productos", len(inventario))
        col4.metric("Bajo stock", len(bajo_stock))
    else:
        col3.metric("Productos", 0)
        col4.metric("Bajo stock", 0)

    st.divider()

    deudas = leer_hoja("PagosProveedores")
    if not deudas.empty:
        deudas["saldo_num"] = pd.to_numeric(deudas["saldo_pendiente"], errors="coerce").fillna(0)
        pendientes = deudas[deudas["saldo_num"] > 0]
        if not pendientes.empty:
            st.subheader("💳 Pagos pendientes a proveedores")
            st.dataframe(
                pendientes[["proveedor", "concepto", "saldo_num", "fecha_pago_programada", "estatus"]]
                .rename(columns={"saldo_num": "saldo_pendiente"})
                .sort_values("fecha_pago_programada"),
                use_container_width=True, hide_index=True,
            )

    if not inventario.empty and not inventario[inventario["stock_actual_num"] <= inventario["stock_minimo_num"]].empty:
        st.subheader("⚠️ Productos con stock bajo")
        st.dataframe(
            inventario[inventario["stock_actual_num"] <= inventario["stock_minimo_num"]][
                ["nombre_producto", "seccion", "stock_actual", "stock_minimo", "proveedor"]
            ],
            use_container_width=True, hide_index=True,
        )

    mensajeria = leer_hoja("Mensajeria")
    if not mensajeria.empty:
        pendientes_envio = mensajeria[mensajeria["estatus"].isin(["Pendiente", "En camino"])]
        if not pendientes_envio.empty:
            st.subheader("🛵 Envíos pendientes")
            st.dataframe(
                pendientes_envio[["fecha", "cliente_pedido", "mensajero", "estatus"]],
                use_container_width=True, hide_index=True,
            )
