"""Módulo de Nómina: catálogo de empleados y registro de pago de sueldos."""

from datetime import date

import streamlit as st

from config import PERIODICIDAD_NOMINA, METODOS_PAGO
from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id


def render():
    st.header("👥 Nómina y Pago de Sueldos")

    tab_empleados, tab_pagar, tab_historial = st.tabs(["Empleados", "Registrar pago", "Historial de pagos"])

    with tab_empleados:
        empleados = leer_hoja("Nomina")
        if not empleados.empty:
            st.dataframe(empleados, use_container_width=True, hide_index=True)

        with st.expander("➕ Agregar empleado"):
            with st.form("form_agregar_empleado", clear_on_submit=True):
                nombre = st.text_input("Nombre completo *")
                puesto = st.text_input("Puesto")
                col1, col2 = st.columns(2)
                with col1:
                    sueldo = st.number_input("Sueldo por periodo", min_value=0.0, step=1.0, format="%.2f")
                    periodicidad = st.selectbox("Periodicidad", PERIODICIDAD_NOMINA)
                with col2:
                    fecha_pago_prog = st.date_input("Próxima fecha de pago programada", value=date.today())

                enviado = st.form_submit_button("Guardar empleado")
                if enviado:
                    if not nombre:
                        st.error("El nombre es obligatorio.")
                    else:
                        id_empleado = siguiente_id("Nomina", "id_empleado", prefijo="E")
                        agregar_fila("Nomina", {
                            "id_empleado": id_empleado,
                            "nombre": nombre,
                            "puesto": puesto,
                            "sueldo_periodo": sueldo,
                            "periodicidad": periodicidad,
                            "fecha_pago_programada": fecha_pago_prog.strftime("%Y-%m-%d"),
                            "activo": "Si",
                        })
                        st.success(f"Empleado '{nombre}' agregado con ID {id_empleado}.")
                        st.rerun()

    with tab_pagar:
        empleados = leer_hoja("Nomina")
        activos = empleados[empleados["activo"].astype(str).str.lower().isin(["si", "sí", "1", "true"])] if not empleados.empty else empleados
        if activos.empty:
            st.info("No hay empleados activos registrados.")
        else:
            opciones = activos["id_empleado"] + " — " + activos["nombre"]
            seleccion = st.selectbox("Empleado", opciones)
            id_sel = seleccion.split(" — ")[0]
            fila = activos[activos["id_empleado"] == id_sel].iloc[0]

            with st.form("form_pagar_sueldo"):
                periodo = st.text_input("Periodo que cubre", placeholder="Ej. 1-15 de septiembre 2026")
                col1, col2 = st.columns(2)
                with col1:
                    monto = st.number_input("Monto a pagar", value=float(fila["sueldo_periodo"] or 0), min_value=0.0, step=1.0, format="%.2f")
                    fecha_pago = st.date_input("Fecha de pago", value=date.today())
                with col2:
                    metodo_pago = st.selectbox("Método de pago", METODOS_PAGO)

                pagar = st.form_submit_button("💵 Registrar pago de sueldo")
                if pagar:
                    id_pago = siguiente_id("PagosNomina", "id_pago", prefijo="NP")
                    agregar_fila("PagosNomina", {
                        "id_pago": id_pago,
                        "id_empleado": id_sel,
                        "empleado": fila["nombre"],
                        "periodo": periodo,
                        "fecha_pago": fecha_pago.strftime("%Y-%m-%d"),
                        "monto_pagado": monto,
                        "metodo_pago": metodo_pago,
                        "estatus": "Pagado",
                    })
                    st.success(f"Pago de ${monto:,.2f} registrado para {fila['nombre']}.")
                    st.rerun()

    with tab_historial:
        pagos = leer_hoja("PagosNomina")
        if pagos.empty:
            st.info("Todavía no hay pagos de nómina registrados.")
        else:
            st.dataframe(pagos.sort_values("fecha_pago", ascending=False), use_container_width=True, hide_index=True)
