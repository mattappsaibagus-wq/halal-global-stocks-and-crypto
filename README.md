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

| Ratio | AAOIFI Standard 21 (default) | DJIM |
|---|---|---|
| Interest-bearing debt / market cap | < 30% | < 33% |
| Cash + interest securities / market cap | < 30% | < 33% |
| Accounts receivable / market cap | < 30% | < 33% |
| Non-compliant revenue / total revenue | < 5% | < 5% |

Switch standards with `shariah_compliance.standard` in `data/advisor_config.json` (`AAOIFI_STANDARD_21`, `DJIM` or `CUSTOM`).

### 3. Dividend purification
Purification per share = dividend × non-compliant revenue ratio. Yahoo Finance does not break out haram revenue, so the default is a labelled **estimate** (0.5%). Every result carries `purification_basis`.

### Spot crypto
Only pairs listed in `data/halal_crypto_registry.json` pass: BTC, ETH, SOL, AVAX, POL (Yahoo symbol `POL28321-USD`), LINK, ADA, DOT, NEAR and ATOM, all against USD. Stablecoins, lending/yield tokens, privacy coins and meme tokens are excluded. Edit the registry to follow your own scholar's view.

### Strict rules built in
- **Missing data never passes.** A ticker whose data can't be fetched becomes `QUESTIONABLE`, not `HALAL`.
- **Spot only.** No shorting, margin, options or futures. `SELL` means exiting a position you own.
- **Execution gate.** `trading/executor.py` refuses anything that isn't a screened-halal BUY or SELL.
- **No fabricated signals.** If news can't be fetched, the news agent emits no signal.

## Match your scholar's view
Everything is set in two files, with no code changes needed:

| Setting | File | Default |
|---|---|---|
| `shariah_compliance.standard` | `data/advisor_config.json` | `AAOIFI_STANDARD_21` (30%). Use `DJIM` for 33%, or `CUSTOM` |
| `standard_profiles.CUSTOM` | `data/advisor_config.json` | Your own debt / cash / receivables / haram-revenue limits |
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

Outputs: `data/signals.json`, `data/learning_history.json` and `dashboard/data.json`. The learning loop also writes tuning stats into `data/advisor_config.json`.

## Automation
`.github/workflows/scan.yml` runs the tests and the scan on weekdays at 14:00 UTC, then deploys the dashboard to GitHub Pages. Enable Pages with source **GitHub Actions** in the repo settings.

## Design docs
- Spec: `docs/superpowers/specs/2026-09-26-halal-stock-crypto-scanner-design.md`
- Plan: `docs/superpowers/plans/2026-09-26-halal-stock-crypto-scanner.md`

## Disclaimer
Research and educational tooling only, following the general consensus of AAOIFI, DJIM and the OIC Fiqh Academy. It is not a fatwa and not financial advice. Consult a qualified Shariah scholar and a financial adviser.
