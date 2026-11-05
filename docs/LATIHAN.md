# 🏋️ Latihan

Latihan disusun dari yang paling mudah. Kerjakan di branch terpisah dan jalankan `python -m pytest tests/ -q`
setelah setiap perubahan.

## Level 1 — Pemanasan

**1.1 Ganti warna sektor.** Ubah `WARNA_SEKTOR` di `src/sektor.py`, jalankan ulang aplikasi, dan perhatikan semua
grafik ikut berubah. Mengapa cukup mengubah satu tempat?

**1.2 Nama pendek baru.** Tambahkan beberapa instansi ke kamus `SINGKATAN` (mis. `"Department of Housing and Urban
Development": "HUD"`). Cek hasilnya di tab *Per instansi*.

**1.3 Momen penting.** Tambahkan satu baris ke `data/momen_penting.csv` dengan tanggal, judul, keterangan, dan tautan
sumber. Pastikan tes `test_momen_penting_bersumber` tetap lulus (urutan tanggal harus naik).

## Level 2 — pandas

**2.1 Kontrak per tahun.** Tulis fungsi `kontrak_baru_per_tahun(trx)` di `src/analisis.py` yang menghitung berapa
award **baru** muncul tiap tahun (petunjuk: ambil tanggal transaksi pertama setiap `award_id`). Tambahkan tesnya.

**2.2 Rata-rata ukuran kontrak.** Apakah kontrak Palantir makin besar atau hanya makin banyak? Hitung median
`nilai_usd` per `tahun_mulai` dari `as_kontrak.csv`, lalu tampilkan sebagai garis di tab *Timeline*.

**2.3 Instansi pendana vs penanda tangan.** Kolom `instansi_pendana` kadang berbeda dari `instansi`. Buat tabel
pasangan (penanda tangan → pendana) yang berbeda, urut berdasarkan nilai. Instansi mana yang paling sering membeli
"atas nama" instansi lain?

## Level 3 — Visualisasi

**3.1 Sankey.** Buat diagram Sankey `sektor → instansi → jenis kontrak` dengan `plotly.graph_objects.Sankey`.

**3.2 Garis waktu kontrak.** Buat grafik Gantt (`px.timeline`) untuk 20 kontrak terbesar: sumbu x = `mulai` sampai
`selesai`, warna = sektor. Kontrak mana yang masih berjalan sampai 2029?

**3.3 Anotasi otomatis.** Di grafik kumulatif, beri label otomatis pada bulan dengan lonjakan terbesar (selisih
bulanan tertinggi) dan cari kontrak penyebabnya.

## Level 4 — Data baru

**4.1 Perusahaan lain.** Ubah `PENERIMA_PALANTIR` dan kata kunci pencarian agar melacak perusahaan lain, misalnya
Anduril atau Scale AI. Bagian mana dari kode yang harus diubah, dan bagian mana yang tetap sama?

**4.2 Uni Eropa.** Pelajari API TED (Tenders Electronic Daily, <https://ted.europa.eu/>) dan tambahkan kontrak
Palantir di negara-negara Uni Eropa sebagai `data/eu_kontrak.csv`. Tambahkan tab baru atau gabungkan ke peta dunia.

**4.3 Laporan tahunan.** Laporan 10-K Palantir mencantumkan pendapatan dari pemerintah AS per tahun. Masukkan angka
itu ke CSV kecil, lalu bandingkan dengan total obligasi USAspending. Berapa persen yang "tidak terlihat" di data
publik, dan apa kemungkinan penyebabnya?

## Level 5 — Tantangan

**5.1 Klasifikasi produk.** Gunakan kata kunci di kolom `deskripsi` (Gotham, Foundry, AIP, Maven, Vantage, license,
FSR, engineering) untuk memberi label produk/layanan pada setiap transaksi. Seberapa banyak transaksi yang tetap
"tidak diketahui"? Bisakah TF-IDF + klasterisasi membantu?

**5.2 Deteksi anomali.** Tandai transaksi yang nilainya jauh di atas kebiasaan instansinya (mis. z-score > 3 dalam
log nilai per instansi). Apakah anomali itu bertepatan dengan momen penting?

**5.3 API sendiri.** Bungkus fungsi di `src/analisis.py` dengan FastAPI (`/sektor`, `/instansi`, `/tahun`) sehingga
data bisa dipakai aplikasi lain.
