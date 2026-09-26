# Halal Global Stocks and Crypto — Design Document

**Date:** 2026-09-26  
**Status:** Approved  
**Target Repository:** `halal-global-stocks-and-crypto` (standalone)

---

## Executive Summary

**Halal Global Stocks and Crypto** is a strict Shariah-compliant early-movement scanner for global equities and spot cryptocurrencies. It integrates a primary **Shariah Gatekeeper Agent** (`ShariahScreenerAgent`) at the start of the scanner pipeline. Assets that fail qualitative (business activity) or quantitative (financial ratio) screens are marked as `HARAM / REJECTED` with detailed reasons, suppressing downstream buy/watch signals while logging compliance status. Compliant stocks are annotated with **Dividend Purification Percentages**, and verified spot cryptocurrencies are screened against a curated Halal asset registry.

---

## 1. System Architecture & Pipeline Data Flow

### Pipeline Sequence
```
watchlist.txt 
   │
   ▼
[Step 1: ShariahScreenerAgent] ──► Checks Sector, Financial Ratios & Crypto Rules
   │
   ├── STATUS: HARAM / REJECTED ──► Suppress BUY/WATCH signal, log violation on Dashboard
   │
   └── STATUS: HALAL ───────────► Execute Technical / Sentiment / DD Agents
                                        (EarlyDetector, Momentum, NewsScanner, DdAgent)
                                               │
                                               ▼
                                  [Step 2: AdvisorAgent]
                                  Consolidates Signals + Halal Metadata
                                               │
                                               ▼
                                  [Step 3: LearningLoop]
                                               │
                                               ▼
                                  [Step 4: Dashboard Output]
                                  Generates dashboard/data.json & UI
```

### Data Contract (`ShariahScreenerAgent` Output)
```json
{
  "symbol": "TLKM.JK",
  "asset_type": "equity",
  "is_halal": true,
  "standard_used": "AAOIFI_STANDARD_21",
  "rejection_reasons": [],
  "ratios": {
    "debt_ratio_pct": 21.4,
    "cash_ratio_pct": 12.1,
    "receivables_ratio_pct": 14.3,
    "non_compliant_rev_pct": 0.8
  },
  "purification_pct": 0.8,
  "sector": "Telecommunications",
  "timestamp": "2026-09-26T14:30:00Z"
}
```

---

## 2. Screening Methodology & Rules

### A. Sector Exclusion List (Qualitative Screen)
Assets are immediately rejected if their industry or sector matches prohibited categories:
* Conventional Banking, Insurance (except Takaful), Interest-based Financial Services
* Alcohol, Brewing, Distilleries
* Gambling, Casinos, Gaming
* Tobacco, Vaping
* Pornography, Adult Entertainment, Explicit Media
* Weapons & Defense Contractors (configurable)

### B. Quantitative Financial Ratio Screening
Standard defaults to **AAOIFI Standard 21** with fallback to **Dow Jones Islamic Market (DJIM)** rules via `data/advisor_config.json`.

| Screen Metric | AAOIFI Standard 21 | DJIM Standard | Formula |
| :--- | :--- | :--- | :--- |
| **Denominator** | 36-Month Avg Market Cap | 24-Month Avg Market Cap | Market Cap / Assets Fallback |
| **Total Debt Ratio** | `< 30%` | `< 33%` | `Interest-Bearing Debt / Denominator * 100` |
| **Cash & Securities Ratio** | `< 30%` | `< 33%` | `(Cash + Short-Term Securities) / Denominator * 100` |
| **Accounts Receivable Ratio**| `< 30%` | `< 33%` | `Accounts Receivable / Denominator * 100` |
| **Non-Compliant Revenue** | `< 5%` | `< 5%` | `Impermissible Revenue / Total Revenue * 100` |

### C. Dividend Purification Calculation
For compliant stocks with incidental non-compliant revenue ($< 5\%$):
$$\text{Purification Factor} = \frac{\text{Impermissible \& Interest Revenue}}{\text{Total Revenue}}$$
$$\text{Purification Per Share (\$) } = \text{Dividend Per Share} \times \text{Purification Factor}$$
$$\text{Purification \% } = \text{Purification Factor} \times 100$$

### D. Global Exchange Support
Native support for global Yahoo Finance ticker formats:
* **Indonesia:** `.JK` (e.g. `TLKM.JK`, `BBCA.JK`, `ICBP.JK`)
* **Malaysia:** `.KL` (e.g. `MAYBANK.KL`, `TENAGA.KL`)
* **Saudi Arabia:** `.SR` (e.g. `2222.SR`, `1120.SR`)
* **UAE:** `.DU` / `.AD` (e.g. `DIB.DU`, `FAB.AD`)
* **Turkey:** `.IS` (e.g. `THYAO.IS`)
* **South Africa:** `.JO` (e.g. `SOL.JO`)
* **Egypt:** `.CA` (e.g. `COMI.CA`)
* **US & Global:** `AAPL`, `MSFT`, `NVDA`, `GOOGL`, etc.

### E. Spot Cryptocurrency Rules
* **Permissible Whitelist:** Spot tokens with utility or store of value (`BTC-USD`, `ETH-USD`, `SOL-USD`, `AVAX-USD`, `POL-USD`, `LINK-USD`, `ADA-USD`, `DOT-USD`, `NEAR-USD`, `ATOM-USD`).
* **Impermissible Assets:** Algorithmic debt stablecoins, lending/borrowing yield protocol tokens (AAVE, COMP), privacy tokens (XMR), zero-utility meme coins.
* **Margin/Futures Blocking:** Leveraged crypto futures/perpetuals are blocked; only spot tickers (e.g. `-USD` or `-USDT` pairs) are processed.

---

## 3. Component Architecture & File Modifications

### 1. Files to Create & Update
* `agents/shariah_agent.py` *(NEW)*: Main gatekeeper agent handling sector checks, financial ratio calculations, dividend purification, and crypto registry verification.
* `data/halal_crypto_registry.json` *(NEW)*: List of allowed spot crypto assets and forbidden categories.
* `agents/base_agent.py` *(UPDATE)*: Added helper functions to fetch yfinance financial statements (balance sheet, income statement) and market cap history.
* `agents/advisor.py` *(UPDATE)*: Reads `ShariahScreenerAgent` output. If asset is `HARAM`, overrides signal recommendations to `REJECTED (HARAM)`. If `HALAL`, attaches compliance badge and purification metrics.
* `data/advisor_config.json` *(UPDATE)*: Contains configuration parameters (`shariah_standard: "AAOIFI_STANDARD_21"`, `max_debt_ratio: 0.30`, `max_cash_ratio: 0.30`, `max_receivables_ratio: 0.30`, `max_haram_revenue: 0.05`).
* `run_pipeline.py` *(UPDATE)*: Runs `ShariahScreenerAgent` before all other agents.
* `watchlist.txt` *(UPDATE)*: Includes default global stocks (`TLKM.JK`, `MAYBANK.KL`, `2222.SR`, `AAPL`, `NVDA`) and halal spot cryptos (`BTC-USD`, `ETH-USD`, `SOL-USD`).
* `dashboard/index.html` *(UPDATE)*: Renders `HALAL` / `HARAM` status chips, purification percentages, and halal crypto badges.

---

## 4. Error Handling & Edge Cases

1. **Incomplete Financial Data:** If balance sheet or income statement data is missing for a ticker, the agent flags it as `QUESTIONABLE / DATA INCOMPLETE` rather than silently approving it.
2. **Local Currency Conversion:** Financial ratios use relative percentages (e.g., Debt / Market Cap), making ratio calculations currency-invariant regardless of whether the ticker is priced in IDR, MYR, SAR, or USD.
3. **Crypto Data Fallback:** Crypto spot market data fetched via yfinance ticker fallback if primary exchange API is delayed.

---

## 5. Verification Plan

1. **Unit Test Gatekeeper Agent:** Verify `ShariahScreenerAgent` correctly classifies a known compliant stock (e.g. `AAPL`), a non-compliant bank (e.g. `JPM` or `BBCA.JK`), and spot crypto (`BTC-USD`).
2. **Pipeline Integration Test:** Run `python run_pipeline.py` and confirm `data/signals.json` and `dashboard/data.json` contain the new Halal fields.
3. **Dashboard Visual Audit:** Open `dashboard/index.html` in browser to confirm Halal badges, rejection tooltips, and purification metrics render clearly.
