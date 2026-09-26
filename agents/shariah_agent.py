import os
from datetime import datetime, timezone

from agents.base_agent import (
    BaseAgent,
    fetch_yf_financials,
    is_crypto_symbol,
    load_advisor_config,
    load_halal_crypto_registry,
    load_json,
    get_data_dir,
    normalise_crypto_symbol,
    to_float,
)

# Business activities that are impermissible in themselves. Matched against
# Yahoo Finance `sector` and `industry` labels, so entries are the vocabulary
# those labels actually use.
PROHIBITED_SECTORS = [
    "financial services",
    "banks",
    "credit services",
    "insurance",
    "gambling",
    "casinos",
    "alcoholic beverages",
    "brewers",
    "distillers",
    "wineries",
    "tobacco",
    "adult entertainment",
    "internet content",
    "publishing",
    "aerospace & defense",
]

# Industry-only additions: impermissible sub-activities inside otherwise
# permissible sectors (a permissible sector does not launder a haram product).
PROHIBITED_INDUSTRIES = [
    "brewers",
    "distillers",
    "wineries",
    "casinos",
    "gambling",
    "adult entertainment",
    "tobacco",
    "cigarettes",
    "arms",
    "aerospace & defense",
]

STATUS_HALAL = "HALAL"
STATUS_HARAM = "HARAM"
STATUS_QUESTIONABLE = "QUESTIONABLE"

DEFAULT_STANDARD = "AAOIFI_STANDARD_21"
DEFAULT_LIMITS = {
    "max_debt_ratio": 0.30,
    "max_cash_ratio": 0.30,
    "max_receivables_ratio": 0.30,
    "max_haram_revenue": 0.05,
    "denominator_basis": "market_cap",
}


def _percent(value):
    return round(value * 100, 2)


def _limit_pct(limit):
    return f"{limit * 100:g}%"


class ShariahScreenerAgent(BaseAgent):
    """Screens equities and spot crypto for Shariah compliance.

    Applies a two-stage test: a qualitative business-activity screen, then the
    quantitative financial-ratio screen of AAOIFI Standard No. 21 (or DJIM).
    Non-compliant assets are reported as HARAM with explicit reasons; assets
    whose data cannot be resolved are reported as QUESTIONABLE so that a missing
    data feed can never be mistaken for a compliance pass.
    """

    name = "shariah_agent"
    description = "Screens stocks and spot cryptos for Shariah compliance (AAOIFI/DJIM)"

    def __init__(self, config=None, standard=None, crypto_registry=None):
        super().__init__(config)
        advisor_cfg = load_advisor_config()
        shariah_cfg = advisor_cfg.get("shariah_compliance", {})

        self.enabled = shariah_cfg.get("enabled", True)
        self.standard = standard or shariah_cfg.get("standard", DEFAULT_STANDARD)

        # Limits come from the named standard's profile, so DJIM can be
        # selected without editing the shipped configuration.
        limits = dict(DEFAULT_LIMITS)
        profile = advisor_cfg.get("standard_profiles", {}).get(self.standard, {})
        limits.update({k: v for k, v in profile.items() if k in DEFAULT_LIMITS})

        # The shariah_compliance block describes the config's *own* standard, so
        # it only overrides when that is the standard in use. Applying it to a
        # different standard would silently reset DJIM's 33% back to 30%.
        if self.standard == shariah_cfg.get("standard", DEFAULT_STANDARD):
            limits.update({k: v for k, v in shariah_cfg.items() if k in DEFAULT_LIMITS})
        # An explicitly passed config wins over everything.
        if config:
            limits.update({k: v for k, v in config.items() if k in DEFAULT_LIMITS})
        self.limits = limits

        self.max_debt_ratio = limits["max_debt_ratio"]
        self.max_cash_ratio = limits["max_cash_ratio"]
        self.max_receivables_ratio = limits["max_receivables_ratio"]
        self.max_haram_revenue = limits["max_haram_revenue"]
        self.denominator_basis = limits["denominator_basis"]
        self.default_non_compliant_revenue_ratio = shariah_cfg.get(
            "default_non_compliant_revenue_ratio", 0.005
        )

        # Scholar-view switches (see README "Match your scholar's view").
        self.exclude_defence = shariah_cfg.get("exclude_defence", True)
        self.islamic_allowlist = {
            t.upper() for t in shariah_cfg.get("islamic_institution_allowlist", [])
        }

        self.crypto_registry = (
            crypto_registry if crypto_registry is not None else load_halal_crypto_registry()
        )

    def analyze(self, symbol, data=None):
        if is_crypto_symbol(symbol):
            return self._analyze_crypto(symbol)
        return self._analyze_equity(symbol, (data or {}).get("financials"))

    # -- equities ---------------------------------------------------------

    def _analyze_equity(self, symbol, financials):
        if not financials:
            financials = fetch_yf_financials(symbol)

        if symbol.upper() in self.islamic_allowlist:
            return self._allowlisted_institution(symbol, financials)

        # Data-quality problems are tracked apart from compliance violations:
        # a feed that returned nothing is not evidence of non-compliance, and
        # must not be reported as HARAM.
        data_issues = []
        if financials.get("error"):
            data_issues.append(f"Data error: {financials['error']}")

        sector = financials.get("sector") or "Unknown"
        industry = financials.get("industry") or "Unknown"

        has_data = financials.get("has_data")
        if has_data is None:
            has_data = bool(financials.get("market_cap", 0) > 0 and sector != "Unknown")
        if not has_data:
            data_issues.append(
                f"Insufficient financial data for Shariah screening: "
                f"no company profile resolved for {symbol} "
                f"(sector={sector}, industry={industry})"
            )

        rejection_reasons = list(self._screen_business_activity(sector, industry))

        denominator, denominator_basis = self._resolve_denominator(financials)
        ratios = {
            "debt_ratio_pct": 0.0,
            "cash_ratio_pct": 0.0,
            "receivables_ratio_pct": 0.0,
            "non_compliant_rev_pct": 0.0,
        }

        if denominator > 0:
            debt_ratio = financials.get("total_debt", 0) / denominator
            cash_ratio = financials.get("cash_and_equivalents", 0) / denominator
            receivables_ratio = financials.get("accounts_receivable", 0) / denominator

            ratios["debt_ratio_pct"] = _percent(debt_ratio)
            ratios["cash_ratio_pct"] = _percent(cash_ratio)
            ratios["receivables_ratio_pct"] = _percent(receivables_ratio)

            for label, value, limit in (
                ("Debt ratio", debt_ratio, self.max_debt_ratio),
                ("Cash ratio", cash_ratio, self.max_cash_ratio),
                ("Receivables ratio", receivables_ratio, self.max_receivables_ratio),
            ):
                if value > limit:
                    rejection_reasons.append(
                        f"{label} ({_percent(value)}%) exceeds {self.standard} limit "
                        f"({_limit_pct(limit)})"
                    )
        else:
            data_issues.append(
                "Cannot compute financial ratios: no market cap or total assets "
                "denominator available"
            )

        non_compliant_ratio, basis = self._resolve_non_compliant_ratio(financials)
        ratios["non_compliant_rev_pct"] = _percent(non_compliant_ratio)
        if non_compliant_ratio > self.max_haram_revenue:
            rejection_reasons.append(
                f"Non-compliant revenue ({_percent(non_compliant_ratio)}%) exceeds "
                f"{self.standard} limit ({_limit_pct(self.max_haram_revenue)})"
            )

        is_halal = not rejection_reasons and not data_issues
        if rejection_reasons:
            status = STATUS_HARAM
        elif data_issues:
            status = STATUS_QUESTIONABLE
        else:
            status = STATUS_HALAL

        all_reasons = rejection_reasons + data_issues

        purification_pct = 0.0
        purification_per_share = 0.0
        if is_halal:
            purification_pct = _percent(non_compliant_ratio)
            dividend_rate = to_float(financials.get("dividend_rate"))
            purification_per_share = round(dividend_rate * non_compliant_ratio, 4)

        return {
            "symbol": symbol,
            "agent": self.name,
            "asset_type": "equity",
            "is_halal": is_halal,
            "status": status,
            "standard_used": self.standard,
            "rejection_reasons": all_reasons,
            "ratios": ratios,
            "purification_pct": purification_pct,
            "purification_per_share": purification_per_share,
            "purification_basis": basis if is_halal else "n/a",
            "denominator_basis": denominator_basis,
            "sector": sector,
            "industry": industry,
            **self._quote_fields(financials),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _quote_fields(financials):
        return {
            "name": financials.get("name") or "",
            "price": to_float(financials.get("price")),
            "currency": financials.get("currency") or "",
            "dividend_rate": to_float(financials.get("dividend_rate")),
        }

    def _allowlisted_institution(self, symbol, financials):
        """Islamic banks / takaful operators named in the config allowlist.

        Their business is Shariah-governed by charter, so the conventional
        sector screen (which rejects every "Bank") and the leverage ratios
        (deposits look like debt) do not apply. Listing is a user decision
        and is labelled as such in the output.
        """
        return {
            "symbol": symbol,
            "agent": self.name,
            "asset_type": "equity",
            "is_halal": True,
            "status": STATUS_HALAL,
            "standard_used": "ISLAMIC_INSTITUTION_ALLOWLIST",
            "rejection_reasons": [],
            "compliance_note": "Islamic financial institution on your allowlist (sector and ratio screens not applied)",
            "ratios": {},
            "purification_pct": 0.0,
            "purification_per_share": 0.0,
            "purification_basis": "n/a",
            "denominator_basis": "n/a",
            "sector": financials.get("sector") or "Islamic Finance",
            "industry": financials.get("industry") or "Unknown",
            **self._quote_fields(financials),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _screen_business_activity(self, sector, industry):
        sector_label = (sector or "").lower()
        industry_label = (industry or "").lower()

        defence = ("aerospace & defense", "arms")

        for prohibited in PROHIBITED_SECTORS:
            if not self.exclude_defence and prohibited in defence:
                continue
            if prohibited in sector_label:
                return [f"Prohibited sector: {sector} (matched '{prohibited}')"]

        for prohibited in PROHIBITED_INDUSTRIES:
            if not self.exclude_defence and prohibited in defence:
                continue
            if prohibited in industry_label:
                return [f"Prohibited industry: {industry} (matched '{prohibited}')"]

        return []

    def _resolve_denominator(self, financials):
        """Pick the AAOIFI ratio denominator, falling back as documented."""
        market_cap = to_float(financials.get("market_cap"))
        total_assets = to_float(financials.get("total_assets"))

        if self.denominator_basis == "total_assets" and total_assets > 0:
            return total_assets, "total_assets"
        if market_cap > 0:
            # Documented fallback: a 24-36 month average market cap is not
            # available from Yahoo Finance, so current market cap is used.
            return market_cap, "market_cap"
        if total_assets > 0:
            return total_assets, "total_assets"
        return 0.0, "unavailable"

    def _resolve_non_compliant_ratio(self, financials):
        """Return (non_compliant_revenue_ratio, basis).

        Yahoo Finance exposes no breakdown of impermissible revenue, so an
        explicit override is used when supplied and a documented estimate is
        used otherwise. The basis label keeps the output honest.
        """
        if financials.get("non_compliant_revenue_ratio") is not None:
            return to_float(financials["non_compliant_revenue_ratio"]), "supplied"
        return to_float(self.default_non_compliant_revenue_ratio), "estimate"

    # -- spot crypto ------------------------------------------------------

    def _analyze_crypto(self, symbol):
        pair = normalise_crypto_symbol(symbol) or symbol.upper()

        allowed = {c.upper() for c in self.crypto_registry.get("allowed_spot_cryptos", [])}
        denylisted = {c.upper() for c in self.crypto_registry.get("denylisted_symbols", [])}

        rejection_reasons = []
        if pair in denylisted:
            rejection_reasons.append(
                f"Spot crypto {pair} is denied by the Halal registry "
                f"(see denylisted_symbols in halal_crypto_registry.json)"
            )
        elif pair not in allowed:
            rejection_reasons.append(
                f"Spot crypto {pair} is not in the approved Halal spot registry"
            )

        is_halal = not rejection_reasons

        return {
            "symbol": pair,
            "agent": self.name,
            "asset_type": "crypto",
            "is_halal": is_halal,
            "status": STATUS_HALAL if is_halal else STATUS_HARAM,
            "standard_used": "SPOT_UTILITY_REGISTRY",
            "rejection_reasons": rejection_reasons,
            "ratios": {},
            "purification_pct": 0.0,
            "purification_per_share": 0.0,
            "purification_basis": "n/a",
            "denominator_basis": "n/a",
            "sector": "Cryptocurrency",
            "industry": "Spot Utility / Store of Value",
            "name": pair,
            "price": 0.0,  # filled by the pipeline from the price agents
            "currency": "USD",
            "dividend_rate": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
