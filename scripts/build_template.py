"""Build the default input workbook (data/pgeo_input.xlsx).

Run:  python scripts/build_template.py
The workbook is the single source of data for the app. Users update it
(or edit the tables inside the app) whenever new financial statements,
market data or assumptions become available.
"""
from datetime import datetime
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "pgeo_input.xlsx"

meta = pd.DataFrame(
    [
        ["company", "PT Pertamina Geothermal Energy Tbk", "Nama perusahaan"],
        ["ticker", "PGEO", "Kode saham BEI (Yahoo: PGEO.JK)"],
        ["valuation_date", "2026-11-20", "Tanggal valuasi (YYYY-MM-DD)"],
        ["reporting_currency", "USD", "Mata uang laporan keuangan (juta)"],
        ["price_currency", "IDR", "Mata uang harga saham"],
        ["last_updated", datetime.now().strftime("%Y-%m-%d %H:%M"), "Diisi otomatis saat file disimpan"],
        ["prepared_by", "Aris Munandar Saputra - BLEMBA 74", "Penyusun"],
    ],
    columns=["key", "value", "description"],
)

market = pd.DataFrame(
    [
        ["share_price", 910, "IDR/saham", "Kabarbursa.com - penutupan 18 Nov 2026", "2026-11-18"],
        ["shares_outstanding", 41900, "juta lembar", "Stockanalysis.com (Jun-2026); termasuk MESOP", "2026-06-30"],
        ["fx_idr_usd", 18269, "IDR per USD", "JISDOR Bank Indonesia 19 Nov 2026 (Kontan)", "2026-11-19"],
        ["total_debt", 741.27, "USD juta", "Stockanalysis.com - neraca Jun-2026 (obligasi + pinjaman + sewa)", "2026-06-30"],
        ["cash", 713.68, "USD juta", "LK 30 Sep 2026 (Emitennews)", "2026-09-30"],
        ["minority_interest", -0.46, "USD juta", "Stockanalysis.com - neraca Jun-2026", "2026-06-30"],
        ["book_equity", 2006.0, "USD juta", "Bisnis.com/Stockanalysis - ekuitas Jun-2026", "2026-06-30"],
        ["installed_capacity_mw", 727, "MW", "PGE - kapasitas own operation (Kabarbursa, Nov 2026)", "2026-11-06"],
        ["us10y_yield", 0.049, "desimal", "Asumsi dari spread SBN-UST 2,81 pp & SBN 10Y 7,71% (Investing.com via Heygotrade)", "2026-11-02"],
        ["sbn10y_yield", 0.0775, "desimal", "IDX Channel 19 Nov 2026", "2026-11-19"],
    ],
    columns=["key", "value", "unit", "source", "as_of"],
)

# Historical: USD million unless stated. NaN = not retrieved (flagged by validation).
nan = float("nan")
historical = pd.DataFrame(
    [
        ["revenue", 406.29, 407.12, 432.73, 318.86, 352.20, "USD juta", "LK audited; LK 9M via IQPlus/Industry.co.id"],
        ["ebitda", nan, 323.79, 330.35, 248.97, 287.77, "USD juta", "FY24 = laba usaha + D&A; FY25 Bareksa; 9M Fortune IDN/Emitennews"],
        ["operating_income", nan, 210.27, 205.57, 158.59, 186.26, "USD juta", "IQPlus/BCA Sekuritas; Indotelko"],
        ["net_income", 163.59, 160.49, 137.67, 104.26, 126.62, "USD juta", "Laba atribusi pemilik entitas induk"],
        ["d_and_a", nan, 113.52, 127.97, nan, nan, "USD juta", "Stockanalysis.com cash flow"],
        ["operating_cash_flow", 255.19, 258.28, 313.52, nan, nan, "USD juta", "Stockanalysis.com"],
        ["capex", 68.11, 103.41, 84.40, nan, nan, "USD juta", "Stockanalysis.com"],
        ["cash", 677.72, 655.19, 718.50, nan, 713.68, "USD juta", "Neraca"],
        ["total_debt", 730.84, 745.81, 752.88, nan, nan, "USD juta", "Stockanalysis.com"],
        ["total_equity", 1971.0, 2008.75, 2045.56, nan, nan, "USD juta", "Neraca"],
        ["generation_gwh", nan, 4827, 5095, 3747, 4114, "GWh", "PGE rilis produksi own operation"],
    ],
    columns=["metric", "FY2023", "FY2024", "FY2025", "9M2025", "9M2026", "unit", "source"],
)

projects = pd.DataFrame(
    [
        ["Co-generation Ulubelu (bottoming)", 30, 2027, 0.85, 3.0, "Bagian program co-generation 230 MW (PGE); binary di lapangan eksisting"],
        ["Hululais Unit 1 & 2", 110, 2029, 0.75, 5.0, "Proyek Hululais 110 MW (PGE public expose 2025)"],
        ["Co-generation lainnya", 100, 2029, 0.60, 3.0, "Sisa program co-generation; jadwal asumsi analis"],
        ["Lumut Balai Unit 3", 55, 2030, 0.80, 4.2, "Pinjaman JICA US$158,9 jt (~70% biaya) (Bisnis.com Agu 2026)"],
        ["Lahendong Unit 7 & 8", 40, 2030, 0.75, 4.5, "Pendanaan World Bank (Bisnis.com Agu 2026)"],
        ["Lumut Balai Unit 4", 55, 2031, 0.70, 4.2, "Pinjaman JICA US$149 jt (Bisnis.com Agu 2026); COD 2030-2032"],
    ],
    columns=["project", "capacity_mw", "cod_year", "probability", "capex_per_mw", "note"],
)

assumptions = pd.DataFrame(
    [
        ["forecast_start_year", 2027, 2027, 2027, "tahun", "Tahun pertama proyeksi"],
        ["forecast_years", 10, 10, 10, "tahun", "Panjang periode proyeksi eksplisit"],
        ["capacity_factor", 0.82, 0.85, 0.87, "desimal", "CF aset eksisting (TTM ~85,8%; FY25 ~80%)"],
        ["capacity_factor_new", 0.80, 0.85, 0.88, "desimal", "CF proyek baru"],
        ["tariff_existing", 80.0, 82.0, 83.0, "USD/MWh", "Tarif rata-rata uap+listrik (TTM implied ~US$82/MWh)"],
        ["tariff_new", 90.0, 95.0, 100.0, "USD/MWh", "Tarif PPA proyek baru (Perpres 112/2022)"],
        ["tariff_escalation", 0.000, 0.010, 0.015, "desimal/thn", "Eskalasi tarif tahunan"],
        ["other_revenue", 17.0, 18.0, 19.0, "USD juta", "Production allowance JOC (FY25 US$17,3 jt)"],
        ["ebitda_margin", 0.75, 0.78, 0.80, "desimal", "Margin EBITDA (FY25 76,3%; TTM 79,2%; guidance 78-80%)"],
        ["base_d_and_a", 138.0, 138.0, 138.0, "USD juta", "D&A basis (TTM US$139 jt)"],
        ["useful_life", 25, 25, 25, "tahun", "Umur depresiasi capex baru"],
        ["maint_capex_per_mw", 0.10, 0.09, 0.085, "USD juta/MW/thn", "Capex pemeliharaan & make-up well"],
        ["capex_cost_multiplier", 1.15, 1.00, 0.90, "x", "Pengali capex per MW proyek (overrun/efisiensi)"],
        ["build_years", 3, 3, 3, "tahun", "Lama konstruksi (capex disebar rata sebelum COD)"],
        ["cod_delay", 1, 0, 0, "tahun", "Keterlambatan COD seluruh proyek"],
        ["probability_multiplier", 0.8, 1.0, 1.1, "x", "Pengali probabilitas sukses proyek (maks 1)"],
        ["tax_rate", 0.30, 0.27, 0.25, "desimal", "Tarif pajak efektif (FY24-25 ~29,7%; statutory 22%)"],
        ["nwc_pct_delta_revenue", 0.10, 0.10, 0.10, "desimal", "Modal kerja atas kenaikan pendapatan"],
        ["risk_free_rate", 0.049, 0.049, 0.049, "desimal", "US Treasury 10Y (arus kas dalam USD)"],
        ["equity_risk_premium", 0.050, 0.045, 0.045, "desimal", "Mature market ERP (Damodaran)"],
        ["country_risk_premium", 0.030, 0.025, 0.022, "desimal", "CRP Indonesia (Damodaran) - verifikasi"],
        ["unlevered_beta", 0.75, 0.70, 0.65, "x", "Beta unlevered utilitas terbarukan"],
        ["target_debt_weight", 0.25, 0.25, 0.25, "desimal", "D/(D+E) target (pasar saat ini ~26%)"],
        ["cost_of_debt", 0.065, 0.060, 0.055, "desimal", "Kd pre-tax USD (green bond 2028 + spread)"],
        ["terminal_growth", 0.015, 0.020, 0.025, "desimal", "Pertumbuhan terminal nominal USD"],
        ["ronic", 0.10, 0.11, 0.12, "desimal", "Return on new invested capital (terminal)"],
        ["tv_method", 1, 1, 1, "kode", "Metode nilai terminal: 1 = value driver (NOPAT, RONIC); 2 = Gordon FCFF"],
        ["scenario_probability", 0.25, 0.50, 0.25, "desimal", "Bobot probabilitas skenario"],
    ],
    columns=["parameter", "Bear", "Base", "Bull", "unit", "description"],
)

peers = pd.DataFrame(
    [
        ["Barito Renewables Energy", "BREN", "ID", "Geothermal + angin", True, 26.0, 99.2, 24.0, "2026-11", "CariSaham (PER, PBV @Rp2.210); EV/EBITDA estimasi dari Zonebourse 2026E", "Pure-play panas bumi domestik; valuasi premium/HSC"],
        ["Cikarang Listrindo", "POWR", "ID", "IPP gas", True, 3.8, 10.5, 1.3, "2026-10", "Stockanalysis (EV/EBITDA), Ajaib (PER Okt-26)", "IPP domestik, bukan EBT"],
        ["Kencana Energi Lestari", "KEEN", "ID", "PLTA/PLTM", True, None, 10.9, None, "2026", "Simply Wall St (PER)", "EBT domestik skala kecil"],
        ["Arkora Hydro", "ARKO", "ID", "PLTA + PLTS", True, None, 46.7, 6.2, "2026-11", "Dihitung: harga Rp1.175, laba TTM ~Rp72,8 mia, ~2,89 mia saham", "EBT domestik fase pertumbuhan"],
        ["Ormat Technologies", "ORA", "US", "Geothermal", True, 15.8, 43.2, 2.18, "2026-11-12", "Yahoo Finance key statistics", "Pure-play panas bumi global"],
        ["Contact Energy", "CEN", "NZ", "Geothermal + hidro", True, 12.2, 20.5, 2.05, "2026", "Seeking Alpha / TipRanks", "Utilitas dengan porsi panas bumi besar"],
        ["ACEN Corporation", "ACEN", "PH", "EBT diversifikasi", True, 31.2, 15.4, 1.42, "2026", "Zonebourse/Marketscreener 2026E, Stockanalysis (PB)", "EBT Asia Tenggara"],
    ],
    columns=["name", "ticker", "country", "business", "include", "ev_ebitda", "pe", "pb", "as_of", "source", "relevance"],
)

method_scores = pd.DataFrame(
    [
        ["Industri & model bisnis", 1.0, 5, 3, "Kontrak jual uap/listrik jangka panjang dengan PLN (take-or-pay) -> arus kas dapat diproyeksikan"],
        ["Maturitas & pertumbuhan", 1.0, 4, 3, "Aset matang 727 MW + pipeline jelas menuju ~1 GW; pertumbuhan berbasis proyek, bukan pasar"],
        ["Profitabilitas & stabilitas arus kas", 1.0, 5, 4, "Margin EBITDA 76-80%, FCF positif 3 tahun berturut-turut"],
        ["Ketersediaan & keandalan informasi", 1.0, 4, 4, "LK audited & data produksi tersedia; tarif per kontrak tidak diungkap"],
        ["Ketersediaan peer yang sebanding", 1.5, 4, 2, "Peer panas bumi murni sedikit; BREN outlier; peer asing beda risiko negara"],
        ["Struktur modal & karakter sektor", 1.0, 5, 3, "Non-keuangan, leverage rendah (net debt ~US$28 jt), mata uang fungsional USD"],
    ],
    columns=["factor", "importance", "dcf_score", "relative_score", "rationale"],
)

multiple_weights = pd.DataFrame(
    [
        ["ev_ebitda", 0.50, "Utama: netral terhadap struktur modal & kebijakan depresiasi, cocok untuk aset padat modal"],
        ["pe", 0.30, "Pelengkap: mencerminkan laba ke pemegang saham, sensitif terhadap pajak & bunga"],
        ["pb", 0.20, "Pelengkap: relevan untuk bisnis berbasis aset; lemah bila ROE berbeda jauh"],
    ],
    columns=["multiple", "weight", "rationale"],
)

decision_rules = pd.DataFrame(
    [
        ["buy_threshold", 0.15, "Upside >= 15% terhadap nilai wajar sentral -> BUY"],
        ["sell_threshold", -0.10, "Upside <= -10% -> SELL; di antaranya HOLD"],
        ["max_relative_weight_if_weak_peers", 0.40, "Batas bobot relatif bila skor peer <= 2"],
        ["max_tv_share_warning", 0.85, "Peringatan bila nilai terminal > 85% EV"],
        ["max_terminal_growth", 0.035, "Batas atas g (pertumbuhan nominal jangka panjang USD)"],
    ],
    columns=["rule", "value", "description"],
)

OUT.parent.mkdir(parents=True, exist_ok=True)
with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
    readme = pd.DataFrame(
        {
            "PETUNJUK": [
                "File input untuk PGEO Valuation Platform.",
                "1. Perbarui sheet Market (harga, kurs, utang, kas) dan Historical saat LK baru terbit.",
                "2. Ubah asumsi di sheet Assumptions (kolom Bear/Base/Bull).",
                "3. Tambah/kurangi proyek di sheet Projects dan peer di sheet Peers (kolom include TRUE/FALSE).",
                "4. Upload file ini di aplikasi (sidebar) -> semua valuasi dihitung ulang otomatis.",
                "Satuan: angka keuangan USD juta; harga saham IDR; saham juta lembar; persentase dalam desimal.",
                "Sel kosong pada Historical = data belum ditemukan (akan ditandai di tab Validasi).",
            ]
        }
    )
    readme.to_excel(xw, sheet_name="README", index=False)
    meta.to_excel(xw, sheet_name="Meta", index=False)
    market.to_excel(xw, sheet_name="Market", index=False)
    historical.to_excel(xw, sheet_name="Historical", index=False)
    projects.to_excel(xw, sheet_name="Projects", index=False)
    assumptions.to_excel(xw, sheet_name="Assumptions", index=False)
    peers.to_excel(xw, sheet_name="Peers", index=False)
    method_scores.to_excel(xw, sheet_name="MethodScores", index=False)
    multiple_weights.to_excel(xw, sheet_name="MultipleWeights", index=False)
    decision_rules.to_excel(xw, sheet_name="DecisionRules", index=False)

print(f"Written {OUT}")
