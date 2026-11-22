"""PGEO Valuation Lab - Streamlit UI.

Run locally:  streamlit run app.py
Layers: data/pgeo_input.xlsx (inputs) -> engine/valuation.py (calculation)
        -> app.py + ui_style.py (interface) -> engine/report.py (exports)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui_style as ui
from engine import report, valuation as v

ROOT = Path(__file__).resolve().parent
DEFAULT_FILE = ROOT / "data" / "pgeo_input.xlsx"

st.set_page_config(page_title="PGEO Valuation Lab", page_icon=str(ROOT / "assets" / "icon.svg"), layout="wide")
ui.inject_css()
ui.register_plotly_template()
try:
    st.logo(str(ROOT / "assets" / "logo_dark.svg"), icon_image=str(ROOT / "assets" / "icon.svg"), size="large")
except Exception:  # noqa: BLE001  (older Streamlit)
    pass

C_BEAR, C_BASE, C_BULL, C_MKT = ui.RED, ui.TEAL, ui.GREEN, "#0f172a"


def rp(x: float) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"Rp{x:,.0f}".replace(",", ".")


def usd(x: float) -> str:
    return f"US${x:,.1f} jt"


# --------------------------------------------------------------------------
# STATE
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
# SIDEBAR (compact, grouped in expanders)
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<div style='font-size:.8rem;opacity:.8;margin-bottom:6px'>AI-Assisted Business Valuation · MM6026 SBM ITB</div>",
                unsafe_allow_html=True)
    with st.expander("Update data pasar", icon=":material/monitoring:", expanded=True):
        st.number_input("Harga saham (Rp)", min_value=0.0, step=5.0, key="ov_price")
        st.number_input("Kurs IDR/USD", min_value=0.0, step=10.0, key="ov_fx")
        if st.button("Ambil harga & kurs terbaru", icon=":material/cloud_sync:", width="stretch"):
            try:
                import yfinance as yf  # optional dependency
                px = yf.Ticker("PGEO.JK").history(period="5d")["Close"].dropna()
                fx = yf.Ticker("IDR=X").history(period="5d")["Close"].dropna()
                st.session_state.ov_price = float(px.iloc[-1])
                st.session_state.ov_fx = float(fx.iloc[-1])
                st.session_state.fetched = f"Yahoo Finance {px.index[-1]:%Y-%m-%d}"
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.warning(f"Koneksi data otomatis gagal ({e}). Isi manual.")
        if st.session_state.get("fetched"):
            st.caption(f"Sumber: {st.session_state.fetched}")
    with st.expander("Sumber data (upload Excel)", icon=":material/upload_file:", expanded=False):
        up = st.file_uploader("File input .xlsx", type=["xlsx"], label_visibility="collapsed")
        if up is not None and st.session_state.get("last_upload") != up.file_id:
            try:
                load_base(up.getvalue(), f"Upload: {up.name}")
                st.session_state.last_upload = up.file_id
                st.success("File dimuat & dihitung ulang.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Gagal membaca file: {e}")
        if st.button("Kembali ke data default", icon=":material/restart_alt:", width="stretch"):
            load_base(DEFAULT_FILE, "Data default (pgeo_input.xlsx)")
            st.rerun()
    with st.expander("Pengaturan relative valuation", icon=":material/tune:", expanded=False):
        auto_disc = st.toggle("Diskon peer asing otomatis (CRP)", value=True)
        man_disc = st.slider("Diskon manual", 0.0, 0.6, 0.25, 0.05, disabled=auto_disc)
    st.markdown(f"<div class='side-card'><b>Aktif</b><br>{st.session_state.source_label}<br>"
                f"<b>Dimuat</b> {st.session_state.loaded_at}</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# TABS
# --------------------------------------------------------------------------
tabs = st.tabs([":material/space_dashboard: Dashboard", ":material/database: Data", ":material/tune: Asumsi",
                ":material/payments: DCF", ":material/compare_arrows: Relatif", ":material/rule: Metode",
                ":material/insights: Skenario", ":material/verified: Validasi", ":material/download: Export",
                ":material/menu_book: Panduan"])
(t_dash, t_data, t_asm, t_dcf, t_rel, t_meth, t_scn, t_val, t_exp, t_help) = tabs
ver = st.session_state.ver
base = st.session_state.base
data: dict[str, pd.DataFrame] = {}


def editor(sheet: str, **kw) -> pd.DataFrame:
    return st.data_editor(base[sheet], key=f"{sheet}_{ver}", width="stretch", **kw)


# ---- input editors (rendered first in code so outputs use current edits) ----
with t_data:
    ui.section("🗂️", "Data input", "Bisa diedit langsung · USD juta · saham juta lembar · harga IDR")
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown("**Meta**")
        data["Meta"] = editor("Meta", hide_index=True, disabled=["key"])
    with c2:
        st.markdown("**Market**")
        data["Market"] = editor("Market", hide_index=True, disabled=["key"])
    st.markdown("**Historical** · TTM = FY2025 − 9M2025 + 9M2026")
    data["Historical"] = editor("Historical", hide_index=True, disabled=["metric"])

with t_asm:
    ui.section("⚙️", "Asumsi proyeksi & parameter valuasi", "Kolom Bear / Base / Bull bisa diedit")
    data["Assumptions"] = editor("Assumptions", hide_index=True, disabled=["parameter", "unit", "description"], height=560)
    ui.section("🏗️", "Pipeline proyek", "Kapasitas & capex dikali probabilitas sukses (expected value)")
    data["Projects"] = editor("Projects", hide_index=True, num_rows="dynamic")

with t_rel:
    ui.section("🌐", "Peer & multiple", "Centang `include` untuk dipakai · tambah baris untuk peer baru")
    data["Peers"] = editor("Peers", hide_index=True, num_rows="dynamic")
    cw1, cw2 = st.columns(2)
    with cw1:
        st.markdown("**Bobot multiple**")
        data["MultipleWeights"] = editor("MultipleWeights", hide_index=True, disabled=["multiple"])

with t_meth:
    ui.section("🧭", "Aturan pemilihan metode", "Skor 1–5 per faktor × bobot kepentingan")
    data["MethodScores"] = editor("MethodScores", hide_index=True, disabled=["factor"])
    data["DecisionRules"] = editor("DecisionRules", hide_index=True, disabled=["rule"])

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
except Exception as e:  # noqa: BLE001
    with t_dash:
        st.error(f"Perhitungan gagal: {e}. Periksa input di tab Data/Asumsi.")
    st.stop()

snap = res["market"]
meta = v.kv(data["Meta"])
checks = res["checks"]
n_err = int((checks["status"] == "ERROR").sum())
n_warn = int((checks["status"] == "WARNING").sum())
s = res["scenarios"]
pB = v.scenario_params(data, "Base")

# ---- Data tab: derived views ----------------------------------------------
with t_data:
    h = v.historical_table(data)
    ui.section("📈", "Kinerja historis & rasio")
    cc1, cc2 = st.columns([1.3, 1])
    with cc1:
        fig = go.Figure()
        cols = ["FY2023", "FY2024", "FY2025", "TTM"]
        for metric, name, col in [("revenue", "Pendapatan", ui.TEAL), ("ebitda", "EBITDA", ui.AMBER),
                                  ("net_income", "Laba bersih", "#2563eb")]:
            fig.add_bar(x=cols, y=h.loc[metric, cols], name=name, marker_color=col, marker_line_width=0)
        fig.update_layout(height=330, barmode="group", yaxis_title="USD juta", margin=dict(t=40, b=10),
                          title="Pendapatan, EBITDA, laba (USD juta)")
        st.plotly_chart(fig, width="stretch")
    with cc2:
        ratios = pd.DataFrame({
            "Margin EBITDA": h.loc["ebitda"] / h.loc["revenue"],
            "Margin laba bersih": h.loc["net_income"] / h.loc["revenue"],
            "Tarif implied (USD/MWh)": (h.loc["revenue"] * 1000) / h.loc["generation_gwh"],
            "Capacity factor implied": h.loc["generation_gwh"] /
                (float(v.kv(data["Market"])["installed_capacity_mw"]) * 8.76 *
                 pd.Series({"FY2023": 1, "FY2024": 1, "FY2025": 1, "9M2025": 0.75, "9M2026": 0.75, "TTM": 1})),
        }).T
        st.dataframe(ratios.style.format("{:.2f}", na_rep="–"), width="stretch")
        st.caption(f"Data diperbarui **{meta.get('last_updated')}** · tanggal valuasi **{meta.get('valuation_date')}**")

# ---- Assumptions: WACC ------------------------------------------------------
with t_asm:
    ui.section("🏦", "Biaya modal (WACC) per skenario",
               "Ke = Rf + βL·ERP + CRP · βL = βU·[1+(1−t)·D/E] · arus kas USD → Rf UST, risiko Indonesia via CRP")
    wrows = []
    for sn in v.SCENARIOS:
        p = v.scenario_params(data, sn)
        w = v.wacc(p)
        wrows.append({"Skenario": sn, "Rf (UST10Y)": p["risk_free_rate"], "ERP": p["equity_risk_premium"],
                      "CRP": p["country_risk_premium"], "Beta unlevered": p["unlevered_beta"],
                      "Beta levered": w["beta_levered"], "Ke": w["cost_of_equity"], "Kd after-tax": w["kd_after_tax"],
                      "D/(D+E)": w["debt_weight"], "WACC": w["wacc"]})
    st.dataframe(pd.DataFrame(wrows).set_index("Skenario").style.format("{:.2%}").format(
        "{:.2f}", subset=["Beta unlevered", "Beta levered"]), width="stretch")

# ---- Dashboard ----------------------------------------------------------------
with t_dash:
    ui.hero(f"{meta.get('company')}",
            "Geothermal power · IDX: PGEO · Valuasi DCF + Relative dengan pemilihan metode otomatis",
            [f"📅 Valuasi {meta.get('valuation_date')}", f"🔄 Data {meta.get('last_updated')}",
             f"⚡ {float(v.kv(data['Market'])['installed_capacity_mw']):,.0f} MW own operation",
             f"💱 Rp{snap['fx']:,.0f}/USD".replace(",", "."), f"🗂️ {st.session_state.source_label}"])
    if n_err:
        st.error(f"{n_err} pemeriksaan ERROR – lihat tab Validasi sebelum memakai hasil.", icon=":material/error:")
    rec = res["recommendation"]
    rec_col = {"BUY": ui.GREEN, "HOLD": ui.AMBER, "SELL": ui.RED}[rec]
    tone = lambda x: "up" if x >= 0 else "down"  # noqa: E731
    ui.kpi_cards([
        dict(icon="🏷️", label="Harga pasar", value=rp(snap["price"]), delta=f"EV/EBITDA {snap['ev_ebitda']:.1f}x",
             tone="neu", accent="#334155", soft="#e2e8f0"),
        dict(icon="🎯", label="Nilai wajar sentral", value=rp(res["fair_central"]), delta=f"{res['upside']:+.1%} upside",
             tone=tone(res["upside"]), accent=ui.TEAL, soft="#ccfbf1"),
        dict(icon="📏", label="Rentang nilai wajar", value=f"{rp(res['fair_low'])} – {rp(res['fair_high'])}".replace("Rp", ""),
             delta="Bear → Bull (Rp)", tone="neu", accent="#2563eb", soft="#dbeafe"),
        dict(icon="🎲", label="Nilai harapan", value=rp(res["fair_expected"]),
             delta=f"{res['upside_expected']:+.1%} · tertimbang prob.", tone=tone(res["upside_expected"]),
             accent="#9333ea", soft="#f3e8ff"),
        dict(icon="🚀" if rec == "BUY" else ("⏸️" if rec == "HOLD" else "🔻"), label="Rekomendasi", value=rec,
             color=rec_col, cls="rec", delta=f"harga {res['price_position']} rentang", tone="neu",
             accent=rec_col, soft="#dcfce7" if rec == "BUY" else "#fef3c7"),
        dict(icon="🛡️", label="Validasi", value=f"{n_err} error", delta=f"{n_warn} peringatan",
             tone="down" if n_err else "neu", accent=ui.RED if n_err else ui.GREEN, soft="#fee2e2" if n_err else "#dcfce7"),
    ])

    # Football field
    rel_ps = res["relative"]["per_share_idr"]
    rt = res["relative"]["table"]
    names = {"ev_ebitda": "EV/EBITDA", "pe": "P/E", "pb": "P/BV"}
    bars = [("DCF · Bear–Bull", s["Bear"]["dcf_px"], s["Bull"]["dcf_px"], s["Base"]["dcf_px"], ui.TEAL),
            ("Relatif · Q1–Q3 peer", rel_ps["Q1"], rel_ps["Q3"], rel_ps["Median"], ui.AMBER)]
    for mult in ["ev_ebitda", "pe", "pb"]:
        sub = rt[rt["multiple"] == mult].set_index("stat")
        if len(sub):
            bars.append((f"   {names[mult]}", sub.loc["Q1", "per_share_idr"], sub.loc["Q3", "per_share_idr"],
                         sub.loc["Median", "per_share_idr"], "#fcd34d"))
    bars.append((f"Blended · {res['method']['w_dcf']:.0%} DCF / {res['method']['w_rel']:.0%} Rel",
                 res["fair_low"], res["fair_high"], res["fair_central"], "#065f46"))
    fig = go.Figure()
    for lab, lo, hi, mid, col in bars:
        lo, hi = min(lo, hi), max(lo, hi)
        fig.add_trace(go.Bar(y=[lab], x=[hi - lo], base=[lo], orientation="h", showlegend=False, marker_color=col,
                             marker_line_width=0, width=0.62,
                             hovertemplate=f"{lab}<br>{rp(lo)} – {rp(hi)}<br>tengah {rp(mid)}<extra></extra>"))
        fig.add_trace(go.Scatter(y=[lab], x=[mid], mode="markers",
                                 marker=dict(color="white", size=11, line=dict(color="#0f172a", width=2)),
                                 showlegend=False, hoverinfo="skip"))
        fig.add_annotation(y=lab, x=hi, text=f"<b>{rp(mid)}</b>", showarrow=False, xanchor="left", xshift=8,
                           font=dict(size=11, color="#0f172a"), bgcolor="rgba(255,255,255,.9)",
                           bordercolor="#cbd5e1", borderpad=3)
    fig.add_vline(x=snap["price"], line_color=C_MKT, line_dash="dash", line_width=2,
                  annotation_text=f"Harga pasar {rp(snap['price'])}", annotation_position="top",
                  annotation_font=dict(color="#0f172a", size=12))
    fig.update_layout(title="🏈 Football field – nilai per saham", height=440, margin=dict(l=10, r=20, t=70, b=10),
                      yaxis=dict(autorange="reversed"), xaxis_title="Rp per saham", bargap=0.35)
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns([1.25, 1])
    with c1:
        ui.section("📋", "Hasil per metode & skenario")
        sf = report.summary_frame(res)
        st.dataframe(sf.set_index("Skenario").style.format({
            "Probabilitas": "{:.0%}", "WACC": "{:.2%}", "g": "{:.1%}",
            "EV DCF (USD jt)": "{:,.0f}", "Ekuitas DCF (USD jt)": "{:,.0f}",
            "DCF (Rp/saham)": "{:,.0f}", "Relatif (Rp/saham)": "{:,.0f}", "Blended (Rp/saham)": "{:,.0f}"})
            , width="stretch")
        st.markdown(ui.card("Kriteria keputusan", [
            f"<b>BUY</b> bila upside terhadap nilai wajar sentral ≥ {res['rules']['buy']:+.0%}",
            f"<b>SELL</b> bila upside ≤ {res['rules']['sell']:+.0%}; selain itu <b>HOLD</b>",
            f"Nilai sentral = Base: DCF × {res['method']['w_dcf']:.0%} + median peer × {res['method']['w_rel']:.0%}",
            "Rentang = Bear (DCF Bear, Q1 peer) s.d. Bull (DCF Bull, Q3 peer)",
            f"Harga pasar berada <b>{res['price_position']}</b> rentang nilai wajar"], "⚖️"), unsafe_allow_html=True)
    with c2:
        ui.section("🤖", "Interpretasi otomatis", "Narasi berbasis aturan dari hasil model")
        st.markdown(ui.card("Ringkasan", v.commentary(res), "💡"), unsafe_allow_html=True)
    ui.section("⚠️", "Risiko, asumsi kunci & keterbatasan")
    r1, r2, r3 = st.columns(3)
    r1.markdown(ui.card("Risiko", [
        "Sumber daya/uap: penurunan tekanan reservoir menurunkan CF",
        "Eksekusi proyek: keterlambatan COD & cost overrun (di Bear)",
        "Regulasi tarif & PLN sebagai pembeli tunggal",
        "Free float 11,18% &lt; 12,5% (HSC) & likuiditas",
        "Kurs: harga saham IDR, arus kas USD"], "🔥"), unsafe_allow_html=True)
    r2.markdown(ui.card("Asumsi kunci (Base)", [
        f"CF eksisting {pB['capacity_factor']:.0%}, tarif US${pB['tariff_existing']:.0f}/MWh",
        f"Margin EBITDA {pB['ebitda_margin']:.0%}",
        f"WACC {s['Base']['dcf']['wacc']['wacc']:.2%}, g {pB['terminal_growth']:.1%}",
        f"Kapasitas {s['Base']['dcf']['forecast']['capacity_mw'].iloc[-1]:,.0f} MW (risked) di akhir proyeksi"], "🧩"),
        unsafe_allow_html=True)
    r3.markdown(ui.card("Keterbatasan", [
        "Tarif per kontrak tidak diungkap → tarif rata-rata implied",
        "Wilayah kerja berjangka; nilai terminal asumsikan perpanjangan",
        "Arus kas Q4-2026 tidak dimodelkan terpisah",
        "Multiple peer dari sumber publik berbeda tanggal"], "📌"), unsafe_allow_html=True)

# ---- DCF ----------------------------------------------------------------------
with t_dcf:
    ui.section("💰", "Discounted Cash Flow (FCFF, USD)", "Berbasis aset: MW × capacity factor × tarif")
    sc = st.segmented_control("Skenario", v.SCENARIOS, default="Base", key="dcf_scn") if hasattr(st, "segmented_control") \
        else st.radio("Skenario", v.SCENARIOS, index=1, horizontal=True, key="dcf_scn")
    sc = sc or "Base"
    d = res["scenarios"][sc]["dcf"]
    ui.kpi_cards([
        dict(icon="🏦", label="WACC", value=f"{d['wacc']['wacc']:.2%}", delta=f"Ke {d['wacc']['cost_of_equity']:.2%}", tone="neu"),
        dict(icon="🏭", label="Enterprise value", value=usd(d["enterprise_value"]), tone="neu", accent="#2563eb", soft="#dbeafe"),
        dict(icon="💼", label="Nilai ekuitas", value=usd(d["equity_value"]), tone="neu", accent="#9333ea", soft="#f3e8ff"),
        dict(icon="🎯", label="Nilai per saham", value=rp(d["per_share_idr"]),
             delta=f"{d['per_share_idr'] / snap['price'] - 1:+.1%} vs pasar", tone=tone(d["per_share_idr"] / snap["price"] - 1)),
        dict(icon="♾️", label="Porsi nilai terminal", value=f"{d['tv_share']:.0%}",
             delta=f"exit {d['implied_exit_ev_ebitda']:.1f}x EBITDA", tone="neu", accent=ui.AMBER, soft="#fef3c7"),
    ])
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
        fig.add_bar(x=f.index, y=f["fcff"], name="FCFF", marker_color=np.where(f["fcff"] < 0, ui.RED, ui.TEAL),
                    marker_line_width=0)
        fig.add_scatter(x=f.index, y=f["ebitda"], name="EBITDA", mode="lines+markers",
                        line=dict(color=ui.AMBER, width=3), marker=dict(size=8))
        fig.update_layout(title="📊 EBITDA vs FCFF (USD juta)", height=350, margin=dict(t=60, b=10))
        st.plotly_chart(fig, width="stretch")
    with cc2:
        wf = go.Figure(go.Waterfall(
            x=["PV FCFF", "PV terminal", "Enterprise value", "(−) Utang", "(+) Kas", "(−) MI", "Nilai ekuitas"],
            measure=["relative", "relative", "total", "relative", "relative", "relative", "total"],
            y=[d["sum_pv_fcff"], d["pv_terminal"], 0, -d["debt"], d["cash"], -d["minority_interest"], 0],
            texttemplate="%{y:,.0f}", increasing=dict(marker_color=ui.TEAL), decreasing=dict(marker_color=ui.RED),
            totals=dict(marker_color="#065f46"), connector=dict(line=dict(color="#94a3b8"))))
        wf.update_layout(title="🧮 Rekonsiliasi EV → ekuitas (USD juta)", height=350, margin=dict(t=60, b=10))
        st.plotly_chart(wf, width="stretch")
    st.markdown(ui.card("Nilai terminal & per saham", [
        f"Metode aktif: <b>{'Gordon FCFF' if int(d['params']['tv_method']) == 2 else 'value driver'}</b>",
        f"Value driver = NOPAT₍T+1₎ × (1 − g/RONIC) / (WACC − g) = {usd(d['tv_value_driver'])}",
        f"Gordon FCFF = FCFF₍T₎ × (1+g) / (WACC − g) = {usd(d['tv_gordon_fcff'])} (pembanding, lebih agresif)",
        f"Ekuitas {usd(d['equity_value'])} ÷ {snap['shares']:,.0f} juta saham × Rp{snap['fx']:,.0f} = <b>{rp(d['per_share_idr'])}/saham</b>",
        f"Selisih rekonsiliasi EV: {d['reconciliation_gap']:.2e}"], "♾️"), unsafe_allow_html=True)

# ---- Relative -----------------------------------------------------------------
with t_rel:
    rel = res["relative"]
    st.info(f"Diskon peer non-Indonesia **{rel['foreign_discount']:.0%}** "
            f"({'otomatis: CRP × bobot ekuitas ÷ (WACC − g)' if auto_disc else 'manual'}). "
            "Multiple ≤0 atau >100x tidak valid; outlier dikeluarkan dengan aturan IQR 1,5×.", icon=":material/info:")
    ui.section("🔎", "Multiple setelah penyesuaian")
    cols = st.columns(3)
    for i, mult in enumerate(["ev_ebitda", "pe", "pb"]):
        dd = rel["detail"][mult]
        with cols[i]:
            adj = dd["adjusted"]
            status = ["dipakai" if t in dd["kept"].index else ("dikeluarkan" if t in dd["dropped"].index else "kosong")
                      for t in adj.index]
            colr = [ui.TEAL if x == "dipakai" else ("#f87171" if x == "dikeluarkan" else "#cbd5e1") for x in status]
            fg = go.Figure(go.Bar(x=adj.fillna(0).values, y=list(adj.index), orientation="h", marker_color=colr,
                                  text=[f"{x:.1f}x" if pd.notna(x) else "–" for x in adj.values], textposition="outside"))
            if len(dd["kept"]):
                fg.add_vline(x=dd["kept"].median(), line_dash="dot", line_color="#0f172a",
                             annotation_text=f"median {dd['kept'].median():.1f}x", annotation_position="top")
            fg.update_layout(title={"ev_ebitda": "EV/EBITDA", "pe": "P/E", "pb": "P/BV"}[mult],
                             height=330, margin=dict(t=60, b=10, l=10, r=30), yaxis=dict(autorange="reversed"))
            st.plotly_chart(fg, width="stretch")
    ui.section("🧾", "Nilai implied PGEO")
    t = rel["table"].copy()
    t["multiple"] = t["multiple"].map({"ev_ebitda": "EV/EBITDA", "pe": "P/E", "pb": "P/BV"})
    st.dataframe(t.style.format({"peer_multiple": "{:.1f}x", "pgeo_metric": "{:,.1f}", "equity_usd": "{:,.0f}",
                                 "per_share_idr": "{:,.0f}", "weight": "{:.0%}"}), width="stretch", hide_index=True)
    ui.kpi_cards([
        dict(icon="📉", label="PGEO EV/EBITDA (TTM)", value=f"{snap['ev_ebitda']:.1f}x", tone="neu"),
        dict(icon="💹", label="PGEO P/E (TTM)", value=f"{snap['pe']:.1f}x", tone="neu", accent=ui.AMBER, soft="#fef3c7"),
        dict(icon="📚", label="PGEO P/BV", value=f"{snap['pb']:.2f}x", tone="neu", accent="#2563eb", soft="#dbeafe"),
        dict(icon="🎯", label="Relatif median", value=rp(rel["per_share_idr"]["Median"]),
             delta=f"Q1 {rp(rel['per_share_idr']['Q1'])} · Q3 {rp(rel['per_share_idr']['Q3'])}", tone="neu",
             accent="#9333ea", soft="#f3e8ff"),
    ])
    with cw2:
        st.markdown("**Metrik PGEO yang dikalikan (TTM)**")
        tm = v.ttm_metrics(data)
        st.dataframe(pd.DataFrame({"USD juta": [tm["ebitda"], tm["net_income"], tm["book_equity"]]},
                                  index=["EBITDA TTM", "Laba bersih TTM", "Ekuitas buku"]).style.format("{:,.1f}"),
                     width="stretch")

# ---- Method selection -----------------------------------------------------------
with t_meth:
    mw = res["method"]
    a, b = st.columns([1, 1.6])
    with a:
        donut = go.Figure(go.Pie(labels=["DCF", "Relatif"], values=[mw["w_dcf"], mw["w_rel"]], hole=.62,
                                 marker=dict(colors=[ui.TEAL, ui.AMBER]), textinfo="label+percent", sort=False))
        donut.update_layout(title="⚖️ Bobot metode", height=320, showlegend=False, margin=dict(t=60, b=10))
        st.plotly_chart(donut, width="stretch")
    with b:
        st.markdown(ui.card("Hasil aturan keputusan", mw["notes"], "🧭"), unsafe_allow_html=True)
        st.markdown(ui.card("Kapan menekankan metode tertentu", [
            "<b>DCF</b>: arus kas kontraktual & terprediksi, bisnis matang, peer sedikit/tidak sebanding",
            "<b>Relatif</b>: banyak peer sebanding (model bisnis, risiko negara, tahap pertumbuhan) dan arus kas sulit diproyeksikan",
            "<b>Sektor keuangan</b>: FCFF tidak dipakai → DDM / P/BV"], "📐"), unsafe_allow_html=True)
    sc_df = data["MethodScores"]
    fig = go.Figure()
    fig.add_bar(y=sc_df["factor"], x=sc_df["dcf_score"], name="DCF", orientation="h", marker_color=ui.TEAL)
    fig.add_bar(y=sc_df["factor"], x=sc_df["relative_score"], name="Relatif", orientation="h", marker_color=ui.AMBER)
    fig.update_layout(title="🧩 Skor kesesuaian per faktor", barmode="group", height=380,
                      xaxis=dict(range=[0, 5], title="Skor 1-5"), yaxis=dict(autorange="reversed"), margin=dict(t=60, b=10))
    st.plotly_chart(fig, width="stretch")

# ---- Scenarios & sensitivity ------------------------------------------------------
with t_scn:
    ui.section("🎲", "Skenario Bear / Base / Bull")
    comp = []
    for sname in v.SCENARIOS:
        p = v.scenario_params(data, sname)
        x = s[sname]
        comp.append({"Skenario": sname, "CF": p["capacity_factor"], "Tarif": p["tariff_existing"],
                     "Margin EBITDA": p["ebitda_margin"], "Capex x": p["capex_cost_multiplier"],
                     "COD delay": p["cod_delay"], "WACC": x["dcf"]["wacc"]["wacc"], "g": p["terminal_growth"],
                     "DCF": x["dcf_px"], "Relatif": x["rel_px"], "Blended": x["blended"],
                     "Prob.": res["scenario_probabilities"][sname]})
    st.dataframe(pd.DataFrame(comp).set_index("Skenario").style.format({
        "CF": "{:.0%}", "Tarif": "{:.0f}", "Margin EBITDA": "{:.0%}", "Capex x": "{:.2f}", "COD delay": "{:.0f}",
        "WACC": "{:.2%}", "g": "{:.1%}", "DCF": "{:,.0f}", "Relatif": "{:,.0f}", "Blended": "{:,.0f}", "Prob.": "{:.0%}"}),
        width="stretch")
    sb = go.Figure()
    for sname, col in zip(v.SCENARIOS, [ui.RED, ui.TEAL, ui.GREEN]):
        sb.add_bar(x=["DCF", "Relatif", "Blended"], y=[s[sname]["dcf_px"], s[sname]["rel_px"], s[sname]["blended"]],
                   name=sname, marker_color=col, text=[f"{y:,.0f}" for y in [s[sname]["dcf_px"], s[sname]["rel_px"],
                                                                            s[sname]["blended"]]], textposition="outside")
    sb.add_hline(y=snap["price"], line_dash="dash", annotation_text=f"Harga pasar {rp(snap['price'])}")
    sb.update_layout(title="📊 Nilai per saham per skenario (Rp)", barmode="group", height=380, margin=dict(t=60, b=10))
    st.plotly_chart(sb, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        hm = go.Figure(go.Heatmap(z=sens.values, x=list(sens.columns), y=list(sens.index), colorscale="Tealgrn",
                                  text=[[f"{val:,.0f}" for val in row] for row in sens.values], texttemplate="%{text}",
                                  showscale=False))
        hm.update_layout(title="🌡️ Sensitivitas DCF: WACC × g (Rp/saham)", height=380, margin=dict(t=60, b=10))
        st.plotly_chart(hm, width="stretch")
        st.caption("Dengan value driver, g berpengaruh kecil karena RONIC ≈ WACC: pertumbuhan hanya menciptakan nilai bila RONIC > WACC.")
    with c2:
        tf = go.Figure()
        bp = torn["base_px"].iloc[0]
        tf.add_bar(y=torn["driver"], x=torn["low_px"] - bp, base=bp, orientation="h", name="Input turun", marker_color=ui.RED)
        tf.add_bar(y=torn["driver"], x=torn["high_px"] - bp, base=bp, orientation="h", name="Input naik", marker_color=ui.GREEN)
        tf.add_vline(x=bp, line_dash="dot")
        tf.update_layout(title="🌪️ Tornado DCF Base (Rp/saham)", barmode="overlay", height=380, margin=dict(t=60, b=10))
        st.plotly_chart(tf, width="stretch")
        st.caption("CF ±3 pp · tarif ±10% · margin ±3 pp · capex ±20% · CRP ±1 pp · g ±0,5 pp · pajak ±3 pp · probabilitas ±20%")
    ui.section("🎛️", "Kalkulator what-if", "Tidak mengubah input")
    w1, w2, w3, w4 = st.columns(4)
    o_cf = w1.slider("Capacity factor", 0.70, 0.95, float(pB["capacity_factor"]), 0.01)
    o_tar = w2.slider("Tarif eksisting (USD/MWh)", 60.0, 110.0, float(pB["tariff_existing"]), 1.0)
    o_crp = w3.slider("CRP", 0.0, 0.06, float(pB["country_risk_premium"]), 0.0025)
    o_g = w4.slider("Terminal growth", 0.0, 0.035, float(pB["terminal_growth"]), 0.0025)
    wi = v.dcf(data, "Base", {"capacity_factor": o_cf, "tariff_existing": o_tar, "country_risk_premium": o_crp,
                              "terminal_growth": o_g})
    ui.kpi_cards([dict(icon="🧪", label="DCF what-if", value=rp(wi["per_share_idr"]),
                       delta=f"{wi['per_share_idr'] / snap['price'] - 1:+.1%} vs pasar · WACC {wi['wacc']['wacc']:.2%}",
                       tone=tone(wi["per_share_idr"] / snap["price"] - 1))])

# ---- Validation -------------------------------------------------------------------
with t_val:
    ui.section("🛡️", "Pemeriksaan kesalahan material")
    ui.kpi_cards([
        dict(icon="✅", label="OK", value=str(int((checks["status"] == "OK").sum())), accent=ui.GREEN, soft="#dcfce7"),
        dict(icon="⚠️", label="Peringatan", value=str(n_warn), accent=ui.AMBER, soft="#fef3c7"),
        dict(icon="⛔", label="Error", value=str(n_err), accent=ui.RED, soft="#fee2e2"),
    ])
    only = st.toggle("Tampilkan hanya yang bermasalah", value=False)
    view = checks[checks["status"] != "OK"] if only else checks
    st.dataframe(view.style.apply(lambda r: [
        "background-color:#fee2e2" if r["status"] == "ERROR" else
        ("background-color:#fef3c7" if r["status"] == "WARNING" else "background-color:#f0fdf4")] * len(r), axis=1),
        width="stretch", hide_index=True, height=520)

# ---- Export -----------------------------------------------------------------------
with t_exp:
    ui.section("📤", "Simpan & ekspor", "Semua file diberi timestamp")
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown(ui.card("Hasil valuasi (Excel)", ["Ringkasan & komentar", "DCF per skenario", "Relatif, sensitivitas",
                                                      "Validasi & snapshot input"], "📗"), unsafe_allow_html=True)
        st.download_button("Unduh .xlsx", report.excel_report(data, res, sens, torn), icon=":material/table:",
                           file_name=f"PGEO_valuation_{stamp}.xlsx", width="stretch")
    with e2:
        st.markdown(ui.card("Laporan ringkas (HTML)", ["KPI & rekomendasi", "Tabel skenario", "Interpretasi",
                                                       "Buka → Print → Save as PDF"], "📄"), unsafe_allow_html=True)
        st.download_button("Unduh .html", report.html_report(data, res).encode("utf-8"), icon=":material/description:",
                           file_name=f"PGEO_report_{stamp}.html", mime="text/html", width="stretch")
    with e3:
        st.markdown(ui.card("File input terkini", ["Semua editan di aplikasi", "Timestamp last_updated otomatis",
                                                   "Upload kembali via sidebar", "Format = template"], "🗂️"),
                    unsafe_allow_html=True)
        st.download_button("Unduh input .xlsx", v.save_inputs(data), icon=":material/save:",
                           file_name=f"pgeo_input_{stamp}.xlsx", width="stretch")

# ---- Help --------------------------------------------------------------------------
with t_help:
    ui.section("📘", "Panduan, metodologi & pengungkapan AI")
    st.markdown((ROOT / "docs" / "panduan.md").read_text(encoding="utf-8"))

st.markdown("<div class='footer'>PGEO Valuation Lab · UTS MM6026 Digital Business Valuation · SBM ITB · "
            "Aris Munandar Saputra (BLEMBA 74) · bukan rekomendasi investasi</div>", unsafe_allow_html=True)
