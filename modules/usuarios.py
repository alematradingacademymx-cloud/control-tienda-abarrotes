"""Módulo de Usuarios (solo admin): alta de encargados/administradores y
control de acceso."""

import streamlit as st

from config import ROLES
from sheets_connector import leer_hoja, actualizar_fila_por_id
from auth import crear_usuario, usuario_actual


def render():
    st.header("🔑 Usuarios del sistema")

    df = leer_hoja("Usuarios")
    if not df.empty:
        st.dataframe(
            df[["usuario", "nombre_completo", "rol", "activo"]],
            use_container_width=True, hide_index=True,
        )

    st.subheader("Agregar nuevo usuario")
    with st.form("form_agregar_usuario", clear_on_submit=True):
        usuario = st.text_input("Nombre de usuario (para iniciar sesión) *")
        nombre_completo = st.text_input("Nombre completo *")
        password = st.text_input("Contraseña *", type="password")
        rol = st.selectbox("Rol", ROLES)
        enviado = st.form_submit_button("Crear usuario")

        if enviado:
            if not usuario or not nombre_completo or not password:
                st.error("Todos los campos son obligatorios.")
            elif not df.empty and usuario.strip().lower() in df["usuario"].astype(str).str.lower().values:
                st.error("Ya existe un usuario con ese nombre.")
            else:
                crear_usuario(usuario.strip(), nombre_completo.strip(), password, rol)
                st.success(f"Usuario '{usuario}' creado con rol {rol}.")
                st.rerun()

    if not df.empty:
        st.subheader("Activar / desactivar usuario")
        opciones = df["usuario"].tolist()
        sel = st.selectbox("Usuario", opciones)
        fila = df[df["usuario"] == sel].iloc[0]
        if sel == usuario_actual():
            st.caption("Este es tu propio usuario; no puedes desactivarte a ti mismo aquí.")
        else:
            activo_actual = str(fila["activo"]).strip().lower() in ("si", "sí", "1", "true")
            nuevo_estado = st.toggle("Usuario activo", value=activo_actual)
            if st.button("Guardar estado"):
                actualizar_fila_por_id("Usuarios", "usuario", sel, {"activo": "Si" if nuevo_estado else "No"})
                st.success("Estado actualizado.")
                st.rerun()
