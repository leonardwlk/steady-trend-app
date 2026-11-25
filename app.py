"""Steady Trend – interactive backtest (Streamlit app for the 2270 Financial Modeling group assignment, group AT).

Run locally:  streamlit run app.py
All calculations come from backtest.py, which is copied from the notebook Steady_Trend_backtest.ipynb.
"""
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from backtest import TICKERS, MARKET, load_data, run_backtest, performance_table

st.set_page_config(page_title="Steady Trend backtest", layout="wide")

COLORS = ["#1F77B4", "#FF7F0E", "#7F7F7F"]     # Steady Trend, 1/n, 60/40 - same colours as the notebook
NAVY, BLUE, GREY, BORDER = "#0B1F3A", "#1F77B4", "#5B6573", "#E3E8EF"   # prospectus design colours
ETF_NAMES = {"SPY": "SPY – US equities", "EFA": "EFA – developed ex-US equities",
             "IEF": "IEF – 7-10y US Treasuries", "GLD": "GLD – gold", "VNQ": "VNQ – US REITs"}

# ---------------------------------------------------------------- look: prospectus design (layout only, no numbers)
st.markdown(f"""
<style>
  .st-label {{ color: {BLUE}; font-size: 0.8rem; font-weight: 700; letter-spacing: 0.12em;
               text-transform: uppercase; margin-bottom: -0.4rem; }}
  .st-title {{ color: {NAVY}; font-size: 2.6rem; font-weight: 800; line-height: 1.15; margin: 0.2rem 0 0.2rem 0; }}
  .st-subtitle {{ color: {GREY}; font-size: 1.1rem; margin-bottom: 1rem; }}
  /* the four headline cards: st.container(border=True, key="card_...") */
  [class*="st-key-card"] {{ background-color: #F5F7FA; border: 1px solid {BORDER} !important;
                            border-radius: 12px; padding: 0.4rem 0.6rem; }}
  [class*="st-key-card"] [data-testid="stMetricValue"] {{ color: {NAVY}; font-size: 2.1rem; font-weight: 700; }}
  [class*="st-key-card"] [data-testid="stMetricLabel"] p {{ color: {GREY}; font-size: 0.85rem; }}
  h2, h3 {{ color: {NAVY}; }}
</style>
""", unsafe_allow_html=True)

# clean matplotlib style for all charts: no top/right spines, light grey grid, legend without frame
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#B8C2CF", "axes.grid": True, "grid.color": "#E3E8EF",
                     "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": False,
                     "axes.labelcolor": "#18212F", "xtick.color": GREY, "ytick.color": GREY,
                     "font.family": "sans-serif", "font.size": 10})


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
st.markdown('<div class="st-label">Steady Trend</div>'
            '<div class="st-title">Steady Trend</div>'
            '<div class="st-subtitle">A trend-filtered five-ETF portfolio for savers about ten years from retirement.'
            '</div>', unsafe_allow_html=True)
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
cards = [("Final value of 1", f"{s['Final value of 1']:.2f}",
          f"{s['Final value of 1'] - perf.loc['Final value of 1', eq_name]:+.2f} vs 1/n"),
         ("Avg. annual return", f"{s['Ann. avg. return']:.1%}",
          f"{100 * (s['Ann. avg. return'] - perf.loc['Ann. avg. return', eq_name]):+.1f} pp vs 1/n"),
         ("Max drawdown", f"-{s['Max drawdown']:.1%}",
          f"{100 * (perf.loc['Max drawdown', eq_name] - s['Max drawdown']):+.1f} pp vs 1/n"),   # + = smaller loss
         ("Sharpe ratio", f"{s['Sharpe ratio']:.2f}",
          f"{s['Sharpe ratio'] - perf.loc['Sharpe ratio', eq_name]:+.2f} vs 1/n")]
for i, (col, (label, value, delta)) in enumerate(zip(st.columns(4), cards)):
    with col.container(border=True, key=f"card_{i}"):        # rounded card (styled in the CSS above)
        st.metric(label, value, delta)                          # green = better than 1/n, red = worse


# ---------------------------------------------------------------- charts
def show_chart(fig, ax, legend_loc="upper left"):
    # common finishing touches for every chart, then display it (legend_loc=None: no legend)
    ax.set_xlabel("")
    if legend_loc is not None:
        ax.legend(loc=legend_loc, ncol=3)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


st.subheader("Growth of 1 invested")
fig, ax = plt.subplots(figsize=(10, 4.5))
cumulative.plot(ax=ax, color=COLORS, linewidth=1.8)
ax.set_ylabel("Value of 1 invested")
show_chart(fig, ax)

st.subheader("Drawdown from the previous peak")
hwm = cumulative.cummax()                                 # high-water mark
fig, ax = plt.subplots(figsize=(10, 3.5))
(-100 * (hwm - cumulative) / hwm).plot(ax=ax, color=COLORS, linewidth=1.4)
ax.set_ylabel("%")
show_chart(fig, ax, legend_loc="lower left")

st.subheader("Steady Trend: share of the portfolio held in T-bills")
cash_share = bt["weights"]["CASH"].loc[str(start_year):]
fig, ax = plt.subplots(figsize=(10, 3))
ax.fill_between(cash_share.index, 100 * cash_share, step="post", alpha=0.35, color=COLORS[0], linewidth=0)
ax.set_ylabel("%"); ax.set_ylim(0, 100); ax.set_xlim(cash_share.index[0], cash_share.index[-1])
show_chart(fig, ax, legend_loc=None)

# ---------------------------------------------------------------- performance table
st.subheader("Performance measures")
pct_rows = ["Ann. avg. return", "Ann. volatility", "Alpha (ann., vs SPY)", "Max drawdown", "CAGR"]
shown = perf.copy().astype(object)
for row in perf.index:                                    # percentages for returns, 2 decimals for ratios
    fmt = "{:.1%}" if row in pct_rows else "{:.2f}"
    shown.loc[row] = [("–" if pd.isna(v) else fmt.format(v)) for v in perf.loc[row]]
styled = shown.style.set_properties(**{"text-align": "right"})
styled = styled.set_properties(subset=["Steady Trend"],   # highlight the strategy's column
                               **{"background-color": "#E8F1FA", "color": NAVY, "font-weight": "bold"})
st.dataframe(styled, width="stretch", height=(len(perf) + 1) * 35 + 3)

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
