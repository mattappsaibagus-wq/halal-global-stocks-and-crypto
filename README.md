# Halal Global Stocks and Crypto

A Shariah-screened early-move scanner for global equities and spot crypto. Every symbol passes a Shariah gate first, and only compliant assets receive trading signals.

## How it works

```
watchlist.txt
     │
     ▼
ShariahScreenerAgent  ── HARAM / QUESTIONABLE ──►  AVOID row on dashboard (with reasons)
     │ HALAL
     ▼
EarlyDetector · Momentum · NewsScanner · DD
     │
     ▼
AdvisorAgent  ──►  BUY / WATCH / SELL (exit) / HOLD  +  purification %
     │
     ▼
data/signals.json · dashboard/data.json · Learning loop
```

### 1. Business-activity screen
Rejects conventional banking and insurance, alcohol, gambling, tobacco, adult content and defence. It matches on Yahoo Finance `sector` / `industry` values.

### 2. Financial-ratio screen
The default is **AAOIFI Shariah Standard 21**, the standard used by Musaffa (and, through Musaffa, Baraka), Zoya and Islamicly.

| Ratio | AAOIFI (default) | S&P Shariah | FTSE Shariah | MSCI Islamic |
|---|---|---|---|---|
| Denominator | 36-month average market cap | 36-month average market cap | Total assets | Total assets |
| Interest-bearing debt | < 30% | < 33% | < 33.33% | < 33.33% |
| Cash + interest-bearing securities | < 30% | < 33% | < 33.33% | < 33.33% |
| Receivables | not tested | < 49% | (receivables + cash) < 50% | < 33.33% |
| Impermissible income / revenue | < 5% | < 5% | < 5% | < 5% |

- **36-month average market cap**: monthly closes over 3 years × shares outstanding. Each month is converted to US dollars at that month's exchange rate, then into the company's reporting currency, so a falling currency (e.g. the Turkish lira) can't shrink old prices and fake a high debt ratio. This smooths out a single-day price swing flipping a verdict.
- The verdict follows your chosen standard (`shariah_compliance.standard`). Every stock card also shows **"Standards: x/4 pass"** with the reason each standard fails, so you can see how robust a verdict is.
- Switch standards in `data/advisor_config.json` (`AAOIFI_STANDARD_21`, `DJIM` or `CUSTOM`). Changing the method re-baselines the compliance watch, so a methodology change never raises false HARAM alerts.

### 3. Dividend purification
Purification per share = dividend × impermissible-income ratio. When the company reports **interest income**, the ratio is measured (interest income ÷ revenue, labelled "measured interest income"). Otherwise it is a labelled **estimate** (0.5%). Every result carries `purification_basis`.

### 4. Your personal filter
`personal_exclusions` in `data/advisor_config.json` lets you add your own list on top of the Shariah screen (like Amal Invest's custom filters or a boycott list): `{"XYZ": "boycott list"}`. Listed symbols always show **AVOID** with your reason.

### Spot crypto
Only pairs listed in `data/halal_crypto_registry.json` pass: BTC, ETH, SOL, AVAX, POL (Yahoo symbol `POL28321-USD`), LINK, ADA, DOT, NEAR and ATOM, all against USD. Stablecoins, lending/yield tokens, privacy coins and meme tokens are excluded. Edit the registry to follow your own scholar's view.

### Strict rules built in
- **Missing data never passes.** A ticker whose data can't be fetched becomes `QUESTIONABLE`, not `HALAL`.
- **Spot only.** No shorting, margin, options or futures. `SELL` means exiting a position you own.
- **Execution gate.** `trading/executor.py` refuses anything that isn't a screened-halal BUY or SELL.
- **No fabricated signals.** If news can't be fetched, the news agent emits no signal.

## Trading tools

### Backtest (`backtest.py`)
Replays 3 years of daily prices through the same agent code the live scan uses, then measures every BUY/SELL/WATCH:

- **Forward returns** after 5, 10 and 20 days, with entry at the next day's open.
- **Edge:** return vs the same stocks on an average day.
- **Expectancy:** each BUY traded with its stop and target, in R, after a 0.2% round-trip cost.
- **Per signal:** which individual signals help or hurt.

It runs daily after the US close and shows on the dashboard's **Backtest** tab. Run it locally with `python backtest.py --years 3`.

Limits: news and fundamentals are not replayed; consecutive-day signals overlap; delisted companies are missing (survivorship bias).

**Out-of-sample study.** Five candidate BUY rules were written down before any results were seen (see `CANDIDATES` in `backtest.py`):

1. The rule with the best results on the older data (all but the last year) is chosen.
2. It is then judged only on the most recent year, which played no part in choosing it.

To pass, on that final year it must:
- make money per trade;
- beat simply buying on any day (t-stat ≥ 2);
- beat an average day's 20-day return;
- have at least 100 trades.

A signal counts once, on the first day it turns on. The live scanner only adopts a rule that passes.

**Result (September 2026): no rule passed.** The best rule on the older data ("volume spike on a 3-day up move", t = 3.2) fell to −0.05R per trade on the unseen year (t = 0.13). The dashboard therefore runs in **watchlist mode**: BUY/WATCH are setups to research, not trade calls. SELL signals were removed, because prices rose after them in the backtest. The study reruns daily, and the banner clears on its own if a rule ever passes.

### Live track record
Every BUY/SELL/WATCH is recorded once, with its entry price and trading date, then scored against actual closes 5, 10 and 20 trading days later. BUY counts as right if the price rose after 20 days; SELL if it fell. The history is kept on the `scan-data` branch so it builds up between runs.

### Trade plan on every BUY
- **Stop** = entry − 2 × ATR(14); **target** = entry + 3 × ATR(14), so reward:risk is 1.5.
- **Position size:** risks 1% of the account if the stop hits, capped at 10% of the account.

Change these under `risk` in `data/advisor_config.json`.

### Scan schedule (completed trading days only)
| UTC | Tokyo | After the close of |
|---|---|---|
| 09:30 Mon–Fri | 18:30 | Indonesia, Malaysia |
| 12:30 Sun–Fri | 21:30 | Saudi Arabia, UAE, Qatar |
| 15:45 Mon–Fri | 00:45 | Turkey |
| 21:30 Mon–Fri | 06:30 | United States (+ backtest) |
| Every 3 hours | every 3 hours | Refresh of news, crypto signals and prices between the closes |

If a market is still trading, today's partial bar is ignored (see `agents/market_hours.py`). Signals are recorded once per completed bar, so the extra runs never double-count the track record.

The dashboard reloads the newest scan every minute and shows when the next scheduled update is due. **Refresh data** reloads it on demand. **Admin console** (for you, the maintainer) opens the workflow on GitHub, where **Run workflow** starts a scan immediately.

### HARAM alerts
When a stock that was HALAL fails the screen, the run opens a GitHub issue, which GitHub emails to you, and the dashboard shows a red banner. Changes back to HALAL, or to QUESTIONABLE, appear on the dashboard only.

### Halal momentum rotation (`rotation.py`)
Each month, hold the 10 halal stocks with the strongest past returns in equal amounts, with a 0.2% cost per swap. It must beat simply holding every halal stock equally.

- **The test:** four candidate rules (6 or 12-month returns, with or without a "cash in downtrends" filter) were fixed in advance. The best on the older months is judged on the last 12, and it must beat the basket on both return and Sharpe.
- **When it runs:** with the daily backtest; results are on the **Backtest** tab.
- **Caveat:** 12 months is a short test.

**Result (September 2026, in USD): did not pass.** The best rule (12-month momentum) returned +22.5% vs +15.8% for the equal-weight basket, but with a lower Sharpe (1.14 vs 1.31), a deeper drop, and t = 0.59. It had a lower Sharpe than the basket in the older data too.

### Halal Basket (dashboard tab)
Hold every current halal stock (not crypto) in equal dollar amounts and review once a month. This is the approach the tests above support.

- **Your plan:** enter an amount; it shows dollars and target shares per stock, converted from local prices at the latest exchange rates.
- **Rebalancing:** enter your current holdings; it lists what to buy or sell. A band (25%, 10% or exact) avoids trading on small drifts.
- **Lots:** Indonesian and Malaysian orders are rounded to lots of 100 shares.
- **حرام stocks:** holdings that turned حرام show as **sell all**.
- **"Why a basket":** compares the basket's last 12 months with momentum and SPUS.

A halal ETF (SPUS, HLAL, UMMA) is the no-effort alternative.

### Market regime panel
For each region, the Scanner tab shows whether the main index is above its 200-day average, and what share of the region's halal stocks are. *Risk-on* means both are positive; *Risk-off* means both are negative. The Saudi, Dubai and Qatar indices have no usable history on Yahoo, so those regions use the stocks only.

### Trade journal
Log real trades (entry, units, stop, fees, reason); a stop is required. The **Journal** tab then shows:
- your win rate, expectancy in R and profit per currency;
- open positions with "near stop", "stop hit" and "now حرام" warnings;
- exposure by market and currency;
- every trade compared with the halal ETF SPUS over the same days.

"Fill from scanner plan" copies a BUY's entry and stop. The journal is stored in your browser; use **Export backup** regularly.

## Data sources and how current they are

| Data | Source | How current |
|---|---|---|
| Crypto prices | Coinbase Exchange public ticker, fetched by your browser | **Live** (every 15 s; each price shows its last-trade time) |
| US stock prices | Finnhub (free key, stored only in your browser) | **Live** during US market hours, every 60 s. Without a key: official close |
| Other stock prices | Yahoo Finance daily bars | Official close of the date shown. The scan runs right after each market closes |
| Shariah ratios | Yahoo Finance company data | As last reported by the company (quarterly) |
| News | Google News RSS (aggregates publishers), English edition plus the local edition for regional stocks (Indonesian, Malaysian, Saudi, UAE, Qatari, Turkish) | Last 7 days, merged and de-duplicated; each headline shows publisher, age and a link. Information only |

A red **STALE** tag means the latest price is more than 3 trading days old. No free, reliable real-time feed exists for the Indonesian, Malaysian, Gulf or Turkish exchanges; real-time data there requires a paid exchange subscription.

## Match your scholar's view
Everything is set in two files, with no code changes needed:

| Setting | File | Default |
|---|---|---|
| `shariah_compliance.standard` | `data/advisor_config.json` | `AAOIFI_STANDARD_21` (30%). Use `DJIM` for 33%, or `CUSTOM` |
| `standard_profiles.CUSTOM` | `data/advisor_config.json` | Your own debt / cash / receivables / haram-revenue limits |
| `personal_exclusions` | `data/advisor_config.json` | Empty. Your own extra exclusions with a reason |
| `shariah_compliance.exclude_defence` | `data/advisor_config.json` | `true` (defence companies rejected) |
| `shariah_compliance.islamic_institution_allowlist` | `data/advisor_config.json` | BRIS.JK, 5258.KL, 1120.SR, 1150.SR, DIB.AE, QIBK.QA |
| `allowed_spot_cryptos` / `denylisted_symbols` | `data/halal_crypto_registry.json` | 10 utility coins; stablecoins denied |

Islamic banks and takaful operators on the allowlist skip the sector and leverage screens. Yahoo labels every bank "Banks", and customer deposits look like debt, so without the allowlist they would be wrongly rejected. The dashboard marks them "on your allowlist" so it's clear this is your choice.

## Zakat & purification calculator
The dashboard has a **Zakat & Purification** tab. Enter your holdings (symbol, units, trading or long-term, dividends received) and it calculates:
- **Zakat at 2.5%:** on full market value for trading holdings and all spot crypto. For long-term shares it uses 25% of market value as a proxy for the company's zakatable assets, or the full value if you choose the cautious option.
- **Purification:** dividends × the stock's non-compliant income % from the latest scan.
- **Nisab check:** against a threshold you enter (the value of 85 g of gold).

Prices come from the latest scan and can be overridden. Totals are per currency, with no conversion. Holdings are stored only in your browser.

## Global markets
Uses Yahoo Finance suffixes: `.JK` Indonesia, `.KL` Malaysia (numeric codes, e.g. `5347.KL` Tenaga), `.SR` Saudi, `.AD`/`.DU` UAE, `.IS` Turkey, `.JO` South Africa, `.CA` Egypt, plus US tickers.

The watchlist covers 50 stocks across the US, Indonesia, Malaysia, Saudi Arabia, the UAE (Dubai, `.AE`), Qatar and Turkey, plus the 10 cryptos. Yahoo Finance does not carry Abu Dhabi (ADX) listings.

Known limitations:
- Current market cap stands in for the 24–36-month average.
- The cash ratio uses total cash, not just interest-bearing cash, so it's stricter than AAOIFI requires.
- Yahoo has no haram-revenue breakdown, so purification uses a labelled 0.5% estimate unless you supply a figure.

## Run locally

```bash
pip install -r requirements.txt
python -m pytest -q        # offline test suite
python run_pipeline.py     # live scan (needs internet access to Yahoo Finance)
```

Then open `dashboard/index.html` via a local server (`python -m http.server -d dashboard`).

Run `python backtest.py --years 3` to measure the signals on your machine.

Outputs: `data/signals.json`, `data/learning_history.json` and `dashboard/data.json`. The learning loop also writes tuning stats into `data/advisor_config.json`.

## Automation
`.github/workflows/scan.yml` runs the tests and the scan four times a day (see the schedule above), then deploys the dashboard to GitHub Pages. Enable Pages with source **GitHub Actions** in the repo settings.

## Design docs
- Spec: `docs/superpowers/specs/2026-09-26-halal-stock-crypto-scanner-design.md`
- Plan: `docs/superpowers/plans/2026-09-26-halal-stock-crypto-scanner.md`

## Disclaimer
Research and educational tooling only, following the general consensus of AAOIFI, DJIM and the OIC Fiqh Academy. It is not a fatwa and not financial advice. Consult a qualified Shariah scholar and a financial adviser.
