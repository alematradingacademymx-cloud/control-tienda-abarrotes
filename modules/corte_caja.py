"""Módulo de Corte de Caja: calcula automáticamente cuánto entró por cada
medio de pago (a partir de Ventas) y permite registrar el corte con el
efectivo contado físicamente, para poder auditar diferencias."""

from datetime import datetime, date

import pandas as pd
import streamlit as st

from config import METODOS_PAGO
from sheets_connector import leer_hoja, agregar_fila, siguiente_id
from auth import usuario_actual


def render():
    st.header("💰 Corte de Caja")

    ventas = leer_hoja("Ventas")
    ventas["total_num"] = pd.to_numeric(ventas["total"], errors="coerce").fillna(0)
    ventas["ganancia_num"] = pd.to_numeric(ventas["ganancia"], errors="coerce").fillna(0)

    fecha_corte = st.date_input("Fecha a cortar", value=date.today())
    fecha_str = fecha_corte.strftime("%Y-%m-%d")
    turno = st.text_input("Turno / nota (opcional)", placeholder="Ej. Matutino, Vespertino")

    ventas_dia = ventas[ventas["fecha"] == fecha_str] if not ventas.empty else ventas

    if ventas_dia.empty:
        st.info(f"No hay ventas registradas para el {fecha_str}.")
        totales = {m: 0.0 for m in METODOS_PAGO}
        total_ventas = 0.0
        ganancia_dia = 0.0
    else:
        totales = ventas_dia.groupby("metodo_pago")["total_num"].sum().reindex(METODOS_PAGO, fill_value=0).to_dict()
        total_ventas = sum(totales.values())
        ganancia_dia = ventas_dia["ganancia_num"].sum()

    st.subheader("Totales calculados por el sistema")
    cols = st.columns(len(METODOS_PAGO) + 2)
    for col, metodo in zip(cols, METODOS_PAGO):
        col.metric(metodo, f"${totales[metodo]:,.2f}")
    cols[-2].metric("Total ventas", f"${total_ventas:,.2f}")
    cols[-1].metric("Ganancia estimada", f"${ganancia_dia:,.2f}")

    st.divider()
    st.subheader("Conteo físico y cierre")
    with st.form("form_corte_caja"):
        efectivo_contado = st.number_input(
            "Efectivo contado en caja", min_value=0.0, step=1.0,
            help="Cuenta el efectivo físico y compáralo contra el total en efectivo del sistema.",
        )
        observaciones = st.text_area("Observaciones (faltantes, sobrantes, incidencias)")
        cerrar = st.form_submit_button("🔒 Registrar corte")

        if cerrar:
            diferencia = efectivo_contado - totales[METODOS_PAGO[0]]  # Efectivo es el primer método
            id_corte = siguiente_id("CorteCaja", "id_corte", prefijo="C")
            agregar_fila("CorteCaja", {
                "id_corte": id_corte,
                "fecha": fecha_str,
                "turno": turno,
                "usuario": usuario_actual(),
                "total_efectivo_sistema": totales.get("Efectivo", 0),
                "total_transferencia_sistema": totales.get("Transferencia", 0),
                "total_tarjeta_sistema": totales.get("Tarjeta", 0),
                "total_ventas_sistema": total_ventas,
                "efectivo_contado": efectivo_contado,
                "diferencia": diferencia,
                "observaciones": observaciones,
                "hora_cierre": datetime.now().strftime("%H:%M:%S"),
            })
            if abs(diferencia) < 0.01:
                st.success(f"Corte {id_corte} registrado. Caja cuadrada ✅")
            elif diferencia > 0:
                st.warning(f"Corte {id_corte} registrado. Sobrante de ${diferencia:,.2f}")
            else:
                st.error(f"Corte {id_corte} registrado. Faltante de ${abs(diferencia):,.2f}")
            st.rerun()

    if not ventas_dia.empty:
        with st.expander("Ver detalle de ventas del día"):
            st.dataframe(
                ventas_dia[["hora", "usuario", "seccion", "producto", "cantidad", "total", "metodo_pago", "ganancia"]],
                use_container_width=True, hide_index=True,
            )

    st.divider()
    st.subheader("Historial de cortes")
    historial = leer_hoja("CorteCaja")
    if historial.empty:
        st.info("Todavía no hay cortes registrados.")
    else:
        st.dataframe(
            historial.sort_values("fecha", ascending=False),
            use_container_width=True, hide_index=True,
        )
