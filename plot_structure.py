"""
Visualisation de la structure de marché détectée : prix de clôture +
zigzags des extrêmes pour un ou plusieurs niveaux hiérarchiques.
Conçu pour fonctionner aussi bien en script qu'à l'intérieur d'une app
Streamlit (on retourne la Figure matplotlib au lieu de faire plt.show()).
"""

from typing import Iterable, Optional

import matplotlib.pyplot as plt
import pandas as pd

from hierarchical_extremes import HierarchicalExtremes
from market_structure import extremes_to_dataframe

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
