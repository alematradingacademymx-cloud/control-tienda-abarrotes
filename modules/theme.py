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
