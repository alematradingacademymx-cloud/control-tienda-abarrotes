"""Módulo de Reportes: tendencias de ventas a través del tiempo — algo que
no se veía en ninguna otra pantalla, ya que Ventas diarias y Corte de caja
solo muestran el día o el turno en curso. Aquí se puede comparar un periodo
contra el equivalente anterior (semana vs semana pasada, mes vs mes
pasado, etc.), ver la venta día por día, y detectar tanto los productos que
más se venden como los que casi no se mueven — útil para decidir qué
reabastecer y qué ya no conviene tener en stock."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from sheets_connector import leer_hoja

OPCIONES_PERIODO = ["Hoy", "Esta semana", "Semana pasada", "Este mes", "Mes pasado", "Personalizado"]


def _rango_periodo(opcion: str, hoy: date):
    if opcion == "Hoy":
        return hoy, hoy
    if opcion == "Esta semana":
        inicio = hoy - timedelta(days=hoy.weekday())
        return inicio, hoy
    if opcion == "Semana pasada":
        inicio_esta_semana = hoy - timedelta(days=hoy.weekday())
        inicio = inicio_esta_semana - timedelta(days=7)
        fin = inicio_esta_semana - timedelta(days=1)
        return inicio, fin
    if opcion == "Este mes":
        return hoy.replace(day=1), hoy
    if opcion == "Mes pasado":
        primer_dia_este_mes = hoy.replace(day=1)
        fin = primer_dia_este_mes - timedelta(days=1)
        return fin.replace(day=1), fin
    return None, None  # "Personalizado" se resuelve aparte, con date_input


def _periodo_anterior_equivalente(inicio: date, fin: date):
    """Calcula el rango de fechas del mismo tamaño justo antes del periodo
    dado, para poder comparar (ej. esta semana vs. la semana pasada)."""
    dias = (fin - inicio).days + 1
    fin_anterior = inicio - timedelta(days=1)
    inicio_anterior = fin_anterior - timedelta(days=dias - 1)
    return inicio_anterior, fin_anterior


def _delta_pct(actual: float, anterior: float):
    if not anterior:
        return None
    return (actual - anterior) / anterior * 100


def render():
    st.header("📊 Reportes")
    st.caption(
        "Compara un periodo contra el equivalente anterior, revisa la venta "
        "día por día, y detecta qué productos se venden más y cuáles casi "
        "no se mueven."
    )

    ventas = leer_hoja("Ventas")
    inventario = leer_hoja("Inventario")

    if ventas.empty:
        st.info("Todavía no hay ventas registradas para generar reportes.")
        return

    ventas = ventas.copy()
    ventas["total_num"] = pd.to_numeric(ventas["total"], errors="coerce").fillna(0)
    ventas["ganancia_num"] = pd.to_numeric(ventas["ganancia"], errors="coerce").fillna(0)
    ventas["cantidad_num"] = pd.to_numeric(ventas["cantidad"], errors="coerce").fillna(0)
    ventas["fecha_dt"] = pd.to_datetime(ventas["fecha"], errors="coerce").dt.date

    hoy = date.today()
    opcion = st.radio("Periodo", OPCIONES_PERIODO, horizontal=True)

    if opcion == "Personalizado":
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Desde", value=hoy - timedelta(days=7))
        with col2:
            fecha_fin = st.date_input("Hasta", value=hoy)
        if fecha_inicio > fecha_fin:
            st.error("La fecha 'Desde' no puede ser posterior a 'Hasta'.")
            return
    else:
        fecha_inicio, fecha_fin = _rango_periodo(opcion, hoy)

    inicio_ant, fin_ant = _periodo_anterior_equivalente(fecha_inicio, fecha_fin)

    ventas_periodo = ventas[(ventas["fecha_dt"] >= fecha_inicio) & (ventas["fecha_dt"] <= fecha_fin)]
    ventas_anterior = ventas[(ventas["fecha_dt"] >= inicio_ant) & (ventas["fecha_dt"] <= fin_ant)]

    st.caption(
        f"📅 Periodo: **{fecha_inicio.strftime('%d/%m/%Y')} – {fecha_fin.strftime('%d/%m/%Y')}** · "
        f"comparado contra **{inicio_ant.strftime('%d/%m/%Y')} – {fin_ant.strftime('%d/%m/%Y')}**"
    )

    total_actual = ventas_periodo["total_num"].sum()
    total_anterior = ventas_anterior["total_num"].sum()
    ganancia_actual = ventas_periodo["ganancia_num"].sum()
    ganancia_anterior = ventas_anterior["ganancia_num"].sum()
    transacciones_actual = ventas_periodo["id_venta"].nunique()
    transacciones_anterior = ventas_anterior["id_venta"].nunique()
    ticket_actual = (total_actual / transacciones_actual) if transacciones_actual else 0
    ticket_anterior = (total_anterior / transacciones_anterior) if transacciones_anterior else 0

    col1, col2, col3, col4 = st.columns(4)
    d1 = _delta_pct(total_actual, total_anterior)
    col1.metric("Total ventas", f"${total_actual:,.2f}", f"{d1:+.1f}%" if d1 is not None else None)
    d2 = _delta_pct(ganancia_actual, ganancia_anterior)
    col2.metric("Ganancia estimada", f"${ganancia_actual:,.2f}", f"{d2:+.1f}%" if d2 is not None else None)
    d3 = _delta_pct(transacciones_actual, transacciones_anterior)
    col3.metric("Ventas (tickets)", f"{transacciones_actual}", f"{d3:+.1f}%" if d3 is not None else None)
    d4 = _delta_pct(ticket_actual, ticket_anterior)
    col4.metric("Ticket promedio", f"${ticket_actual:,.2f}", f"{d4:+.1f}%" if d4 is not None else None)

    if ventas_periodo.empty:
        st.info("No hay ventas en el periodo seleccionado.")
        return

    st.divider()
    st.subheader("Ventas por día")
    por_dia = ventas_periodo.groupby("fecha_dt")["total_num"].sum().sort_index()
    st.bar_chart(por_dia)

    st.divider()
    resumen_productos = (
        ventas_periodo.groupby(["id_producto", "producto"])
        .agg(cantidad_vendida=("cantidad_num", "sum"), total_vendido=("total_num", "sum"))
        .reset_index()
    )

    col_top, col_bajo = st.columns(2)

    with col_top:
        st.subheader("🔥 Productos más vendidos")
        top = resumen_productos.sort_values("cantidad_vendida", ascending=False).head(10)
        st.dataframe(
            top[["producto", "cantidad_vendida", "total_vendido"]].rename(columns={
                "producto": "Producto",
                "cantidad_vendida": "Cantidad vendida",
                "total_vendido": "Total vendido ($)",
            }),
            use_container_width=True, hide_index=True,
        )

    with col_bajo:
        st.subheader("🐢 Productos que casi no se mueven")
        if inventario.empty:
            st.info("No hay productos en Inventario.")
        else:
            inv = inventario[["id_producto", "nombre_producto", "seccion"]].copy()
            comparativo = inv.merge(
                resumen_productos[["id_producto", "cantidad_vendida"]],
                on="id_producto", how="left",
            )
            comparativo["cantidad_vendida"] = comparativo["cantidad_vendida"].fillna(0)
            bajos = comparativo.sort_values("cantidad_vendida", ascending=True).head(10)
            st.dataframe(
                bajos[["nombre_producto", "seccion", "cantidad_vendida"]].rename(columns={
                    "nombre_producto": "Producto",
                    "seccion": "Sección",
                    "cantidad_vendida": "Vendido en el periodo",
                }),
                use_container_width=True, hide_index=True,
            )
