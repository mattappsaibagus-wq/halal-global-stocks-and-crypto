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

Switch standards with `shariah_compliance.standard` in `data/advisor_config.json` (`AAOIFI_STANDARD_21` or `DJIM`).

### 3. Dividend purification
Purification per share = dividend × non-compliant revenue ratio. Yahoo Finance does not break out haram revenue, so the default is a labelled **estimate** (0.5%). Every result carries `purification_basis`.

### Spot crypto
Only pairs listed in `data/halal_crypto_registry.json` pass: BTC, ETH, SOL, AVAX, POL, LINK, ADA, DOT, NEAR and ATOM, all against USD. Stablecoins, lending/yield tokens, privacy coins and meme tokens are excluded. Edit the registry to follow your own scholar's view.

### Strict rules built in
- **Missing data never passes.** A ticker whose data can't be fetched becomes `QUESTIONABLE`, not `HALAL`.
- **Spot only.** No shorting, margin, options or futures. `SELL` means exiting a position you own.
- **Execution gate.** `trading/executor.py` refuses anything that isn't a screened-halal BUY or SELL.
- **No fabricated signals.** If news can't be fetched, the news agent emits no signal.

## Global markets
Uses Yahoo Finance suffixes: `.JK` Indonesia, `.KL` Malaysia (numeric codes, e.g. `5347.KL` Tenaga), `.SR` Saudi, `.AD`/`.DU` UAE, `.IS` Turkey, `.JO` South Africa, `.CA` Egypt, plus US tickers.

Known limitations:
- Islamic banks (e.g. `1120.SR` Al Rajhi) are rejected by the sector screen, because Yahoo labels them "Banks". Treat those as manual review.
- Current market cap stands in for the 24–36-month average.

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
