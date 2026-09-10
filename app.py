"""
App principal — Sistema de administración para tienda de abarrotes.

Ejecutar con:  streamlit run app.py
"""

import streamlit as st

from config import MENU_POR_ROL
from sheets_connector import leer_hoja
from auth import (
    pantalla_login, esta_autenticado, cerrar_sesion, rol_actual, nombre_actual,
    crear_usuario, restaurar_sesion,
)
from modules import (
    inicio, inventario, stock, ventas, corte_caja, proveedores,
    pagos_proveedores, nomina, mensajeria, usuarios, theme,
)

st.set_page_config(page_title="Tienda de Abarrotes — Administración", page_icon="🏪", layout="wide")
theme.selector_tema()


def _bootstrap_primer_admin():
    """Si la hoja Usuarios está vacía, permite crear el primer administrador
    directamente desde la app (necesario para poder iniciar sesión la primera vez)."""
    st.markdown("## 🏪 Configuración inicial")
    st.info(
        "Todavía no hay usuarios registrados. Crea la cuenta de administrador "
        "para empezar a usar el sistema."
    )
    with st.form("form_primer_admin"):
        usuario = st.text_input("Usuario")
        nombre_completo = st.text_input("Nombre completo")
        password = st.text_input("Contraseña", type="password")
        password2 = st.text_input("Confirmar contraseña", type="password")
        enviado = st.form_submit_button("Crear administrador")

    if enviado:
        if not usuario or not nombre_completo or not password:
            st.error("Todos los campos son obligatorios.")
        elif password != password2:
            st.error("Las contraseñas no coinciden.")
        else:
            crear_usuario(usuario.strip(), nombre_completo.strip(), password, "admin")
            st.success("Administrador creado. Ahora puedes iniciar sesión.")
            st.rerun()


def main():
    try:
        usuarios_df = leer_hoja("Usuarios")
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    if usuarios_df.empty:
        _bootstrap_primer_admin()
        return

    restaurar_sesion()

    if not esta_autenticado():
        pantalla_login()
        return

    rol = rol_actual()
    opciones_menu = MENU_POR_ROL.get(rol, ["Inicio"])

    with st.sidebar:
        st.markdown(f"### 🏪 Tienda de Abarrotes")
        st.write(f"👤 **{nombre_actual()}**  \n_Rol: {rol}_")
        pagina = st.radio("Menú", opciones_menu, label_visibility="collapsed")
        st.divider()
        if st.button("Cerrar sesión"):
            cerrar_sesion()
            st.rerun()

    paginas = {
        "Inicio": inicio.render,
        "Inventario": inventario.render,
        "Stock": stock.render,
        "Ventas diarias": ventas.render,
        "Corte de caja": corte_caja.render,
        "Proveedores": proveedores.render,
        "Pagos a proveedores": pagos_proveedores.render,
        "Nómina": nomina.render,
        "Mensajería": mensajeria.render,
        "Usuarios": usuarios.render,
    }

    render_fn = paginas.get(pagina, inicio.render)
    render_fn()


if __name__ == "__main__":
    main()
