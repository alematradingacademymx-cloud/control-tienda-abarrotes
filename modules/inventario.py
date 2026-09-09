"""Módulo de Inventario: alta, edición y consulta de productos y stock."""

from datetime import datetime

import pandas as pd
import streamlit as st

from config import SECCIONES_DEFAULT
from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id
from auth import rol_actual


def _secciones_disponibles(df: pd.DataFrame):
    secciones = sorted(set(SECCIONES_DEFAULT) | set(df["seccion"].dropna().astype(str)) - {""})
    return secciones


def render():
    st.header("📦 Inventario")

    df = leer_hoja("Inventario")

    tab_ver, tab_agregar, tab_editar = st.tabs(["Ver inventario", "Agregar producto", "Editar / Reabastecer"])

    with tab_ver:
        col1, col2 = st.columns([2, 1])
        with col1:
            filtro_texto = st.text_input("Buscar por nombre de producto")
        with col2:
            secciones = ["Todas"] + _secciones_disponibles(df)
            filtro_seccion = st.selectbox("Sección", secciones)

        df_mostrar = df.copy()
        if filtro_texto:
            df_mostrar = df_mostrar[df_mostrar["nombre_producto"].astype(str).str.contains(filtro_texto, case=False, na=False)]
        if filtro_seccion != "Todas":
            df_mostrar = df_mostrar[df_mostrar["seccion"] == filtro_seccion]

        if not df_mostrar.empty:
            df_mostrar = df_mostrar.copy()
            df_mostrar["stock_actual_num"] = pd.to_numeric(df_mostrar["stock_actual"], errors="coerce").fillna(0)
            df_mostrar["stock_minimo_num"] = pd.to_numeric(df_mostrar["stock_minimo"], errors="coerce").fillna(0)
            bajo_stock = df_mostrar[df_mostrar["stock_actual_num"] <= df_mostrar["stock_minimo_num"]]
            if not bajo_stock.empty:
                st.warning(f"⚠️ {len(bajo_stock)} producto(s) en o por debajo del stock mínimo.")

            def resaltar_bajo_stock(row):
                if row["stock_actual_num"] <= row["stock_minimo_num"]:
                    return ["background-color: #ffe1e1"] * len(row)
                return [""] * len(row)

            columnas_mostrar = [c for c in df.columns]
            st.dataframe(
                df_mostrar[columnas_mostrar].style.apply(resaltar_bajo_stock, axis=1),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No hay productos que coincidan con el filtro.")

    with tab_agregar:
        with st.form("form_agregar_producto", clear_on_submit=True):
            nombre = st.text_input("Nombre del producto *")
            col1, col2 = st.columns(2)
            with col1:
                seccion = st.selectbox("Sección *", _secciones_disponibles(df) + ["Otra..."])
                if seccion == "Otra...":
                    seccion = st.text_input("Escribe la nueva sección")
                unidad = st.text_input("Unidad (pieza, kg, litro, paquete...)", value="pieza")
                proveedor = st.text_input("Proveedor")
            with col2:
                costo_unitario = st.number_input("Costo unitario", min_value=0.0, step=0.5, format="%.2f")
                precio_venta = st.number_input("Precio de venta", min_value=0.0, step=0.5, format="%.2f")
                stock_actual = st.number_input("Stock inicial", min_value=0.0, step=1.0)
                stock_minimo = st.number_input("Stock mínimo (alerta)", min_value=0.0, step=1.0)

            enviado = st.form_submit_button("Guardar producto")
            if enviado:
                if not nombre or not seccion:
                    st.error("El nombre y la sección son obligatorios.")
                else:
                    id_producto = siguiente_id("Inventario", "id_producto", prefijo="P")
                    agregar_fila("Inventario", {
                        "id_producto": id_producto,
                        "nombre_producto": nombre,
                        "seccion": seccion,
                        "unidad": unidad,
                        "costo_unitario": costo_unitario,
                        "precio_venta": precio_venta,
                        "stock_actual": stock_actual,
                        "stock_minimo": stock_minimo,
                        "proveedor": proveedor,
                        "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    st.success(f"Producto '{nombre}' agregado con ID {id_producto}.")
                    st.rerun()

    with tab_editar:
        if df.empty:
            st.info("Todavía no hay productos registrados.")
        else:
            opciones = df["id_producto"] + " — " + df["nombre_producto"]
            seleccion = st.selectbox("Selecciona un producto", opciones)
            id_sel = seleccion.split(" — ")[0]
            fila = df[df["id_producto"] == id_sel].iloc[0]

            with st.form("form_editar_producto"):
                col1, col2 = st.columns(2)
                with col1:
                    nuevo_precio = st.number_input("Precio de venta", value=float(fila["precio_venta"] or 0), min_value=0.0, step=0.5, format="%.2f")
                    nuevo_costo = st.number_input("Costo unitario", value=float(fila["costo_unitario"] or 0), min_value=0.0, step=0.5, format="%.2f")
                with col2:
                    ajuste_stock = st.number_input("Ajustar stock (+ entrada / - salida)", value=0.0, step=1.0)
                    nuevo_minimo = st.number_input("Stock mínimo", value=float(fila["stock_minimo"] or 0), min_value=0.0, step=1.0)

                guardar = st.form_submit_button("Guardar cambios")
                eliminar = False
                if rol_actual() == "admin":
                    eliminar = st.form_submit_button("🗑️ Eliminar producto", type="secondary")

                if guardar:
                    nuevo_stock = float(fila["stock_actual"] or 0) + ajuste_stock
                    actualizar_fila_por_id("Inventario", "id_producto", id_sel, {
                        "precio_venta": nuevo_precio,
                        "costo_unitario": nuevo_costo,
                        "stock_actual": nuevo_stock,
                        "stock_minimo": nuevo_minimo,
                        "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    st.success("Producto actualizado.")
                    st.rerun()

                if eliminar:
                    from sheets_connector import eliminar_fila_por_id
                    eliminar_fila_por_id("Inventario", "id_producto", id_sel)
                    st.success("Producto eliminado.")
                    st.rerun()
