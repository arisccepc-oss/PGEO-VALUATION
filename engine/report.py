"""Export layer: Excel summary workbook and printable HTML report."""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

from . import valuation as v


def summary_frame(res: dict) -> pd.DataFrame:
    rows = []
    for s in v.SCENARIOS:
        x = res["scenarios"][s]
        d = x["dcf"]
        rows.append({
            "Skenario": s, "Probabilitas": res["scenario_probabilities"][s],
            "WACC": d["wacc"]["wacc"], "g": d["params"]["terminal_growth"],
            "EV DCF (USD jt)": d["enterprise_value"], "Ekuitas DCF (USD jt)": d["equity_value"],
            "DCF (Rp/saham)": x["dcf_px"], "Relatif (Rp/saham)": x["rel_px"],
            "Blended (Rp/saham)": x["blended"],
        })
    return pd.DataFrame(rows)


def excel_report(data: dict, res: dict, sens: pd.DataFrame, torn: pd.DataFrame) -> bytes:
    snap = res["market"]
    meta = v.kv(data["Meta"])
    head = pd.DataFrame([
        ["Perusahaan", meta.get("company")], ["Ticker", meta.get("ticker")],
        ["Tanggal valuasi", meta.get("valuation_date")],
        ["Data terakhir diperbarui", meta.get("last_updated")],
        ["Laporan dibuat", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Harga pasar (Rp)", snap["price"]],
        ["Nilai wajar sentral (Rp)", res["fair_central"]],
        ["Rentang nilai wajar (Rp)", f"{res['fair_low']:,.0f} - {res['fair_high']:,.0f}"],
        ["Nilai harapan tertimbang probabilitas (Rp)", res["fair_expected"]],
        ["Upside (sentral)", res["upside"]],
        ["Rekomendasi", res["recommendation"]],
        ["Bobot DCF / Relatif", f"{res['method']['w_dcf']:.0%} / {res['method']['w_rel']:.0%}"],
    ], columns=["Item", "Nilai"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        head.to_excel(xw, sheet_name="Ringkasan", index=False)
        summary_frame(res).to_excel(xw, sheet_name="Ringkasan", index=False, startrow=len(head) + 2)
        pd.DataFrame({"Komentar": v.commentary(res)}).to_excel(
            xw, sheet_name="Ringkasan", index=False, startrow=len(head) + 8)
        for s in v.SCENARIOS:
            d = res["scenarios"][s]["dcf"]
            d["forecast"].to_excel(xw, sheet_name=f"DCF_{s}")
            pd.DataFrame([
                ["Sum PV FCFF", d["sum_pv_fcff"]], ["Terminal value", d["terminal_value"]],
                ["PV terminal value", d["pv_terminal"]], ["Enterprise value", d["enterprise_value"]],
                ["(-) Utang", d["debt"]], ["(+) Kas", d["cash"]], ["(-) Kepentingan non-pengendali", d["minority_interest"]],
                ["Nilai ekuitas", d["equity_value"]], ["Nilai per saham (USD)", d["per_share_usd"]],
                ["Nilai per saham (Rp)", d["per_share_idr"]],
                ["WACC", d["wacc"]["wacc"]], ["Cost of equity", d["wacc"]["cost_of_equity"]],
                ["Beta levered", d["wacc"]["beta_levered"]],
            ], columns=["Item", "Nilai"]).to_excel(xw, sheet_name=f"DCF_{s}", index=False, startrow=len(d["forecast"]) + 3)
        res["relative"]["table"].to_excel(xw, sheet_name="Relatif", index=False)
        sens.to_excel(xw, sheet_name="Sensitivitas")
        torn.to_excel(xw, sheet_name="Sensitivitas", index=False, startrow=len(sens) + 3)
        res["checks"].to_excel(xw, sheet_name="Validasi", index=False)
        data["MethodScores"].to_excel(xw, sheet_name="PemilihanMetode", index=False)
        for s in ["Market", "Historical", "Projects", "Assumptions", "Peers"]:
            data[s].to_excel(xw, sheet_name=f"Input_{s}", index=False)
        for ws in xw.sheets.values():
            ws.set_column(0, 0, 34)
            ws.set_column(1, 20, 16)
    return buf.getvalue()


def html_report(data: dict, res: dict) -> str:
    meta = v.kv(data["Meta"])
    snap = res["market"]
    sf = summary_frame(res)
    fmt = {c: "{:,.0f}" for c in sf.columns if "Rp" in c or "USD" in c}
    fmt.update({"Probabilitas": "{:.0%}", "WACC": "{:.2%}", "g": "{:.1%}"})
    table = sf.style.format(fmt).hide(axis="index").to_html()
    checks = res["checks"]
    issues = checks[checks["status"] != "OK"]
    issue_html = issues.to_html(index=False) if len(issues) else "<p>Semua pemeriksaan OK.</p>"
    comm = "".join(f"<li>{c}</li>" for c in v.commentary(res))
    color = {"BUY": "#1b7f3b", "HOLD": "#b7791f", "SELL": "#b42318"}[res["recommendation"]]
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<title>Laporan Valuasi {meta.get('ticker')}</title>
<style>body{{font-family:Arial,sans-serif;max-width:900px;margin:30px auto;color:#1f2937}}
h1{{font-size:22px}} table{{border-collapse:collapse;font-size:13px;width:100%}}
td,th{{border:1px solid #d1d5db;padding:4px 8px;text-align:right}} th{{background:#f3f4f6}}
.rec{{display:inline-block;padding:6px 14px;border-radius:6px;color:#fff;background:{color};font-weight:bold}}
.kpi{{display:flex;gap:24px;margin:16px 0}} .kpi div{{background:#f9fafb;padding:10px 14px;border-radius:8px}}
small{{color:#6b7280}}</style></head><body>
<h1>Laporan Valuasi - {meta.get('company')} ({meta.get('ticker')})</h1>
<small>Tanggal valuasi {meta.get('valuation_date')} | data diperbarui {meta.get('last_updated')} | dibuat {datetime.now():%Y-%m-%d %H:%M}</small>
<div class="kpi"><div>Harga pasar<br><b>Rp{snap['price']:,.0f}</b></div>
<div>Nilai wajar sentral<br><b>Rp{res['fair_central']:,.0f}</b></div>
<div>Rentang<br><b>Rp{res['fair_low']:,.0f} - Rp{res['fair_high']:,.0f}</b></div>
<div>Upside<br><b>{res['upside']:+.1%}</b></div><div><span class="rec">{res['recommendation']}</span></div></div>
<h2>Hasil per metode & skenario</h2>{table}
<h2>Interpretasi</h2><ul>{comm}</ul>
<h2>Pemeriksaan yang perlu diperhatikan</h2>{issue_html}
<p><small>Dihasilkan oleh PGEO Valuation Platform. Bukan rekomendasi investasi; untuk keperluan akademik (MM6026 SBM ITB).</small></p>
</body></html>"""
