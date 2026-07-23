"""
Script de démonstration en ligne de commande.

Usage:
    python main.py AAPL --period 1y --interval 1d --levels 3 --atr 30

Ceci va :
1. Télécharger les données OHLC du ticker depuis Yahoo Finance
2. Lancer la détection de structure de marché (extrêmes hiérarchiques)
3. Afficher un résumé (tendance par niveau)
4. Tracer le graphique prix + structure
"""

import argparse
import matplotlib.pyplot as plt

from ohlc_data import get_ohlc_data
from market_structure import compute_market_structure, structure_summary
from plot_structure import plot_market_structure


def main():
    parser = argparse.ArgumentParser(description="Détection de structure de marché")
    parser.add_argument("ticker", type=str, help="Ticker Yahoo Finance (ex: AAPL, BTC-USD, EURUSD=X)")
    parser.add_argument("--period", type=str, default="1y", help="Période d'historique (ex: 6mo, 1y, 2y, 5y, max)")
    parser.add_argument("--interval", type=str, default="1d", help="Granularité (ex: 1d, 1h, 15m)")
    parser.add_argument("--levels", type=int, default=3, help="Nombre de niveaux hiérarchiques")
    parser.add_argument("--atr", type=int, default=30, help="Fenêtre ATR (en nombre de bougies)")
    args = parser.parse_args()

    print(f"Téléchargement des données pour {args.ticker} ({args.period}, {args.interval})...")
    df = get_ohlc_data(args.ticker, period=args.period, interval=args.interval)
    print(f"{len(df)} bougies chargées.\n")

    print("Détection de la structure de marché...")
    he = compute_market_structure(df, levels=args.levels, atr_lookback=args.atr)

    summary = structure_summary(he)
    print("\nRésumé de la structure par niveau :")
    print(summary.to_string(index=False))

    fig = plot_market_structure(df, he, title=f"Structure de marché - {args.ticker}")
    plt.show()


if __name__ == "__main__":
    main()
