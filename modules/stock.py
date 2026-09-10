"""Módulo de Stock: recepción de mercancía agrupada por proveedor.

Pensado para cuando llega un pedido y hay que actualizar el stock de varios
productos a la vez: se muestran agrupados por proveedor y, dentro de cada
proveedor, uno por producto, con su stock actual, un campo para capturar
cuánto está entrando, y el total resultante. Se puede guardar producto por
producto con el botón ✔️ de su fila, o capturar varios y guardar todo junto
al final con "Confirmar stock final".

Como esto escribe directamente en la hoja 'Inventario' — la misma que usan
Ventas diarias, Corte de caja, Mensajería, etc. — el stock queda
sincronizado en toda la app de inmediato, sin necesidad de nada extra."""

from datetime import datetime

import pandas as pd
import streamlit as st

from sheets_connector import leer_hoja, actualizar_fila_por_id

SIN_PROVEEDOR = "Sin proveedor asignado"


def _guardar_stock(id_producto: str, nuevo_stock: float):
    actualizar_fila_por_id("Inventario", "id_producto", id_producto, {
        "stock_actual": nuevo_stock,
        "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


def render():
    st.header("📦 Stock — Recepción de mercancía")
    st.caption(
        "Agrupado por proveedor y producto: captura cuánto está entrando, "
        "revisa el total y guárdalo. Se actualiza directo en Inventario, "
        "así que queda sincronizado con Ventas diarias, Corte de caja y "
        "todo lo demás al instante."
    )

    df = leer_hoja("Inventario")
    if df.empty:
        st.info("Todavía no hay productos registrados en Inventario.")
        return

    df = df.copy()
    df["stock_actual_num"] = pd.to_numeric(df["stock_actual"], errors="coerce").fillna(0)
    df["proveedor_mostrar"] = df["proveedor"].astype(str).str.strip()
    df.loc[df["proveedor_mostrar"] == "", "proveedor_mostrar"] = SIN_PROVEEDOR

    proveedores_reales = sorted(p for p in df["proveedor_mostrar"].unique() if p != SIN_PROVEEDOR)
    proveedores = proveedores_reales + ([SIN_PROVEEDOR] if SIN_PROVEEDOR in df["proveedor_mostrar"].unique() else [])

    filtro_texto = st.text_input("Buscar producto (opcional)", placeholder="Escribe para filtrar por nombre")

    filas_pendientes = []  # (id_producto, nombre, total, cantidad_key)

    for proveedor in proveedores:
        productos_prov = df[df["proveedor_mostrar"] == proveedor]
        if filtro_texto:
            productos_prov = productos_prov[
                productos_prov["nombre_producto"].astype(str).str.contains(filtro_texto, case=False, na=False)
            ]
        if productos_prov.empty:
            continue

        etiqueta = f"🏭 {proveedor} ({len(productos_prov)} producto{'s' if len(productos_prov) != 1 else ''})"
        with st.expander(etiqueta):
            col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([3, 1.3, 1.3, 1.3, 0.8])
            col_h1.markdown("**Producto**")
            col_h2.markdown("**Stock actual**")
            col_h3.markdown("**Entrada**")
            col_h4.markdown("**Total**")
            col_h5.markdown(" ")

            for _, fila in productos_prov.iterrows():
                id_producto = fila["id_producto"]
                cantidad_key = f"stock_entrada_{id_producto}"

                col1, col2, col3, col4, col5 = st.columns([3, 1.3, 1.3, 1.3, 0.8])
                col1.write(fila["nombre_producto"])
                col2.write(f"{fila['stock_actual_num']:g}")
                # Fuera de un form: así el Total se recalcula al instante
                # mientras escribes la entrada, en vez de quedarse fijo
                # hasta enviar algo.
                entrada = col3.number_input(
                    "Entrada", min_value=0.0, step=1.0, value=0.0,
                    key=cantidad_key, label_visibility="collapsed",
                )
                total = fila["stock_actual_num"] + entrada
                col4.write(f"**{total:g}**")

                if col5.button("✔️", key=f"stock_check_{id_producto}", help="Guardar el stock de este producto"):
                    if entrada > 0:
                        _guardar_stock(id_producto, total)
                        st.session_state.pop(cantidad_key, None)
                        st.toast(f"Stock de '{fila['nombre_producto']}' actualizado a {total:g}.", icon="✅")
                        st.rerun()
                    else:
                        st.warning("Captura una cantidad de entrada mayor a 0 antes de guardar.", icon="⚠️")

                if entrada > 0:
                    filas_pendientes.append((id_producto, fila["nombre_producto"], total, cantidad_key))

    st.divider()
    if filas_pendientes:
        st.info(f"📝 Tienes {len(filas_pendientes)} producto(s) con cantidad capturada y sin guardar todavía.")
    if st.button("✅ Confirmar stock final", type="primary", disabled=not filas_pendientes,
                 help="Guarda de un jalón todos los productos con una cantidad de entrada capturada."):
        for id_producto, nombre, total, cantidad_key in filas_pendientes:
            _guardar_stock(id_producto, total)
            st.session_state.pop(cantidad_key, None)
        st.toast(f"Stock actualizado para {len(filas_pendientes)} producto(s).", icon="✅")
        st.rerun()
