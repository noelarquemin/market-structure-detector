# Détection de structure de marché — Yahoo Finance

## Contenu

- `local_extreme.py` — dataclass `LocalExtreme` + vérifications de cohérence (fournis, inchangés)
- `atr_directional_change.py` — détection des extrêmes de base via ATR (fourni, inchangé)
- `hierarchical_extremes.py` — agrégation des extrêmes en niveaux hiérarchiques (fourni, inchangé)
- `ohlc_data.py` — **nouveau** : téléchargement des données OHLC depuis Yahoo Finance (`yfinance`)
- `market_structure.py` — **nouveau** : orchestration de la détection + calcul de tendance par niveau
- `plot_structure.py` — **nouveau** : visualisation matplotlib (retourne une `Figure`, réutilisable dans Streamlit)
- `main.py` — **nouveau** : script CLI de démonstration

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation en ligne de commande

```bash
python main.py AAPL --period 1y --interval 1d --levels 3 --atr 30
python main.py BTC-USD --period 6mo --interval 1h --levels 4 --atr 50
```

Paramètres :
- `ticker` : symbole Yahoo Finance (`AAPL`, `BTC-USD`, `EURUSD=X`, `^GSPC`, ...)
- `--period` : historique (`6mo`, `1y`, `2y`, `5y`, `max`)
- `--interval` : granularité (`1d`, `1h`, `15m`, ...) — attention aux limites Yahoo
  Finance sur l'intraday (`1m` ≈ 7 jours max, `1h`/`15m` ≈ 60-730 jours max)
- `--levels` : nombre de niveaux hiérarchiques (plus il y en a, plus la structure
  "macro" est filtrée)
- `--atr` : fenêtre ATR en nombre de bougies (sensibilité de détection : plus
  grand = moins d'extrêmes, structure plus large)

## Utilisation programmatique

```python
from ohlc_data import get_ohlc_data
from market_structure import compute_market_structure, structure_summary, extremes_to_dataframe
from plot_structure import plot_market_structure

df = get_ohlc_data("AAPL", period="1y", interval="1d")
he = compute_market_structure(df, levels=3, atr_lookback=30)

print(structure_summary(he))          # tendance + derniers points par niveau
ext_lvl1 = extremes_to_dataframe(he, 1)  # extrêmes détaillés du niveau 1

fig = plot_market_structure(df, he)
fig.savefig("structure.png")
```

## Logique de tendance

Pour chaque niveau, la tendance est déterminée à partir des 2 derniers hauts
et des 2 derniers bas confirmés :
- **Higher High + Higher Low** → tendance haussière
- **Lower High + Lower Low** → tendance baissière
- sinon → range / indéterminée

## Vers Streamlit (prochaine étape)

Le code est déjà découpé pour être branché directement dans une app Streamlit :
- `get_ohlc_data(ticker, period, interval)` ← champ texte + selectbox pour le ticker/période
- `compute_market_structure(df, levels, atr_lookback)` ← sliders pour `levels`/`atr_lookback`
- `plot_market_structure(...)` renvoie une `Figure` matplotlib → `st.pyplot(fig)`
- `structure_summary(he)` renvoie un DataFrame → `st.dataframe(...)`

Exemple de squelette d'app (à créer à l'étape suivante) :

```python
import streamlit as st
from ohlc_data import get_ohlc_data
from market_structure import compute_market_structure, structure_summary
from plot_structure import plot_market_structure

st.title("Analyse de structure de marché")
ticker = st.text_input("Ticker", "AAPL")
period = st.selectbox("Période", ["6mo", "1y", "2y", "5y"], index=1)
interval = st.selectbox("Intervalle", ["1d", "1h", "15m"], index=0)
levels = st.slider("Niveaux hiérarchiques", 1, 5, 3)
atr = st.slider("Fenêtre ATR", 5, 200, 30)

if st.button("Analyser"):
    df = get_ohlc_data(ticker, period=period, interval=interval)
    he = compute_market_structure(df, levels=levels, atr_lookback=atr)
    st.pyplot(plot_market_structure(df, he))
    st.dataframe(structure_summary(he))
```

## Remarque importante

Le téléchargement Yahoo Finance n'a pas pu être testé en conditions réelles
dans cet environnement (pas d'accès réseau sortant vers Yahoo Finance ici).
Toute la mécanique de détection (`ATRDirectionalChange`, `HierarchicalExtremes`,
tendance, tracé) a été validée avec des données synthétiques et respecte les
vérifications de cohérence (`extremes_sanity_checks`). Testez `ohlc_data.py`
en local pour confirmer le bon fonctionnement du téléchargement.
