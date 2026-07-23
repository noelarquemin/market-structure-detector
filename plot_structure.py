"""
Visualisation de la structure de marché détectée : prix de clôture +
zigzags des extrêmes pour un ou plusieurs niveaux hiérarchiques.
Conçu pour fonctionner aussi bien en script qu'à l'intérieur d'une app
Streamlit (on retourne la Figure matplotlib au lieu de faire plt.show()).
"""

from typing import Iterable, Optional

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go

from hierarchical_extremes import HierarchicalExtremes
from market_structure import extremes_to_dataframe, classify_extremes

LEVEL_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def plot_market_structure(
    df: pd.DataFrame,
    he: HierarchicalExtremes,
    levels_to_plot: Optional[Iterable[int]] = None,
    title: str = "Structure de marché",
    figsize=(14, 7),
):
    """
    Trace le prix de clôture et superpose, pour chaque niveau demandé,
    les segments reliant les extrêmes confirmés (hauts/bas alternés).

    Parameters
    ----------
    df : pd.DataFrame
        Données OHLC utilisées pour la détection (index = datetime).
    he : HierarchicalExtremes
        Résultat de `compute_market_structure`.
    levels_to_plot : Iterable[int], optionnel
        Niveaux à superposer (par défaut : tous les niveaux disponibles).
    title : str
        Titre du graphique.
    figsize : tuple
        Taille de la figure.

    Returns
    -------
    matplotlib.figure.Figure
    """
    if levels_to_plot is None:
        levels_to_plot = range(he._levels)

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(df.index, df["close"], color="lightgray", linewidth=0.8, label="Close", zorder=1)

    for lvl in levels_to_plot:
        ext_df = extremes_to_dataframe(he, lvl)
        if ext_df.empty:
            continue
        color = LEVEL_COLORS[lvl % len(LEVEL_COLORS)]
        ax.plot(
            ext_df["timestamp"], ext_df["price"],
            marker="o", markersize=4, linewidth=1.5,
            color=color, label=f"Niveau {lvl} ({len(ext_df)} extrêmes)",
            zorder=2 + lvl,
        )

    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Prix")
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_market_structure_interactive(
    df: pd.DataFrame,
    he: HierarchicalExtremes,
    levels_to_plot: Optional[Iterable[int]] = None,
    label_level: Optional[int] = None,
    title: str = "Structure de marché",
    height: int = 700,
    trades: Optional[pd.DataFrame] = None,
) -> go.Figure:
    """
    Graphique interactif (Plotly) : chandeliers OHLC + zigzags de structure
    par niveau, avec zoom molette, glisser (pan) et range slider en bas du
    graphique pour naviguer dans le temps. Les extrêmes du niveau
    `label_level` sont annotés HH / LH / HL / LL.

    Parameters
    ----------
    df : pd.DataFrame
        Données OHLC (colonnes 'open', 'high', 'low', 'close').
    he : HierarchicalExtremes
        Résultat de `compute_market_structure`.
    levels_to_plot : Iterable[int], optionnel
        Niveaux à superposer (par défaut : tous les niveaux disponibles).
    label_level : int, optionnel
        Niveau dont les points reçoivent les étiquettes HH/LH/HL/LL
        (par défaut : le niveau le plus élevé parmi `levels_to_plot`,
        c'est-à-dire la structure la plus "macro").
    title : str
        Titre du graphique.
    height : int
        Hauteur du graphique en pixels.

    Returns
    -------
    plotly.graph_objects.Figure
    """
    if levels_to_plot is None:
        levels_to_plot = list(range(he._levels))
    else:
        levels_to_plot = list(levels_to_plot)

    if label_level is None and levels_to_plot:
        label_level = max(levels_to_plot)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="Prix",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ))

    for lvl in levels_to_plot:
        ext_df = extremes_to_dataframe(he, lvl)
        if ext_df.empty:
            continue
        ext_df = classify_extremes(ext_df)
        color = LEVEL_COLORS[lvl % len(LEVEL_COLORS)]
        show_labels = (lvl == label_level)

        textposition = [
            "top center" if t == 1 else "bottom center"
            for t in ext_df["ext_type"]
        ]

        fig.add_trace(go.Scatter(
            x=ext_df["timestamp"], y=ext_df["price"],
            mode="lines+markers+text" if show_labels else "lines+markers",
            text=ext_df["label"] if show_labels else None,
            textposition=textposition if show_labels else None,
            textfont=dict(size=11, color=color),
            line=dict(color=color, width=1.5),
            marker=dict(size=5, color=color),
            name=f"Niveau {lvl} ({len(ext_df)} extrêmes)",
        ))

    fig.update_layout(
        title=title,
        height=height,
        xaxis_rangeslider_visible=True,
        dragmode="pan",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_yaxes(title_text="Prix", fixedrange=False)
    fig.update_xaxes(title_text="Date")

    if trades is not None and not trades.empty:
        color_map = {"win": "#00c853", "loss": "#d50000", "open": "#9e9e9e"}
        symbol_map = {"bearish": "triangle-down", "bullish": "triangle-up"}

        for outcome_val, grp in trades.groupby("outcome"):
            fig.add_trace(go.Scatter(
                x=grp["entry_time"], y=grp["entry_price"],
                mode="markers",
                marker=dict(
                    size=12,
                    color=color_map.get(outcome_val, "#9e9e9e"),
                    symbol=[symbol_map.get(d, "circle") for d in grp["direction"]],
                    line=dict(width=1, color="#222"),
                ),
                name=f"Entrées ({outcome_val})",
                text=[
                    f"{d} | RR={rr:.2f}" if pd.notna(rr) else f"{d}"
                    for d, rr in zip(grp["direction"], grp["rr"])
                ],
                hovertemplate="%{text}<br>Prix: %{y:.2f}<br>%{x}<extra></extra>",
            ))

    return fig
