# 📚 Belajar dari proyek ini

Panduan ini menjelaskan cara proyek dibangun dari nol, langkah demi langkah. Cocok dibaca sambil membuka kodenya.
Tidak perlu pengalaman dengan data pengadaan; cukup Python dasar dan sedikit pandas.

## Langkah 0 — Pertanyaan dulu, baru kode

Dashboard yang bagus berangkat dari pertanyaan yang jelas:

1. Berapa total uang pemerintah yang masuk ke Palantir?
2. Dari instansi dan sektor mana?
3. Bagaimana trennya dari tahun ke tahun?
4. Angka besar di berita ("$10 miliar") itu uang sungguhan atau bukan?

Setiap tab di `app.py` menjawab satu pertanyaan. Kalau kamu membuat proyek sendiri, tulis daftar pertanyaan seperti
ini sebelum menulis satu baris kode.

## Langkah 1 — Mengenal istilah pengadaan

| Istilah | Arti sederhana |
|---|---|
| **Award** | Satu kontrak. Punya nomor unik (PIID), misalnya `W519TC25D0039` |
| **Transaksi / action** | Setiap perubahan pada kontrak: award awal, tambahan dana, perpanjangan, pembatalan |
| **Obligasi** (*obligation*) | Dana yang sudah diikat secara hukum. Ini yang dijumlahkan di dashboard |
| **Outlay** | Uang yang benar-benar sudah ditransfer |
| **IDV** / **BPA** | Kontrak payung: belum ada uangnya, hanya aturan dan **plafon**. Uang muncul saat instansi membuat **pesanan** (*task order*) di bawahnya |
| **Plafon** (*ceiling*) | Batas atas nilai semua pesanan. Angka inilah yang biasanya jadi judul berita |
| **Single / multiple award** | Kontrak payung untuk satu vendor saja, atau dibagi bersama banyak vendor |
| **Place of performance** | Lokasi pekerjaan dicatat. Sering kali kantor kontraktor |
| **Tahun fiskal AS** | Mulai 1 Oktober. 15 Oktober 2025 masuk FY2026 |

## Langkah 2 — Mengambil data dari API

Buka `scripts/kumpulkan_data.py`. Polanya sama untuk semua endpoint USAspending:

```python
payload = {
    "filters": {"recipient_search_text": ["Palantir"], "award_type_codes": ["A", "B", "C", "D"]},
    "fields": ["Action Date", "Award ID", "Transaction Amount", "Awarding Sub Agency"],
    "limit": 100,
    "page": 1,
}
res = requests.post("https://api.usaspending.gov/api/v2/search/spending_by_transaction/", json=payload).json()
```

Hasil dibagi per halaman. Fungsi `halaman_semua()` terus meminta halaman berikutnya selama
`page_metadata.hasNext` bernilai `True`.

**Pelajaran penting:** pencarian teks itu longgar. "Palantir" juga cocok dengan *Palantir.net Inc* (agensi web) dan
*Lonely Mountain Palantir Enterprises*. Karena itu hasilnya disaring dengan regex daftar putih:

```python
PENERIMA_PALANTIR = re.compile(r"^PALANTIR (TECHNOLOGIES|USG|USA)\b", re.I)
df = df[df["Recipient Name"].fillna("").str.match(PENERIMA_PALANTIR)]
```

Selalu periksa nilai unik kolom kunci (`df["Recipient Name"].value_counts()`) sebelum percaya pada total.

## Langkah 3 — Data Inggris dan jebakan kata kunci

Contracts Finder punya dua API. Yang berformat OCDS ternyata **mengabaikan** parameter `keyword` (hasilnya kontrak
acak terbaru), jadi dipakai endpoint `search_notices/json` yang benar-benar mencari. Setelah itu ada dua jebakan:

- Pengumuman yang *menyebut* Palantir tetapi pemenangnya perusahaan lain, misalnya kontrak "transisi dari Palantir ke
  sistem lain". Solusi: wajibkan `awardedSupplier` berisi "palantir".
- Framework berisi puluhan pemasok dengan nilai miliaran. Solusi: tandai `framework=True` bila daftar pemasok panjang,
  lalu jangan dijumlahkan.

## Langkah 4 — Memetakan instansi ke sektor

USAspending tidak punya kolom "sektor". Kita membuatnya sendiri di `src/sektor.py` dengan aturan berurutan:

```python
ATURAN_AS = [
    (r"Department of Defense", None, MILITER),
    (r"Homeland Security", r"Immigration and Customs|Customs and Border|Citizenship", IMIGRASI),
    (r"Homeland Security", None, HUKUM),
    ...
]
```

Urutan penting: aturan ICE harus dicek **sebelum** aturan "DHS lainnya". Coba tukar urutannya lalu jalankan
`pytest tests/test_sektor.py` untuk melihat tes yang gagal.

## Langkah 5 — Kolom turunan di `src/muat_data.py`

- `tahun` dan `tahun_fiskal` dari tanggal.
- `sektor` dan `nama_pendek` dari aturan di langkah 4.
- `url` ke halaman resmi agar setiap angka bisa dicek ulang.
- `nilai_usd` untuk kontrak Inggris, memakai kurs rata-rata tahun kontraknya.

Prinsipnya: file `muat_data.py` dan `analisis.py` tidak mengimpor Streamlit, sehingga bisa diuji dengan pytest tanpa
membuka browser.

## Langkah 6 — Agregasi dengan pandas

Tiga pola yang paling sering dipakai di `src/analisis.py`:

```python
# 1. Total per kelompok
trx.groupby("sektor", as_index=False)["nilai_usd"].sum()

# 2. Tabel silang tahun x sektor (untuk stacked bar)
trx.pivot_table(index="tahun", columns="sektor", values="nilai_usd", aggfunc="sum", fill_value=0)

# 3. Total berjalan bulanan (untuk grafik kumulatif)
trx.set_index("tanggal")["nilai_usd"].resample("MS").sum().cumsum()
```

Rumus pertumbuhan rata-rata tahunan (CAGR):

```
CAGR = (nilai_akhir / nilai_awal) ^ (1 / jumlah_tahun) - 1
```

Dari 2016 ($130 juta) ke 2025 ($1,45 miliar), CAGR sekitar 31% per tahun.

## Langkah 7 — Memilih grafik

| Pertanyaan | Grafik | Alasan |
|---|---|---|
| Komposisi per tahun | Stacked bar | Tinggi batang = total, warna = sektor |
| Akumulasi dan momen | Garis + penanda | Cerita "kapan melonjak" paling jelas di kurva kumulatif |
| Bagian dari keseluruhan | Treemap / bar horizontal | Lebih mudah dibandingkan daripada pie |
| Kapan setiap instansi aktif | Heatmap dinormalisasi per baris | Tanpa normalisasi, Army menenggelamkan semua instansi lain |
| Plafon vs realisasi | Dua bar bertumpuk (overlay) | Bar abu-abu = janji, bar oranye = uang yang sudah diikat |
| Lokasi | Gelembung (dunia), choropleth (negara bagian) | Nilai AS ribuan kali negara lain; gelembung tetap terbaca |

## Langkah 8 — Streamlit

`app.py` dibaca dari atas ke bawah setiap kali pengguna mengubah filter. Agar cepat:

- `@st.cache_data` pada fungsi pemuat data: CSV hanya dibaca sekali.
- Filter sidebar menghasilkan DataFrame `trx`, `uk`, `idv` yang dipakai semua tab.
- `st.column_config.LinkColumn` mengubah kolom URL menjadi tautan "buka ↗".

Satu jebakan kecil: Streamlit membaca `$...$` sebagai rumus LaTeX. Teks berisi dua tanda dolar harus di-escape
(`\$`), lihat fungsi `md()` di `app.py`.

## Langkah 9 — Tes dan otomatisasi

- `tests/test_sektor.py` dan `tests/test_analisis.py` memakai data kecil buatan sendiri sehingga hasilnya bisa
  dihitung dengan tangan.
- `tests/test_muat_data.py` memeriksa snapshot asli: semua penerima benar-benar Palantir, total transaksi dan total
  kontrak cocok, tahun fiskal benar.
- `.github/workflows/tests.yml` menjalankan semua tes pada setiap push.
- `.github/workflows/perbarui-data.yml` mengambil ulang data setiap Senin, menjalankan tes, lalu commit bila ada
  perubahan. Data yang gagal tes tidak akan pernah masuk.

## Ide lanjutan

Lihat [LATIHAN.md](LATIHAN.md) untuk latihan bertingkat, mulai dari mengganti perusahaan yang dilacak sampai
menambahkan sumber data Uni Eropa.
