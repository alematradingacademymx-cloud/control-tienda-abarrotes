"""Módulo de Tema: permite al usuario alternar entre modo claro y oscuro
dentro de la propia app (además del que ya trae Streamlit escondido en el
menú ☰ → Settings, este selector es visible siempre en la barra lateral)."""

import streamlit as st

CSS_OSCURO = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stBottomBlockContainer"] {
        background-color: #0e1117;
        color: #fafafa;
    }
    [data-testid="stSidebar"] {
        background-color: #161a23;
    }
    [data-testid="stSidebar"] * {
        color: #fafafa;
    }
    h1, h2, h3, h4, h5, h6, p, span, label, li,
    .stMarkdown, .stCaption, .stAlert, [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"] {
        color: #fafafa !important;
    }
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    .stDateInput input, .stSelectbox div[data-baseweb="select"] > div,
    div[data-baseweb="select"] * {
        background-color: #262730 !important;
        color: #fafafa !important;
        border-color: #3b3f4a !important;
    }
    .stButton button, .stFormSubmitButton button, .stDownloadButton button {
        background-color: #262730;
        color: #fafafa;
        border: 1px solid #3b3f4a;
    }
    .stButton button:hover, .stFormSubmitButton button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
    }
    [data-testid="stMetric"] {
        background-color: #1c1f28;
        border: 1px solid #2d3039;
        border-radius: 8px;
        padding: 10px;
    }
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        background-color: #1c1f28;
        color: #fafafa;
    }
    button[data-baseweb="tab"] {
        color: #d0d0d0 !important;
    }
    [data-testid="stExpander"] {
        background-color: #1c1f28;
        border: 1px solid #2d3039;
    }
    [data-testid="stForm"] {
        background-color: #161a23;
        border: 1px solid #2d3039;
        border-radius: 8px;
    }
    hr {
        border-color: #2d3039 !important;
    }
</style>
"""

# Streamlit, si no se le indica lo contrario, a veces sigue el modo oscuro del
# navegador/sistema operativo — por eso "Claro" también necesita su propio
# CSS explícito (fondo blanco, letras oscuras/azules) en vez de solo "no
# aplicar nada" y confiar en que el tema por defecto sea claro.
CSS_CLARO = """
<style>
    [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stBottomBlockContainer"] {
        background-color: #ffffff;
        color: #0e1117;
    }
    [data-testid="stSidebar"] {
        background-color: #f4f6fa;
    }
    [data-testid="stSidebar"] * {
        color: #0e1117;
    }
    h1, h2, h3, h4, h5, h6, p, span, label, li,
    .stMarkdown, .stCaption, [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"] {
        color: #0e1117 !important;
    }
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    .stDateInput input, .stSelectbox div[data-baseweb="select"] > div,
    div[data-baseweb="select"] * {
        background-color: #ffffff !important;
        color: #0e1117 !important;
        border-color: #c7cdd6 !important;
    }
    .stButton button, .stFormSubmitButton button, .stDownloadButton button {
        background-color: #0b5fff !important;
        color: #ffffff !important;
        border: 1px solid #0b5fff !important;
    }
    .stButton button *, .stFormSubmitButton button *, .stDownloadButton button * {
        color: #ffffff !important;
        fill: #ffffff !important;
    }
    .stButton button:hover, .stFormSubmitButton button:hover, .stDownloadButton button:hover {
        background-color: #084bcc !important;
        border-color: #084bcc !important;
        color: #ffffff !important;
    }
    .stButton button:disabled, .stFormSubmitButton button:disabled {
        background-color: #a9c3f5 !important;
        border-color: #a9c3f5 !important;
        color: #ffffff !important;
        opacity: 1 !important;
    }
    /* Botones +/- de los campos numéricos (number_input): sin esta regla se
    quedaban con el estilo oscuro por defecto de Streamlit y no se veían
    bien en modo claro (cuadro negro, texto del mismo color). */
    [data-testid="stNumberInput"] button {
        background-color: #0b5fff !important;
        border: 1px solid #0b5fff !important;
    }
    [data-testid="stNumberInput"] button svg,
    [data-testid="stNumberInput"] button * {
        fill: #ffffff !important;
        color: #ffffff !important;
    }
    /* Cuadros de selección (Sección, Producto, Método de pago, etc.): con
    versiones más nuevas de Streamlit la regla de arriba a veces ya no
    alcanza a cubrir todo el cuadro, y se quedaba con el fondo oscuro por
    defecto (cuadro negro, letras del mismo color, ilegible). Aquí se cubre
    con más fuerza, incluyendo el menú de opciones que se abre al hacer
    clic (ese menú se dibuja aparte, fuera del cuadro). */
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stSelectbox"] div[data-baseweb="select"],
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-baseweb="select"] {
        background-color: #ffffff !important;
        border-color: #c7cdd6 !important;
    }
    [data-testid="stSelectbox"] * {
        color: #0e1117 !important;
        fill: #0e1117 !important;
    }
    div[data-baseweb="popover"] div[data-baseweb="menu"],
    ul[role="listbox"], li[role="option"] {
        background-color: #ffffff !important;
        color: #0e1117 !important;
    }
    li[role="option"]:hover, li[aria-selected="true"] {
        background-color: #f4f6fa !important;
    }
    /* Encabezado de los "expander" (el título que se le da clic para
    abrir/cerrar, ej. "Buscar producto manualmente"): igual se quedaba con
    el fondo oscuro por defecto y el texto no se veía. */
    [data-testid="stExpander"] summary {
        background-color: #f4f6fa !important;
    }
    [data-testid="stExpander"] summary * {
        color: #0e1117 !important;
        fill: #0e1117 !important;
    }
    /* Avisos flotantes (st.toast) que aparecen arriba a la derecha al
    guardar algo: se quedaban con el fondo oscuro por defecto y el texto
    (forzado a oscuro por las reglas de arriba) no se alcanzaba a leer. */
    [data-testid="stToast"] {
        background-color: #ffffff !important;
        color: #0e1117 !important;
        border: 1px solid #e3e7ee !important;
        box-shadow: 0 4px 14px rgba(14, 17, 23, 0.15) !important;
    }
    [data-testid="stToast"] * {
        color: #0e1117 !important;
    }
    [data-testid="stMetric"] {
        background-color: #f4f6fa;
        border: 1px solid #e3e7ee;
        border-radius: 8px;
        padding: 10px;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #0b5fff !important;
    }
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        background-color: #ffffff;
        color: #0e1117;
    }
    button[data-baseweb="tab"] {
        color: #33415c !important;
    }
    [data-testid="stExpander"] {
        background-color: #f4f6fa;
        border: 1px solid #e3e7ee;
    }
    [data-testid="stForm"] {
        background-color: #f9fafc;
        border: 1px solid #e3e7ee;
        border-radius: 8px;
    }
    hr {
        border-color: #e3e7ee !important;
    }
</style>
"""


def _inicializar_tema():
    if "tema" not in st.session_state:
        st.session_state["tema"] = "Claro"


def selector_tema():
    """Muestra el selector Claro/Oscuro en la barra lateral y aplica el CSS
    correspondiente. Se debe llamar una sola vez, al inicio de app.py, antes
    de dibujar cualquier otra cosa (incluida la pantalla de login)."""
    _inicializar_tema()

    opciones = ["☀️ Claro", "🌙 Oscuro"]
    valor_actual = "☀️ Claro" if st.session_state["tema"] == "Claro" else "🌙 Oscuro"

    with st.sidebar:
        seleccion = st.radio(
            "Tema",
            opciones,
            index=opciones.index(valor_actual),
            horizontal=True,
            label_visibility="collapsed",
            key="selector_tema_radio",
        )

    nuevo_tema = "Oscuro" if "Oscuro" in seleccion else "Claro"
    if nuevo_tema != st.session_state["tema"]:
        st.session_state["tema"] = nuevo_tema
        st.rerun()

    if st.session_state["tema"] == "Oscuro":
        st.markdown(CSS_OSCURO, unsafe_allow_html=True)
    else:
        st.markdown(CSS_CLARO, unsafe_allow_html=True)
