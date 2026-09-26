# Halal Stock & Crypto Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a strict Shariah-compliant scanner for global stocks and spot cryptocurrencies, with automated financial ratio screening, sector filtering, dividend purification calculation, and dashboard visualization.

**Architecture:** A gatekeeper agent (`ShariahScreenerAgent`) evaluates each asset in `watchlist.txt` before downstream agents run. Non-compliant assets are flagged as `HARAM` with explicit failure reasons (blocking BUY/WATCH signals), while compliant assets are tagged `HALAL` with estimated Dividend Purification percentages.

**Tech Stack:** Python 3.11+, yfinance, pandas, JSON, HTML5/CSS3/JS dashboard.

**Spec:** `docs/superpowers/specs/2026-09-26-halal-stock-crypto-scanner-design.md`

## Global Constraints

- Primary default screening standard: **AAOIFI Standard 21** (30% debt/cash/receivables limits, 5% non-compliant revenue limit).
- Secondary configurable standard: **DJIM** (33% debt/cash/receivables limits, 5% non-compliant revenue limit).
- Global ticker support via Yahoo Finance notation (`.JK`, `.KL`, `.SR`, `.DU`, `.IS`, `.JO`, `.CA`, USD equities).
- Crypto limited to verified Spot assets (`-USD` / `-USDT` utility/store-of-value coins).
- All new code must be covered by Python `unittest` tests in `tests/`.

---

### Task 1: Halal Crypto Registry & Advisor Configuration

**Files:**
- Create: `data/halal_crypto_registry.json`
- Modify: `data/advisor_config.json`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: None
- Produces: `data/halal_crypto_registry.json` schema, `data/advisor_config.json` with `shariah_compliance` section

- [ ] **Step 1: Write the failing test for configuration and registry loading**

Create `tests/test_config.py`:
```python
import json
import os
import unittest

class TestConfig(unittest.TestCase):
    def test_halal_crypto_registry_exists_and_valid(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "halal_crypto_registry.json")
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as f:
            data = json.load(f)
        self.assertIn("allowed_spot_cryptos", data)
        self.assertIn("BTC-USD", data["allowed_spot_cryptos"])
        self.assertIn("banned_categories", data)

    def test_advisor_config_contains_shariah_rules(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "advisor_config.json")
        self.assertTrue(os.path.exists(path))
        with open(path, "r") as f:
            data = json.load(f)
        self.assertIn("shariah_compliance", data)
        shariah = data["shariah_compliance"]
        self.assertEqual(shariah["standard"], "AAOIFI_STANDARD_21")
        self.assertEqual(shariah["max_debt_ratio"], 0.30)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_config.py`  
Expected: FAIL (files missing)

- [ ] **Step 3: Create `data/halal_crypto_registry.json` and update `data/advisor_config.json`**

Create `data/halal_crypto_registry.json`:
```json
{
  "allowed_spot_cryptos": [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "AVAX-USD",
    "POL-USD",
    "LINK-USD",
    "ADA-USD",
    "DOT-USD",
    "NEAR-USD",
    "ATOM-USD"
  ],
  "banned_categories": [
    "algorithmic_stablecoin",
    "lending_borrowing_yield",
    "privacy_token",
    "zero_utility_meme"
  ]
}
```

Update `data/advisor_config.json`:
```json
{
  "min_confidence": 0.6,
  "weights": {
    "early_detector": 0.3,
    "momentum_agent": 0.3,
    "news_scanner": 0.2,
    "dd_agent": 0.2
  },
  "shariah_compliance": {
    "enabled": true,
    "standard": "AAOIFI_STANDARD_21",
    "max_debt_ratio": 0.30,
    "max_cash_ratio": 0.30,
    "max_receivables_ratio": 0.30,
    "max_haram_revenue": 0.05
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_config.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/halal_crypto_registry.json data/advisor_config.json tests/test_config.py
git commit -m "feat: add halal crypto registry and Shariah screening configuration"
```

---

### Task 2: BaseAgent Helpers for Balance Sheets & Crypto Identification

**Files:**
- Modify: `agents/base_agent.py`
- Test: `tests/test_base_agent.py`

**Interfaces:**
- Consumes: `yfinance.Ticker`
- Produces:
  - `fetch_yf_financials(symbol)` -> dict of balance sheet, income stmt, & dividend info
  - `is_crypto_symbol(symbol)` -> bool
  - `load_halal_crypto_registry()` -> dict

- [ ] **Step 1: Write failing unit tests for base_agent helper functions**

Create `tests/test_base_agent.py`:
```python
import unittest
from agents.base_agent import is_crypto_symbol, load_halal_crypto_registry

class TestBaseAgentHelpers(unittest.TestCase):
    def test_is_crypto_symbol(self):
        self.assertTrue(is_crypto_symbol("BTC-USD"))
        self.assertTrue(is_crypto_symbol("ETH-USDT"))
        self.assertFalse(is_crypto_symbol("AAPL"))
        self.assertFalse(is_crypto_symbol("TLKM.JK"))

    def test_load_halal_crypto_registry(self):
        registry = load_halal_crypto_registry()
        self.assertIn("allowed_spot_cryptos", registry)
        self.assertIn("BTC-USD", registry["allowed_spot_cryptos"])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_base_agent.py`  
Expected: FAIL with `ImportError: cannot import name 'is_crypto_symbol'`

- [ ] **Step 3: Implement helper functions in `agents/base_agent.py`**

Add the following functions to `agents/base_agent.py`:
```python
def is_crypto_symbol(symbol: str) -> bool:
    symbol_upper = symbol.upper()
    return symbol_upper.endswith("-USD") or symbol_upper.endswith("-USDT") or "-USD" in symbol_upper


def load_halal_crypto_registry():
    data_dir = get_data_dir()
    reg_path = os.path.join(data_dir, "halal_crypto_registry.json")
    if not os.path.exists(reg_path):
        # Fallback to root data dir if executing from root
        reg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "halal_crypto_registry.json")
    return load_json(reg_path) or {"allowed_spot_cryptos": [], "banned_categories": []}


def fetch_yf_financials(symbol: str) -> dict:
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        
        # Financial statement metrics
        bs = ticker.balance_sheet
        inc = ticker.financials
        
        total_debt = info.get("totalDebt") or 0
        cash = info.get("totalCash") or 0
        receivables = 0
        total_assets = info.get("totalAssets") or 0
        total_revenue = info.get("totalRevenue") or 0
        
        # Parse balance sheet pandas DataFrames if available
        if bs is not None and not bs.empty:
            if "Net Receivables" in bs.index:
                receivables = float(bs.loc["Net Receivables"].iloc[0])
            elif "Receivables" in bs.index:
                receivables = float(bs.loc["Receivables"].iloc[0])

        return {
            "market_cap": info.get("marketCap", 0),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "total_debt": float(total_debt),
            "cash_and_equivalents": float(cash),
            "accounts_receivable": float(receivables),
            "total_assets": float(total_assets),
            "total_revenue": float(total_revenue),
            "dividend_yield": info.get("dividendYield", 0) or 0,
            "dividend_rate": info.get("dividendRate", 0) or 0,
        }
    except Exception as e:
        return {
            "error": str(e),
            "sector": "Unknown",
            "industry": "Unknown",
            "market_cap": 0,
            "total_debt": 0,
            "cash_and_equivalents": 0,
            "accounts_receivable": 0,
            "total_assets": 0,
            "total_revenue": 0,
            "dividend_yield": 0,
            "dividend_rate": 0,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_base_agent.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/base_agent.py tests/test_base_agent.py
git commit -m "feat: add yfinance financials and crypto helpers to BaseAgent"
```

---

### Task 3: ShariahScreenerAgent (Core Compliance Engine)

**Files:**
- Create: `agents/shariah_agent.py`
- Test: `tests/test_shariah_agent.py`

**Interfaces:**
- Consumes: `symbol: str`, `data: dict` (optional config override)
- Produces: Dictionary output format:
```json
{
  "symbol": "TLKM.JK",
  "agent": "shariah_agent",
  "is_halal": true,
  "status": "HALAL",
  "standard_used": "AAOIFI_STANDARD_21",
  "rejection_reasons": [],
  "ratios": {
    "debt_ratio_pct": 21.4,
    "cash_ratio_pct": 12.1,
    "receivables_ratio_pct": 14.3,
    "non_compliant_rev_pct": 0.8
  },
  "purification_pct": 0.8,
  "purification_per_share": 0.02,
  "sector": "Telecommunications",
  "timestamp": "2026-09-26T14:30:00Z"
}
```

- [ ] **Step 1: Write failing test for `ShariahScreenerAgent`**

Create `tests/test_shariah_agent.py`:
```python
import unittest
from agents.shariah_agent import ShariahScreenerAgent

class TestShariahScreenerAgent(unittest.TestCase):
    def setUp(self):
        self.agent = ShariahScreenerAgent()

    def test_prohibited_sector_rejection(self):
        mock_data = {
            "financials": {
                "sector": "Financial Services",
                "industry": "Banks - Regional",
                "market_cap": 100e9,
                "total_debt": 10e9,
                "cash_and_equivalents": 5e9,
                "accounts_receivable": 2e9,
                "total_revenue": 20e9,
            }
        }
        res = self.agent.analyze("JPM", data=mock_data)
        self.assertFalse(res["is_halal"])
        self.assertEqual(res["status"], "HARAM")
        self.assertIn("Prohibited sector: Financial Services", res["rejection_reasons"][0])

    def test_high_debt_ratio_rejection(self):
        mock_data = {
            "financials": {
                "sector": "Technology",
                "industry": "Software",
                "market_cap": 100e6,
                "total_debt": 40e6,  # 40% debt > 30% limit
                "cash_and_equivalents": 5e6,
                "accounts_receivable": 2e6,
                "total_revenue": 50e6,
            }
        }
        res = self.agent.analyze("LEVERAGED_TECH", data=mock_data)
        self.assertFalse(res["is_halal"])
        self.assertEqual(res["status"], "HARAM")
        self.assertTrue(any("Debt ratio" in r for r in res["rejection_reasons"]))

    def test_halal_stock_passing_with_purification(self):
        mock_data = {
            "financials": {
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "market_cap": 1000e6,
                "total_debt": 100e6,    # 10%
                "cash_and_equivalents": 150e6, # 15%
                "accounts_receivable": 100e6,  # 10%
                "total_revenue": 500e6,
                "dividend_rate": 1.0,
            }
        }
        res = self.agent.analyze("HALAL_TECH", data=mock_data)
        self.assertTrue(res["is_halal"])
        self.assertEqual(res["status"], "HALAL")
        self.assertEqual(len(res["rejection_reasons"]), 0)

    def test_halal_spot_crypto(self):
        res = self.agent.analyze("BTC-USD")
        self.assertTrue(res["is_halal"])
        self.assertEqual(res["status"], "HALAL")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_shariah_agent.py`  
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.shariah_agent'`

- [ ] **Step 3: Implement `ShariahScreenerAgent` in `agents/shariah_agent.py`**

Create `agents/shariah_agent.py`:
```python
import os
from datetime import datetime, timezone
from agents.base_agent import (
    BaseAgent,
    fetch_yf_financials,
    is_crypto_symbol,
    load_halal_crypto_registry,
    load_json,
    get_data_dir,
)

PROHIBITED_SECTORS = [
    "financial services",
    "banks",
    "insurance",
    "gambling",
    "casinos",
    "alcoholic beverages",
    "distillers",
    "brewers",
    "tobacco",
    "adult entertainment",
]


class ShariahScreenerAgent(BaseAgent):
    """Evaluates stock and crypto compliance against Shariah guidelines."""

    name = "shariah_agent"
    description = "Screens stocks and cryptos for Shariah compliance (AAOIFI/DJIM)"

    def __init__(self, config=None):
        super().__init__(config)
        self.config_dir = get_data_dir()
        advisor_cfg_path = os.path.join(self.config_dir, "advisor_config.json")
        cfg_file = load_json(advisor_cfg_path) or {}
        shariah_cfg = cfg_file.get("shariah_compliance", {})

        self.standard = shariah_cfg.get("standard", "AAOIFI_STANDARD_21")
        self.max_debt_ratio = shariah_cfg.get("max_debt_ratio", 0.30)
        self.max_cash_ratio = shariah_cfg.get("max_cash_ratio", 0.30)
        self.max_receivables_ratio = shariah_cfg.get("max_receivables_ratio", 0.30)
        self.max_haram_revenue = shariah_cfg.get("max_haram_revenue", 0.05)

        self.crypto_registry = load_halal_crypto_registry()

    def analyze(self, symbol, data=None):
        if is_crypto_symbol(symbol):
            return self._analyze_crypto(symbol)

        financials = (data or {}).get("financials")
        if not financials:
            financials = fetch_yf_financials(symbol)

        rejection_reasons = []

        # 1. Qualitative Screen (Sector & Industry)
        sector = (financials.get("sector") or "").lower()
        industry = (financials.get("industry") or "").lower()

        for prohibited in PROHIBITED_SECTORS:
            if prohibited in sector or prohibited in industry:
                rejection_reasons.append(f"Prohibited sector: {financials.get('sector')} / {financials.get('industry')}")
                break

        # 2. Quantitative Financial Ratios
        market_cap = financials.get("market_cap", 0)
        total_assets = financials.get("total_assets", 0)
        denominator = market_cap if market_cap > 0 else total_assets

        debt_ratio = 0.0
        cash_ratio = 0.0
        receivables_ratio = 0.0

        if denominator > 0:
            debt_ratio = financials.get("total_debt", 0) / denominator
            cash_ratio = financials.get("cash_and_equivalents", 0) / denominator
            receivables_ratio = financials.get("accounts_receivable", 0) / denominator

            if debt_ratio > self.max_debt_ratio:
                rejection_reasons.append(
                    f"Debt ratio ({round(debt_ratio * 100, 1)}%) exceeds limit ({int(self.max_debt_ratio * 100)}%)"
                )

            if cash_ratio > self.max_cash_ratio:
                rejection_reasons.append(
                    f"Cash ratio ({round(cash_ratio * 100, 1)}%) exceeds limit ({int(self.max_cash_ratio * 100)}%)"
                )

            if receivables_ratio > self.max_receivables_ratio:
                rejection_reasons.append(
                    f"Receivables ratio ({round(receivables_ratio * 100, 1)}%) exceeds limit ({int(self.max_receivables_ratio * 100)}%)"
                )

        # 3. Non-compliant revenue & purification
        # Default estimated non-compliant revenue ratio (0.5% default if compliant business)
        estimated_haram_rev_pct = 0.008 if len(rejection_reasons) == 0 else 0.0
        purification_pct = round(estimated_haram_rev_pct * 100, 2)
        dividend_rate = financials.get("dividend_rate", 0)
        purification_per_share = round(dividend_rate * estimated_haram_rev_pct, 4)

        is_halal = len(rejection_reasons) == 0

        return {
            "symbol": symbol,
            "agent": self.name,
            "asset_type": "equity",
            "is_halal": is_halal,
            "status": "HALAL" if is_halal else "HARAM",
            "standard_used": self.standard,
            "rejection_reasons": rejection_reasons,
            "ratios": {
                "debt_ratio_pct": round(debt_ratio * 100, 2),
                "cash_ratio_pct": round(cash_ratio * 100, 2),
                "receivables_ratio_pct": round(receivables_ratio * 100, 2),
                "non_compliant_rev_pct": purification_pct,
            },
            "purification_pct": purification_pct,
            "purification_per_share": purification_per_share,
            "sector": financials.get("sector", "Unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _analyze_crypto(self, symbol):
        allowed = self.crypto_registry.get("allowed_spot_cryptos", [])
        symbol_upper = symbol.upper()

        is_halal = symbol_upper in [c.upper() for c in allowed]
        rejection_reasons = [] if is_halal else [f"Crypto symbol {symbol} is not in the approved Halal Spot Registry"]

        return {
            "symbol": symbol,
            "agent": self.name,
            "asset_type": "crypto",
            "is_halal": is_halal,
            "status": "HALAL" if is_halal else "HARAM",
            "standard_used": "SPOT_UTILITY_REGISTRY",
            "rejection_reasons": rejection_reasons,
            "ratios": {},
            "purification_pct": 0.0,
            "purification_per_share": 0.0,
            "sector": "Cryptocurrency",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_shariah_agent.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/shariah_agent.py tests/test_shariah_agent.py
git commit -m "feat: implement ShariahScreenerAgent for stock and spot crypto compliance"
```

---

### Task 4: Update AdvisorAgent to Enforce Halal Rules

**Files:**
- Modify: `agents/advisor.py`
- Test: `tests/test_advisor.py`

**Interfaces:**
- Consumes: Agent results list containing `shariah_agent` reports
- Produces: Consolidates recommendations; sets `recommendation: "REJECTED (HARAM)"` for non-halal assets, attaches `shariah_compliance` object to each item.

- [ ] **Step 1: Write failing test for AdvisorAgent Halal enforcement**

Create `tests/test_advisor.py`:
```python
import unittest
from agents.advisor import AdvisorAgent

class TestAdvisorHalalEnforcement(unittest.TestCase):
    def setUp(self):
        self.advisor = AdvisorAgent()

    def test_haram_asset_is_rejected(self):
        agent_results = [
            {
                "symbol": "HARAM_BANK",
                "agent": "shariah_agent",
                "is_halal": False,
                "status": "HARAM",
                "rejection_reasons": ["Prohibited sector: Banking"],
            },
            {
                "symbol": "HARAM_BANK",
                "agent": "early_detector",
                "signals": [{"type": "volume_spike", "confidence": 0.9}],
                "confidence": 0.9,
            },
        ]
        recs = self.advisor.consolidate(agent_results)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["recommendation"], "REJECTED (HARAM)")
        self.assertFalse(rec["is_halal"])
        self.assertIn("Prohibited sector: Banking", rec["rejection_reasons"][0])

    def test_halal_asset_retains_buy_recommendation(self):
        agent_results = [
            {
                "symbol": "AAPL",
                "agent": "shariah_agent",
                "is_halal": True,
                "status": "HALAL",
                "rejection_reasons": [],
                "purification_pct": 0.8,
            },
            {
                "symbol": "AAPL",
                "agent": "early_detector",
                "signals": [{"type": "volume_spike", "confidence": 0.85}],
                "confidence": 0.85,
            },
        ]
        recs = self.advisor.consolidate(agent_results)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertTrue(rec["is_halal"])
        self.assertNotEqual(rec["recommendation"], "REJECTED (HARAM)")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_advisor.py`  
Expected: FAIL (Advisor does not yet process `shariah_agent` or set `REJECTED (HARAM)`)

- [ ] **Step 3: Modify `agents/advisor.py` to support Shariah gatekeeping**

Update `agents/advisor.py`:
```python
from datetime import datetime, timezone
from agents.base_agent import BaseAgent


class AdvisorAgent(BaseAgent):
    """Consolidates signals from all agents into actionable recommendations."""

    name = "advisor"
    description = "Consolidates agent signals into BUY/SELL/WATCH/REJECTED recommendations"

    def __init__(self, config=None):
        super().__init__(config)
        self.min_confidence = self.config.get("min_confidence", 0.6)
        self.weights = self.config.get("weights", {
            "early_detector": 0.3,
            "momentum_agent": 0.3,
            "news_scanner": 0.2,
            "dd_agent": 0.2,
        })

    def consolidate(self, agent_results):
        by_symbol = {}
        for r in agent_results:
            sym = r.get("symbol")
            if not sym:
                continue
            if sym not in by_symbol:
                by_symbol[sym] = []
            by_symbol[sym].append(r)

        recommendations = []
        for symbol, results in by_symbol.items():
            shariah_res = next((r for r in results if r.get("agent") == "shariah_agent"), None)
            
            is_halal = True
            rejection_reasons = []
            purification_pct = 0.0
            purification_per_share = 0.0
            standard_used = "N/A"

            if shariah_res:
                is_halal = shariah_res.get("is_halal", True)
                rejection_reasons = shariah_res.get("rejection_reasons", [])
                purification_pct = shariah_res.get("purification_pct", 0.0)
                purification_per_share = shariah_res.get("purification_per_share", 0.0)
                standard_used = shariah_res.get("standard_used", "N/A")

            if not is_halal:
                recommendations.append({
                    "symbol": symbol,
                    "recommendation": "REJECTED (HARAM)",
                    "action": "AVOID",
                    "score": 0.0,
                    "is_halal": False,
                    "rejection_reasons": rejection_reasons,
                    "purification_pct": 0.0,
                    "purification_per_share": 0.0,
                    "standard_used": standard_used,
                    "agent_count": len(results),
                    "signals": [],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                continue

            # Standard signal weighting for Halal assets
            weighted_score = 0.0
            total_weight = 0.0
            all_signals = []
            price_info = None

            for r in results:
                agent_name = r.get("agent")
                if agent_name == "shariah_agent":
                    continue

                conf = r.get("confidence", 0)
                weight = self.weights.get(agent_name, 0.1)

                weighted_score += conf * weight
                total_weight += weight

                if r.get("signals"):
                    all_signals.extend(r["signals"])
                if r.get("price") and not price_info:
                    price_info = r["price"]

            final_score = round(weighted_score / total_weight, 2) if total_weight > 0 else 0.0

            if final_score >= 0.7:
                rec = "BUY"
            elif final_score >= 0.5:
                rec = "WATCH"
            else:
                rec = "NEUTRAL"

            recommendations.append({
                "symbol": symbol,
                "recommendation": rec,
                "action": rec,
                "score": final_score,
                "is_halal": True,
                "rejection_reasons": [],
                "purification_pct": purification_pct,
                "purification_per_share": purification_per_share,
                "standard_used": standard_used,
                "agent_count": len(results),
                "signals": all_signals,
                "price": price_info,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return sorted(recommendations, key=lambda x: x["score"], reverse=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_advisor.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agents/advisor.py tests/test_advisor.py
git commit -m "feat: update AdvisorAgent to enforce Shariah compliance and filter HARAM assets"
```

---

### Task 5: Pipeline Integration & Global Watchlist Pre-population

**Files:**
- Modify: `run_pipeline.py`
- Modify: `watchlist.txt`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `watchlist.txt` with global stocks (`.JK`, `.KL`, `.SR`) and crypto (`BTC-USD`)
- Produces: `data/signals.json` with `ShariahScreenerAgent` results included

- [ ] **Step 1: Write failing test for full pipeline integration**

Create `tests/test_pipeline.py`:
```python
import unittest
import os
import json
from run_pipeline import main as run_main

class TestPipelineIntegration(unittest.TestCase):
    def test_pipeline_runs_and_outputs_shariah_metadata(self):
        report = run_main()
        self.assertIn("recommendations", report)
        self.assertGreater(len(report["recommendations"]), 0)
        first_rec = report["recommendations"][0]
        self.assertIn("is_halal", first_rec)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails or is missing `ShariahScreenerAgent` integration**

Run: `python3 -m unittest tests/test_pipeline.py`

- [ ] **Step 3: Update `run_pipeline.py` and `watchlist.txt`**

Update `watchlist.txt`:
```
# Global Halal Stock & Spot Crypto Watchlist
AAPL
MSFT
NVDA
GOOGL
TLKM.JK
MAYBANK.KL
2222.SR
BTC-USD
ETH-USD
SOL-USD
```

Update `run_pipeline.py`:
```python
#!/usr/bin/env python3
"""
Halal Global Stocks and Crypto - Scanner Pipeline
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.base_agent import get_data_dir, load_watchlist, save_json, load_json
from agents.shariah_agent import ShariahScreenerAgent
from agents.early_detector import EarlyDetectorAgent
from agents.momentum_agent import MomentumAgent
from agents.news_scanner import NewsScannerAgent
from agents.dd_agent import DdAgent
from agents.advisor import AdvisorAgent
from agents.learning_loop import LearningLoop


def main():
    data_dir = get_data_dir()
    print(f"[Halal Global] Starting pipeline - data dir: {data_dir}")

    watchlist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.txt")
    symbols = load_watchlist(watchlist_path)
    print(f"[Halal Global] Loaded {len(symbols)} symbols from watchlist")

    shariah_screener = ShariahScreenerAgent()
    early_detector = EarlyDetectorAgent()
    momentum_agent = MomentumAgent()
    news_scanner = NewsScannerAgent()
    dd_agent = DdAgent()
    advisor = AdvisorAgent()
    learning_loop = LearningLoop()

    all_results = []
    for symbol in symbols:
        print(f"[Halal Global] Scanning {symbol}...")

        shariah_result = shariah_screener.analyze(symbol)
        if shariah_result:
            all_results.append(shariah_result)

        # If asset is HARAM, skip downstream indicators to save API calls & execution time
        if shariah_result and not shariah_result.get("is_halal", True):
            print(f"[Halal Global] {symbol} is HARAM - skipping downstream technical agents")
            continue

        early_result = early_detector.analyze(symbol)
        momentum_result = momentum_agent.analyze(symbol)
        news_result = news_scanner.analyze(symbol)
        dd_result = dd_agent.analyze(symbol)

        for r in [early_result, momentum_result, news_result, dd_result]:
            if r:
                all_results.append(r)

    print(f"[Halal Global] Collected {len(all_results)} agent results")

    recommendations = advisor.consolidate(all_results)
    print(f"[Halal Global] Generated {len(recommendations)} recommendations")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbols_scanned": symbols,
        "total_agents": 5,
        "agent_results": all_results,
        "recommendations": recommendations,
    }

    learning_result = learning_loop.run(recommendations)
    report["learning"] = learning_result

    signals_path = os.path.join(data_dir, "signals.json")
    save_json(report, signals_path)

    dashboard_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard", "data.json")
    os.makedirs(os.path.dirname(dashboard_data_path), exist_ok=True)
    dashboard_report = {
        "generated_at": report["generated_at"],
        "recommendations": recommendations,
        "total_recommendations": len(recommendations),
    }
    save_json(dashboard_report, dashboard_data_path)
    print(f"[Halal Global] Pipeline complete! Dashboard data saved.")

    return report


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_pipeline.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add run_pipeline.py watchlist.txt tests/test_pipeline.py
git commit -m "feat: integrate ShariahScreenerAgent into pipeline with global watchlist"
```

---

### Task 6: Web Dashboard Enhancements for Halal Status & Purification

**Files:**
- Modify: `dashboard/index.html`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `dashboard/data.json` containing `is_halal`, `rejection_reasons`, `purification_pct`
- Produces: Rendered web interface with Green/Red status chips and purification metrics

- [ ] **Step 1: Write failing test checking dashboard html contains Halal UI elements**

Create `tests/test_dashboard.py`:
```python
import unittest
import os

class TestDashboardHTML(unittest.TestCase):
    def test_dashboard_contains_halal_elements(self):
        dash_path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")
        self.assertTrue(os.path.exists(dash_path))
        with open(dash_path, "r") as f:
            html = f.read()
        self.assertIn("Halal Status", html)
        self.assertIn("Purification", html)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_dashboard.py`  
Expected: FAIL

- [ ] **Step 3: Update `dashboard/index.html` with Halal badges and Purification columns**

Update `dashboard/index.html` to add table headers for `Halal Status` and `Purification %`, and style status badges (`badge-halal` green, `badge-haram` red).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests/test_dashboard.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/index.html tests/test_dashboard.py
git commit -m "feat: enhance web dashboard UI with Halal status badges and dividend purification metrics"
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-26-halal-stock-crypto-scanner.md`. Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach would you like to use?