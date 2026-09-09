"""Módulo de Pagos internos / Deudas a proveedores."""

from datetime import date

import pandas as pd
import streamlit as st

from config import METODOS_PAGO, ESTATUS_PAGO
from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id


def render():
    st.header("🧾 Pagos a Proveedores / Deudas")

    proveedores = leer_hoja("Proveedores")
    deudas = leer_hoja("PagosProveedores")

    if not deudas.empty:
        deudas["saldo_num"] = pd.to_numeric(deudas["saldo_pendiente"], errors="coerce").fillna(0)
        total_pendiente = deudas["saldo_num"].sum()
        st.metric("Saldo pendiente total con proveedores", f"${total_pendiente:,.2f}")

    tab_nueva, tab_abonar, tab_ver = st.tabs(["Registrar deuda/compra", "Registrar pago", "Ver deudas"])

    with tab_nueva:
        if proveedores.empty:
            st.info("Primero registra proveedores en el módulo de Proveedores.")
        else:
            with st.form("form_nueva_deuda", clear_on_submit=True):
                proveedor_sel = st.selectbox("Proveedor", proveedores["nombre"])
                fila_prov = proveedores[proveedores["nombre"] == proveedor_sel].iloc[0]
                concepto = st.text_input("Concepto (ej. Pedido semanal, factura #123)")
                col1, col2 = st.columns(2)
                with col1:
                    monto_total = st.number_input("Monto total", min_value=0.0, step=1.0, format="%.2f")
                    fecha_compra = st.date_input("Fecha de compra", value=date.today())
                with col2:
                    fecha_pago_prog = st.date_input("Fecha de pago programada")

                enviado = st.form_submit_button("Guardar deuda")
                if enviado:
                    id_pago = siguiente_id("PagosProveedores", "id_pago", prefijo="DP")
                    agregar_fila("PagosProveedores", {
                        "id_pago": id_pago,
                        "id_proveedor": fila_prov["id_proveedor"],
                        "proveedor": proveedor_sel,
                        "fecha_compra": fecha_compra.strftime("%Y-%m-%d"),
                        "concepto": concepto,
                        "monto_total": monto_total,
                        "monto_pagado": 0,
                        "saldo_pendiente": monto_total,
                        "fecha_pago_programada": fecha_pago_prog.strftime("%Y-%m-%d"),
                        "estatus": "Pendiente",
                        "metodo_pago": "",
                    })
                    st.success(f"Deuda {id_pago} registrada por ${monto_total:,.2f}.")
                    st.rerun()

    with tab_abonar:
        if deudas.empty:
            st.info("No hay deudas registradas.")
        else:
            pendientes = deudas[deudas["estatus"] != "Pagado"]
            if pendientes.empty:
                st.success("No hay deudas pendientes. 🎉")
            else:
                opciones = pendientes["id_pago"] + " — " + pendientes["proveedor"] + " (saldo: $" + pendientes["saldo_num"].round(2).astype(str) + ")"
                seleccion = st.selectbox("Selecciona la deuda a abonar", opciones)
                id_sel = seleccion.split(" — ")[0]
                fila = pendientes[pendientes["id_pago"] == id_sel].iloc[0]

                with st.form("form_abonar_deuda"):
                    st.write(f"Saldo pendiente actual: **${float(fila['saldo_num']):,.2f}**")
                    monto_abono = st.number_input("Monto a pagar ahora", min_value=0.0, max_value=float(fila["saldo_num"]), step=1.0, format="%.2f")
                    metodo_pago = st.radio("Método de pago", METODOS_PAGO, horizontal=True)
                    abonar = st.form_submit_button("Registrar pago")

                    if abonar:
                        if monto_abono <= 0:
                            st.error("El monto debe ser mayor a cero.")
                        else:
                            nuevo_pagado = float(fila["monto_pagado"] or 0) + monto_abono
                            nuevo_saldo = float(fila["saldo_num"]) - monto_abono
                            nuevo_estatus = "Pagado" if nuevo_saldo <= 0.01 else "Parcial"
                            actualizar_fila_por_id("PagosProveedores", "id_pago", id_sel, {
                                "monto_pagado": nuevo_pagado,
                                "saldo_pendiente": max(nuevo_saldo, 0),
                                "estatus": nuevo_estatus,
                                "metodo_pago": metodo_pago,
                            })
                            st.success(f"Pago de ${monto_abono:,.2f} registrado. Estatus: {nuevo_estatus}")
                            st.rerun()

    with tab_ver:
        if deudas.empty:
            st.info("No hay deudas registradas.")
        else:
            filtro_estatus = st.multiselect("Filtrar por estatus", ESTATUS_PAGO, default=ESTATUS_PAGO)
            df_mostrar = deudas[deudas["estatus"].isin(filtro_estatus)]
            st.dataframe(
                df_mostrar.drop(columns=["saldo_num"], errors="ignore"),
                use_container_width=True, hide_index=True,
            )
