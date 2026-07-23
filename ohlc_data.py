"""
Récupération des données OHLC (Open/High/Low/Close) depuis Yahoo Finance
via la librairie `yfinance`, au format attendu par les modules de
détection de structure (atr_directional_change.py / hierarchical_extremes.py).
"""

import pandas as pd
import yfinance as yf


def get_ohlc_data(
    ticker: str,
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Télécharge les données OHLC d'un ticker depuis Yahoo Finance.

    Parameters
    ----------
    ticker : str
        Symbole du ticker Yahoo Finance (ex: 'AAPL', 'BTC-USD', 'EURUSD=X').
    period : str
        Période d'historique ('6mo', '1y', '2y', '5y', 'max', ...).
        Ignoré si `start`/`end` sont utilisés côté yfinance (non exposé ici
        pour rester simple, mais peut être ajouté si besoin).
    interval : str
        Granularité des bougies ('1d', '1h', '15m', '5m', ...).
        Attention : Yahoo Finance limite l'historique disponible pour les
        intervalles intraday (ex: '1m' -> 7 jours max, '1h' -> 730 jours max).

    Returns
    -------
    pd.DataFrame
        Index : DatetimeIndex trié par ordre croissant.
        Colonnes (en minuscules, pour matcher le code fourni) :
        'open', 'high', 'low', 'close', 'volume'.

    Raises
    ------
    ValueError
        Si le ticker n'existe pas ou si aucune donnée n'est retournée.
    """
    df = yf.download(
        tickers=ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    if df is None or df.empty:
        raise ValueError(
            f"Aucune donnée retournée pour le ticker '{ticker}' "
            f"(period='{period}', interval='{interval}'). "
            "Vérifiez le symbole ou réduisez la période pour les intervalles intraday."
        )

    # yfinance peut retourner des colonnes multi-index (Ticker, OHLCV) selon la version
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    keep_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep_cols].copy()

    df.index.name = "datetime"
    df = df.sort_index()

    # Sécurité : suppression des lignes avec des NaN sur OHLC
    df = df.dropna(subset=["open", "high", "low", "close"])

    return df


if __name__ == "__main__":
    data = get_ohlc_data("AAPL", period="1y", interval="1d")
    print(data.head())
    print(data.tail())
    print(f"\n{len(data)} bougies chargées pour AAPL")
