"""Independent re-computation tests for the valuation engine.

The DCF is recomputed here with plain arithmetic (no shared code with the
engine except input loading) to prove the engine's numbers.
Run:  python -m pytest -q   (or: python tests/test_engine.py)
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import valuation as v  # noqa: E402

DATA = v.load_inputs(ROOT / "data" / "pgeo_input.xlsx")


def manual_dcf(data, scenario="Base"):
    a = data["Assumptions"].set_index("parameter")[scenario].astype(float).to_dict()
    mk = dict(zip(data["Market"]["key"], data["Market"]["value"]))
    hist = data["Historical"].set_index("metric")
    ttm_rev = hist.loc["revenue", "FY2025"] - hist.loc["revenue", "9M2025"] + hist.loc["revenue", "9M2026"]

    # WACC by hand
    wd = a["target_debt_weight"]; we = 1 - wd
    beta = a["unlevered_beta"] * (1 + (1 - a["tax_rate"]) * wd / we)
    ke = a["risk_free_rate"] + beta * a["equity_risk_premium"] + a["country_risk_premium"]
    wacc = we * ke + wd * a["cost_of_debt"] * (1 - a["tax_rate"])
    g = a["terminal_growth"]

    projects = data["Projects"].to_dict("records")
    base_mw = float(mk["installed_capacity_mw"])
    pv, cum, prev = 0.0, 0.0, ttm_rev
    nopat = fcff = None
    for i in range(int(a["forecast_years"])):
        y = int(a["forecast_start_year"]) + i
        new_mw, gcap = 0.0, 0.0
        for pr in projects:
            prob = min(1.0, max(0.0, pr["probability"] * a["probability_multiplier"]))
            cod = pr["cod_year"] + int(a["cod_delay"])
            if cod <= y:
                new_mw += pr["capacity_mw"] * prob
            if cod - int(a["build_years"]) <= y < cod:
                gcap += pr["capacity_mw"] * prob * pr["capex_per_mw"] * a["capex_cost_multiplier"] / a["build_years"]
        esc = (1 + a["tariff_escalation"]) ** (i + 1)
        rev = (base_mw * a["capacity_factor"] * 8.76 * a["tariff_existing"]
               + new_mw * a["capacity_factor_new"] * 8.76 * a["tariff_new"]) * esc / 1000 + a["other_revenue"] * esc
        ebitda = rev * a["ebitda_margin"]
        da = a["base_d_and_a"] + cum / a["useful_life"]
        cum += gcap
        ebit = ebitda - da
        nopat = ebit - max(ebit, 0) * a["tax_rate"]
        capex = gcap + (base_mw + new_mw) * a["maint_capex_per_mw"]
        fcff = nopat + da - capex - a["nwc_pct_delta_revenue"] * (rev - prev)
        prev = rev
        pv += fcff / (1 + wacc) ** (i + 0.5)
    n = int(a["forecast_years"])
    if int(a["tv_method"]) == 2:
        tv = fcff * (1 + g) / (wacc - g)
    else:
        tv = nopat * (1 + g) * (1 - g / a["ronic"]) / (wacc - g)
    ev = pv + tv / (1 + wacc) ** n
    eq = ev - mk["total_debt"] + mk["cash"] - mk["minority_interest"]
    return wacc, ev, eq / mk["shares_outstanding"] * mk["fx_idr_usd"]


def test_dcf_matches_manual_all_scenarios():
    for s in v.SCENARIOS:
        w, ev, px = manual_dcf(DATA, s)
        r = v.dcf(DATA, s)
        assert math.isclose(r["wacc"]["wacc"], w, rel_tol=1e-12), s
        assert math.isclose(r["enterprise_value"], ev, rel_tol=1e-9), s
        assert math.isclose(r["per_share_idr"], px, rel_tol=1e-9), s


def test_reconciliation_and_monotonicity():
    base = v.dcf(DATA, "Base")
    assert abs(base["reconciliation_gap"]) < 1e-9
    hi = v.dcf(DATA, "Base", {"country_risk_premium": 0.035})
    assert hi["per_share_idr"] < base["per_share_idr"], "higher WACC must lower value"
    up = v.dcf(DATA, "Base", {"tariff_existing": 90})
    assert up["per_share_idr"] > base["per_share_idr"], "higher tariff must raise value"


def test_scenario_ordering_and_recommendation():
    r = v.run_all(DATA)
    s = r["scenarios"]
    assert s["Bear"]["blended"] < s["Base"]["blended"] < s["Bull"]["blended"]
    assert r["fair_low"] <= r["fair_central"] <= r["fair_high"]
    up = r["upside"]
    exp = "BUY" if up >= 0.15 else ("SELL" if up <= -0.10 else "HOLD")
    assert r["recommendation"] == exp


def test_relative_outlier_and_invalid_filter():
    kept, dropped = v.clean_multiples(v.pd.Series([10, 11, 12, 13, 99, -5]))
    assert 99 in dropped.values and -5 in dropped.values
    assert set(kept.values) == {10, 11, 12, 13}


def test_validation_catches_bad_terminal_growth():
    bad = {k: df.copy() for k, df in DATA.items()}
    a = bad["Assumptions"]
    a.loc[a["parameter"] == "terminal_growth", "Base"] = 0.12
    chk = v.validate(bad)
    row = chk[chk["check"].str.contains(r"\[Base\] g < WACC", regex=True)]
    assert (row["status"] == "ERROR").all()


def test_market_multiples():
    m = v.market_snapshot(DATA)
    assert math.isclose(m["market_cap_usd"], 910 * 41900 / 18269, rel_tol=1e-12)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
    for s in v.SCENARIOS:
        w, ev, px = manual_dcf(DATA, s)
        print(f"{s}: manual WACC {w:.4%}  EV US${ev:,.1f} m  Rp{px:,.0f}/saham  | engine Rp{v.dcf(DATA, s)['per_share_idr']:,.0f}")
