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
from strategy import detect_setups, backtest_setups, performance_summary, performance_by_period

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

    st.header("Stratégie")
    st.caption("Setup bearish : HH → LL → LH (entrée LH, SL>HH, TP=LL) · Setup bullish (symétrique) : LL → HH → HL")
    strategy_level = st.selectbox(
        "Niveau à analyser (stratégie)",
        options=list(range(levels)),
        index=min(1, levels - 1),
        key="strategy_level",
    )
    period_freq_label = st.selectbox(
        "Regrouper les stats par",
        ["Année", "Trimestre", "Mois", "Semaine"],
        index=0,
    )
    show_trades_on_chart = st.checkbox("Afficher les entrées sur le graphique", value=True)

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

    # Les widgets ci-dessus reflètent l'état ACTUEL des sliders, qui peut avoir
    # changé depuis le dernier clic sur "Analyser" (donc ne pas forcément
    # correspondre au nombre de niveaux réellement calculés dans `he`).
    # On borne tout à ce qui existe vraiment dans `he` pour éviter tout accès
    # hors limites.
    actual_levels = he._levels
    safe_levels_range = list(range(actual_levels))
    safe_levels_to_plot = [l for l in levels_to_plot if l in safe_levels_range] or safe_levels_range
    safe_label_level = label_level if label_level in safe_levels_range else safe_levels_range[-1]
    safe_strategy_level = strategy_level if strategy_level in safe_levels_range else safe_levels_range[-1]

    if actual_levels != levels:
        st.warning(
            f"⚠️ Les paramètres ont changé depuis le dernier clic sur *Analyser* "
            f"(dernière analyse : {actual_levels} niveau(x)). Cliquez à nouveau sur "
            f"**Analyser** pour appliquer les nouveaux réglages."
        )

    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric("Bougies chargées", len(df))
    with col2:
        st.metric("Dernier prix (close)", f"{df['close'].iloc[-1]:.2f}")

    try:
        # --- Calcul de la stratégie sur le niveau sélectionné ---
        setups = detect_setups(he, safe_strategy_level)
        trades = backtest_setups(setups, df) if not setups.empty else setups

        st.subheader("Graphique de structure (chandeliers, zoom & glisser)")
        st.caption(
            "🔍 Molette / pinch pour zoomer · glisser-déposer pour naviguer dans le temps · "
            "range slider en bas · double-clic pour réinitialiser le zoom. "
            "Triangles = entrées de trade (▼ bearish, ▲ bullish), vert = gagnant, rouge = perdant."
        )
        fig = plot_market_structure_interactive(
            df, he,
            levels_to_plot=safe_levels_to_plot,
            label_level=safe_label_level,
            title=f"Structure de marché - {ticker}",
            trades=trades if (show_trades_on_chart and not trades.empty) else None,
        )
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

        st.subheader("Résumé par niveau")
        st.dataframe(structure_summary(he), use_container_width=True)

        with st.expander("Voir les extrêmes détaillés d'un niveau (avec labels HH/LH/HL/LL)"):
            lvl_choice = st.selectbox("Niveau", options=safe_levels_range, key="lvl_detail")
            st.dataframe(get_labeled_extremes(he, lvl_choice), use_container_width=True)

        # --- Section stratégie ---
        st.divider()
        st.subheader(f"📊 Stratégie — niveau {safe_strategy_level}")

        if trades.empty:
            st.info("Aucun setup HH→LL→LH / LL→HH→HL détecté sur ce niveau avec ces paramètres.")
        else:
            summary = performance_summary(trades)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Trades", summary["n_trades"])
            c2.metric("Winrate", f"{summary['winrate']*100:.1f}%" if summary["winrate"] == summary["winrate"] else "—")
            c3.metric("RR moyen", f"{summary['avg_rr']:.2f}" if summary["avg_rr"] == summary["avg_rr"] else "—")
            c4.metric("Expectancy (R)", f"{summary['expectancy_r']:+.2f}" if summary["expectancy_r"] == summary["expectancy_r"] else "—")
            c5.metric("Trades ouverts", summary["n_open"])

            st.markdown(f"**Détail par {period_freq_label.lower()}**")
            freq_code = {"Année": "Y", "Trimestre": "Q", "Mois": "M", "Semaine": "W"}[period_freq_label]
            by_period = performance_by_period(trades, freq=freq_code)
            if by_period.empty:
                st.info("Pas encore de trade clôturé pour établir des statistiques par période.")
            else:
                display_period = by_period.copy()
                display_period["winrate"] = (display_period["winrate"] * 100).round(1).astype(str) + "%"
                display_period["avg_rr"] = display_period["avg_rr"].round(2)
                display_period["expectancy_r"] = display_period["expectancy_r"].round(2)
                st.dataframe(display_period, use_container_width=True)

            with st.expander("Voir le journal détaillé des trades"):
                trade_cols = [
                    "direction", "entry_time", "entry_price", "sl_price", "tp_price",
                    "risk", "reward", "rr", "outcome", "exit_time", "exit_price", "pnl_r",
                ]
                st.dataframe(trades[trade_cols], use_container_width=True)
    except Exception as e:
        st.error("Une erreur est survenue pendant l'affichage. Détail complet ci-dessous :")
        st.exception(e)
else:
    st.info("Renseignez un ticker dans la barre latérale puis cliquez sur **Analyser**.")
