# Sumber data

Semua file di folder ini dibuat oleh `scripts/kumpulkan_data.py` (kecuali `momen_penting.csv` yang dikurasi manual).
Tanggal pengambilan terakhir tercatat di `META.json`.

## 1. USAspending.gov (Amerika Serikat)

- **Penerbit:** U.S. Department of the Treasury, Bureau of the Fiscal Service
- **API:** <https://api.usaspending.gov/> (tanpa key, tanpa batas resmi)
- **Lisensi:** domain publik (karya pemerintah federal AS)
- **Filter:** `recipient_search_text = "Palantir"`, jenis kontrak A–D (kontrak biasa) dan IDV (kontrak payung),
  1 Oktober 2007 sampai hari pengambilan. Hasil disaring dengan daftar putih nama penerima
  `PALANTIR TECHNOLOGIES INC.`, `PALANTIR USG INC`, `PALANTIR USA INC.`.

### `as_transaksi.csv` — endpoint `search/spending_by_transaction`

| Kolom | Arti |
|---|---|
| `tanggal` | Action date: tanggal aksi kontrak ditandatangani |
| `award_id` | Nomor kontrak (PIID) |
| `penerima` | Nama entitas Palantir penerima |
| `nilai_usd` | Obligasi pada aksi ini (USD). Bisa negatif bila dana ditarik kembali (de-obligasi) |
| `instansi`, `sub_instansi` | Awarding agency dan sub-agency (instansi yang menandatangani kontrak) |
| `instansi_pendana`, `sub_instansi_pendana` | Funding agency (instansi yang membayar; kadang berbeda) |
| `deskripsi` | Deskripsi transaksi dari petugas kontrak |
| `modifikasi` | Nomor modifikasi (0 = award awal) |
| `jenis_aksi` | Kode action type (A = pekerjaan baru, B = pesanan tambahan, C = pembatalan sebagian, M = modifikasi lain, dst.) |
| `negara_bagian`, `kota_pelaksanaan`, `negara_pelaksanaan` | Place of performance |
| `kode_psc`, `deskripsi_psc` | Product/Service Code |
| `kode_naics` | Kode industri NAICS |
| `id_usaspending` | ID unik untuk tautan `https://www.usaspending.gov/award/<id>` |

### `as_kontrak.csv` — endpoint `search/spending_by_award`

Satu baris per kontrak. `nilai_usd` = total obligasi kontrak sampai hari pengambilan, `dibayar_usd` = total outlay
(uang yang sudah dibayarkan; sering 0 untuk kontrak lama karena pelaporannya baru dimulai 2017). `mulai`/`selesai` =
periode pelaksanaan. `jenis` = definitive contract, delivery order, purchase order, atau BPA call.

### `as_idv.csv` — endpoint `search/spending_by_award` + `awards/{id}` + `idvs/amounts/{id}`

| Kolom | Arti |
|---|---|
| `plafon_usd` | `base_and_all_options`: batas atas nilai kontrak payung bila semua opsi diambil |
| `diikat_usd` | Total obligasi pesanan anak + cucu di bawah kontrak payung ini |
| `jumlah_pesanan` | Jumlah pesanan (task/delivery order) |
| `tipe_award` | `SINGLE AWARD` (khusus Palantir) atau `MULTIPLE AWARD` (plafon dibagi dengan vendor lain) |
| `batas_pesan` | Last date to order |

## 2. Contracts Finder (Inggris)

- **Penerbit:** UK Cabinet Office
- **API:** `POST https://www.contractsfinder.service.gov.uk/api/rest/2/search_notices/json`
- **Lisensi:** [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- **Filter:** kata kunci "Palantir", tipe *Contract*, status *Awarded*, lalu hanya yang `awardedSupplier`-nya Palantir.

### `uk_kontrak.csv`

| Kolom | Arti |
|---|---|
| `diumumkan`, `tanggal_award` | Tanggal pengumuman dan tanggal kontrak diberikan |
| `mulai`, `selesai` | Periode kontrak |
| `pembeli` | Organisasi sektor publik pembeli |
| `judul`, `deskripsi` | Dari pengumuman |
| `pemasok` | Nama pemenang (framework ditulis sebagai "salah satu pemasok framework") |
| `nilai_gbp` | Nilai kontrak yang diumumkan (GBP) |
| `framework` | `True` bila daftar pemenang berisi banyak pemasok; tidak dijumlahkan di dashboard |
| `cpv` | Kategori pengadaan (Common Procurement Vocabulary) |
| `kode_pos`, `lat`, `lon`, `wilayah` | Lokasi pembeli |
| `url` | Halaman pengumuman |

## 3. `kurs_gbp_usd.csv` — Frankfurter

Rata-rata tahunan kurs harian GBP→USD dari European Central Bank lewat <https://frankfurter.dev/>. Dipakai untuk
membandingkan skala AS dan Inggris dalam satu mata uang.

## 4. `momen_penting.csv` — kurasi manual

12 peristiwa (gugatan 2016, IPO 2020, NHS, Maven, ICE ImmigrationOS, Army Enterprise Agreement, dan lainnya). Setiap
baris punya kolom `sumber` berisi tautan berita atau catatan resmi. Baris yang merujuk kontrak di data ini memakai
tautan USAspending atau Contracts Finder langsung.

## Catatan kualitas

- Total `as_transaksi.csv` dan `as_kontrak.csv` selisih kurang dari 1% (dicek di `tests/test_muat_data.py`).
- Kontrak klasifikasi tidak dilaporkan ke USAspending; angka adalah batas bawah.
- Place of performance sering diisi alamat kantor kontraktor, bukan lokasi instansi.
