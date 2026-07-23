"""
App Streamlit : détection de structure de marché à partir de tickers Yahoo Finance.

Lancement local :
    streamlit run streamlit_app.py

Sur Streamlit Community Cloud : configurer le "Main file path" sur
`streamlit_app.py` (et non `main.py`, qui est un script CLI séparé).
"""

import streamlit as st

from ohlc_data import get_ohlc_data
from market_structure import compute_market_structure, structure_summary, get_labeled_extremes
from plot_structure import plot_market_structure_interactive

st.set_page_config(page_title="Structure de marché", layout="wide")

st.title("📈 Détection de structure de marché")
st.caption(
    "Basé sur un directional change piloté par l'ATR, agrégé en niveaux "
    "hiérarchiques (zigzags emboîtés)."
)

# --- Barre latérale : paramètres ---
with st.sidebar:
    st.header("Paramètres")
    ticker = st.text_input("Ticker Yahoo Finance", value="AAPL").strip().upper()
    period = st.selectbox("Période d'historique", ["6mo", "1y", "2y", "5y", "max"], index=1)
    interval = st.selectbox("Intervalle", ["1d", "1h", "30m", "15m"], index=0)
    levels = st.slider("Niveaux hiérarchiques", min_value=1, max_value=5, value=3)
    atr_lookback = st.slider("Fenêtre ATR (nb de bougies)", min_value=5, max_value=200, value=30)
    levels_to_plot = st.multiselect(
        "Niveaux à afficher sur le graphique",
        options=list(range(levels)),
        default=list(range(levels)),
    )
    label_level = st.selectbox(
        "Niveau à étiqueter (HH / LH / HL / LL)",
        options=list(range(levels)),
        index=levels - 1,
    )
    run = st.button("Analyser", type="primary", use_container_width=True)

if "history" not in st.session_state:
    st.session_state.history = {}

if run:
    if not ticker:
        st.error("Merci de renseigner un ticker.")
    else:
        try:
            with st.spinner(f"Téléchargement des données pour {ticker}..."):
                df = get_ohlc_data(ticker, period=period, interval=interval)

            with st.spinner("Détection de la structure de marché..."):
                he = compute_market_structure(df, levels=levels, atr_lookback=atr_lookback)

            st.session_state.history[ticker] = (df, he)
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Erreur inattendue : {e}")

# --- Affichage ---
if ticker in st.session_state.history:
    df, he = st.session_state.history[ticker]

    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric("Bougies chargées", len(df))
    with col2:
        st.metric("Dernier prix (close)", f"{df['close'].iloc[-1]:.2f}")

    st.subheader("Graphique de structure (chandeliers, zoom & glisser)")
    st.caption(
        "🔍 Molette / pinch pour zoomer · glisser-déposer pour naviguer dans le temps · "
        "range slider en bas · double-clic pour réinitialiser le zoom."
    )
    fig = plot_market_structure_interactive(
        df, he,
        levels_to_plot=levels_to_plot if levels_to_plot else None,
        label_level=label_level,
        title=f"Structure de marché - {ticker}",
    )
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

    st.subheader("Résumé par niveau")
    st.dataframe(structure_summary(he), use_container_width=True)

    with st.expander("Voir les extrêmes détaillés d'un niveau (avec labels HH/LH/HL/LL)"):
        lvl_choice = st.selectbox("Niveau", options=list(range(he._levels)), key="lvl_detail")
        st.dataframe(get_labeled_extremes(he, lvl_choice), use_container_width=True)
else:
    st.info("Renseignez un ticker dans la barre latérale puis cliquez sur **Analyser**.")
