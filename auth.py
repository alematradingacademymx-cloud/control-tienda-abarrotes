"""
Autenticación y control de sesión.
Los usuarios y contraseñas (hasheadas con bcrypt) viven en la hoja "Usuarios".
"""

import bcrypt
import streamlit as st

from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def crear_usuario(usuario: str, nombre_completo: str, password: str, rol: str):
    agregar_fila("Usuarios", {
        "usuario": usuario,
        "nombre_completo": nombre_completo,
        "password_hash": hash_password(password),
        "rol": rol,
        "activo": "Si",
    })


def _buscar_usuario(usuario: str):
    df = leer_hoja("Usuarios")
    coincidencias = df[df["usuario"].astype(str).str.lower() == usuario.strip().lower()]
    if coincidencias.empty:
        return None
    return coincidencias.iloc[0].to_dict()


def intentar_login(usuario: str, password: str):
    """Devuelve el diccionario del usuario si las credenciales son correctas
    y la cuenta está activa; en caso contrario devuelve None."""
    fila = _buscar_usuario(usuario)
    if fila is None:
        return None
    if str(fila.get("activo", "")).strip().lower() not in ("si", "sí", "yes", "true", "1"):
        return None
    if verificar_password(password, str(fila.get("password_hash", ""))):
        return fila
    return None


def iniciar_sesion(fila_usuario: dict):
    st.session_state["autenticado"] = True
    st.session_state["usuario"] = fila_usuario["usuario"]
    st.session_state["nombre_completo"] = fila_usuario.get("nombre_completo", fila_usuario["usuario"])
    st.session_state["rol"] = fila_usuario.get("rol", "encargado")


def cerrar_sesion():
    for clave in ("autenticado", "usuario", "nombre_completo", "rol"):
        st.session_state.pop(clave, None)


def esta_autenticado() -> bool:
    return bool(st.session_state.get("autenticado", False))


def usuario_actual() -> str:
    return st.session_state.get("usuario", "")


def nombre_actual() -> str:
    return st.session_state.get("nombre_completo", "")


def rol_actual() -> str:
    return st.session_state.get("rol", "")


def pantalla_login():
    """Dibuja el formulario de login. Devuelve True si el usuario quedó autenticado."""
    st.markdown("## 🏪 Tienda de Abarrotes — Acceso al sistema")
    with st.form("form_login"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        enviado = st.form_submit_button("Ingresar")
    if enviado:
        fila = intentar_login(usuario, password)
        if fila is not None:
            iniciar_sesion(fila)
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos, o la cuenta está inactiva.")
    return esta_autenticado()
