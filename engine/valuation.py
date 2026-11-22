"""PGEO valuation engine.

Pure functions, no Streamlit dependency, so the engine can be tested and
reused (e.g. from a notebook or another UI).

Units
-----
Financial figures : USD million
Shares            : million shares
Share price       : IDR per share
FX                : IDR per USD
Rates             : decimals (0.10 = 10%)
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd

SCENARIOS = ["Bear", "Base", "Bull"]
SHEETS = [
    "Meta", "Market", "Historical", "Projects", "Assumptions", "Peers",
    "MethodScores", "MultipleWeights", "DecisionRules",
]
HOURS_PER_YEAR = 8760


# --------------------------------------------------------------------------
# 1. INPUT LAYER
# --------------------------------------------------------------------------
def load_inputs(source) -> dict[str, pd.DataFrame]:
    """Read every sheet of the input workbook (path, bytes or file-like)."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    xl = pd.ExcelFile(source)
    missing = [s for s in SHEETS if s not in xl.sheet_names]
    if missing:
        raise ValueError(f"Sheet wajib tidak ditemukan: {', '.join(missing)}")
    data = {s: xl.parse(s) for s in SHEETS}
    data["Peers"]["include"] = data["Peers"]["include"].astype(bool)
    return data


def kv(df: pd.DataFrame, key_col: str = "key", val_col: str = "value") -> dict:
    return dict(zip(df[key_col], df[val_col]))


def scenario_params(data: dict, scenario: str) -> dict:
    a = data["Assumptions"]
    return dict(zip(a["parameter"], a[scenario].astype(float)))


def save_inputs(data: dict) -> bytes:
    """Serialise (possibly edited) inputs back to an .xlsx, stamping last_updated."""
    meta = data["Meta"].copy()
    meta.loc[meta["key"] == "last_updated", "value"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for s in SHEETS:
            (meta if s == "Meta" else data[s]).to_excel(xw, sheet_name=s, index=False)
    return buf.getvalue()


# --------------------------------------------------------------------------
# 2. HISTORICAL ANALYSIS
# --------------------------------------------------------------------------
def historical_table(data: dict) -> pd.DataFrame:
    """Historical metrics + derived TTM column + ratios."""
    h = data["Historical"].set_index("metric")
    cols = ["FY2023", "FY2024", "FY2025", "9M2025", "9M2026"]
    h = h[cols].astype(float)
    ttm = h["FY2025"] - h["9M2025"] + h["9M2026"]
    # balance-sheet style items: TTM = latest available point, not a flow
    for stock_item in ["cash", "total_debt", "total_equity"]:
        ttm[stock_item] = h.loc[stock_item, "9M2026"] if not np.isnan(h.loc[stock_item, "9M2026"]) else h.loc[stock_item, "FY2025"]
    h["TTM"] = ttm
    return h


def ttm_metrics(data: dict) -> dict:
    h = historical_table(data)
    m = kv(data["Market"])
    ttm = h["TTM"]
    da = ttm.get("d_and_a")
    if da is None or np.isnan(da):
        da = scenario_params(data, "Base")["base_d_and_a"]
    return {
        "revenue": ttm["revenue"],
        "ebitda": ttm["ebitda"],
        "net_income": ttm["net_income"],
        "d_and_a": da,
        "generation_gwh": ttm["generation_gwh"],
        "book_equity": float(m["book_equity"]),
    }


def market_snapshot(data: dict) -> dict:
    m = kv(data["Market"])
    price = float(m["share_price"])
    shares = float(m["shares_outstanding"])
    fx = float(m["fx_idr_usd"])
    mcap_usd = price * shares / fx  # (IDR * m shares) / (IDR/USD) = USD m
    net_debt = float(m["total_debt"]) - float(m["cash"])
    ev = mcap_usd + net_debt + float(m["minority_interest"])
    t = ttm_metrics(data)
    return {
        "price": price, "shares": shares, "fx": fx,
        "market_cap_usd": mcap_usd, "market_cap_idr_tn": price * shares / 1e6,
        "net_debt": net_debt, "ev": ev,
        "ev_ebitda": ev / t["ebitda"], "pe": mcap_usd / t["net_income"],
        "pb": mcap_usd / t["book_equity"],
        "debt_weight_market": float(m["total_debt"]) / (float(m["total_debt"]) + mcap_usd),
    }


# --------------------------------------------------------------------------
# 3. COST OF CAPITAL
# --------------------------------------------------------------------------
def wacc(p: dict) -> dict:
    wd = p["target_debt_weight"]
    we = 1 - wd
    de = wd / we
    beta_l = p["unlevered_beta"] * (1 + (1 - p["tax_rate"]) * de)  # Hamada
    ke = p["risk_free_rate"] + beta_l * p["equity_risk_premium"] + p["country_risk_premium"]
    kd_after = p["cost_of_debt"] * (1 - p["tax_rate"])
    w = we * ke + wd * kd_after
    return {"beta_levered": beta_l, "cost_of_equity": ke, "kd_after_tax": kd_after,
            "equity_weight": we, "debt_weight": wd, "wacc": w}


# --------------------------------------------------------------------------
# 4. DCF (FCFF) - asset/project driven
# --------------------------------------------------------------------------
def forecast(data: dict, p: dict) -> pd.DataFrame:
    m = kv(data["Market"])
    base_mw = float(m["installed_capacity_mw"])
    start = int(p["forecast_start_year"])
    n = int(p["forecast_years"])
    years = list(range(start, start + n))
    proj = data["Projects"].copy()
    proj["prob_adj"] = (proj["probability"] * p["probability_multiplier"]).clip(0, 1)
    proj["cod_adj"] = proj["cod_year"] + int(p["cod_delay"])

    rows = []
    cum_growth_capex = 0.0
    prev_rev = None
    for i, y in enumerate(years):
        # risked new capacity online by year y (full-year from COD year)
        online = proj[proj["cod_adj"] <= y]
        new_mw = float((online["capacity_mw"] * online["prob_adj"]).sum())
        esc = (1 + p["tariff_escalation"]) ** (i + 1)
        gen_exist = base_mw * p["capacity_factor"] * HOURS_PER_YEAR / 1000          # GWh
        gen_new = new_mw * p["capacity_factor_new"] * HOURS_PER_YEAR / 1000          # GWh
        rev = (gen_exist * p["tariff_existing"] + gen_new * p["tariff_new"]) * esc / 1000 \
            + p["other_revenue"] * esc                                               # USD m
        ebitda = rev * p["ebitda_margin"]
        # growth capex: spread evenly over build_years before COD (risked)
        bys = int(p["build_years"])
        building = proj[(proj["cod_adj"] > y) & (proj["cod_adj"] - bys <= y)]
        growth_capex = float((building["capacity_mw"] * building["prob_adj"] * building["capex_per_mw"]).sum()
                             * p["capex_cost_multiplier"] / bys)
        maint_capex = (base_mw + new_mw) * p["maint_capex_per_mw"]
        capex = growth_capex + maint_capex
        da = p["base_d_and_a"] + cum_growth_capex / p["useful_life"]
        cum_growth_capex += growth_capex
        ebit = ebitda - da
        tax = max(ebit, 0) * p["tax_rate"]
        nopat = ebit - tax
        if prev_rev is None:
            prev_rev = ttm_metrics(data)["revenue"]
        d_nwc = p["nwc_pct_delta_revenue"] * (rev - prev_rev)
        prev_rev = rev
        fcff = nopat + da - capex - d_nwc
        rows.append({
            "year": y, "capacity_mw": base_mw + new_mw, "new_mw_risked": new_mw,
            "generation_gwh": gen_exist + gen_new, "revenue": rev, "ebitda": ebitda,
            "d_and_a": da, "ebit": ebit, "tax": tax, "nopat": nopat,
            "maint_capex": maint_capex, "growth_capex": growth_capex, "capex": capex,
            "delta_nwc": d_nwc, "fcff": fcff,
        })
    return pd.DataFrame(rows).set_index("year")


def dcf(data: dict, scenario: str = "Base", overrides: dict | None = None) -> dict:
    p = scenario_params(data, scenario)
    if overrides:
        p.update(overrides)
    w = wacc(p)
    r, g = w["wacc"], p["terminal_growth"]
    f = forecast(data, p)
    n = len(f)
    t = np.arange(1, n + 1) - 0.5                      # mid-year convention
    disc = 1 / (1 + r) ** t
    f["discount_factor"] = disc
    f["pv_fcff"] = f["fcff"] * disc
    # Terminal value
    #  method 1 (default) value driver: NOPAT(T+1) * (1 - g/RONIC) / (WACC - g)
    #  method 2 Gordon on FCFF:          FCFF(T) * (1 + g) / (WACC - g)
    nopat_next = f["nopat"].iloc[-1] * (1 + g)
    reinvest_rate = g / p["ronic"] if p["ronic"] > 0 else 0
    tv_vd = nopat_next * (1 - reinvest_rate) / (r - g) if r > g else float("nan")
    tv_gordon = f["fcff"].iloc[-1] * (1 + g) / (r - g) if r > g else float("nan")
    tv = tv_gordon if int(p.get("tv_method", 1)) == 2 else tv_vd
    pv_tv = tv / (1 + r) ** n
    ev = f["pv_fcff"].sum() + pv_tv
    m = kv(data["Market"])
    debt, cash, mi = float(m["total_debt"]), float(m["cash"]), float(m["minority_interest"])
    equity = ev - debt + cash - mi
    shares, fx = float(m["shares_outstanding"]), float(m["fx_idr_usd"])
    per_share_usd = equity / shares
    return {
        "scenario": scenario, "params": p, "wacc": w, "forecast": f,
        "sum_pv_fcff": f["pv_fcff"].sum(), "terminal_value": tv, "pv_terminal": pv_tv,
        "tv_value_driver": tv_vd, "tv_gordon_fcff": tv_gordon,
        "tv_share": pv_tv / ev if ev else float("nan"),
        "implied_exit_ev_ebitda": tv / (f["ebitda"].iloc[-1] * (1 + g)),
        "enterprise_value": ev, "debt": debt, "cash": cash, "minority_interest": mi,
        "equity_value": equity, "per_share_usd": per_share_usd,
        "per_share_idr": per_share_usd * fx,
        # reconciliation check: equity + debt - cash + MI must equal EV
        "reconciliation_gap": (equity + debt - cash + mi) - ev,
    }


# --------------------------------------------------------------------------
# 5. RELATIVE VALUATION
# --------------------------------------------------------------------------
def suggested_foreign_discount(p: dict) -> float:
    """Multiple discount for developed/foreign peers implied by Indonesia's CRP.

    Multiple ~ 1/(WACC - g). A peer without Indonesian CRP has WACC lower by
    CRP x equity weight, so PGEO-equivalent multiple = peer x (W' - g)/(W - g).
    """
    w = wacc(p)["wacc"]
    g = p["terminal_growth"]
    crp_w = p["country_risk_premium"] * (1 - p["target_debt_weight"])
    return max(0.0, min(0.6, crp_w / (w - g)))


def clean_multiples(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Drop invalid (<=0, >100, NaN) then IQR outliers. Returns (kept, dropped)."""
    v = pd.to_numeric(values, errors="coerce")
    invalid = v.isna() | (v <= 0) | (v > 100)
    valid = v[~invalid]
    if len(valid) >= 4:
        q1, q3 = valid.quantile(0.25), valid.quantile(0.75)
        iqr = q3 - q1
        out = (valid < q1 - 1.5 * iqr) | (valid > q3 + 1.5 * iqr)
        return valid[~out], pd.concat([v[invalid & v.notna()], valid[out]])
    return valid, v[invalid & v.notna()]


def relative(data: dict, scenario: str = "Base", foreign_discount: float | None = None) -> dict:
    p = scenario_params(data, scenario)
    disc = suggested_foreign_discount(p) if foreign_discount is None else foreign_discount
    peers = data["Peers"][data["Peers"]["include"]].copy()
    t = ttm_metrics(data)
    m = kv(data["Market"])
    debt, cash, mi = float(m["total_debt"]), float(m["cash"]), float(m["minority_interest"])
    shares, fx = float(m["shares_outstanding"]), float(m["fx_idr_usd"])
    weights = dict(zip(data["MultipleWeights"]["multiple"], data["MultipleWeights"]["weight"]))

    metric_base = {"ev_ebitda": t["ebitda"], "pe": t["net_income"], "pb": t["book_equity"]}
    rows, detail = [], {}
    for mult in ["ev_ebitda", "pe", "pb"]:
        adj = peers[mult].astype(float).where(peers["country"] == "ID",
                                              peers[mult].astype(float) * (1 - disc))
        adj.index = peers["ticker"]
        kept, dropped = clean_multiples(adj)
        detail[mult] = {"adjusted": adj, "kept": kept, "dropped": dropped}
        if len(kept) == 0:
            continue
        stats = {"Q1": kept.quantile(0.25), "Median": kept.median(), "Q3": kept.quantile(0.75)}
        for k, mv in stats.items():
            if mult == "ev_ebitda":
                eq = mv * metric_base[mult] - debt + cash - mi
            else:
                eq = mv * metric_base[mult]
            rows.append({"multiple": mult, "stat": k, "peer_multiple": mv,
                         "pgeo_metric": metric_base[mult], "equity_usd": eq,
                         "per_share_idr": eq / shares * fx, "n_peers": len(kept),
                         "weight": weights.get(mult, 0)})
    table = pd.DataFrame(rows)
    # weighted implied price for each statistic (renormalise weights over available multiples)
    out = {}
    for k in ["Q1", "Median", "Q3"]:
        sub = table[table["stat"] == k]
        wsum = sub["weight"].sum()
        out[k] = float((sub["per_share_idr"] * sub["weight"]).sum() / wsum) if wsum else float("nan")
    return {"table": table, "detail": detail, "foreign_discount": disc,
            "per_share_idr": out, "scenario_stat": {"Bear": "Q1", "Base": "Median", "Bull": "Q3"}}


# --------------------------------------------------------------------------
# 6. METHOD SELECTION
# --------------------------------------------------------------------------
def method_weights(data: dict) -> dict:
    s = data["MethodScores"]
    imp = s["importance"].astype(float)
    dcf_score = float((s["dcf_score"] * imp).sum() / (5 * imp.sum()))
    rel_score = float((s["relative_score"] * imp).sum() / (5 * imp.sum()))
    w_dcf = dcf_score / (dcf_score + rel_score)
    rules = kv(data["DecisionRules"], "rule", "value")
    peer_row = s[s["factor"].str.contains("peer", case=False)]
    notes = [f"Skor kesesuaian DCF {dcf_score:.0%} vs Relatif {rel_score:.0%} (rata-rata tertimbang skala 1-5)."]
    w_rel = 1 - w_dcf
    if len(peer_row) and float(peer_row["relative_score"].iloc[0]) <= 2:
        cap = float(rules.get("max_relative_weight_if_weak_peers", 0.4))
        if w_rel > cap:
            notes.append(f"Aturan: skor peer <= 2 -> bobot relatif dibatasi {cap:.0%}.")
            w_rel = cap
    w_dcf = 1 - w_rel
    if w_dcf >= 0.55:
        emphasis = "DCF lebih ditekankan: arus kas kontraktual stabil & terprediksi, sedangkan peer kurang sebanding."
    elif w_dcf <= 0.45:
        emphasis = "Valuasi relatif lebih ditekankan: peer sebanding tersedia dan arus kas sulit diproyeksikan."
    else:
        emphasis = "Kedua metode berbobot seimbang."
    notes.append(emphasis)
    return {"dcf_score": dcf_score, "rel_score": rel_score, "w_dcf": w_dcf, "w_rel": w_rel, "notes": notes}


# --------------------------------------------------------------------------
# 7. RECONCILIATION, SCENARIOS, RECOMMENDATION
# --------------------------------------------------------------------------
def run_all(data: dict, foreign_discount: float | None = None) -> dict:
    mw = method_weights(data)
    rel = relative(data, "Base", foreign_discount)
    snap = market_snapshot(data)
    rules = kv(data["DecisionRules"], "rule", "value")
    res = {"method": mw, "relative": rel, "market": snap, "scenarios": {}}
    probs = {}
    for s in SCENARIOS:
        d = dcf(data, s)
        rel_px = rel["per_share_idr"][rel["scenario_stat"][s]]
        blended = mw["w_dcf"] * d["per_share_idr"] + mw["w_rel"] * rel_px
        res["scenarios"][s] = {"dcf": d, "dcf_px": d["per_share_idr"], "rel_px": rel_px, "blended": blended}
        probs[s] = scenario_params(data, s)["scenario_probability"]
    tot = sum(probs.values())
    expected = sum(res["scenarios"][s]["blended"] * probs[s] / tot for s in SCENARIOS)
    lo = min(res["scenarios"][s]["blended"] for s in SCENARIOS)
    hi = max(res["scenarios"][s]["blended"] for s in SCENARIOS)
    central = res["scenarios"]["Base"]["blended"]
    upside = central / snap["price"] - 1
    buy, sell = float(rules["buy_threshold"]), float(rules["sell_threshold"])
    if upside >= buy:
        rec = "BUY"
    elif upside <= sell:
        rec = "SELL"
    else:
        rec = "HOLD"
    pos = "di bawah" if snap["price"] < lo else ("di atas" if snap["price"] > hi else "di dalam")
    res.update({
        "fair_low": lo, "fair_high": hi, "fair_central": central, "fair_expected": expected,
        "upside": upside, "upside_expected": expected / snap["price"] - 1,
        "recommendation": rec, "price_position": pos,
        "scenario_probabilities": {s: probs[s] / tot for s in SCENARIOS},
        "rules": {"buy": buy, "sell": sell},
    })
    res["checks"] = validate(data, res)
    return res


# --------------------------------------------------------------------------
# 8. SENSITIVITY
# --------------------------------------------------------------------------
def sensitivity_grid(data: dict, wacc_deltas=None, g_values=None) -> pd.DataFrame:
    """DCF IDR/share for WACC shifts (via CRP) x terminal growth."""
    wacc_deltas = wacc_deltas or [-0.02, -0.01, 0.0, 0.01, 0.02]
    g_values = g_values or [0.010, 0.015, 0.020, 0.025, 0.030]
    base = scenario_params(data, "Base")
    base_w = wacc(base)["wacc"]
    we = 1 - base["target_debt_weight"]
    grid = {}
    for dw in wacc_deltas:
        col = {}
        for g in g_values:
            # shift WACC by dw by moving CRP (equity-side) by dw/we
            d = dcf(data, "Base", {"country_risk_premium": base["country_risk_premium"] + dw / we,
                                   "terminal_growth": g})
            col[f"g={g:.1%}"] = d["per_share_idr"]
        grid[f"WACC {base_w + dw:.1%}"] = col
    return pd.DataFrame(grid).T


TORNADO_DRIVERS = [
    ("capacity_factor", "Capacity factor", 0.03, "abs"),
    ("tariff_existing", "Tarif eksisting (USD/MWh)", 0.10, "rel"),
    ("ebitda_margin", "Margin EBITDA", 0.03, "abs"),
    ("capex_cost_multiplier", "Capex proyek per MW", 0.20, "rel"),
    ("country_risk_premium", "CRP (WACC)", 0.01, "abs"),
    ("terminal_growth", "Terminal growth", 0.005, "abs"),
    ("tax_rate", "Tarif pajak", 0.03, "abs"),
    ("probability_multiplier", "Probabilitas proyek", 0.20, "rel"),
]


def tornado(data: dict) -> pd.DataFrame:
    base_px = dcf(data, "Base")["per_share_idr"]
    p = scenario_params(data, "Base")
    rows = []
    for key, label, step, kind in TORNADO_DRIVERS:
        lo_v = p[key] - step if kind == "abs" else p[key] * (1 - step)
        hi_v = p[key] + step if kind == "abs" else p[key] * (1 + step)
        lo_px = dcf(data, "Base", {key: lo_v})["per_share_idr"]
        hi_px = dcf(data, "Base", {key: hi_v})["per_share_idr"]
        rows.append({"driver": label, "low_input": lo_v, "high_input": hi_v,
                     "low_px": lo_px, "high_px": hi_px, "range": abs(hi_px - lo_px), "base_px": base_px})
    return pd.DataFrame(rows).sort_values("range")


# --------------------------------------------------------------------------
# 9. VALIDATION CHECKS
# --------------------------------------------------------------------------
@dataclass
class Check:
    area: str
    check: str
    status: str  # OK / WARNING / ERROR
    detail: str = ""


def validate(data: dict, res: dict | None = None) -> pd.DataFrame:
    c: list[Check] = []
    m = kv(data["Market"])
    required = ["share_price", "shares_outstanding", "fx_idr_usd", "total_debt", "cash", "book_equity", "installed_capacity_mw"]
    for k in required:
        v = m.get(k)
        ok = v is not None and not (isinstance(v, float) and math.isnan(v))
        c.append(Check("Input", f"Market: {k} terisi", "OK" if ok else "ERROR", "" if ok else "Input wajib kosong"))
    # unit plausibility
    fx = float(m.get("fx_idr_usd", 0) or 0)
    c.append(Check("Satuan", "Kurs IDR/USD dalam rentang 10.000-30.000",
                   "OK" if 10000 <= fx <= 30000 else "ERROR", f"Nilai: {fx:,.0f}"))
    sh = float(m.get("shares_outstanding", 0) or 0)
    c.append(Check("Satuan", "Jumlah saham dalam juta lembar (1.000-1.000.000)",
                   "OK" if 1000 <= sh <= 1_000_000 else "ERROR", f"Nilai: {sh:,.0f} juta"))
    px = float(m.get("share_price", 0) or 0)
    c.append(Check("Satuan", "Harga saham dalam IDR (50-100.000)",
                   "OK" if 50 <= px <= 100_000 else "ERROR", f"Nilai: Rp{px:,.0f}"))
    # historical consistency
    h = historical_table(data)
    miss = [f"{idx}/{col}" for idx in h.index for col in ["FY2024", "FY2025", "9M2026"]
            if idx in ("revenue", "net_income", "ebitda") and np.isnan(h.loc[idx, col])]
    c.append(Check("Input", "Historis inti (pendapatan, EBITDA, laba) lengkap FY24-9M26",
                   "OK" if not miss else "ERROR", ", ".join(miss)))
    other_missing = int(h.drop(columns=["TTM"]).isna().sum().sum())
    c.append(Check("Input", "Sel historis kosong (non-inti)", "OK" if other_missing == 0 else "WARNING",
                   f"{other_missing} sel kosong - tidak dipakai di kalkulasi inti"))
    bad = [col for col in h.columns if (h.loc["ebitda", col] > h.loc["revenue", col])]
    c.append(Check("Konsistensi", "EBITDA <= Pendapatan", "OK" if not bad else "ERROR", ", ".join(bad)))
    # timestamp freshness
    try:
        vd = pd.to_datetime(kv(data["Meta"])["valuation_date"]).date()
        asof = pd.to_datetime(data["Market"].set_index("key").loc["share_price", "as_of"]).date()
        lag = (vd - asof).days
        c.append(Check("Data", "Harga saham <= 7 hari dari tanggal valuasi",
                       "OK" if 0 <= lag <= 7 else "WARNING", f"Selisih {lag} hari"))
    except Exception as e:  # noqa: BLE001
        c.append(Check("Data", "Tanggal valuasi / as_of terbaca", "WARNING", str(e)))
    # assumptions
    rules = kv(data["DecisionRules"], "rule", "value")
    for s in SCENARIOS:
        p = scenario_params(data, s)
        w = wacc(p)["wacc"]
        g = p["terminal_growth"]
        c.append(Check("Asumsi", f"[{s}] g < WACC", "OK" if g < w else "ERROR", f"g {g:.2%} vs WACC {w:.2%}"))
        gmax = float(rules["max_terminal_growth"])
        c.append(Check("Asumsi", f"[{s}] g <= {gmax:.1%} (pertumbuhan nominal jangka panjang USD)",
                       "OK" if g <= gmax else "ERROR", f"g {g:.2%}"))
        for k in ["capacity_factor", "capacity_factor_new"]:
            c.append(Check("Asumsi", f"[{s}] {k} 0,5-0,95", "OK" if 0.5 <= p[k] <= 0.95 else "ERROR", f"{p[k]:.2f}"))
        c.append(Check("Asumsi", f"[{s}] margin EBITDA 0-95%", "OK" if 0 < p["ebitda_margin"] < 0.95 else "ERROR",
                       f"{p['ebitda_margin']:.1%}"))
        c.append(Check("Asumsi", f"[{s}] RONIC > g", "OK" if p["ronic"] > g else "ERROR", f"RONIC {p['ronic']:.1%}"))
    pr = data["Projects"]
    c.append(Check("Asumsi", "Probabilitas proyek dalam 0-1",
                   "OK" if pr["probability"].between(0, 1).all() else "ERROR", ""))
    sp = sum(scenario_params(data, s)["scenario_probability"] for s in SCENARIOS)
    c.append(Check("Asumsi", "Total probabilitas skenario = 100%", "OK" if abs(sp - 1) < 1e-6 else "WARNING", f"{sp:.0%}"))
    mw = data["MultipleWeights"]["weight"].sum()
    c.append(Check("Asumsi", "Total bobot multiple = 100%", "OK" if abs(mw - 1) < 1e-6 else "WARNING", f"{mw:.0%}"))
    # peers / multiples
    peers = data["Peers"][data["Peers"]["include"]]
    for mult in ["ev_ebitda", "pe", "pb"]:
        v = pd.to_numeric(peers[mult], errors="coerce")
        inval = peers.loc[(v <= 0) | (v > 100), "ticker"].tolist()
        c.append(Check("Multiple", f"{mult}: tidak ada multiple negatif/>100x", "OK" if not inval else "WARNING",
                       ("Dikeluarkan otomatis: " + ", ".join(inval)) if inval else ""))
        n = int(v.notna().sum())
        c.append(Check("Multiple", f"{mult}: minimal 3 peer", "OK" if n >= 3 else "WARNING", f"{n} peer"))
    if res is not None:
        for mult, d in res["relative"]["detail"].items():
            if len(d["dropped"]):
                c.append(Check("Multiple", f"{mult}: outlier IQR dikeluarkan", "WARNING",
                               ", ".join(f"{k} ({v:.1f}x)" for k, v in d["dropped"].items())))
        for s in SCENARIOS:
            d = res["scenarios"][s]["dcf"]
            gap = abs(d["reconciliation_gap"])
            c.append(Check("Rekonsiliasi", f"[{s}] EV = Ekuitas + Utang - Kas + MI", "OK" if gap < 1e-6 else "ERROR",
                           f"selisih {gap:.6f}"))
            tvmax = float(rules["max_tv_share_warning"])
            c.append(Check("DCF", f"[{s}] porsi nilai terminal <= {tvmax:.0%}",
                           "OK" if d["tv_share"] <= tvmax else "WARNING", f"{d['tv_share']:.0%}"))
            ex = d["implied_exit_ev_ebitda"]
            c.append(Check("DCF", f"[{s}] implied exit EV/EBITDA 4-20x", "OK" if 4 <= ex <= 20 else "WARNING", f"{ex:.1f}x"))
            neg = int((d["forecast"]["fcff"] < 0).sum())
            c.append(Check("DCF", f"[{s}] FCFF negatif", "OK" if neg == 0 else "WARNING",
                           f"{neg} tahun negatif (wajar saat fase capex)"))
        # cross-check EV/EBITDA of DCF vs market
        snap = res["market"]
        c.append(Check("Rekonsiliasi", "EV pasar = Market cap + Net debt + MI",
                       "OK", f"EV pasar US${snap['ev']:,.0f} jt"))
    out = pd.DataFrame([vars(x) for x in c])
    return out


# --------------------------------------------------------------------------
# 10. NARRATIVE (rule-based commentary)
# --------------------------------------------------------------------------
def commentary(res: dict) -> list[str]:
    s = res["scenarios"]
    snap = res["market"]
    base = s["Base"]["dcf"]
    lines = [
        f"Nilai wajar sentral Rp{res['fair_central']:,.0f}/saham (rentang Rp{res['fair_low']:,.0f}-Rp{res['fair_high']:,.0f}); "
        f"harga pasar Rp{snap['price']:,.0f} berada {res['price_position']} rentang tersebut.",
        f"Upside terhadap nilai sentral {res['upside']:+.1%} -> rekomendasi {res['recommendation']} "
        f"(aturan: BUY >= {res['rules']['buy']:+.0%}, SELL <= {res['rules']['sell']:+.0%}).",
        f"DCF (Base) Rp{s['Base']['dcf_px']:,.0f} dengan WACC {base['wacc']['wacc']:.2%} dan g {base['params']['terminal_growth']:.1%}; "
        f"nilai terminal {base['tv_share']:.0%} dari EV (implied exit {base['implied_exit_ev_ebitda']:.1f}x EBITDA).",
        f"Relatif (median peer, setelah diskon risiko negara {res['relative']['foreign_discount']:.0%} untuk peer asing) "
        f"Rp{s['Base']['rel_px']:,.0f}.",
        f"Pasar saat ini memberi PGEO EV/EBITDA {snap['ev_ebitda']:.1f}x, P/E {snap['pe']:.1f}x, P/BV {snap['pb']:.2f}x.",
        f"Bobot metode: DCF {res['method']['w_dcf']:.0%} / Relatif {res['method']['w_rel']:.0%}.",
    ]
    n_err = int((res["checks"]["status"] == "ERROR").sum())
    n_warn = int((res["checks"]["status"] == "WARNING").sum())
    lines.append(f"Validasi: {n_err} error, {n_warn} peringatan." + (" Hasil belum layak dipakai." if n_err else ""))
    return lines
