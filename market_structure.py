"""
Détection de la structure de marché à partir de données OHLC.

S'appuie sur :
- atr_directional_change.py : détecte les extrêmes (hauts/bas) "bruts" de niveau 0
  via un algorithme de directional change basé sur l'ATR.
- hierarchical_extremes.py   : agrège ces extrêmes de niveau 0 en extrêmes de
  niveaux supérieurs (structure "macro"), un peu comme des zigzags emboîtés.

Ce module ajoute :
- une fonction pour lancer la détection sur un DataFrame OHLC complet
- une conversion des résultats en DataFrame par niveau (facile à afficher/tracer)
- une estimation simple de la tendance par niveau (haussière / baissière / range)
  basée sur la logique HH-HL (Higher High / Higher Low) et LH-LL (Lower High / Lower Low)
"""

from dataclasses import asdict
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from hierarchical_extremes import HierarchicalExtremes
from local_extreme import LocalExtreme


TREND_BULLISH = "haussière"
TREND_BEARISH = "baissière"
TREND_RANGE = "indéterminée"


def compute_market_structure(
    df: pd.DataFrame,
    levels: int = 3,
    atr_lookback: int = 100,
) -> HierarchicalExtremes:
    """
    Lance la détection de structure sur l'intégralité du DataFrame OHLC.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame indexé par datetime, avec colonnes 'open', 'high', 'low', 'close'
        (voir ohlc_data.get_ohlc_data).
    levels : int
        Nombre de niveaux hiérarchiques à calculer (1 = uniquement les extrêmes
        "bruts" du directional change, sans agrégation).
    atr_lookback : int
        Fenêtre (en nombre de bougies) utilisée pour le calcul de l'ATR qui
        pilote la sensibilité de détection des extrêmes. Plus la valeur est
        grande, moins il y a d'extrêmes détectés (structure plus "macro").

    Returns
    -------
    HierarchicalExtremes
        Instance contenant `.extremes[level]` = liste de LocalExtreme pour
        chaque niveau demandé.
    """
    if not {"open", "high", "low", "close"}.issubset(df.columns):
        raise ValueError("Le DataFrame doit contenir les colonnes 'open', 'high', 'low', 'close'.")

    he = HierarchicalExtremes(levels=levels, atr_lookback=atr_lookback)

    time_index = df.index
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()

    for i in range(len(df)):
        he.update(i, time_index, high, low, close)

    return he


def extremes_to_dataframe(he: HierarchicalExtremes, level: int) -> pd.DataFrame:
    """
    Convertit les extrêmes confirmés d'un niveau donné en DataFrame,
    triés par ordre chronologique (index de bougie croissant).
    """
    exts = he.extremes[level]
    if len(exts) == 0:
        return pd.DataFrame(columns=[
            "ext_type", "index", "price", "timestamp",
            "conf_index", "conf_price", "conf_timestamp",
        ])
    rows = [asdict(e) for e in exts]
    ext_df = pd.DataFrame(rows).sort_values("index").reset_index(drop=True)
    return ext_df


def get_all_levels_dataframes(he: HierarchicalExtremes) -> List[pd.DataFrame]:
    """Retourne la liste des DataFrames d'extrêmes, un par niveau."""
    return [extremes_to_dataframe(he, lvl) for lvl in range(he._levels)]


def determine_trend(ext_df: pd.DataFrame) -> Dict[str, object]:
    """
    Détermine la tendance courante d'un niveau à partir de ses 4 derniers
    extrêmes confirmés (2 hauts + 2 bas), selon la logique classique de
    structure de marché :

    - Higher High + Higher Low  -> tendance haussière
    - Lower High  + Lower Low   -> tendance baissière
    - sinon                     -> range / indéterminée

    Parameters
    ----------
    ext_df : pd.DataFrame
        DataFrame d'extrêmes pour un niveau (voir `extremes_to_dataframe`),
        triés chronologiquement, avec alternance haut/bas garantie par
        `extremes_sanity_checks`.

    Returns
    -------
    dict avec les clés :
        'trend'        : TREND_BULLISH / TREND_BEARISH / TREND_RANGE
        'last_high'    : dernier haut confirmé (float ou None)
        'prev_high'    : haut précédent (float ou None)
        'last_low'     : dernier bas confirmé (float ou None)
        'prev_low'     : bas précédent (float ou None)
    """
    result = {
        "trend": TREND_RANGE,
        "last_high": None, "prev_high": None,
        "last_low": None, "prev_low": None,
    }

    if len(ext_df) < 4:
        return result

    highs = ext_df[ext_df["ext_type"] == 1]
    lows = ext_df[ext_df["ext_type"] == -1]

    if len(highs) < 2 or len(lows) < 2:
        return result

    last_high, prev_high = highs["price"].iloc[-1], highs["price"].iloc[-2]
    last_low, prev_low = lows["price"].iloc[-1], lows["price"].iloc[-2]

    result.update({
        "last_high": float(last_high), "prev_high": float(prev_high),
        "last_low": float(last_low), "prev_low": float(prev_low),
    })

    if last_high > prev_high and last_low > prev_low:
        result["trend"] = TREND_BULLISH
    elif last_high < prev_high and last_low < prev_low:
        result["trend"] = TREND_BEARISH
    else:
        result["trend"] = TREND_RANGE

    return result


def classify_extremes(ext_df: pd.DataFrame) -> pd.DataFrame:
    """
    Classe chaque extrême confirmé d'un niveau selon la nomenclature
    classique de structure de marché, en le comparant au précédent
    extrême du même type (haut vs haut précédent, bas vs bas précédent) :

    - 'HH' (Higher High)  : haut plus haut que le haut précédent
    - 'LH' (Lower High)   : haut plus bas que le haut précédent
    - 'HL' (Higher Low)   : bas plus haut que le bas précédent
    - 'LL' (Lower Low)    : bas plus bas que le bas précédent
    - 'H' / 'L'           : tout premier haut / bas de la série (pas de référence)

    Parameters
    ----------
    ext_df : pd.DataFrame
        DataFrame d'extrêmes pour un niveau, trié chronologiquement
        (voir `extremes_to_dataframe`).

    Returns
    -------
    pd.DataFrame
        Copie de `ext_df` avec une colonne supplémentaire 'label'.
    """
    df = ext_df.copy()
    if df.empty:
        df["label"] = pd.Series(dtype=str)
        return df

    labels = []
    last_high: Optional[float] = None
    last_low: Optional[float] = None

    for _, row in df.iterrows():
        if row["ext_type"] == 1:  # haut
            if last_high is None:
                labels.append("H")
            elif row["price"] > last_high:
                labels.append("HH")
            else:
                labels.append("LH")
            last_high = row["price"]
        else:  # bas
            if last_low is None:
                labels.append("L")
            elif row["price"] < last_low:
                labels.append("LL")
            else:
                labels.append("HL")
            last_low = row["price"]

    df["label"] = labels
    return df


def get_labeled_extremes(he: HierarchicalExtremes, level: int) -> pd.DataFrame:
    """Raccourci : récupère les extrêmes d'un niveau déjà classés HH/LH/HL/LL."""
    return classify_extremes(extremes_to_dataframe(he, level))


def structure_summary(he: HierarchicalExtremes) -> pd.DataFrame:
    """
    Construit un tableau récapitulatif (une ligne par niveau) avec la
    tendance détectée et les derniers points de structure.
    Pratique pour un affichage rapide dans une app Streamlit.
    """
    rows = []
    for lvl in range(he._levels):
        ext_df = extremes_to_dataframe(he, lvl)
        trend_info = determine_trend(ext_df)
        rows.append({
            "level": lvl,
            "n_extremes": len(ext_df),
            "trend": trend_info["trend"],
            "last_high": trend_info["last_high"],
            "prev_high": trend_info["prev_high"],
            "last_low": trend_info["last_low"],
            "prev_low": trend_info["prev_low"],
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    # Petit test avec des données synthétiques (utile hors connexion internet)
    rng = np.random.default_rng(42)
    n = 3000
    dates = pd.date_range("2023-01-01", periods=n, freq="h")
    steps = rng.normal(0, 1, n).cumsum()
    close = 100 + steps
    high = close + rng.uniform(0, 1, n)
    low = close - rng.uniform(0, 1, n)
    open_ = close + rng.normal(0, 0.3, n)

    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=dates)

    he = compute_market_structure(df, levels=3, atr_lookback=50)
    print(structure_summary(he))
