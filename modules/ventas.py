"""Módulo de Ventas diarias: arma un carrito con varios productos (por
escáner o buscando manualmente), y hasta el final se confirma la venta
completa: se elige el método de pago y, si es efectivo, se calcula el
cambio exacto a entregar. La lógica del carrito y el registro de la venta
viven en carrito_utils.py (se comparten con Mensajería, que registra la
venta de un envío exactamente de la misma forma)."""

import pandas as pd
import streamlit as st

from config import METODOS_PAGO
from sheets_connector import leer_hoja, timestamp_hoy
import modules.carrito_utils as carrito_utils

CLAVE_CARRITO = "carrito_venta"
PREFIJO = "venta"


def _render_confirmacion_venta(total: float):
    st.markdown("#### Confirmar venta")

    metodo_pago = st.radio(
        "Método de pago", METODOS_PAGO, horizontal=True, key=f"{PREFIJO}_metodo_pago",
    )

    cambio = None
    recibido = 0.0
    if metodo_pago == "Efectivo":
        recibido = st.number_input(
            "¿Cuánto dinero te dio el cliente?",
            min_value=0.0, step=10.0, format="%.2f", key=f"{PREFIJO}_recibido_efectivo",
        )
        cambio = recibido - total
        if recibido == 0:
            st.caption("Escribe el monto recibido para calcular el cambio.")
        elif cambio < 0:
            st.error(f"Faltan ${abs(cambio):,.2f} — lo recibido es menor al total (${total:,.2f}).")
        else:
            st.success(f"💰 Cambio a entregar: ${cambio:,.2f}")

    col_a, col_b = st.columns(2)
    confirmar = col_a.button("✅ Confirmar y registrar venta", type="primary", key=f"{PREFIJO}_btn_confirmar_final")
    cancelar = col_b.button("Cancelar", key=f"{PREFIJO}_btn_cancelar_final")

    if cancelar:
        st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = False
        st.rerun()

    if confirmar:
        if metodo_pago == "Efectivo" and recibido < total:
            st.error("El monto recibido debe cubrir el total antes de confirmar.")
        else:
            id_venta = carrito_utils.registrar_venta_carrito(CLAVE_CARRITO, metodo_pago)
            st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = False
            st.session_state.pop(f"{PREFIJO}_recibido_efectivo", None)
            mensaje = f"Venta {id_venta} registrada por ${total:,.2f} ({metodo_pago})."
            if cambio is not None and cambio >= 0:
                mensaje += f" Cambio: ${cambio:,.2f}."
            st.toast(mensaje, icon="✅")
            st.rerun()


def _render_carrito():
    st.subheader("🛒 Carrito de la venta actual")
    total = carrito_utils.render_lista_carrito(CLAVE_CARRITO, PREFIJO)

    if not carrito_utils.obtener_carrito(CLAVE_CARRITO):
        return

    if st.button("🗑️ Vaciar carrito", key=f"{PREFIJO}_vaciar"):
        carrito_utils.vaciar_carrito(CLAVE_CARRITO)
        st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = False
        st.rerun()

    if not st.session_state.get(f"{PREFIJO}_mostrar_confirmacion"):
        if st.button("💵 Confirmar venta", type="primary", key=f"{PREFIJO}_btn_abrir_confirmacion"):
            st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = True
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
        carrito_utils.render_agregar_por_escaner(CLAVE_CARRITO, inventario, PREFIJO)
    with tab_manual:
        carrito_utils.render_agregar_manual(CLAVE_CARRITO, inventario, PREFIJO)

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
            ventas_hoy[["id_venta", "hora", "usuario", "seccion", "producto", "cantidad", "precio_unitario", "total", "metodo_pago", "ganancia", "turno"]],
            use_container_width=True,
            hide_index=True,
        )
