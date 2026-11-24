# Steady Trend – interactive backtest

Streamlit app for the **2270 Financial Modeling group assignment (Nova SBE, group AT)**.

**Deployed app:** *to be added after deployment*

## What it is
"Steady Trend" is a trend-filtered ETF portfolio for savers about ten years from retirement. Five ETFs
(SPY, EFA, IEF, GLD, VNQ) each get 1/5 of the money. At every month-end an ETF is held for the next month only if
its price is above its 10-month simple moving average; otherwise its 1/5 earns the 3-month T-bill rate.
The app compares the strategy with two benchmarks – the same ETFs in equal weights (1/n) and 60/40 SPY/IEF – all
rebalanced monthly and charged the same transaction cost.

In the sidebar you can change:
- the moving-average window (3–12 months),
- the transaction cost (0–50 bp per unit of turnover),
- which ETFs are in the portfolio,
- the year from which performance is measured.

The app shows cumulative performance, drawdowns, the share held in T-bills and a table of performance measures
(annualised return and volatility, Sharpe ratio, beta and alpha vs SPY, information ratio vs 1/n, max drawdown).
With the default settings it reproduces the headline numbers of the group's Jupyter notebook.

## Data
Downloaded live through APIs, no API keys needed: daily adjusted closes from Yahoo Finance (`yfinance`),
Nov 2004 – Oct 2026, converted to month-end prices; 3-month T-bill rate from FRED (series TB3MS), lagged one month.

**Fallback.** Yahoo Finance sometimes blocks or rate-limits cloud servers. The app therefore always tries the live
download first and only if it fails (or returns an incomplete sample) uses `data_snapshot.csv` – the same month-end
prices and TB3MS values, saved from the same APIs on 24 Nov 2026. A yellow warning in the app says when the snapshot
is in use; after one hour the live download is tried again. Both paths give identical results. To rebuild the
snapshot: `python backtest.py`. (The group's Jupyter notebook uses the APIs only.)

## Files
- `app.py` – the Streamlit user interface
- `backtest.py` – data download and backtest logic, copied unchanged from the notebook
- `data_snapshot.csv` – fallback data (used only if the live download fails)
- `requirements.txt` – Python packages

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
The app opens in your browser at http://localhost:8501.

## Deploy
share.streamlit.io → *Create app* → select this repository, branch `main`, main file `app.py`.

*Built with AI coding assistance (Claude Code); the group checked the code and results.*
