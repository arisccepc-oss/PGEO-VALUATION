## Panduan penggunaan

**Alur kerja update (tanpa membangun ulang model)**

1. **Update data.** Ada tiga cara:
   - *Cepat:* ubah harga saham & kurs di sidebar, atau klik **Ambil harga & kurs terbaru** (Yahoo Finance, butuh internet).
   - *Langsung di aplikasi:* edit tabel di tab **Data & Input**, **Asumsi & Proyek**, **Relatif**, **Pemilihan Metode**.
   - *Lewat file:* unduh **file input** (tab Export), perbarui di Excel (LK baru, kurs, peer), lalu upload di sidebar.
2. **Ubah asumsi.** Kolom Bear/Base/Bull di tab Asumsi; proyek baru di tabel Projects; peer di tab Relatif.
3. **Hitung ulang.** Otomatis setiap ada perubahan; semua skenario, sensitivitas, dan validasi ikut diperbarui.
4. **Refresh dashboard & rekomendasi.** Tab Dashboard selalu memakai hasil terakhir.
5. **Ekspor.** Tab Export: hasil (.xlsx), laporan (.html → PDF), dan file input terkini (.xlsx, dengan timestamp).

**Pemisahan lapisan:** `data/pgeo_input.xlsx` (input & sumber) → `engine/valuation.py` (logika kalkulasi) →
`app.py` (antarmuka) → `engine/report.py` (output). Mesin valuasi diuji ulang secara independen di `tests/test_engine.py`.

---

## Metodologi

**1. DCF (FCFF, USD).** Proyeksi 10 tahun berbasis aset:
- Produksi = MW × capacity factor × 8.760 jam; kapasitas baru dari tabel Projects × probabilitas sukses.
- Pendapatan = produksi eksisting × tarif + produksi baru × tarif PPA baru (+ eskalasi) + pendapatan lain (JOC).
- EBITDA = pendapatan × margin; D&A = basis + capex pengembangan ÷ umur manfaat.
- FCFF = NOPAT + D&A − capex pemeliharaan − capex pengembangan − Δ modal kerja.
- Diskonto mid-year dengan WACC: Ke = Rf(UST) + βL·ERP + CRP; βL = βU·[1+(1−t)D/E].
- Nilai terminal (default) = NOPAT₍T+1₎ × (1 − g/RONIC) / (WACC − g); pembanding Gordon FCFF.
- Ekuitas = EV − utang + kas − kepentingan non-pengendali; per saham dikonversi ke Rupiah dengan kurs JISDOR.

**2. Relative valuation.** EV/EBITDA, P/E, P/BV peer (domestik & global). Peer asing didiskon sebesar
CRP × bobot ekuitas ÷ (WACC − g) karena multiple ≈ 1/(WACC − g). Multiple ≤0 atau >100x tidak valid; outlier
IQR dikeluarkan. Nilai implied = multiple × metrik TTM PGEO (EV → ekuitas untuk EV/EBITDA), dibobot 50/30/20.

**3. Pemilihan metode.** Enam faktor (model bisnis, maturitas, stabilitas arus kas, kualitas informasi,
ketersediaan peer, struktur modal/sektor) diberi skor 1–5 untuk DCF dan relatif × bobot kepentingan.
Bobot metode = proporsi skor; bila skor peer ≤ 2, bobot relatif dibatasi maksimal 40%.

**4. Rekonsiliasi & rekomendasi.** Nilai blended per skenario = w_DCF × DCF + w_Rel × relatif
(Bear: Q1 peer, Base: median, Bull: Q3). Nilai sentral = Base; rentang = Bear–Bull; nilai harapan = tertimbang
probabilitas. BUY bila upside ≥ +15%, SELL bila ≤ −10%, selain itu HOLD.

**5. Validasi.** Input wajib, plausibilitas satuan (kurs, jumlah saham, harga), konsistensi historis, g < WACC dan
g ≤ 3,5%, RONIC > g, multiple tidak valid/outlier, rekonsiliasi EV ↔ ekuitas, porsi nilai terminal, implied exit
multiple, FCFF negatif, total bobot & probabilitas = 100%, kesegaran data harga.

---

## Sumber data (lihat kolom *source* di setiap tabel)
LK PGEO FY2023–FY2025 & 9M-2026 (via IQPlus/BCA Sekuritas, Bisnis.com, Kontan, Emitennews, Fortune IDN,
Stockanalysis.com); rilis produksi PGE; harga saham Kabarbursa (18 Nov 2026); JISDOR BI via Kontan (19 Nov 2026);
yield SBN IDX Channel; multiple peer: Yahoo Finance, Seeking Alpha, TipRanks, Zonebourse/Marketscreener, CariSaham,
Stockanalysis, Simply Wall St. Akses data otomatis (opsional) memakai Yahoo Finance gratis tanpa API key.

## Pengungkapan penggunaan AI
- **Tool:** Claude (Anthropic) sebagai asisten riset data, penulisan kode Python/Streamlit, dan draf dokumentasi.
- **Tugas yang dibantu AI:** pencarian & kompilasi data publik, struktur model, kode mesin valuasi & antarmuka,
  uji otomatis, draf narasi.
- **Cara verifikasi:** (1) DCF dihitung ulang secara independen di `tests/test_engine.py` dan harus identik;
  (2) uji monotonisitas (WACC naik → nilai turun; tarif naik → nilai naik); (3) angka historis dicocokkan
  antar-sumber (mis. pendapatan FY2025 US$432,7 jt di Bisnis.com, Kontan, IQPlus); (4) pemeriksaan validasi otomatis.
- **Koreksi yang dilakukan:** capex seragam US$5,5 jt/MW diganti capex per proyek (co-generation lebih murah);
  nilai terminal Gordon FCFF diganti value-driver karena D&A > capex pemeliharaan membuat Gordon terlalu agresif.
- **Keterbatasan:** sebagian data peer & EBITDA FY2023 belum terverifikasi dari LK asli; asumsi proyek
  (COD, probabilitas, capex/MW) adalah estimasi analis. Penyusun tetap bertanggung jawab atas semua angka.
