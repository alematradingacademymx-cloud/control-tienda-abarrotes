"""Módulo de Corte de Caja: calcula automáticamente cuánto entró por cada
medio de pago (a partir de Ventas) y permite registrar el corte con el
efectivo contado físicamente, para poder auditar diferencias.

Ahora el corte se hace POR TURNO (Matutino, Vespertino, Nocturno) además de
mostrar el total general del día: así se puede saber cuánto entró en la
mañana, la tarde y la noche por separado, y se pueden registrar 2 o 3 cortes
en un mismo día (uno por cada turno que realmente se trabajó)."""

from datetime import datetime, date

import pandas as pd
import streamlit as st

from config import METODOS_PAGO, TURNOS, HORARIO_TURNOS
from sheets_connector import leer_hoja, agregar_fila, siguiente_id
from auth import usuario_actual
from modules.carrito_utils import turno_por_hora as _turno_por_hora


def _calcular_totales(ventas_subset: pd.DataFrame):
    """Devuelve (dict de totales por método de pago, total de ventas,
    ganancia) para el subconjunto de ventas dado."""
    if ventas_subset.empty:
        return {m: 0.0 for m in METODOS_PAGO}, 0.0, 0.0
    totales = (
        ventas_subset.groupby("metodo_pago")["total_num"]
        .sum()
        .reindex(METODOS_PAGO, fill_value=0)
        .to_dict()
    )
    total_ventas = sum(totales.values())
    ganancia = ventas_subset["ganancia_num"].sum()
    return totales, total_ventas, ganancia


def _mostrar_metricas(ventas_subset: pd.DataFrame):
    """Muestra la fila de métricas (Efectivo/Transferencia/Tarjeta/Total
    ventas/Ganancia estimada) para el subconjunto de ventas dado, y devuelve
    los totales calculados."""
    totales, total_ventas, ganancia = _calcular_totales(ventas_subset)
    cols = st.columns(len(METODOS_PAGO) + 2)
    for col, metodo in zip(cols, METODOS_PAGO):
        col.metric(metodo, f"${totales[metodo]:,.2f}")
    cols[-2].metric("Total ventas", f"${total_ventas:,.2f}")
    cols[-1].metric("Ganancia estimada", f"${ganancia:,.2f}")
    return totales, total_ventas, ganancia


def render():
    st.header("💰 Corte de Caja")

    ventas = leer_hoja("Ventas")
    ventas["total_num"] = pd.to_numeric(ventas["total"], errors="coerce").fillna(0)
    ventas["ganancia_num"] = pd.to_numeric(ventas["ganancia"], errors="coerce").fillna(0)

    fecha_corte = st.date_input("Fecha a cortar", value=date.today())
    fecha_str = fecha_corte.strftime("%Y-%m-%d")

    ventas_dia = ventas[ventas["fecha"] == fecha_str].copy() if not ventas.empty else ventas.copy()

    if ventas_dia.empty:
        ventas_dia["turno_calculado"] = []
    else:
        ventas_dia["turno_calculado"] = ventas_dia["hora"].apply(_turno_por_hora)

    if ventas_dia.empty:
        st.info(f"No hay ventas registradas para el {fecha_str}.")

    st.subheader("📊 Totales del día completo")
    totales_dia, total_ventas_dia, ganancia_dia = _mostrar_metricas(ventas_dia)

    st.divider()
    st.subheader("🕐 Totales por turno")

    totales_por_turno = {}
    for turno in TURNOS:
        inicio, fin = HORARIO_TURNOS[turno]
        st.markdown(f"**{turno}** ({inicio} – {fin})")
        ventas_turno = ventas_dia[ventas_dia["turno_calculado"] == turno] if not ventas_dia.empty else ventas_dia
        totales_por_turno[turno] = _mostrar_metricas(ventas_turno)
        st.markdown("")

    st.divider()
    st.subheader("Conteo físico y cierre de un turno")

    if "ultimo_resultado_corte" in st.session_state:
        resultado = st.session_state.pop("ultimo_resultado_corte")
        if resultado["tipo"] == "success":
            st.success(resultado["mensaje"])
        elif resultado["tipo"] == "warning":
            st.warning(resultado["mensaje"])
        else:
            st.error(resultado["mensaje"])

    with st.form("form_corte_caja"):
        turno_sel = st.selectbox("Turno a cortar", TURNOS)
        efectivo_contado = st.number_input(
            "Efectivo contado en caja", min_value=0.0, step=1.0,
            help="Cuenta el efectivo físico de ese turno y compáralo contra el total en efectivo del sistema para ese turno.",
        )
        observaciones = st.text_area("Observaciones (faltantes, sobrantes, incidencias)")
        cerrar = st.form_submit_button("🔒 Registrar corte de este turno")

        if cerrar:
            totales_sel, total_ventas_sel, _ = totales_por_turno[turno_sel]
            diferencia = efectivo_contado - totales_sel.get("Efectivo", 0)
            id_corte = siguiente_id("CorteCaja", "id_corte", prefijo="C")
            agregar_fila("CorteCaja", {
                "id_corte": id_corte, "fecha": fecha_str, "turno": turno_sel,
                "usuario": usuario_actual(),
                "total_efectivo_sistema": totales_sel.get("Efectivo", 0),
                "total_transferencia_sistema": totales_sel.get("Transferencia", 0),
                "total_tarjeta_sistema": totales_sel.get("Tarjeta", 0),
                "total_ventas_sistema": total_ventas_sel,
                "efectivo_contado": efectivo_contado, "diferencia": diferencia,
                "observaciones": observaciones,
                "hora_cierre": datetime.now().strftime("%H:%M:%S"),
            })
            if abs(diferencia) < 0.01:
                st.session_state["ultimo_resultado_corte"] = {
                    "tipo": "success",
                    "mensaje": f"Corte {id_corte} ({turno_sel}) registrado. Caja cuadrada ✅",
                }
            elif diferencia > 0:
                st.session_state["ultimo_resultado_corte"] = {
                    "tipo": "warning",
                    "mensaje": f"Corte {id_corte} ({turno_sel}) registrado. Sobrante de ${diferencia:,.2f}",
                }
            else:
                st.session_state["ultimo_resultado_corte"] = {
                    "tipo": "error",
                    "mensaje": f"Corte {id_corte} ({turno_sel}) registrado. Faltante de ${abs(diferencia):,.2f}",
                }
            st.rerun()

    if not ventas_dia.empty:
        with st.expander("Ver detalle de ventas del día (con turno)"):
            st.dataframe(
                ventas_dia[["hora", "turno_calculado", "usuario", "seccion", "producto", "cantidad", "total", "metodo_pago", "ganancia"]],
                use_container_width=True, hide_index=True,
            )

    st.divider()
    st.subheader("Historial de cortes")
    historial = leer_hoja("CorteCaja")
    if historial.empty:
        st.info("Todavía no hay cortes registrados.")
    else:
        columnas_orden = [c for c in ["fecha", "hora_cierre"] if c in historial.columns]
        historial_ordenado = historial.sort_values(columnas_orden, ascending=False) if columnas_orden else historial
        st.dataframe(historial_ordenado, use_container_width=True, hide_index=True)
