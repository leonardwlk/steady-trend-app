"""Backtest logic of the Steady Trend strategy.

The functions strategy_weights, portfolio_returns, run_backtest and performance_table are copied unchanged from
the notebook notebook/Steady_Trend_backtest.ipynb (sections 6, 7 and 9), so the app and the notebook give the same
numbers. The data functions repeat the notebook's sections 3-4 (download, month-end prices, lagged T-bill rate).

Data: the app always tries the live APIs first (Yahoo Finance, FRED). Only if that fails does it use
data_snapshot.csv (month-end prices and TB3MS saved from the same APIs; rebuild it with `python backtest.py`).
The notebook itself uses the APIs only.
"""
import os

import numpy as np
import pandas as pd
import yfinance as yf

START = "2004-11-01"        # same sample as the notebook
END = "2026-11-01"
TICKERS = ["SPY", "EFA", "IEF", "GLD", "VNQ"]
MARKET = "SPY"
SNAPSHOT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_snapshot.csv")


def download_live(start=START, end=END, tickers=TICKERS):
    # Month-end adjusted prices (Yahoo Finance) and the TB3MS rate in % p.a., labelled at month-end (FRED).
    if os.environ.get("STEADY_TREND_FORCE_SNAPSHOT") == "1":     # used only to test the fallback
        raise RuntimeError("live download switched off for testing")

    prices_daily = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)["Close"]
    for t in tickers:                                   # retry a ticker that failed to download, once
        if t not in prices_daily.columns or prices_daily[t].isna().all():
            prices_daily[t] = yf.download(t, start=start, end=end, auto_adjust=True, progress=False)["Close"][t]
    prices_daily = prices_daily[tickers]
    if not prices_daily.notna().any().all():
        raise RuntimeError("Yahoo Finance download failed for a ticker")
    prices = prices_daily.resample("ME").last().dropna()     # month-end prices

    # the download must cover the whole sample (Yahoo sometimes returns only part of it)
    expected = pd.date_range(start, end, freq="ME")
    if len(prices.index.difference(expected)) > 0 or len(expected.difference(prices.index)) > 0:
        raise RuntimeError("Yahoo Finance returned an incomplete sample")

    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=TB3MS"
    tb3ms = pd.to_numeric(pd.read_csv(url, index_col=0, parse_dates=True)["TB3MS"], errors="coerce")
    tb3ms = tb3ms.resample("ME").last()                       # TB3MS of month t, labelled with month-end t
    return prices, tb3ms


def load_snapshot(path=SNAPSHOT_FILE, tickers=TICKERS):
    # The same two series, read from the saved CSV file.
    snap = pd.read_csv(path, index_col=0, parse_dates=True)
    prices = snap[tickers].dropna()          # the first row (Oct 2004) only holds TB3MS
    tb3ms = snap["TB3MS"]
    return prices, tb3ms


def to_monthly_rf(prices, tb3ms):
    # TB3MS (% p.a.) -> monthly decimal rf, lagged one month: rf for month t = rate of month t-1 (as in the notebook)
    rf_monthly = tb3ms / 100 / 12
    rf = rf_monthly.shift(1).reindex(prices.index)
    rf.name = "rf"
    return rf


def load_data():
    # Live APIs first; the snapshot file only if they fail. Returns prices, rf and a message (None = live data).
    try:
        prices, tb3ms = download_live()
        message = None
    except Exception as e:
        prices, tb3ms = load_snapshot()
        message = f"Live download failed ({e}). Showing saved data from data_snapshot.csv instead."
    return prices, to_monthly_rf(prices, tb3ms), message


def save_snapshot(path=SNAPSHOT_FILE):
    # Download live data and save it as the fallback file (month-end prices + TB3MS from Oct 2004).
    prices, tb3ms = download_live()
    first_rf_month = prices.index[0] - pd.offsets.MonthEnd(1)     # rf of Nov 2004 needs TB3MS of Oct 2004
    snap = prices.reindex(tb3ms.loc[first_rf_month:prices.index[-1]].index)
    snap["TB3MS"] = tb3ms
    snap.index.name = "Date"
    snap.to_csv(path)                                          # full precision: same numbers as live
    print(f"Saved {len(snap)} months to {path}")


def strategy_weights(prices, tickers, window=10):
    # Monthly weights of the Steady Trend strategy (columns: tickers + "CASH").
    p = prices[tickers]
    sma = p.rolling(window=window).mean()          # SMA_t = mean of the last `window` month-end prices, incl. P_t
    signal = (p > sma).astype(float)               # 1 = price above its SMA, 0 = below
    signal = signal.where(sma.notna())             # no signal before the first full SMA (NaN)
    weights = signal.shift(1) / len(tickers)       # signal at month-end t -> weight held during month t+1
    weights = weights.dropna()                     # keep months for which all ETFs have a signal
    weights["CASH"] = 1 - weights.sum(axis=1)      # the rest earns the T-bill rate
    return weights


def portfolio_returns(weights, asset_returns, rf, cost):
    # Net return, gross return and turnover of a portfolio with the given monthly weights (incl. a "CASH" column).
    r = asset_returns.copy()
    r["CASH"] = rf                                    # cash earns the T-bill rate
    r = r.loc[weights.index, weights.columns]         # same months and columns as the weights

    gross = (weights * r).sum(axis=1)                 # sum_i w_i,t * r_i,t (incl. cash)

    grown = weights.shift(1) * (1 + r.shift(1))       # last month's weights after last month's returns
    drifted = grown.div(grown.sum(axis=1), axis=0)    # ... rescaled to sum to 1 = weights before trading
    turnover = (weights - drifted).abs().sum(axis=1)  # sum_i |w_i,t - drifted w_i,t|
    turnover.iloc[0] = 0                              # first month: no set-up cost

    net = gross - cost * turnover
    return net, gross, turnover


def run_backtest(prices, rf, tickers, window=10, cost=0.001):
    # Steady Trend strategy and both benchmarks over the same months. Returns a dictionary of DataFrames.
    asset_returns = prices / prices.shift(1) - 1

    # 1) the strategy
    w_strategy = strategy_weights(prices, tickers, window)
    months = w_strategy.index                          # common period: starts when the first SMA exists

    # 2) benchmark 1/n: same ETFs, 1/n each, rebalanced monthly, never in cash
    w_equal = pd.DataFrame(1 / len(tickers), index=months, columns=tickers)
    w_equal["CASH"] = 0.0

    # 3) benchmark 60/40: 60% SPY, 40% IEF, rebalanced monthly
    w_6040 = pd.DataFrame({"SPY": 0.6, "IEF": 0.4, "CASH": 0.0}, index=months)

    names = ["Steady Trend", "1/n (5 ETFs)", "60/40 SPY/IEF"]
    net, gross, turnover = {}, {}, {}
    for name, w in zip(names, [w_strategy, w_equal, w_6040]):
        net[name], gross[name], turnover[name] = portfolio_returns(w, asset_returns, rf, cost)
    net, gross, turnover = pd.DataFrame(net), pd.DataFrame(gross), pd.DataFrame(turnover)

    # cumulative value of 1 invested at the end of the month before the first return (all series start at 1)
    start = prices.index[prices.index.get_loc(months[0]) - 1]
    cumulative = pd.concat([pd.DataFrame(1.0, index=[start], columns=names), (1 + net).cumprod()])

    return {"returns": net, "gross_returns": gross, "turnover": turnover,
            "weights": w_strategy, "cumulative": cumulative}


def performance_table(rets, rf, market_returns, benchmark):
    # One column per portfolio, one row per performance measure (decimals; Sharpe, beta, IR are ratios).
    rf = rf.reindex(rets.index)
    market_excess = market_returns.reindex(rets.index) - rf
    table = {}
    for name in rets.columns:
        R = rets[name]
        excess = R - rf
        beta = excess.cov(market_excess) / market_excess.var()
        alpha = 12 * (excess.mean() - beta * market_excess.mean())    # regression intercept, annualised
        active = R - rets[benchmark]
        ir = 12 * active.mean() / (np.sqrt(12) * active.std()) if name != benchmark else np.nan

        wealth = pd.concat([pd.Series([1.0]), (1 + R).cumprod()])     # start at 1 so a loss in month 1 counts
        hwm = wealth.cummax()
        max_dd = ((hwm - wealth) / hwm).max()
        years = len(R) / 12

        table[name] = {"Ann. avg. return": 12 * R.mean(),
                       "Ann. volatility": np.sqrt(12) * R.std(),
                       "Sharpe ratio": 12 * excess.mean() / (np.sqrt(12) * excess.std()),
                       "Beta (vs SPY)": beta,
                       "Alpha (ann., vs SPY)": alpha,
                       f"Information ratio (vs {benchmark})": ir,
                       "Max drawdown": max_dd,
                       "CAGR": wealth.iloc[-1] ** (1 / years) - 1,
                       "Final value of 1": wealth.iloc[-1]}
    return pd.DataFrame(table)


if __name__ == "__main__":
    save_snapshot()                          # `python backtest.py` rebuilds data_snapshot.csv
