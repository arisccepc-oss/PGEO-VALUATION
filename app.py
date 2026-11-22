"""PGEO Valuation Platform - Streamlit UI.

Run locally:  streamlit run app.py
Layers: data/pgeo_input.xlsx (inputs) -> engine/valuation.py (calculation)
        -> this file (interface) -> engine/report.py (exports)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import report, valuation as v

ROOT = Path(__file__).resolve().parent
DEFAULT_FILE = ROOT / "data" / "pgeo_input.xlsx"
EDITABLE = ["Meta", "Market", "Historical", "Projects", "Assumptions", "Peers",
            "MethodScores", "MultipleWeights", "DecisionRules"]

st.set_page_config(page_title="PGEO Valuation Platform", page_icon="🌋", layout="wide")

C_BEAR, C_BASE, C_BULL, C_MKT = "#b42318", "#1d4ed8", "#15803d", "#111827"


def rp(x: float) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"Rp{x:,.0f}".replace(",", ".")


def usd(x: float) -> str:
    return f"US${x:,.1f} jt"


# --------------------------------------------------------------------------
# STATE: base inputs (as loaded) + editor version (reset editors on reload)
# --------------------------------------------------------------------------
def load_base(source, label: str):
    st.session_state.base = v.load_inputs(source)
    st.session_state.source_label = label
    st.session_state.loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state.ver = st.session_state.get("ver", 0) + 1
    mk = v.kv(st.session_state.base["Market"])
    st.session_state.ov_price = float(mk["share_price"])
    st.session_state.ov_fx = float(mk["fx_idr_usd"])


if "base" not in st.session_state:
    load_base(DEFAULT_FILE, "Data default (pgeo_input.xlsx)")

# --------------------------------------------------------------------------
# SIDEBAR - data update workflow
# --------------------------------------------------------------------------
with st.sidebar:
    st.title("🌋 PGEO Valuation")
    st.caption("AI-Assisted Business Valuation Model - MM6026 SBM ITB")
    st.markdown("**1. Sumber data**")
    up = st.file_uploader("Upload file input (.xlsx)", type=["xlsx"],
                          help="Gunakan template dari tab Export -> 'Unduh file input'.")
    if up is not None and st.session_state.get("last_upload") != up.file_id:
        try:
            load_base(up.getvalue(), f"Upload: {up.name}")
            st.session_state.last_upload = up.file_id
            st.success("File dimuat. Semua valuasi dihitung ulang.")
        except Exception as e:  # noqa: BLE001
            st.error(f"Gagal membaca file: {e}")
    if st.button("↺ Kembali ke data default", width="stretch"):
        load_base(DEFAULT_FILE, "Data default (pgeo_input.xlsx)")
        st.rerun()
    st.caption(f"Aktif: {st.session_state.source_label}  \nDimuat: {st.session_state.loaded_at}")

    st.markdown("**2. Update cepat data pasar**")
    st.number_input("Harga saham (Rp)", min_value=0.0, step=5.0, key="ov_price")
    st.number_input("Kurs IDR/USD", min_value=0.0, step=10.0, key="ov_fx")
    if st.button("⟳ Ambil harga & kurs terbaru (Yahoo Finance)", width="stretch"):
        try:
            import yfinance as yf  # optional dependency
            px = yf.Ticker("PGEO.JK").history(period="5d")["Close"].dropna()
            fx = yf.Ticker("IDR=X").history(period="5d")["Close"].dropna()
            st.session_state.ov_price = float(px.iloc[-1])
            st.session_state.ov_fx = float(fx.iloc[-1])
            st.session_state.fetched = f"Yahoo Finance {px.index[-1]:%Y-%m-%d}"
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.warning(f"Koneksi data otomatis gagal ({e}). Isi manual di atas.")
    if st.session_state.get("fetched"):
        st.caption(f"Data pasar: {st.session_state.fetched}")

    st.markdown("**3. Relative valuation**")
    auto_disc = st.toggle("Diskon peer asing otomatis (berbasis CRP)", value=True)
    man_disc = st.slider("Diskon manual peer asing", 0.0, 0.6, 0.25, 0.05, disabled=auto_disc)

# --------------------------------------------------------------------------
# TABS (inputs rendered first in code so outputs always use current edits)
# --------------------------------------------------------------------------
tabs = st.tabs(["🎯 Dashboard", "📥 Data & Input", "⚙️ Asumsi & Proyek", "💰 DCF",
                "📊 Relatif", "🧭 Pemilihan Metode", "🎲 Skenario & Sensitivitas",
                "✅ Validasi", "📤 Export", "📘 Panduan & Metodologi"])
(t_dash, t_data, t_asm, t_dcf, t_rel, t_meth, t_scn, t_val, t_exp, t_help) = tabs
ver = st.session_state.ver
base = st.session_state.base
data: dict[str, pd.DataFrame] = {}


def editor(sheet: str, container, **kw) -> pd.DataFrame:
    with container:
        return st.data_editor(base[sheet], key=f"{sheet}_{ver}", width="stretch", **kw)


# ---- Data & Input -------------------------------------------------------
with t_data:
    st.subheader("Data input (bisa diedit langsung)")
    st.caption("Satuan: USD juta untuk angka keuangan, saham dalam juta lembar, harga dalam IDR. "
               "Kolom *source* & *as_of* wajib diisi saat memperbarui data.")
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown("**Meta**")
        data["Meta"] = editor("Meta", c1, hide_index=True, disabled=["key"])
    with c2:
        st.markdown("**Market**")
        data["Market"] = editor("Market", c2, hide_index=True, disabled=["key"])
    st.markdown("**Historical** (kolom TTM dihitung otomatis = FY2025 - 9M2025 + 9M2026)")
    data["Historical"] = editor("Historical", st.container(), hide_index=True, disabled=["metric"])

# ---- Assumptions & projects --------------------------------------------
with t_asm:
    st.subheader("Asumsi proyeksi & parameter valuasi (Bear / Base / Bull)")
    data["Assumptions"] = editor("Assumptions", st.container(), hide_index=True,
                                 disabled=["parameter", "unit", "description"], height=560)
    st.subheader("Pipeline proyek (driver pertumbuhan kapasitas)")
    st.caption("Kapasitas baru masuk penuh mulai tahun COD; capex disebar rata selama `build_years` sebelum COD; "
               "keduanya dikali probabilitas sukses (expected value).")
    data["Projects"] = editor("Projects", st.container(), hide_index=True, num_rows="dynamic")

# ---- Peers / method scores (editors live in their tabs) ------------------
with t_rel:
    st.subheader("Peer & multiple (centang `include` untuk dipakai)")
    data["Peers"] = editor("Peers", st.container(), hide_index=True, num_rows="dynamic")
    cw1, cw2 = st.columns(2)
    with cw1:
        st.markdown("**Bobot multiple**")
        data["MultipleWeights"] = editor("MultipleWeights", cw1, hide_index=True, disabled=["multiple"])
with t_meth:
    st.subheader("Aturan keputusan pemilihan metode")
    st.caption("Skor 1-5: seberapa cocok metode untuk faktor tersebut. Bobot metode = proporsi skor tertimbang; "
               "aturan tambahan di tabel DecisionRules.")
    data["MethodScores"] = editor("MethodScores", st.container(), hide_index=True, disabled=["factor"])
    data["DecisionRules"] = editor("DecisionRules", st.container(), hide_index=True, disabled=["rule"])

# apply sidebar market overrides
mk = data["Market"].copy()
mk.loc[mk["key"] == "share_price", "value"] = st.session_state.ov_price
mk.loc[mk["key"] == "fx_idr_usd", "value"] = st.session_state.ov_fx
data["Market"] = mk
data["Peers"]["include"] = data["Peers"]["include"].fillna(False).astype(bool)
for c in ["probability", "capacity_mw", "cod_year", "capex_per_mw"]:
    data["Projects"][c] = pd.to_numeric(data["Projects"][c], errors="coerce").fillna(0)

# --------------------------------------------------------------------------
# CALCULATION
# --------------------------------------------------------------------------
try:
    res = v.run_all(data, None if auto_disc else man_disc)
    sens = v.sensitivity_grid(data)
    torn = v.tornado(data)
    calc_error = None
except Exception as e:  # noqa: BLE001
    calc_error = e

if calc_error is not None:
    with t_dash:
        st.error(f"Perhitungan gagal: {calc_error}. Periksa input di tab Data/Asumsi.")
    st.stop()

snap = res["market"]
meta = v.kv(data["Meta"])
checks = res["checks"]
n_err = int((checks["status"] == "ERROR").sum())
n_warn = int((checks["status"] == "WARNING").sum())

# ---- Data tab: derived views --------------------------------------------
with t_data:
    h = v.historical_table(data)
    st.markdown("**Rasio historis**")
    ratios = pd.DataFrame({
        "Margin EBITDA": h.loc["ebitda"] / h.loc["revenue"],
        "Margin laba bersih": h.loc["net_income"] / h.loc["revenue"],
        "Tarif implied (USD/MWh)": (h.loc["revenue"] * 1000) / h.loc["generation_gwh"],
        "Capacity factor implied": h.loc["generation_gwh"] /
            (float(v.kv(data["Market"])["installed_capacity_mw"]) * 8.76 *
             pd.Series({"FY2023": 1, "FY2024": 1, "FY2025": 1, "9M2025": 0.75, "9M2026": 0.75, "TTM": 1})),
    }).T
    st.dataframe(ratios.style.format("{:.2f}", na_rep="-"), width="stretch")
    fig = go.Figure()
    cols = ["FY2023", "FY2024", "FY2025", "TTM"]
    for metric, name in [("revenue", "Pendapatan"), ("ebitda", "EBITDA"), ("net_income", "Laba bersih")]:
        fig.add_bar(x=cols, y=h.loc[metric, cols], name=name)
    fig.update_layout(height=320, barmode="group", yaxis_title="USD juta", margin=dict(t=30, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Data terakhir diperbarui: **{meta.get('last_updated')}** | Tanggal valuasi: **{meta.get('valuation_date')}**")

# ---- Assumptions: WACC breakdown ------------------------------------------
with t_asm:
    st.subheader("Biaya modal (WACC) per skenario")
    wrows = []
    for s in v.SCENARIOS:
        p = v.scenario_params(data, s)
        w = v.wacc(p)
        wrows.append({"Skenario": s, "Rf (UST10Y)": p["risk_free_rate"], "ERP": p["equity_risk_premium"],
                      "CRP": p["country_risk_premium"], "Beta unlevered": p["unlevered_beta"],
                      "Beta levered": w["beta_levered"], "Ke": w["cost_of_equity"], "Kd after-tax": w["kd_after_tax"],
                      "D/(D+E)": w["debt_weight"], "WACC": w["wacc"]})
    st.dataframe(pd.DataFrame(wrows).set_index("Skenario").style.format("{:.2%}").format(
        "{:.2f}", subset=["Beta unlevered", "Beta levered"]), width="stretch")
    st.caption("Ke = Rf + βL x ERP + CRP;  βL = βU x [1 + (1 - t) x D/E] (Hamada). Arus kas dalam USD sehingga Rf memakai "
               "US Treasury, risiko Indonesia masuk lewat CRP.")

# ---- Dashboard ---------------------------------------------------------------
with t_dash:
    st.title(f"{meta.get('company')} ({meta.get('ticker')})")
    st.caption(f"Tanggal valuasi {meta.get('valuation_date')} · data diperbarui {meta.get('last_updated')} · "
               f"dihitung {datetime.now():%Y-%m-%d %H:%M} · sumber: {st.session_state.source_label}")
    if n_err:
        st.error(f"⚠️ {n_err} pemeriksaan ERROR - lihat tab Validasi sebelum memakai hasil.")
    k = st.columns(6)
    k[0].metric("Harga pasar", rp(snap["price"]))
    k[1].metric("Nilai wajar sentral", rp(res["fair_central"]), f"{res['upside']:+.1%}")
    k[2].metric("Rentang nilai wajar", f"{rp(res['fair_low'])} – {rp(res['fair_high'])}")
    k[3].metric("Nilai harapan (prob.)", rp(res["fair_expected"]), f"{res['upside_expected']:+.1%}")
    color = {"BUY": "green", "HOLD": "orange", "SELL": "red"}[res["recommendation"]]
    k[4].markdown(f"**Rekomendasi**<br><span style='font-size:2rem;color:{color};font-weight:700'>"
                  f"{res['recommendation']}</span>", unsafe_allow_html=True)
    k[5].metric("Validasi", f"{n_err} error", f"{n_warn} peringatan", delta_color="off")

    # Football field
    s = res["scenarios"]
    rel_ps = res["relative"]["per_share_idr"]
    bars = [
        ("DCF (Bear–Bull)", s["Bear"]["dcf_px"], s["Bull"]["dcf_px"], s["Base"]["dcf_px"]),
        ("Relatif (Q1–Q3 peer)", rel_ps["Q1"], rel_ps["Q3"], rel_ps["Median"]),
    ]
    rt = res["relative"]["table"]
    names = {"ev_ebitda": "EV/EBITDA", "pe": "P/E", "pb": "P/BV"}
    for mult in ["ev_ebitda", "pe", "pb"]:
        sub = rt[rt["multiple"] == mult].set_index("stat")
        if len(sub):
            bars.append((f"  · {names[mult]}", sub.loc["Q1", "per_share_idr"], sub.loc["Q3", "per_share_idr"],
                         sub.loc["Median", "per_share_idr"]))
    bars.append((f"Blended ({res['method']['w_dcf']:.0%} DCF / {res['method']['w_rel']:.0%} Rel)",
                 res["fair_low"], res["fair_high"], res["fair_central"]))
    fig = go.Figure()
    for i, (lab, lo, hi, mid) in enumerate(bars):
        lo, hi = min(lo, hi), max(lo, hi)
        fig.add_trace(go.Bar(y=[lab], x=[hi - lo], base=[lo], orientation="h", showlegend=False,
                             marker_color="#1d4ed8" if "Blended" in lab else ("#93c5fd" if "·" in lab else "#60a5fa"),
                             hovertemplate=f"{lab}<br>{rp(lo)} – {rp(hi)}<br>tengah {rp(mid)}<extra></extra>"))
        fig.add_trace(go.Scatter(y=[lab], x=[mid], mode="markers", marker=dict(color="white", size=9,
                                 line=dict(color="#111827", width=1.5)), showlegend=False, hoverinfo="skip"))
    fig.add_vline(x=snap["price"], line_color=C_MKT, line_dash="dash",
                  annotation_text=f"Harga pasar {rp(snap['price'])}", annotation_position="top")
    fig.update_layout(title="Football field – nilai per saham (Rp)", height=420, margin=dict(l=10, r=10, t=60, b=10),
                      yaxis=dict(autorange="reversed"), xaxis_title="Rp per saham")
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("#### Hasil per metode & skenario")
        sf = report.summary_frame(res)
        st.dataframe(sf.set_index("Skenario").style.format({
            "Probabilitas": "{:.0%}", "WACC": "{:.2%}", "g": "{:.1%}",
            "EV DCF (USD jt)": "{:,.0f}", "Ekuitas DCF (USD jt)": "{:,.0f}",
            "DCF (Rp/saham)": "{:,.0f}", "Relatif (Rp/saham)": "{:,.0f}", "Blended (Rp/saham)": "{:,.0f}"}),
            width="stretch")
        st.markdown("#### Kriteria keputusan")
        st.markdown(
            f"- **BUY** bila upside terhadap nilai wajar sentral ≥ {res['rules']['buy']:+.0%}\n"
            f"- **SELL** bila upside ≤ {res['rules']['sell']:+.0%}; selain itu **HOLD**\n"
            f"- Nilai sentral = skenario Base (DCF Base × {res['method']['w_dcf']:.0%} + median peer × {res['method']['w_rel']:.0%}); "
            f"rentang = Bear (DCF Bear, Q1 peer) s.d. Bull (DCF Bull, Q3 peer)\n"
            f"- Harga pasar saat ini berada **{res['price_position']}** rentang nilai wajar.")
    with c2:
        st.markdown("#### Interpretasi otomatis")
        for line in v.commentary(res):
            st.markdown(f"- {line}")
    st.markdown("#### Risiko utama, asumsi kunci & keterbatasan")
    r1, r2, r3 = st.columns(3)
    r1.markdown("**Risiko**\n- Risiko sumber daya/uap: penurunan tekanan reservoir menurunkan CF\n"
                "- Eksekusi proyek: keterlambatan COD & cost overrun (dimodelkan di Bear)\n"
                "- Regulasi tarif & ketergantungan pada PLN sebagai pembeli tunggal\n"
                "- Free float 11,18% < 12,5% (HSC) & likuiditas saham\n"
                "- Kurs: harga saham IDR, arus kas USD")
    r2.markdown("**Asumsi kunci (Base)**\n"
                f"- CF eksisting {v.scenario_params(data, 'Base')['capacity_factor']:.0%}, tarif "
                f"US${v.scenario_params(data, 'Base')['tariff_existing']:.0f}/MWh\n"
                f"- Margin EBITDA {v.scenario_params(data, 'Base')['ebitda_margin']:.0%}\n"
                f"- WACC {s['Base']['dcf']['wacc']['wacc']:.2%}, g {v.scenario_params(data, 'Base')['terminal_growth']:.1%}\n"
                f"- Kapasitas {s['Base']['dcf']['forecast']['capacity_mw'].iloc[-1]:,.0f} MW (risked) di akhir proyeksi")
    r3.markdown("**Keterbatasan**\n- Tarif per kontrak tidak diungkap → tarif rata-rata implied\n"
                "- Wilayah kerja berjangka waktu; nilai terminal mengasumsikan perpanjangan\n"
                "- Arus kas Q4-2026 tidak dimodelkan terpisah (valuasi ≈ akhir 2026)\n"
                "- Multiple peer dari sumber publik berbeda tanggal; perlu diverifikasi")

# ---- DCF ------------------------------------------------------------------
with t_dcf:
    sc = st.radio("Skenario", v.SCENARIOS, index=1, horizontal=True, key="dcf_scn")
    d = res["scenarios"][sc]["dcf"]
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("WACC", f"{d['wacc']['wacc']:.2%}")
    m2.metric("Enterprise value", usd(d["enterprise_value"]))
    m3.metric("Nilai ekuitas", usd(d["equity_value"]))
    m4.metric("Nilai per saham", rp(d["per_share_idr"]), f"{d['per_share_idr'] / snap['price'] - 1:+.1%} vs pasar")
    m5.metric("Porsi nilai terminal", f"{d['tv_share']:.0%}", f"exit {d['implied_exit_ev_ebitda']:.1f}x EBITDA", delta_color="off")
    f = d["forecast"]
    show = f[["capacity_mw", "generation_gwh", "revenue", "ebitda", "d_and_a", "ebit", "tax", "nopat",
              "maint_capex", "growth_capex", "delta_nwc", "fcff", "discount_factor", "pv_fcff"]].T
    show.index = ["Kapasitas (MW, risked)", "Produksi (GWh)", "Pendapatan", "EBITDA", "D&A", "EBIT", "Pajak", "NOPAT",
                  "Capex pemeliharaan", "Capex pengembangan", "Δ Modal kerja", "FCFF", "Faktor diskonto", "PV FCFF"]
    st.dataframe(show.style.format("{:,.1f}").format("{:.3f}", subset=pd.IndexSlice[["Faktor diskonto"], :]),
                 width="stretch")
    cc1, cc2 = st.columns(2)
    with cc1:
        fig = go.Figure()
        fig.add_bar(x=f.index, y=f["fcff"], name="FCFF", marker_color=np.where(f["fcff"] < 0, C_BEAR, C_BASE))
        fig.add_scatter(x=f.index, y=f["ebitda"], name="EBITDA", mode="lines+markers")
        fig.update_layout(title="EBITDA vs FCFF (USD juta)", height=330, margin=dict(t=40, b=10))
        st.plotly_chart(fig, width="stretch")
    with cc2:
        wf = go.Figure(go.Waterfall(
            x=["PV FCFF", "PV terminal", "Enterprise value", "(-) Utang", "(+) Kas", "(-) MI", "Nilai ekuitas"],
            measure=["relative", "relative", "total", "relative", "relative", "relative", "total"],
            y=[d["sum_pv_fcff"], d["pv_terminal"], 0, -d["debt"], d["cash"], -d["minority_interest"], 0],
            texttemplate="%{y:,.0f}"))
        wf.update_layout(title="Rekonsiliasi EV → ekuitas (USD juta)", height=330, margin=dict(t=40, b=10))
        st.plotly_chart(wf, width="stretch")
    st.markdown(f"**Nilai terminal.** Metode aktif: {'Gordon FCFF' if int(d['params']['tv_method']) == 2 else 'value driver'}. "
                f"Value driver = NOPAT₍T+1₎ × (1 − g/RONIC) / (WACC − g) = {usd(d['tv_value_driver'])}; "
                f"Gordon FCFF = FCFF₍T₎ × (1+g)/(WACC − g) = {usd(d['tv_gordon_fcff'])}. "
                "Value driver dipakai sebagai default karena konsisten dengan kebutuhan reinvestasi untuk tumbuh; "
                "Gordon FCFF menganggap D&A > capex pemeliharaan berlangsung selamanya (lebih agresif).")
    st.markdown(f"Ekuitas {usd(d['equity_value'])} ÷ {snap['shares']:,.0f} juta saham × kurs Rp{snap['fx']:,.0f} = "
                f"**{rp(d['per_share_idr'])}/saham**. Selisih rekonsiliasi EV: {d['reconciliation_gap']:.2e}.")

# ---- Relative ---------------------------------------------------------------
with t_rel:
    rel = res["relative"]
    st.info(f"Diskon untuk peer non-Indonesia: **{rel['foreign_discount']:.0%}** "
            f"({'otomatis: CRP × bobot ekuitas ÷ (WACC − g)' if auto_disc else 'manual'}). "
            "Multiple ≤ 0 atau > 100x dianggap tidak valid; outlier dikeluarkan dengan aturan IQR (1,5×).")
    names = {"ev_ebitda": "EV/EBITDA", "pe": "P/E", "pb": "P/BV"}
    cols = st.columns(3)
    for i, mult in enumerate(["ev_ebitda", "pe", "pb"]):
        dd = rel["detail"][mult]
        with cols[i]:
            st.markdown(f"**{names[mult]}** (setelah penyesuaian)")
            tbl = pd.DataFrame({"multiple": dd["adjusted"]})
            tbl["status"] = ["dipakai" if t in dd["kept"].index else ("dikeluarkan" if t in dd["dropped"].index else "kosong")
                             for t in tbl.index]
            st.dataframe(tbl.style.format({"multiple": "{:.1f}x"}, na_rep="-"), width="stretch")
    st.markdown("**Nilai implied PGEO**")
    t = rel["table"].copy()
    t["multiple"] = t["multiple"].map(names)
    st.dataframe(t.style.format({"peer_multiple": "{:.1f}x", "pgeo_metric": "{:,.1f}", "equity_usd": "{:,.0f}",
                                 "per_share_idr": "{:,.0f}", "weight": "{:.0%}"}), width="stretch", hide_index=True)
    st.markdown(f"PGEO saat ini diperdagangkan pada EV/EBITDA **{snap['ev_ebitda']:.1f}x**, P/E **{snap['pe']:.1f}x**, "
                f"P/BV **{snap['pb']:.2f}x** (TTM). Nilai relatif tertimbang: Q1 {rp(rel['per_share_idr']['Q1'])} · "
                f"median {rp(rel['per_share_idr']['Median'])} · Q3 {rp(rel['per_share_idr']['Q3'])}.")
    with cw2:
        st.markdown("**Metrik PGEO yang dikalikan (TTM)**")
        tm = v.ttm_metrics(data)
        st.dataframe(pd.DataFrame({"USD juta": [tm["ebitda"], tm["net_income"], tm["book_equity"]]},
                                  index=["EBITDA TTM", "Laba bersih TTM", "Ekuitas buku"]).style.format("{:,.1f}"),
                     width="stretch")

# ---- Method selection -------------------------------------------------------
with t_meth:
    mw = res["method"]
    a, b = st.columns([1, 2])
    a.metric("Bobot DCF", f"{mw['w_dcf']:.0%}")
    a.metric("Bobot Relatif", f"{mw['w_rel']:.0%}")
    with b:
        for n in mw["notes"]:
            st.markdown(f"- {n}")
        st.markdown(
            "**Kapan DCF lebih ditekankan?** Bila arus kas kontraktual & dapat diproyeksikan, bisnis matang, "
            "dan peer sedikit/tidak sebanding.  \n**Kapan relatif lebih ditekankan?** Bila banyak peer sebanding "
            "(model bisnis, risiko negara, tahap pertumbuhan sama) dan arus kas sulit diproyeksikan (mis. start-up, "
            "laba negatif). Untuk perusahaan sektor keuangan, DCF berbasis FCFF tidak dipakai (gunakan DDM/P/BV).")
    sc_df = data["MethodScores"]
    fig = go.Figure()
    fig.add_bar(y=sc_df["factor"], x=sc_df["dcf_score"], name="DCF", orientation="h", marker_color=C_BASE)
    fig.add_bar(y=sc_df["factor"], x=sc_df["relative_score"], name="Relatif", orientation="h", marker_color="#94a3b8")
    fig.update_layout(barmode="group", height=360, xaxis=dict(range=[0, 5], title="Skor 1-5"),
                      yaxis=dict(autorange="reversed"), margin=dict(t=20, b=10))
    st.plotly_chart(fig, width="stretch")

# ---- Scenarios & sensitivity ------------------------------------------------
with t_scn:
    st.subheader("Skenario")
    comp = []
    for sname in v.SCENARIOS:
        p = v.scenario_params(data, sname)
        x = res["scenarios"][sname]
        comp.append({"Skenario": sname, "CF": p["capacity_factor"], "Tarif": p["tariff_existing"],
                     "Margin EBITDA": p["ebitda_margin"], "Capex x": p["capex_cost_multiplier"],
                     "COD delay": p["cod_delay"], "WACC": x["dcf"]["wacc"]["wacc"], "g": p["terminal_growth"],
                     "DCF": x["dcf_px"], "Relatif": x["rel_px"], "Blended": x["blended"],
                     "Prob.": res["scenario_probabilities"][sname]})
    st.dataframe(pd.DataFrame(comp).set_index("Skenario").style.format({
        "CF": "{:.0%}", "Tarif": "{:.0f}", "Margin EBITDA": "{:.0%}", "Capex x": "{:.2f}", "COD delay": "{:.0f}",
        "WACC": "{:.2%}", "g": "{:.1%}", "DCF": "{:,.0f}", "Relatif": "{:,.0f}", "Blended": "{:,.0f}", "Prob.": "{:.0%}"}),
        width="stretch")
    st.caption(f"Nilai harapan tertimbang probabilitas: **{rp(res['fair_expected'])}**")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Sensitivitas DCF Base: WACC × terminal growth (Rp/saham)**")
        hm = go.Figure(go.Heatmap(z=sens.values, x=list(sens.columns), y=list(sens.index), colorscale="RdYlGn",
                                  text=[[f"{val:,.0f}" for val in row] for row in sens.values], texttemplate="%{text}"))
        hm.update_layout(height=360, margin=dict(t=10, b=10))
        st.plotly_chart(hm, width="stretch")
        st.caption("Dengan metode value driver, g berpengaruh kecil karena RONIC mendekati WACC: pertumbuhan "
                   "hanya menciptakan nilai bila RONIC > WACC.")
    with c2:
        st.markdown("**Tornado DCF Base (Rp/saham)**")
        tf = go.Figure()
        bp = torn["base_px"].iloc[0]
        tf.add_bar(y=torn["driver"], x=torn["low_px"] - bp, base=bp, orientation="h", name="Input turun",
                   marker_color=C_BEAR)
        tf.add_bar(y=torn["driver"], x=torn["high_px"] - bp, base=bp, orientation="h", name="Input naik",
                   marker_color=C_BULL)
        tf.add_vline(x=bp, line_dash="dot")
        tf.update_layout(barmode="overlay", height=360, margin=dict(t=10, b=10))
        st.plotly_chart(tf, width="stretch")
        st.caption("Perubahan: CF ±3 pp, tarif ±10%, margin ±3 pp, capex ±20%, CRP ±1 pp, g ±0,5 pp, pajak ±3 pp, "
                   "probabilitas proyek ±20%.")
    st.subheader("Kalkulator what-if (tidak mengubah input)")
    w1, w2, w3, w4 = st.columns(4)
    pb_ = v.scenario_params(data, "Base")
    o_cf = w1.slider("Capacity factor", 0.70, 0.95, float(pb_["capacity_factor"]), 0.01)
    o_tar = w2.slider("Tarif eksisting (USD/MWh)", 60.0, 110.0, float(pb_["tariff_existing"]), 1.0)
    o_crp = w3.slider("CRP", 0.0, 0.06, float(pb_["country_risk_premium"]), 0.0025)
    o_g = w4.slider("Terminal growth", 0.0, 0.035, float(pb_["terminal_growth"]), 0.0025)
    wi = v.dcf(data, "Base", {"capacity_factor": o_cf, "tariff_existing": o_tar, "country_risk_premium": o_crp,
                              "terminal_growth": o_g})
    st.metric("DCF what-if", rp(wi["per_share_idr"]), f"{wi['per_share_idr'] / snap['price'] - 1:+.1%} vs pasar · "
              f"WACC {wi['wacc']['wacc']:.2%}")

# ---- Validation -------------------------------------------------------------
with t_val:
    st.subheader("Pemeriksaan kesalahan material")
    a, b, c = st.columns(3)
    a.metric("OK", int((checks["status"] == "OK").sum()))
    b.metric("Peringatan", n_warn)
    c.metric("Error", n_err)
    only = st.toggle("Tampilkan hanya yang bermasalah", value=False)
    view = checks[checks["status"] != "OK"] if only else checks
    st.dataframe(view.style.apply(lambda r: [
        "background-color:#fee2e2" if r["status"] == "ERROR" else
        ("background-color:#fef3c7" if r["status"] == "WARNING" else "")] * len(r), axis=1),
        width="stretch", hide_index=True, height=520)

# ---- Export -----------------------------------------------------------------
with t_exp:
    st.subheader("Simpan & ekspor")
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown("**Ringkasan hasil (Excel)**  \nRingkasan, DCF per skenario, relatif, sensitivitas, validasi, snapshot input.")
        st.download_button("⬇ Unduh hasil valuasi (.xlsx)", report.excel_report(data, res, sens, torn),
                           file_name=f"PGEO_valuation_{stamp}.xlsx", width="stretch")
    with e2:
        st.markdown("**Laporan ringkas (HTML)**  \nBuka di browser → Print → Save as PDF.")
        st.download_button("⬇ Unduh laporan (.html)", report.html_report(data, res).encode("utf-8"),
                           file_name=f"PGEO_report_{stamp}.html", mime="text/html", width="stretch")
    with e3:
        st.markdown("**File input terkini**  \nSemua editan di aplikasi tersimpan; upload kembali untuk melanjutkan.")
        st.download_button("⬇ Unduh file input (.xlsx)", v.save_inputs(data),
                           file_name=f"pgeo_input_{stamp}.xlsx", width="stretch")

# ---- Help -------------------------------------------------------------------
with t_help:
    st.markdown((ROOT / "docs" / "panduan.md").read_text(encoding="utf-8"))
