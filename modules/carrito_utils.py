"""Utilidades de carrito de productos, compartidas entre Ventas diarias
(venta de mostrador) y Mensajería (venta a domicilio) — así ambas registran
la venta exactamente de la misma forma: se arma un carrito con uno o varios
productos (por escáner o buscando manualmente) y al confirmar se escribe una
fila por producto en 'Ventas' (todas con el mismo id_venta) y se descuenta
el inventario.

Cada pantalla que use este módulo debe pasar una `clave` distinta (el
nombre de la llave en session_state) para que sus carritos no se mezclen, y
un `key_prefix` distinto para que los widgets de Streamlit no choquen entre
pantallas."""

from datetime import datetime

import pandas as pd
import streamlit as st

from config import TURNOS, HORARIO_TURNOS
from sheets_connector import leer_hoja, agregar_fila, actualizar_fila_por_id, siguiente_id, timestamp_hoy
from auth import usuario_actual


def turno_por_hora(hora_str: str) -> str:
    """Clasifica una hora ('HH:MM:SS' o 'HH:MM') dentro de uno de los TURNOS,
    según los rangos definidos en HORARIO_TURNOS. El turno nocturno cruza la
    medianoche (ej. 20:00 a 06:00)."""
    if not hora_str or not isinstance(hora_str, str):
        return TURNOS[-1]
    hora = hora_str[:5]
    for turno, (inicio, fin) in HORARIO_TURNOS.items():
        if inicio < fin:
            if inicio <= hora < fin:
                return turno
        else:
            # Turno que cruza la medianoche (ej. Nocturno: 20:00 - 06:00)
            if hora >= inicio or hora < fin:
                return turno
    return TURNOS[-1]


def turno_sugerido_ahora() -> str:
    """Turno que le correspondería a la hora actual del sistema."""
    return turno_por_hora(datetime.now().strftime("%H:%M:%S"))


def render_selector_turno(key_prefix: str) -> str:
    """Muestra un selector de turno (Matutino/Vespertino/Nocturno) ya
    sugerido automáticamente según la hora actual, pero que se puede cambiar
    a mano si el horario real no coincide (ej. alguien se queda más tiempo).
    El valor elegido se guarda en session_state y se usa al registrar la
    venta. Devuelve el turno elegido."""
    turno_key = f"{key_prefix}_turno_actual"
    if turno_key not in st.session_state:
        st.session_state[turno_key] = turno_sugerido_ahora()

    valor_guardado = st.session_state[turno_key]
    indice = TURNOS.index(valor_guardado) if valor_guardado in TURNOS else 0

    turno = st.selectbox(
        "🕐 Turno de esta venta",
        TURNOS,
        index=indice,
        key=turno_key,
        help="Se sugiere solo según la hora actual, pero puedes cambiarlo si tu turno real es otro.",
    )
    return turno


def obtener_carrito(clave: str) -> list:
    if clave not in st.session_state:
        st.session_state[clave] = []
    return st.session_state[clave]


def cantidad_en_carrito(clave: str, id_producto) -> float:
    return sum(item["cantidad"] for item in obtener_carrito(clave) if item["id_producto"] == id_producto)


def agregar_al_carrito(clave: str, fila_producto: dict, seccion: str, cantidad: float, precio_unitario: float):
    """Agrega `cantidad` unidades del producto al carrito. Si ese mismo
    producto (mismo id_producto y mismo precio_unitario) ya está en el
    carrito, simplemente le suma la cantidad a esa línea en vez de crear una
    línea nueva — así, si escaneas el mismo producto varias veces, se ve como
    una sola línea con el total acumulado (ej. '3 x Cigarro suelto') en vez
    de tres líneas repetidas."""
    costo_unitario = float(pd.to_numeric(fila_producto.get("costo_unitario", 0), errors="coerce") or 0)
    carrito = obtener_carrito(clave)
    for item in carrito:
        if item["id_producto"] == fila_producto["id_producto"] and item["precio_unitario"] == precio_unitario:
            item["cantidad"] += cantidad
            item["subtotal"] = item["precio_unitario"] * item["cantidad"]
            return
    carrito.append({
        "id_producto": fila_producto["id_producto"],
        "nombre_producto": fila_producto["nombre_producto"],
        "codigo_barras": str(fila_producto.get("codigo_barras", "") or ""),
        "seccion": seccion,
        "cantidad": cantidad,
        "precio_unitario": precio_unitario,
        "costo_unitario": costo_unitario,
        "subtotal": precio_unitario * cantidad,
    })


def quitar_del_carrito(clave: str, indice: int):
    carrito = obtener_carrito(clave)
    if 0 <= indice < len(carrito):
        carrito.pop(indice)


def restar_uno_del_carrito(clave: str, indice: int):
    """Resta 1 unidad a la línea del carrito en ese índice (útil para
    corregir un escaneo de más). Si llega a 0 o menos, quita la línea por
    completo."""
    carrito = obtener_carrito(clave)
    if not (0 <= indice < len(carrito)):
        return
    item = carrito[indice]
    item["cantidad"] -= 1
    if item["cantidad"] <= 0:
        carrito.pop(indice)
    else:
        item["subtotal"] = item["precio_unitario"] * item["cantidad"]


def vaciar_carrito(clave: str):
    st.session_state[clave] = []


def total_carrito(clave: str) -> float:
    return sum(item["subtotal"] for item in obtener_carrito(clave))


def registrar_venta_carrito(clave: str, metodo_pago: str, turno: str = "") -> str:
    """Escribe una fila en 'Ventas' por cada producto del carrito indicado
    (mismo id_venta para todas, como líneas de un mismo ticket), descuenta
    el inventario, vacía el carrito y devuelve el id_venta generado.
    Si el carrito está vacío, no escribe nada y devuelve ''."""
    carrito = obtener_carrito(clave)
    if not carrito:
        return ""

    fecha, hora = timestamp_hoy()
    id_venta = siguiente_id("Ventas", "id_venta", prefijo="V")
    usuario = usuario_actual()

    for item in carrito:
        ganancia = (item["precio_unitario"] - item["costo_unitario"]) * item["cantidad"]
        agregar_fila("Ventas", {
            "id_venta": id_venta,
            "fecha": fecha,
            "hora": hora,
            "usuario": usuario,
            "seccion": item["seccion"],
            "id_producto": item["id_producto"],
            "producto": item["nombre_producto"],
            "cantidad": item["cantidad"],
            "precio_unitario": item["precio_unitario"],
            "total": item["subtotal"],
            "metodo_pago": metodo_pago,
            "turno": turno,
            "costo_unitario": item["costo_unitario"],
            "ganancia": ganancia,
        })

    cantidades_por_producto = {}
    for item in carrito:
        cantidades_por_producto[item["id_producto"]] = (
            cantidades_por_producto.get(item["id_producto"], 0) + item["cantidad"]
        )

    inventario_actual = leer_hoja("Inventario")
    for id_producto, cantidad_vendida in cantidades_por_producto.items():
        fila_inv = inventario_actual[inventario_actual["id_producto"] == id_producto]
        if fila_inv.empty:
            continue
        stock_actual = pd.to_numeric(fila_inv.iloc[0].get("stock_actual", 0), errors="coerce")
        stock_actual = float(stock_actual) if pd.notna(stock_actual) else 0.0
        actualizar_fila_por_id("Inventario", "id_producto", id_producto, {
            "stock_actual": stock_actual - cantidad_vendida,
            "fecha_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    vaciar_carrito(clave)
    return id_venta


def render_agregar_por_escaner(clave: str, inventario: pd.DataFrame, key_prefix: str):
    """Widget de escaneo de código de barras para agregar productos al
    carrito `clave`.

    Para productos que se venden por pieza, cada escaneo agrega 1 unidad de
    inmediato — sin pasos manuales — así que para vender, por ejemplo, 3
    cigarros sueltos basta con pasar el escáner 3 veces seguidas y el
    carrito acumula la cantidad solo. Para productos que se venden por peso
    (kilo, medio kilo, etc.) sí se pide capturar la cantidad a mano, porque
    ahí no tiene sentido "contar escaneos" — se necesita pesar el producto."""
    st.caption(
        "Coloca el cursor en el siguiente campo y escanea el código de barras del producto. "
        "Para productos por pieza, puedes escanear varias veces seguidas: cada escaneo suma 1 al carrito."
    )

    if "codigo_barras" not in inventario.columns:
        st.warning("Todavía no hay productos con código de barras registrado. Agrégalo desde el módulo de Inventario.")
        return

    estado_key = f"{key_prefix}_producto_escaneado"

    with st.form(f"{key_prefix}_form_escanear_codigo", clear_on_submit=True):
        codigo = st.text_input("Código de barras", key=f"{key_prefix}_input_codigo_barras")
        buscar = st.form_submit_button("Buscar")

    if buscar:
        codigo = (codigo or "").strip()
        if not codigo:
            st.warning("Escanea o escribe un código antes de buscar.")
        else:
            coincidencias = inventario[inventario["codigo_barras"].astype(str).str.strip() == codigo]
            if coincidencias.empty:
                st.error(f"No se encontró ningún producto con el código '{codigo}'.")
                st.session_state.pop(estado_key, None)
            else:
                producto_escaneado = coincidencias.iloc[0].to_dict()
                unidad = str(producto_escaneado.get("unidad", "") or "").strip()

                if unidad in ("", "Pieza"):
                    # Se vende por pieza: agregar 1 unidad de inmediato, sin
                    # confirmación manual, para poder escanear varias veces seguidas.
                    stock_disp = float(pd.to_numeric(producto_escaneado.get("stock_actual", 0), errors="coerce") or 0)
                    stock_disp -= cantidad_en_carrito(clave, producto_escaneado["id_producto"])
                    precio_unitario = float(pd.to_numeric(producto_escaneado.get("precio_venta", 0), errors="coerce") or 0)

                    if stock_disp < 1:
                        st.error(f"'{producto_escaneado['nombre_producto']}' ya no tiene stock disponible (o ya lo agregaste todo al carrito).")
                    else:
                        agregar_al_carrito(clave, producto_escaneado, producto_escaneado["seccion"], 1.0, precio_unitario)
                        st.toast(f"+1 {producto_escaneado['nombre_producto']} agregado al carrito.", icon="🛒")
                    st.session_state.pop(estado_key, None)
                    st.rerun()
                else:
                    # Se vende por peso: se necesita capturar la cantidad a mano.
                    st.session_state[estado_key] = producto_escaneado

    producto = st.session_state.get(estado_key)
    if not producto:
        return

    stock_disp = float(pd.to_numeric(producto.get("stock_actual", 0), errors="coerce") or 0)
    stock_disp -= cantidad_en_carrito(clave, producto["id_producto"])
    precio_unitario = float(pd.to_numeric(producto.get("precio_venta", 0), errors="coerce") or 0)

    if stock_disp <= 0:
        st.error(f"'{producto['nombre_producto']}' ya no tiene stock disponible (o ya lo agregaste todo al carrito).")
        return

    unidad_producto = str(producto.get("unidad", "") or "Pieza").strip() or "Pieza"
    st.success(
        f"Producto encontrado: **{producto['nombre_producto']}** — Sección: {producto['seccion']} — "
        f"Se vende por: {unidad_producto} — Stock disponible: {stock_disp:g}"
    )

    # Dentro de un form: escribes la cantidad (el peso) y presionas Enter
    # para mandarlo directo al carrito, sin necesidad de darle clic a nada
    # — más rápido para vender por peso seguido. El precio de contado se
    # ve aparte; el importe final ya se ve en la línea del ticket en
    # cuanto se agrega.
    cantidad_key = f"{key_prefix}_cantidad_escaner"
    with st.form(f"{key_prefix}_form_cantidad_escaner", clear_on_submit=False):
        colc1, colc2, colc3 = st.columns(3)
        with colc1:
            # Vacío en vez de venir con "1.00" ya puesto: así el empleado
            # siempre escribe la cantidad real a mano y nunca se le pasa
            # por alto dejar el "1" que traía por default.
            cantidad = st.number_input(
                "Cantidad", min_value=0.0, max_value=stock_disp, step=1.0, value=None,
                placeholder="Escribe la cantidad", key=cantidad_key,
            )
        with colc2:
            st.metric("Precio unitario", f"${precio_unitario:,.2f}")
        with colc3:
            # Este valor es solo el inicial (para cuando no hay JavaScript,
            # como en Mensajería). En Ventas diarias se recalcula al
            # instante con cada tecla que se escribe en "Cantidad" gracias al
            # script inyectado en ventas.py — así se ve junto al precio
            # unitario sin tener que bajar la página, incluso antes de
            # presionar Enter.
            st.metric("Total a pagar", f"${precio_unitario * (cantidad or 0):,.2f}")
        agregar = st.form_submit_button("➕ Agregar al carrito (o presiona Enter)", type="primary")

    if agregar:
        if cantidad is None or cantidad <= 0:
            st.error("Escribe una cantidad mayor a cero.")
        elif cantidad > stock_disp:
            st.error("No hay suficiente stock para esa cantidad.")
        else:
            agregar_al_carrito(clave, producto, producto["seccion"], cantidad, precio_unitario)
            st.session_state.pop(estado_key, None)
            st.session_state.pop(cantidad_key, None)
            st.toast(f"{cantidad:g} x {producto['nombre_producto']} agregado al carrito.", icon="🛒")
            st.rerun()

    if st.button("Cancelar / escanear otro producto", key=f"{key_prefix}_cancelar_escaneo"):
        st.session_state.pop(estado_key, None)
        st.rerun()


def render_agregar_manual(clave: str, inventario: pd.DataFrame, key_prefix: str):
    """Widget de búsqueda manual (sección + producto) para agregar productos
    al carrito `clave`."""
    secciones = sorted(inventario["seccion"].dropna().unique().tolist())
    col1, col2 = st.columns(2)
    with col1:
        seccion_sel = st.selectbox("Sección", secciones, key=f"{key_prefix}_seccion_manual")
    productos_seccion = inventario[inventario["seccion"] == seccion_sel]
    productos_disponibles = productos_seccion[productos_seccion["stock_actual_num"] > 0]

    if productos_disponibles.empty:
        st.warning("No hay productos con stock disponible en esta sección.")
        return

    with col2:
        opciones_producto = (
            productos_disponibles["nombre_producto"]
            + " (stock: " + productos_disponibles["stock_actual_num"].astype(str) + ")"
        )
        seleccion = st.selectbox("Producto", opciones_producto, key=f"{key_prefix}_producto_manual")
    nombre_producto = seleccion.split(" (stock:")[0]
    fila_producto = productos_disponibles[productos_disponibles["nombre_producto"] == nombre_producto].iloc[0]

    precio_unitario = float(fila_producto["precio_venta"] or 0)
    stock_disp = float(fila_producto["stock_actual_num"]) - cantidad_en_carrito(clave, fila_producto["id_producto"])

    if stock_disp <= 0:
        st.warning(f"Ya agregaste al carrito todo el stock disponible de '{nombre_producto}'.")
        return

    # Dentro de un form: escribes/ajustas la cantidad y presionas Enter
    # para mandarlo directo al carrito, sin necesidad de darle clic a
    # "Agregar al carrito" — la sección y el producto se quedan fuera del
    # form para que el menú reaccione al instante al elegirlos.
    cantidad_key = f"{key_prefix}_cantidad_manual"
    with st.form(f"{key_prefix}_form_cantidad_manual", clear_on_submit=False):
        colc1, colc2, colc3 = st.columns(3)
        with colc1:
            # Vacío en vez de "1.00" por default, igual que en el escáner:
            # el empleado siempre escribe la cantidad real a mano.
            cantidad = st.number_input(
                "Cantidad", min_value=0.0, max_value=stock_disp, step=1.0, value=None,
                placeholder="Escribe la cantidad", key=cantidad_key,
            )
        with colc2:
            st.metric("Precio unitario", f"${precio_unitario:,.2f}")
        with colc3:
            # Igual que en el escáner: valor inicial nada más, en Ventas
            # diarias se recalcula al instante con JavaScript mientras se
            # escribe la cantidad (ver ventas.py).
            st.metric("Total a pagar", f"${precio_unitario * (cantidad or 0):,.2f}")
        agregar = st.form_submit_button("➕ Agregar al carrito (o presiona Enter)", type="primary")

    if agregar:
        if cantidad is None or cantidad <= 0:
            st.error("Escribe una cantidad mayor a cero.")
        elif cantidad > stock_disp:
            st.error("No hay suficiente stock para esa cantidad.")
        else:
            agregar_al_carrito(clave, fila_producto, seccion_sel, cantidad, precio_unitario)
            st.session_state.pop(cantidad_key, None)
            st.toast(f"{cantidad:g} x {nombre_producto} agregado al carrito.", icon="🛒")
            st.rerun()


def render_lista_carrito(clave: str, key_prefix: str) -> float:
    """Muestra los productos ya agregados con un botón para quitar cada uno,
    y el total. Devuelve el total actual (0.0 si el carrito está vacío)."""
    carrito = obtener_carrito(clave)
    if not carrito:
        st.info("Todavía no has agregado productos (usa el escáner o la búsqueda manual de arriba).")
        return 0.0

    for i, item in enumerate(carrito):
        col_desc, col_menos, col_quitar = st.columns([6, 1, 1])
        col_desc.write(f"**{item['cantidad']:g}** x {item['nombre_producto']} — ${item['subtotal']:,.2f}")
        if col_menos.button("➖", key=f"{key_prefix}_menos_{i}", help="Quitar 1 unidad (por si escaneaste de más)"):
            restar_uno_del_carrito(clave, i)
            st.rerun()
        if col_quitar.button("❌", key=f"{key_prefix}_quitar_{i}", help="Quitar todo del carrito"):
            quitar_del_carrito(clave, i)
            st.rerun()

    total = total_carrito(clave)
    st.metric("Total de productos", f"${total:,.2f}")
    return total
