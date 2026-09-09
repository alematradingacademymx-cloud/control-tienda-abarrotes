"""Módulo de Proveedores: catálogo con fechas de entrega y de pago."""

import streamlit as st

from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id


def render():
    st.header("🚚 Proveedores")

    df = leer_hoja("Proveedores")

    tab_ver, tab_agregar, tab_editar = st.tabs(["Ver proveedores", "Agregar proveedor", "Editar proveedor"])

    with tab_ver:
        if df.empty:
            st.info("Todavía no hay proveedores registrados.")
        else:
            solo_activos = st.checkbox("Mostrar solo activos", value=True)
            df_mostrar = df[df["activo"].astype(str).str.lower().isin(["si", "sí", "yes", "true", "1"])] if solo_activos else df
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

            st.caption("📅 Próximas entregas y pagos programados")
            resumen = df_mostrar[["nombre", "dia_entrega", "dia_pago"]].rename(columns={
                "nombre": "Proveedor", "dia_entrega": "Día/fecha de entrega", "dia_pago": "Día/fecha de pago",
            })
            st.dataframe(resumen, use_container_width=True, hide_index=True)

    with tab_agregar:
        with st.form("form_agregar_proveedor", clear_on_submit=True):
            nombre = st.text_input("Nombre del proveedor *")
            contacto = st.text_input("Persona de contacto")
            telefono = st.text_input("Teléfono")
            productos = st.text_area("Productos que surte")
            col1, col2 = st.columns(2)
            with col1:
                dia_entrega = st.text_input("Día(s) o fecha de entrega", placeholder="Ej. Lunes y jueves")
            with col2:
                dia_pago = st.text_input("Día(s) o fecha de pago", placeholder="Ej. Cada 15 y 30")
            condiciones = st.selectbox("Condiciones", ["Contado", "Crédito"])

            enviado = st.form_submit_button("Guardar proveedor")
            if enviado:
                if not nombre:
                    st.error("El nombre del proveedor es obligatorio.")
                else:
                    id_proveedor = siguiente_id("Proveedores", "id_proveedor", prefijo="PR")
                    agregar_fila("Proveedores", {
                        "id_proveedor": id_proveedor,
                        "nombre": nombre,
                        "contacto": contacto,
                        "telefono": telefono,
                        "productos_que_surte": productos,
                        "dia_entrega": dia_entrega,
                        "dia_pago": dia_pago,
                        "condiciones": condiciones,
                        "activo": "Si",
                    })
                    st.success(f"Proveedor '{nombre}' agregado con ID {id_proveedor}.")
                    st.rerun()

    with tab_editar:
        if df.empty:
            st.info("Todavía no hay proveedores registrados.")
        else:
            opciones = df["id_proveedor"] + " — " + df["nombre"]
            seleccion = st.selectbox("Selecciona un proveedor", opciones)
            id_sel = seleccion.split(" — ")[0]
            fila = df[df["id_proveedor"] == id_sel].iloc[0]

            with st.form("form_editar_proveedor"):
                contacto = st.text_input("Persona de contacto", value=fila["contacto"])
                telefono = st.text_input("Teléfono", value=fila["telefono"])
                productos = st.text_area("Productos que surte", value=fila["productos_que_surte"])
                col1, col2 = st.columns(2)
                with col1:
                    dia_entrega = st.text_input("Día(s) o fecha de entrega", value=fila["dia_entrega"])
                with col2:
                    dia_pago = st.text_input("Día(s) o fecha de pago", value=fila["dia_pago"])
                activo = st.selectbox("Activo", ["Si", "No"], index=0 if str(fila["activo"]).lower() in ("si", "sí", "1", "true") else 1)

                guardar = st.form_submit_button("Guardar cambios")
                if guardar:
                    actualizar_fila_por_id("Proveedores", "id_proveedor", id_sel, {
                        "contacto": contacto,
                        "telefono": telefono,
                        "productos_que_surte": productos,
                        "dia_entrega": dia_entrega,
                        "dia_pago": dia_pago,
                        "activo": activo,
                    })
                    st.success("Proveedor actualizado.")
                    st.rerun()
