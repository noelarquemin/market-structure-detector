"""
Stratégie de trading basée sur les séquences de structure de marché
(labels HH / LH / HL / LL), appliquée indépendamment sur chaque niveau
hiérarchique.

Setup bearish : HH -> LL -> LH   (entrée sur le LH)
    - Entrée      : prix de confirmation du LH (3e point)
    - Stop Loss   : au-dessus du HH (1er point)
    - Take Profit : à la cassure du LL (2e point) — ce niveau correspond
      exactement à l'apparition du "deuxième LL" de la séquence complète
      HH->LL->LH->LL->HH décrite dans la stratégie : dès que le prix
      clôture/confirme sous le niveau du 1er LL, un nouveau plus bas
      (Lower Low) est mécaniquement formé.

Setup bullish (symétrique) : LL -> HH -> HL   (entrée sur le HL)
    - Entrée      : prix de confirmation du HL
    - Stop Loss   : en dessous du LL (1er point)
    - Take Profit : à la cassure du HH (2e point)

Important : l'entrée utilise le prix de CONFIRMATION (conf_price/conf_index)
de l'extrême, jamais son prix exact au pivot — pour éviter tout biais
d'anticipation (look-ahead) : au moment de l'entrée, on ne connaît que ce
qui est déjà confirmé par le marché.
"""

from typing import Optional

import numpy as np
import pandas as pd

from hierarchical_extremes import HierarchicalExtremes
from market_structure import get_labeled_extremes, determine_trend

BEARISH_PATTERN = ("HH", "LL", "LH")
BULLISH_PATTERN = ("LL", "HH", "HL")

_PERIOD_ALIAS = {"Année": "Y", "Trimestre": "Q", "Mois": "M", "Semaine": "W"}


def detect_setups(he: HierarchicalExtremes, level: int) -> pd.DataFrame:
    """
    Détecte tous les setups bearish (HH->LL->LH) et bullish (LL->HH->HL)
    sur le niveau `level`, un par un, sans filtre d'autres niveaux.

    Returns
    -------
    pd.DataFrame avec une ligne par setup détecté : direction, les 3 points
    de la séquence, prix/index/heure d'entrée, SL, TP, risque, reward, RR.
    """
    ext_df = get_labeled_extremes(he, level)
    if len(ext_df) < 3:
        return pd.DataFrame()

    labels = ext_df["label"].tolist()
    rows = []

    for i in range(len(ext_df) - 2):
        seq = tuple(labels[i:i + 3])
        if seq == BEARISH_PATTERN:
            direction = "bearish"
        elif seq == BULLISH_PATTERN:
            direction = "bullish"
        else:
            continue

        p1, p2, p3 = ext_df.iloc[i], ext_df.iloc[i + 1], ext_df.iloc[i + 2]

        entry_price = float(p3["conf_price"])
        entry_index = int(p3["conf_index"])
        entry_time = p3["conf_timestamp"]

        sl_price = float(p1["price"])
        tp_price = float(p2["price"])

        risk = abs(entry_price - sl_price)
        reward = abs(entry_price - tp_price)

        rows.append({
            "level": level,
            "direction": direction,
            "p1_index": int(p1["index"]), "p1_price": float(p1["price"]), "p1_time": p1["timestamp"],
            "p2_index": int(p2["index"]), "p2_price": float(p2["price"]), "p2_time": p2["timestamp"],
            "p3_index": int(p3["index"]), "p3_price": float(p3["price"]), "p3_time": p3["timestamp"],
            "entry_index": entry_index, "entry_price": entry_price, "entry_time": entry_time,
            "sl_price": sl_price, "tp_price": tp_price,
            "risk": risk, "reward": reward,
            "rr": (reward / risk) if risk > 0 else np.nan,
        })

    return pd.DataFrame(rows)


def backtest_setups(setups: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """
    Simule chaque setup détecté, bougie par bougie, à partir de la bougie
    suivant l'entrée, pour déterminer si le Take Profit ou le Stop Loss
    est touché en premier.

    Parameters
    ----------
    setups : pd.DataFrame
        Résultat de `detect_setups`.
    df : pd.DataFrame
        Données OHLC utilisées pour la détection (mêmes index/positions
        que lors du calcul de `he`).

    Returns
    -------
    pd.DataFrame
        `setups` enrichi de : 'outcome' ('win'/'loss'/'open'), 'exit_index',
        'exit_time', 'exit_price', 'pnl_r' (résultat en multiples de R,
        où R = risque initial du trade).
    """
    if setups.empty:
        return setups.assign(
            outcome=pd.Series(dtype=str), exit_index=pd.Series(dtype="Int64"),
            exit_time=pd.Series(dtype="datetime64[ns]"), exit_price=pd.Series(dtype=float),
            pnl_r=pd.Series(dtype=float),
        )

    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    n = len(df)

    outcomes, exit_idx, exit_time, exit_price, pnl_r = [], [], [], [], []

    for _, t in setups.iterrows():
        start = t["entry_index"] + 1
        sl, tp = t["sl_price"], t["tp_price"]
        direction = t["direction"]

        result, e_idx, e_price = "open", None, None
        for bar in range(start, n):
            if direction == "bearish":
                hit_sl = high[bar] >= sl
                hit_tp = low[bar] <= tp
            else:
                hit_sl = low[bar] <= sl
                hit_tp = high[bar] >= tp

            if hit_sl:
                # Hypothèse conservatrice si les deux niveaux sont touchés
                # sur la même bougie : le Stop Loss est considéré prioritaire.
                result, e_idx, e_price = "loss", bar, sl
                break
            elif hit_tp:
                result, e_idx, e_price = "win", bar, tp
                break

        outcomes.append(result)
        exit_idx.append(e_idx)
        exit_time.append(df.index[e_idx] if e_idx is not None else pd.NaT)
        exit_price.append(e_price)

        if result == "win":
            pnl_r.append(t["rr"] if not np.isnan(t["rr"]) else np.nan)
        elif result == "loss":
            pnl_r.append(-1.0)
        else:
            pnl_r.append(np.nan)

    out = setups.copy()
    out["outcome"] = outcomes
    out["exit_index"] = pd.array(exit_idx, dtype="Int64")
    out["exit_time"] = exit_time
    out["exit_price"] = exit_price
    out["pnl_r"] = pnl_r
    return out


def performance_summary(trades: pd.DataFrame) -> dict:
    """Statistiques globales (winrate, RR moyen, expectancy) sur les trades clôturés."""
    if trades.empty:
        return {"n_trades": 0, "n_wins": 0, "n_losses": 0, "n_open": 0,
                "winrate": np.nan, "avg_rr": np.nan, "expectancy_r": np.nan}

    closed = trades[trades["outcome"].isin(["win", "loss"])]
    n = len(closed)
    n_open = len(trades[trades["outcome"] == "open"])

    if n == 0:
        return {"n_trades": len(trades), "n_wins": 0, "n_losses": 0, "n_open": n_open,
                "winrate": np.nan, "avg_rr": np.nan, "expectancy_r": np.nan}

    wins = closed[closed["outcome"] == "win"]
    return {
        "n_trades": len(trades),
        "n_wins": len(wins),
        "n_losses": n - len(wins),
        "n_open": n_open,
        "winrate": len(wins) / n,
        "avg_rr": closed["rr"].mean(),
        "expectancy_r": closed["pnl_r"].mean(),
    }


def performance_by_period(trades: pd.DataFrame, freq: str = "Y") -> pd.DataFrame:
    """
    Statistiques (winrate, RR moyen, expectancy) regroupées par période
    calendaire, basée sur la date d'entrée du trade.

    freq : alias pandas pour `to_period` ('Y' annuel, 'Q' trimestriel,
    'M' mensuel, 'W' hebdomadaire).
    """
    cols = ["period", "n_trades", "n_wins", "n_losses", "winrate", "avg_rr", "expectancy_r"]
    if trades.empty:
        return pd.DataFrame(columns=cols)

    closed = trades[trades["outcome"].isin(["win", "loss"])].copy()
    if closed.empty:
        return pd.DataFrame(columns=cols)

    closed["period"] = pd.to_datetime(closed["entry_time"]).dt.to_period(freq)

    rows = []
    for period, grp in closed.groupby("period"):
        n = len(grp)
        wins = grp[grp["outcome"] == "win"]
        rows.append({
            "period": str(period),
            "n_trades": n,
            "n_wins": len(wins),
            "n_losses": n - len(wins),
            "winrate": len(wins) / n if n else np.nan,
            "avg_rr": grp["rr"].mean(),
            "expectancy_r": grp["pnl_r"].mean(),
        })
    return pd.DataFrame(rows).sort_values("period").reset_index(drop=True)


def run_strategy_all_levels(he: HierarchicalExtremes, df: pd.DataFrame) -> pd.DataFrame:
    """Détecte et backteste les setups sur tous les niveaux disponibles, concaténés."""
    all_trades = []
    for lvl in range(he._levels):
        setups = detect_setups(he, lvl)
        if setups.empty:
            continue
        trades = backtest_setups(setups, df)
        all_trades.append(trades)
    if not all_trades:
        return pd.DataFrame()
    return pd.concat(all_trades, ignore_index=True)
