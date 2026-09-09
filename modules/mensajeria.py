"""Módulo de Mensajería: envíos a domicilio y su costo/pago."""

import streamlit as st

from config import METODOS_PAGO, ESTATUS_ENVIO, QUIEN_PAGA_ENVIO
from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id, timestamp_hoy
from auth import usuario_actual


def render():
    st.header("🛵 Mensajería / Envíos a domicilio")

    tab_nuevo, tab_ver = st.tabs(["Registrar envío", "Ver / actualizar envíos"])

    with tab_nuevo:
        with st.form("form_nuevo_envio", clear_on_submit=True):
            cliente_pedido = st.text_input("Cliente / referencia del pedido *")
            mensajero = st.text_input("Mensajero asignado")
            direccion = st.text_area("Dirección / zona de entrega")
            col1, col2 = st.columns(2)
            with col1:
                costo_envio = st.number_input("Costo del envío", min_value=0.0, step=1.0, format="%.2f")
                quien_paga = st.selectbox("¿Quién paga el envío?", QUIEN_PAGA_ENVIO)
            with col2:
                metodo_pago_envio = st.selectbox("Método de pago del envío", METODOS_PAGO)
                estatus = st.selectbox("Estatus inicial", ESTATUS_ENVIO)

            enviado = st.form_submit_button("Registrar envío")
            if enviado:
                if not cliente_pedido:
                    st.error("Indica el cliente o referencia del pedido.")
                else:
                    fecha, _ = timestamp_hoy()
                    id_envio = siguiente_id("Mensajeria", "id_envio", prefijo="M")
                    agregar_fila("Mensajeria", {
                        "id_envio": id_envio,
                        "fecha": fecha,
                        "cliente_pedido": cliente_pedido,
                        "mensajero": mensajero,
                        "direccion_zona": direccion,
                        "costo_envio": costo_envio,
                        "metodo_pago_envio": metodo_pago_envio,
                        "quien_paga": quien_paga,
                        "estatus": estatus,
                        "usuario_registro": usuario_actual(),
                    })
                    st.success(f"Envío {id_envio} registrado.")
                    st.rerun()

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
                st.success("Estatus actualizado.")
                st.rerun()
