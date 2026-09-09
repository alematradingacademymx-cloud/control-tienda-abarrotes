"""
Autenticación y control de sesión.
Los usuarios y contraseñas (hasheadas con bcrypt) viven en la hoja "Usuarios".

La sesión de login normalmente vive en st.session_state, que Streamlit borra
por completo cada vez que el navegador hace un refresh (F5) — esto forzaría
a volver a iniciar sesión a cada rato. Para evitarlo, además de guardar el
login en session_state, se guarda un token firmado en la URL (st.query_params).
Al recargar la página, restaurar_sesion() detecta ese token y vuelve a iniciar
sesión automáticamente sin pedir usuario/contraseña, siempre que no haya
expirado y la cuenta siga activa.
"""

import base64
import hashlib
import hmac
import time

import bcrypt
import streamlit as st

from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id

DURACION_SESION_HORAS = 12
_SECRETO_RESPALDO = "cambia-esto-agregando-AUTH_SECRET-en-secrets.toml"


def _clave_secreta() -> bytes:
    # Se recomienda definir AUTH_SECRET en secrets.toml (cualquier texto largo
    # y aleatorio). Si no existe, se usa un respaldo fijo: funciona igual,
    # solo que cualquiera que vea el código sabría la clave de firma.
    secreto = st.secrets.get("AUTH_SECRET", _SECRETO_RESPALDO)
    return str(secreto).encode("utf-8")


def _generar_token(usuario: str) -> str:
    expira = int(time.time()) + DURACION_SESION_HORAS * 3600
    payload = f"{usuario}:{expira}"
    firma = hmac.new(_clave_secreta(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    crudo = f"{payload}:{firma}"
    return base64.urlsafe_b64encode(crudo.encode("utf-8")).decode("utf-8")


def _validar_token(token: str):
    """Devuelve el nombre de usuario si el token es válido y no ha expirado,
    o None si es inválido/expiró."""
    try:
        crudo = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        usuario, expira_str, firma = crudo.split(":")
        payload = f"{usuario}:{expira_str}"
        firma_esperada = hmac.new(_clave_secreta(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(firma, firma_esperada):
            return None
        if int(expira_str) < int(time.time()):
            return None
        return usuario
    except Exception:
        return None


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
    st.query_params["s"] = _generar_token(fila_usuario["usuario"])


def cerrar_sesion():
    for clave in ("autenticado", "usuario", "nombre_completo", "rol"):
        st.session_state.pop(clave, None)
    st.query_params.pop("s", None)


def restaurar_sesion():
    """Si ya hay un token de sesión válido guardado en la URL (por ejemplo,
    después de un refresh de la página), restaura el login automáticamente
    sin pedir usuario/contraseña de nuevo. Se debe llamar una sola vez, al
    inicio de app.py, antes de revisar esta_autenticado()."""
    if esta_autenticado():
        return
    token = st.query_params.get("s")
    if not token:
        return
    usuario_token = _validar_token(token)
    if not usuario_token:
        st.query_params.pop("s", None)
        return
    fila = _buscar_usuario(usuario_token)
    if fila is None or str(fila.get("activo", "")).strip().lower() not in ("si", "sí", "yes", "true", "1"):
        st.query_params.pop("s", None)
        return
    iniciar_sesion(fila)


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
