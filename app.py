"""Steady Trend – interactive backtest (Streamlit app for the 2270 Financial Modeling group assignment, group AT).

Run locally:  streamlit run app.py
All calculations come from backtest.py, which is copied from the notebook Steady_Trend_backtest.ipynb.
"""
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from backtest import TICKERS, MARKET, load_data, run_backtest, performance_table

st.set_page_config(page_title="Steady Trend backtest", layout="wide")

COLORS = ["#1f77b4", "#ff7f0e", "#7f7f7f"]     # Steady Trend, 1/n, 60/40 - same colours as the notebook
ETF_NAMES = {"SPY": "SPY – US equities", "EFA": "EFA – developed ex-US equities",
             "IEF": "IEF – 7-10y US Treasuries", "GLD": "GLD – gold", "VNQ": "VNQ – US REITs"}


@st.cache_data(ttl=3600, show_spinner="Downloading prices (Yahoo Finance) and T-bill rates (FRED)...")
def get_data():
    # live APIs first, saved snapshot only if they fail; cached for 1 hour, then the live download is tried again
    return load_data()


# ---------------------------------------------------------------- sidebar: the assumptions the user can change
st.sidebar.header("Assumptions")
window = st.sidebar.slider("Moving-average window (months)", min_value=3, max_value=12, value=10,
                           help="An ETF is held next month only if its month-end price is above its average "
                                "price over this many months.")
cost_bp = st.sidebar.slider("Transaction cost (bp per unit of turnover)", min_value=0, max_value=50, value=10,
                            help="Charged on every buy and sell, for the strategy and both benchmarks. "
                                 "1 bp = 0.01%.")
assets = st.sidebar.multiselect("ETFs in the portfolio", options=TICKERS, default=TICKERS,
                                format_func=lambda t: ETF_NAMES[t],
                                help="Each selected ETF gets an equal share. The 1/n benchmark uses the same ETFs.")
start_year = st.sidebar.slider("Backtest start year", min_value=2005, max_value=2020, value=2005,
                               help="Performance is measured from January of this year (2005: from the first "
                                    "month with a full moving average, e.g. September 2005 for 10 months).")
st.sidebar.caption("Moodle group AT: Eric Doering (78838), Cloé Dellac (79655), Mark Iourist (78670), "
                   "Liz Annkathrin Krönke (79332), Leonard Wölk (77920), Julian Zährl (78758)")

# ---------------------------------------------------------------- header and explanation for the client
st.title("Steady Trend – a trend-filtered ETF portfolio")
st.markdown(
    "**For savers about 10 years from retirement** who want equity-like growth but cannot afford a 2008-style loss. "
    "The money is split equally across up to five ETFs. At the end of every month, each ETF is checked: if its price "
    "is **above its moving average**, it is held for the next month; if not, its share is **parked in 3-month "
    "T-bills** until the trend turns up again. The rule is compared with two benchmarks that never go to cash: the "
    "same ETFs in equal weights (**1/n**) and a classic **60/40** mix of US stocks (SPY) and Treasuries (IEF). "
    "Change the assumptions on the left to see how the result depends on them."
)

if len(assets) == 0:
    st.warning("Please select at least one ETF.")
    st.stop()

try:
    prices, rf, data_message = get_data()
except Exception as e:                                 # live download AND snapshot file failed
    st.error(f"Could not load the data ({e}). Please reload the page in a minute.")
    st.stop()
if data_message is not None:                           # live download failed -> saved snapshot is used
    st.warning(data_message)

# ---------------------------------------------------------------- run the backtest (same code as the notebook)
tickers = [t for t in TICKERS if t in assets]          # keep the notebook's order
bt = run_backtest(prices, rf, tickers, window=window, cost=cost_bp / 10000)

rets = bt["returns"].loc[str(start_year):]             # measure performance from the chosen start year
if len(rets) < 24:
    st.warning("Fewer than 24 months of returns – please choose an earlier start year.")
    st.stop()

start = prices.index[prices.index.get_loc(rets.index[0]) - 1]       # all series start at 1 one month earlier
cumulative = pd.concat([pd.DataFrame(1.0, index=[start], columns=rets.columns), (1 + rets).cumprod()])
market_returns = prices[MARKET] / prices[MARKET].shift(1) - 1
perf = performance_table(rets, rf, market_returns, benchmark="1/n (5 ETFs)")

# label the 1/n benchmark with the number of ETFs actually selected
eq_name = f"1/n ({len(tickers)} ETF{'s' if len(tickers) > 1 else ''})"
rename = {"1/n (5 ETFs)": eq_name}
cumulative = cumulative.rename(columns=rename)
perf = perf.rename(columns=rename, index={"Information ratio (vs 1/n (5 ETFs))": f"Information ratio (vs {eq_name})"})

# ---------------------------------------------------------------- headline numbers
st.caption(f"Backtest {rets.index[0]:%b %Y} – {rets.index[-1]:%b %Y} ({len(rets)} months), monthly data, "
           f"returns after {cost_bp} bp transaction costs. Moving average: {window} months. "
           f"ETFs: {', '.join(tickers)}.")
s = perf["Steady Trend"]
st.markdown("**Steady Trend** – difference to the 1/n benchmark shown below each number (pp = percentage points):")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Final value of 1", f"{s['Final value of 1']:.2f}",
          f"{s['Final value of 1'] - perf.loc['Final value of 1', eq_name]:+.2f} vs 1/n")
c2.metric("Avg. annual return", f"{s['Ann. avg. return']:.1%}",
          f"{100 * (s['Ann. avg. return'] - perf.loc['Ann. avg. return', eq_name]):+.1f} pp vs 1/n")
c3.metric("Max drawdown", f"-{s['Max drawdown']:.1%}",
          f"{100 * (perf.loc['Max drawdown', eq_name] - s['Max drawdown']):+.1f} pp vs 1/n")   # + = smaller loss
c4.metric("Sharpe ratio", f"{s['Sharpe ratio']:.2f}",
          f"{s['Sharpe ratio'] - perf.loc['Sharpe ratio', eq_name]:+.2f} vs 1/n")

# ---------------------------------------------------------------- charts
st.subheader("Growth of 1 invested")
fig, ax = plt.subplots(figsize=(10, 4.5))
cumulative.plot(ax=ax, color=COLORS)
ax.set_ylabel("Value of 1 invested"); ax.set_xlabel("")
st.pyplot(fig)

st.subheader("Drawdown from the previous peak")
hwm = cumulative.cummax()                                 # high-water mark
fig, ax = plt.subplots(figsize=(10, 3.5))
(-100 * (hwm - cumulative) / hwm).plot(ax=ax, color=COLORS)
ax.set_ylabel("%"); ax.set_xlabel("")
st.pyplot(fig)

st.subheader("Steady Trend: share of the portfolio held in T-bills")
cash_share = bt["weights"]["CASH"].loc[str(start_year):]
fig, ax = plt.subplots(figsize=(10, 3))
ax.fill_between(cash_share.index, 100 * cash_share, step="post", alpha=0.6, color=COLORS[0])
ax.set_ylabel("%"); ax.set_ylim(0, 100); ax.set_xlim(cash_share.index[0], cash_share.index[-1])
st.pyplot(fig)

# ---------------------------------------------------------------- performance table
st.subheader("Performance measures")
pct_rows = ["Ann. avg. return", "Ann. volatility", "Alpha (ann., vs SPY)", "Max drawdown", "CAGR"]
shown = perf.copy().astype(object)
for row in perf.index:
    fmt = "{:.1%}" if row in pct_rows else "{:.2f}"
    shown.loc[row] = [("–" if pd.isna(v) else fmt.format(v)) for v in perf.loc[row]]
st.table(shown)

st.markdown(
    "**How to read this.** *Annual return* and *volatility* are monthly averages × 12 and standard deviations × √12. "
    "The *Sharpe ratio* is return above T-bills per unit of risk. *Beta* (not annualised) measures how much the "
    "portfolio moves with US stocks (SPY); *alpha* is the annual return not explained by that exposure. The "
    "*information ratio* compares the strategy with the 1/n benchmark. *Max drawdown* is the largest month-end fall "
    "from a previous peak – the loss an investor would actually have felt.\n\n"
    "**Assumptions and limits.** Monthly data, so falls within a month are not visible and trades happen at "
    "month-end prices. Cash earns the 3-month T-bill rate known at the start of each month. Costs are charged on "
    "both legs of every trade (selling an ETF and buying T-bills). Past performance does not guarantee future "
    "results; ETFs that exist today were chosen with hindsight."
)
st.caption("Data: Yahoo Finance (adjusted closes via yfinance) and FRED series TB3MS. "
           "Nova SBE 2270 Financial Modeling, group AT. Built with AI coding assistance (Claude Code).")
