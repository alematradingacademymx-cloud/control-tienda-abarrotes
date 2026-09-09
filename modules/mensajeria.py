"""Módulo de Mensajería: envíos a domicilio. Se arma el pedido igual que una
venta de mostrador (carrito de productos por escáner o búsqueda manual —
comparte la lógica con Ventas diarias en carrito_utils.py) y además se
capturan los datos propios del envío: cliente, mensajero, dirección, costo
de envío y quién lo paga. Al confirmar, se registra la venta de productos
(descontando inventario) y el envío queda ligado a ella."""

import pandas as pd
import streamlit as st

from config import METODOS_PAGO, ESTATUS_ENVIO, QUIEN_PAGA_ENVIO
from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id, timestamp_hoy
from auth import usuario_actual
import modules.carrito_utils as carrito_utils

CLAVE_CARRITO = "carrito_mensajeria"
PREFIJO = "envio"


def _render_confirmacion_envio(total_productos: float):
    st.markdown("#### Datos del envío")

    cliente_pedido = st.text_input("Cliente / referencia del pedido *", key=f"{PREFIJO}_cliente")
    mensajero = st.text_input("Mensajero asignado", key=f"{PREFIJO}_mensajero")
    direccion = st.text_area("Dirección / zona de entrega", key=f"{PREFIJO}_direccion")

    col1, col2 = st.columns(2)
    with col1:
        costo_envio = st.number_input("Costo del envío", min_value=0.0, step=1.0, format="%.2f", key=f"{PREFIJO}_costo")
        quien_paga = st.selectbox("¿Quién paga el envío?", QUIEN_PAGA_ENVIO, key=f"{PREFIJO}_quien_paga")
    with col2:
        estatus = st.selectbox("Estatus inicial", ESTATUS_ENVIO, key=f"{PREFIJO}_estatus")

    total_a_cobrar = total_productos + (costo_envio if quien_paga == "Cliente" else 0.0)
    st.metric("Total a cobrar al cliente", f"${total_a_cobrar:,.2f}")

    metodo_pago = st.radio("Forma de pago", METODOS_PAGO, horizontal=True, key=f"{PREFIJO}_metodo_pago")

    cambio = None
    recibido = 0.0
    if metodo_pago == "Efectivo" and total_a_cobrar > 0:
        recibido = st.number_input(
            "¿Cuánto dinero te dio el cliente?",
            min_value=0.0, step=10.0, format="%.2f", key=f"{PREFIJO}_recibido_efectivo",
        )
        cambio = recibido - total_a_cobrar
        if recibido == 0:
            st.caption("Escribe el monto recibido para calcular el cambio.")
        elif cambio < 0:
            st.error(f"Faltan ${abs(cambio):,.2f} — lo recibido es menor al total (${total_a_cobrar:,.2f}).")
        else:
            st.success(f"💰 Cambio a entregar: ${cambio:,.2f}")

    col_a, col_b = st.columns(2)
    confirmar = col_a.button("✅ Confirmar y registrar envío", type="primary", key=f"{PREFIJO}_btn_confirmar_final")
    cancelar = col_b.button("Cancelar", key=f"{PREFIJO}_btn_cancelar_final")

    if cancelar:
        st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = False
        st.rerun()

    if confirmar:
        if not cliente_pedido:
            st.error("Indica el cliente o referencia del pedido.")
        elif metodo_pago == "Efectivo" and total_a_cobrar > 0 and recibido < total_a_cobrar:
            st.error("El monto recibido debe cubrir el total antes de confirmar.")
        else:
            id_venta = carrito_utils.registrar_venta_carrito(CLAVE_CARRITO, metodo_pago, turno="Mensajería")

            fecha, _ = timestamp_hoy()
            id_envio = siguiente_id("Mensajeria", "id_envio", prefijo="M")
            agregar_fila("Mensajeria", {
                "id_envio": id_envio,
                "fecha": fecha,
                "cliente_pedido": cliente_pedido,
                "mensajero": mensajero,
                "direccion_zona": direccion,
                "costo_envio": costo_envio,
                "metodo_pago_envio": metodo_pago,
                "quien_paga": quien_paga,
                "estatus": estatus,
                "usuario_registro": usuario_actual(),
                "id_venta": id_venta,
                "monto_productos": total_productos,
            })

            st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = False
            st.session_state.pop(f"{PREFIJO}_recibido_efectivo", None)
            mensaje = f"Envío {id_envio} registrado por ${total_a_cobrar:,.2f} ({metodo_pago})."
            if cambio is not None and cambio >= 0:
                mensaje += f" Cambio: ${cambio:,.2f}."
            st.toast(mensaje, icon="✅")
            st.rerun()


def _render_carrito_envio():
    st.subheader("🛒 Productos del pedido")
    st.caption("Si el envío no lleva productos de la tienda (solo un mandado/paquete), puedes dejar esto vacío y pasar directo a los datos del envío.")
    total_productos = carrito_utils.render_lista_carrito(CLAVE_CARRITO, PREFIJO)

    if carrito_utils.obtener_carrito(CLAVE_CARRITO):
        if st.button("🗑️ Vaciar carrito", key=f"{PREFIJO}_vaciar"):
            carrito_utils.vaciar_carrito(CLAVE_CARRITO)
            st.rerun()

    st.divider()
    _render_confirmacion_envio(total_productos)


def render():
    st.header("🛵 Mensajería / Envíos a domicilio")

    tab_nuevo, tab_ver = st.tabs(["Registrar envío", "Ver / actualizar envíos"])

    with tab_nuevo:
        inventario = leer_hoja("Inventario")
        if not inventario.empty:
            inventario["stock_actual_num"] = pd.to_numeric(inventario["stock_actual"], errors="coerce").fillna(0)
            tab_escaner, tab_manual = st.tabs(["📷 Escanear código de barras", "🔍 Buscar manualmente"])
            with tab_escaner:
                carrito_utils.render_agregar_por_escaner(CLAVE_CARRITO, inventario, PREFIJO)
            with tab_manual:
                carrito_utils.render_agregar_manual(CLAVE_CARRITO, inventario, PREFIJO)
            st.divider()

        _render_carrito_envio()

    with tab_ver:
        envios = leer_hoja("Mensajeria")
        if envios.empty:
            st.info("No hay envíos registrados.")
        else:
            filtro = st.multiselect("Filtrar por estatus", ESTATUS_ENVIO, default=ESTATUS_ENVIO)
            df_mostrar = envios[envios["estatus"].isin(filtro)]
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Actualizar estatus de un envío")
            opciones = envios["id_envio"] + " — " + envios["cliente_pedido"]
            seleccion = st.selectbox("Selecciona un envío", opciones)
            id_sel = seleccion.split(" — ")[0]
            fila = envios[envios["id_envio"] == id_sel].iloc[0]
            nuevo_estatus = st.selectbox(
                "Nuevo estatus", ESTATUS_ENVIO,
                index=ESTATUS_ENVIO.index(fila["estatus"]) if fila["estatus"] in ESTATUS_ENVIO else 0,
            )
            if st.button("Actualizar estatus"):
                actualizar_fila_por_id("Mensajeria", "id_envio", id_sel, {"estatus": nuevo_estatus})
                st.toast("Estatus actualizado.", icon="✅")
                st.rerun()
