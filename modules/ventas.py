"""Módulo de Ventas diarias: arma un carrito con varios productos (por
escáner o buscando manualmente), y hasta el final se confirma la venta
completa: se elige el método de pago y, si es efectivo, se calcula el
cambio exacto a entregar. La lógica del carrito y el registro de la venta
viven en carrito_utils.py (se comparten con Mensajería, que registra la
venta de un envío exactamente de la misma forma).

La pantalla está pensada como una sola vista de "punto de venta": el
código del producto arriba (escanea o escribe y Enter agrega), una barra
de acciones rápidas (Buscar / Vaciar / Cobrar), el ticket en una tabla en
medio, y el total al final — todo visible de un jalón, sin pestañas ni
tener que bajar mucho la pantalla, muy parecido a como ya están
acostumbrados a trabajar en mostrador."""

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import METODOS_PAGO
from sheets_connector import leer_hoja, timestamp_hoy
import modules.carrito_utils as carrito_utils

CLAVE_CARRITO = "carrito_venta"
PREFIJO = "venta"


def _inyectar_atajos():
    """Mantiene enfocado, sin necesidad de mouse, el campo que le toca en
    cada momento: el de 'Cantidad' cuando está pidiendo capturar un peso o
    una cantidad manual, o si no el de 'Código de barras' — y activa los
    atajos Ctrl+C o Alt+C (cobro rápido en efectivo, de un solo golpe),
    Alt+B (buscar producto), Alt+V (vaciar carrito) y Enter (confirmar la
    venta, solo cuando se abrió el panel de "elegir método" con el mouse).

    Se usa Alt+letra en vez de solo la letra porque el campo de código se
    queda enfocado casi todo el tiempo — una letra suelta se interpretaría
    como parte de un código escaneado o escrito a mano, no como un atajo.

    Esto es un truco que aprovecha cómo Streamlit arma su HTML por dentro
    (no es una función oficial de Streamlit ni de este framework), así que
    si en algún momento deja de funcionar bien después de actualizar la
    versión de Streamlit, este es el primer lugar a revisar."""
    components.html(
        """
        <script>
        (function() {
            const parentDoc = window.parent.document;

            function encontrarBoton(texto) {
                const botones = parentDoc.querySelectorAll('button');
                for (const b of botones) {
                    if (b.innerText && b.innerText.includes(texto)) return b;
                }
                return null;
            }

            function campoCodigo() {
                return parentDoc.querySelector('input[aria-label="Código de barras"]');
            }

            function campoCantidad() {
                return parentDoc.querySelector('input[aria-label="Cantidad"]');
            }

            function campoRecibido() {
                return parentDoc.querySelector('input[aria-label="¿Cuánto dinero te dio el cliente? (opcional, solo para calcular el cambio)"]');
            }

            // --- Enfocar automáticamente el campo que corresponda, sin
            // necesidad de mouse: si está pidiendo una cantidad (peso, o
            // búsqueda manual) le da prioridad a ese; si no, al de código,
            // para poder escanear sin darle clic primero. Solo se lo "roba"
            // a la página cuando no hay nada más en uso (nadie escribiendo
            // en otro campo ni con un botón recién presionado). ---
            setInterval(function() {
                const objetivo = campoCantidad() || campoCodigo();
                if (!objetivo) return;
                const activo = parentDoc.activeElement;
                const libre = !activo || activo === parentDoc.body || activo.tagName === 'BUTTON';
                if (libre && activo !== objetivo) {
                    objetivo.focus();
                }
            }, 400);

            // --- Atajos de teclado (instalados una sola vez, aunque este
            // script se vuelva a inyectar en cada actualización de la
            // página). ---
            if (window.parent.__ventasAtajosInstalados) return;
            window.parent.__ventasAtajosInstalados = true;

            window.parent.document.addEventListener('keydown', function(e) {
                const activo = parentDoc.activeElement;

                // Ctrl+C (o Cmd+C en Mac) hace el cobro completo de un
                // golpe: registra la venta en efectivo sin abrir ningún
                // panel ni pedir un Enter aparte.
                if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'c') {
                    const boton = encontrarBoton('Cobro rápido');
                    if (boton) { e.preventDefault(); boton.click(); }
                    return;
                }

                if (e.altKey && !e.ctrlKey && !e.metaKey) {
                    const tecla = e.key.toLowerCase();
                    let boton = null;
                    if (tecla === 'b') boton = encontrarBoton('Buscar producto');
                    else if (tecla === 'v') boton = encontrarBoton('Vaciar carrito');
                    else if (tecla === 'c') boton = encontrarBoton('Cobro rápido');
                    if (boton) { e.preventDefault(); boton.click(); }
                    return;
                }

                if (e.key === 'Enter' && !e.altKey && !e.ctrlKey && !e.metaKey) {
                    // No confirmar si se está escribiendo el código (ese Enter
                    // ya busca/agrega el producto) ni el monto recibido (para
                    // no confirmar a medio escribir la cantidad).
                    if (activo === campoCodigo() || activo === campoRecibido()) return;
                    const boton = encontrarBoton('Confirmar y registrar venta');
                    if (boton) { e.preventDefault(); boton.click(); }
                }
            });
        })();
        </script>
        """,
        height=0,
    )


def _limpiar_pantalla_venta():
    """Deja la pantalla lista para la siguiente venta: cierra la búsqueda
    manual y borra la sección/producto/cantidad/método de pago que hayan
    quedado seleccionados, para no arrastrarlos a la siguiente venta. El
    carrito ya se vacía por su cuenta dentro de registrar_venta_carrito."""
    for key in (
        f"{PREFIJO}_mostrar_busqueda",
        f"{PREFIJO}_seccion_manual",
        f"{PREFIJO}_producto_manual",
        f"{PREFIJO}_cantidad_manual",
        f"{PREFIJO}_cantidad_escaner",
        f"{PREFIJO}_producto_escaneado",
        f"{PREFIJO}_metodo_pago",
        f"{PREFIJO}_recibido_efectivo",
    ):
        st.session_state.pop(key, None)


def _procesar_cobro_rapido():
    """Registra la venta completa de un solo golpe, en efectivo y sin
    calcular cambio — pensado para el atajo Ctrl+C: nada de abrir un panel
    ni de presionar Enter después, todo en una sola acción. Si se necesita
    elegir otro método de pago o calcular el cambio exacto, sigue estando
    el botón "Cobrar (elegir método)" de al lado."""
    if not carrito_utils.obtener_carrito(CLAVE_CARRITO):
        st.warning("Agrega al menos un producto antes de cobrar.")
        return
    turno_venta = st.session_state.get(f"{PREFIJO}_turno_actual", "")
    total_actual = carrito_utils.total_carrito(CLAVE_CARRITO)
    id_venta = carrito_utils.registrar_venta_carrito(CLAVE_CARRITO, "Efectivo", turno=turno_venta)
    mensaje = f"Venta {id_venta} registrada por ${total_actual:,.2f} (Efectivo)."
    st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = False
    _limpiar_pantalla_venta()
    st.session_state[f"{PREFIJO}_ultima_venta"] = mensaje
    st.rerun()


def _render_confirmacion_venta(total: float):
    st.markdown("#### Confirmar venta")

    metodo_pago = st.radio(
        "Método de pago", METODOS_PAGO, horizontal=True, key=f"{PREFIJO}_metodo_pago",
    )

    cambio = None
    recibido = 0.0
    if metodo_pago == "Efectivo":
        recibido = st.number_input(
            "¿Cuánto dinero te dio el cliente? (opcional, solo para calcular el cambio)",
            min_value=0.0, step=10.0, format="%.2f", key=f"{PREFIJO}_recibido_efectivo",
        )
        if recibido == 0:
            st.caption("Puedes dejarlo en 0 y confirmar directo si no necesitas calcular el cambio.")
        else:
            cambio = recibido - total
            if cambio < 0:
                st.warning(f"El monto recibido (${recibido:,.2f}) es menor al total (${total:,.2f}). Aun así puedes confirmar la venta.")
            else:
                st.success(f"💰 Cambio a entregar: ${cambio:,.2f}")

    col_a, col_b = st.columns(2)
    confirmar = col_a.button("✅ Confirmar y registrar venta", type="primary", key=f"{PREFIJO}_btn_confirmar_final")
    cancelar = col_b.button("Cancelar", key=f"{PREFIJO}_btn_cancelar_final")

    if cancelar:
        st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = False
        st.rerun()

    if confirmar:
        # Ya no se exige que el monto recibido cubra el total: si el
        # empleado no lo captura (o le queda corto), la venta se registra
        # de todas formas — el monto recibido es solo para calcular el
        # cambio, no un requisito para guardar.
        turno_venta = st.session_state.get(f"{PREFIJO}_turno_actual", "")
        id_venta = carrito_utils.registrar_venta_carrito(CLAVE_CARRITO, metodo_pago, turno=turno_venta)
        mensaje = f"Venta {id_venta} registrada por ${total:,.2f} ({metodo_pago})."
        if cambio is not None and cambio >= 0:
            mensaje += f" Cambio: ${cambio:,.2f}."
        st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = False
        _limpiar_pantalla_venta()
        st.session_state[f"{PREFIJO}_ultima_venta"] = mensaje
        st.rerun()


def _render_ticket(clave: str, key_prefix: str) -> float:
    """Muestra el carrito como una tabla de ticket (Código / Producto /
    Precio / Cant. / Importe), con sus controles para quitar una unidad o
    la línea completa. Devuelve el total actual (0.0 si está vacío)."""
    st.subheader("🛒 Ticket de venta")
    carrito = carrito_utils.obtener_carrito(clave)
    if not carrito:
        st.info("Todavía no has agregado productos. Escanea o busca uno arriba para empezar.")
        return 0.0

    columnas_grid = [1.6, 3, 1.1, 0.8, 1.2, 0.55, 0.55]
    col_h1, col_h2, col_h3, col_h4, col_h5, col_h6, col_h7 = st.columns(columnas_grid)
    col_h1.markdown("**Código**")
    col_h2.markdown("**Producto**")
    col_h3.markdown("**Precio**")
    col_h4.markdown("**Cant.**")
    col_h5.markdown("**Importe**")
    col_h6.markdown(" ")
    col_h7.markdown(" ")

    for i, item in enumerate(carrito):
        col1, col2, col3, col4, col5, col6, col7 = st.columns(columnas_grid)
        col1.write(item.get("codigo_barras") or item["id_producto"])
        col2.write(item["nombre_producto"])
        col3.write(f"${item['precio_unitario']:,.2f}")
        col4.write(f"{item['cantidad']:g}")
        col5.write(f"**${item['subtotal']:,.2f}**")
        if col6.button("➖", key=f"{key_prefix}_ticket_menos_{i}", help="Quitar 1 unidad (por si escaneaste de más)"):
            carrito_utils.restar_uno_del_carrito(clave, i)
            st.rerun()
        if col7.button("❌", key=f"{key_prefix}_ticket_quitar_{i}", help="Quitar esta línea del ticket"):
            carrito_utils.quitar_del_carrito(clave, i)
            st.rerun()

    st.divider()
    total = carrito_utils.total_carrito(clave)
    st.metric("Total", f"${total:,.2f}")
    return total


def render():
    st.header("🧾 Ventas diarias")
    st.caption(
        "Atajos: Ctrl+C (o Alt+C) cobro rápido en efectivo, de un solo golpe · "
        "Alt+B buscar producto · Alt+V vaciar carrito · Enter confirma solo si abriste "
        "\"Cobrar (elegir método)\" con el mouse."
    )
    _inyectar_atajos()

    if st.session_state.get(f"{PREFIJO}_ultima_venta"):
        st.success(f"✅ {st.session_state.pop(f'{PREFIJO}_ultima_venta')}")

    inventario = leer_hoja("Inventario")
    if inventario.empty:
        st.info("Primero registra productos en el módulo de Inventario.")
        return

    inventario["stock_actual_num"] = pd.to_numeric(inventario["stock_actual"], errors="coerce").fillna(0)

    col_turno, _ = st.columns([1, 3])
    with col_turno:
        carrito_utils.render_selector_turno(PREFIJO)

    st.divider()

    # --- Código del producto: arriba y siempre visible, como en un punto
    # de venta de mostrador — escanea o escribe el código y presiona Enter.
    carrito_utils.render_agregar_por_escaner(CLAVE_CARRITO, inventario, PREFIJO)

    # --- Barra de acciones rápidas ---
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        if st.button("🔍 Buscar producto", key=f"{PREFIJO}_toggle_buscar", use_container_width=True):
            st.session_state[f"{PREFIJO}_mostrar_busqueda"] = not st.session_state.get(f"{PREFIJO}_mostrar_busqueda", False)
    with col_b2:
        if st.button("🗑️ Vaciar carrito", key=f"{PREFIJO}_vaciar_toolbar", use_container_width=True):
            carrito_utils.vaciar_carrito(CLAVE_CARRITO)
            st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = False
            st.rerun()
    with col_b3:
        if st.button(
            "💵 Cobrar (elegir método)", key=f"{PREFIJO}_cobrar_toolbar", use_container_width=True,
            help="Abre el panel para elegir Efectivo/Tarjeta/Transferencia y calcular el cambio exacto.",
        ):
            if not carrito_utils.obtener_carrito(CLAVE_CARRITO):
                st.warning("Agrega al menos un producto antes de cobrar.")
            else:
                st.session_state[f"{PREFIJO}_mostrar_confirmacion"] = True
                st.rerun()
    with col_b4:
        if st.button(
            "⚡ Cobro rápido (Efectivo)", key=f"{PREFIJO}_cobro_rapido", type="primary", use_container_width=True,
            help="Registra la venta de inmediato en efectivo, sin abrir ningún panel (Ctrl+C).",
        ):
            _procesar_cobro_rapido()

    if st.session_state.get(f"{PREFIJO}_mostrar_busqueda"):
        with st.expander("🔍 Buscar producto manualmente", expanded=True):
            carrito_utils.render_agregar_manual(CLAVE_CARRITO, inventario, PREFIJO)

    st.divider()

    total = _render_ticket(CLAVE_CARRITO, PREFIJO)

    if st.session_state.get(f"{PREFIJO}_mostrar_confirmacion"):
        st.divider()
        _render_confirmacion_venta(total)

    st.divider()
    with st.expander("📊 Ventas de hoy"):
        ventas = leer_hoja("Ventas")
        fecha_hoy, _ = timestamp_hoy()
        ventas_hoy = ventas[ventas["fecha"] == fecha_hoy].copy()

        if ventas_hoy.empty:
            st.info("Aún no hay ventas registradas hoy.")
        else:
            ventas_hoy["total_num"] = pd.to_numeric(ventas_hoy["total"], errors="coerce").fillna(0)
            ventas_hoy["ganancia_num"] = pd.to_numeric(ventas_hoy["ganancia"], errors="coerce").fillna(0)
            total_dia = ventas_hoy["total_num"].sum()
            ganancia_dia = ventas_hoy["ganancia_num"].sum()
            resumen = ventas_hoy.groupby("metodo_pago")["total_num"].sum().reindex(METODOS_PAGO, fill_value=0)

            colr1, colr2, colr3, colr4, colr5 = st.columns(5)
            colr1.metric("Total del día", f"${total_dia:,.2f}")
            for col, metodo in zip((colr2, colr3, colr4), METODOS_PAGO):
                col.metric(metodo, f"${resumen.get(metodo, 0):,.2f}")
            colr5.metric("Ganancia estimada", f"${ganancia_dia:,.2f}")

            st.dataframe(
                ventas_hoy[["id_venta", "hora", "usuario", "seccion", "producto", "cantidad", "precio_unitario", "total", "metodo_pago", "ganancia", "turno"]],
                use_container_width=True,
                hide_index=True,
            )
