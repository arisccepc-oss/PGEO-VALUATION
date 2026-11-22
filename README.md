# PGEO Valuation Platform
**AI-Assisted Business Valuation Model – PT Pertamina Geothermal Energy Tbk (IDX: PGEO)**
UTS MM6026 Digital Business Valuation · SBM ITB · Aris Munandar Saputra (BLEMBA 74)

Aplikasi web (Streamlit) yang menggabungkan input data, mesin valuasi DCF + relative valuation, logika pemilihan
metode, skenario, sensitivitas, validasi, dashboard rekomendasi, dan ekspor hasil.

---

## 1. Setup & menjalankan

### Opsi A – Online (Streamlit Community Cloud, gratis)
1. Buat akun GitHub, lalu buat repository baru (mis. `pgeo-valuation`, Public).
2. Upload seluruh isi folder ini (`app.py`, `requirements.txt`, folder `engine/`, `data/`, `docs/`, `tests/`,
   `scripts/`, `.streamlit/`) lewat **Add file → Upload files**.
3. Buka https://share.streamlit.io → login dengan GitHub → **Create app** → pilih repository, branch `main`,
   main file `app.py` → **Deploy**. Dalam 2–3 menit aplikasi aktif di URL `https://<nama>.streamlit.app`.
4. Bagikan URL tersebut ke dosen.

### Opsi B – Lokal
```bash
pip install -r requirements.txt
streamlit run app.py          # buka http://localhost:8501
python -m pytest -q           # menjalankan uji mesin valuasi
```

**Kebutuhan akses:** tidak ada langganan/API key. Tombol "Ambil harga & kurs terbaru" memakai Yahoo Finance
(gratis, butuh internet); bila gagal, isi harga & kurs secara manual.

## 2. Input
Semua input ada di `data/pgeo_input.xlsx` (juga bisa diedit langsung di aplikasi):

| Sheet | Isi |
|---|---|
| Meta | nama, ticker, tanggal valuasi, timestamp update |
| Market | harga saham, jumlah saham, kurs, utang, kas, ekuitas buku, kapasitas MW, yield (dengan sumber & tanggal) |
| Historical | pendapatan, EBITDA, laba, arus kas, neraca, produksi GWh FY2023–FY2025, 9M2025, 9M2026 |
| Projects | pipeline proyek: MW, tahun COD, probabilitas, capex/MW |
| Assumptions | parameter Bear/Base/Bull (operasional, capex, pajak, WACC, terminal) |
| Peers | multiple EV/EBITDA, P/E, P/BV peer + flag include |
| MethodScores | skor kesesuaian DCF vs relatif per faktor |
| MultipleWeights | bobot multiple |
| DecisionRules | ambang BUY/SELL, batas bobot, batas g, batas porsi TV |

Satuan: USD juta (keuangan), juta lembar (saham), IDR (harga), desimal (persentase).

## 3. Update
1. Data pasar harian: sidebar (manual atau Yahoo Finance).
2. LK baru: isi kolom baru/ganti angka di sheet Historical & Market → upload di sidebar
   (atau edit tabel di tab **Data & Input**).
3. Asumsi: tab **Asumsi & Proyek**; peer: tab **Relatif**.
4. Semua valuasi, skenario, sensitivitas, validasi, dan rekomendasi dihitung ulang otomatis.
5. Tab **Export** → unduh file input terkini (timestamp otomatis) untuk dipakai lagi.

## 4. Kalkulasi
Lihat tab **Panduan & Metodologi** (`docs/panduan.md`). Ringkas:
DCF FCFF berbasis aset (MW × CF × tarif) → WACC CAPM USD + CRP → nilai terminal value-driver →
EV ke ekuitas → Rp/saham. Relatif: multiple peer disesuaikan risiko negara, filter outlier, dibobot.
Bobot metode dari scoring 6 faktor. Rekomendasi: BUY ≥ +15%, SELL ≤ −10%.

## 5. Output
Dashboard (KPI, football field, rekomendasi, risiko), tabel DCF & waterfall EV→ekuitas, nilai implied relatif,
heatmap WACC×g, tornado, kalkulator what-if, tabel validasi; ekspor Excel, HTML (→PDF), dan file input.

## 6. Struktur kode
```
app.py                  antarmuka Streamlit
engine/valuation.py     mesin valuasi (tanpa dependensi UI)
engine/report.py        ekspor Excel/HTML
data/pgeo_input.xlsx    data & asumsi (dengan sumber)
scripts/build_template.py  membangun ulang file input default
tests/test_engine.py    uji independen (DCF dihitung ulang manual)
docs/panduan.md         panduan, metodologi, pengungkapan AI
```

## 7. Keterbatasan yang diketahui
- Tarif per kontrak tidak diungkap; dipakai tarif rata-rata implied (pendapatan ÷ produksi).
- EBITDA/D&A FY2023 dan beberapa pos 9M belum diambil dari LK asli (sel kosong, ditandai validasi).
- Multiple peer berasal dari agregator publik dengan tanggal berbeda; perlu diverifikasi sebelum dipakai serius.
- Jadwal, probabilitas, dan capex/MW proyek pipeline adalah estimasi analis.
- Arus kas Q4-2026 tidak dimodelkan terpisah; valuasi diperlakukan setara akhir 2026.
- Wilayah kerja panas bumi berjangka waktu; nilai terminal mengasumsikan perpanjangan izin.
- Bukan rekomendasi investasi.
