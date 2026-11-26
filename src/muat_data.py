"""
src/muat_data.py - Membaca CSV di data/ dan menambahkan kolom turunan
=====================================================================
Fungsi di sini murni pandas (tanpa Streamlit) supaya bisa diuji dengan pytest.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src import sektor

DATA = Path(__file__).resolve().parents[1] / "data"
URL_AWARD_AS = "https://www.usaspending.gov/award/"


def muat_meta() -> dict:
    try:
        return json.loads((DATA / "META.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def tambah_sektor_as(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["sub_instansi"] = df["sub_instansi"].fillna(df["instansi"])
    df["sektor"] = [sektor.sektor_as(a, b) for a, b in zip(df["instansi"], df["sub_instansi"])]
    df["nama_pendek"] = df["sub_instansi"].map(sektor.singkat)
    return df


def _uang(kolom: pd.Series) -> pd.Series:
    """Kolom nilai uang -> float. Sel rusak dan "inf" dihitung 0; inf membuat semua total jadi "-"."""
    angka = pd.to_numeric(kolom, errors="coerce")
    return angka.where(np.isfinite(angka), 0.0)


def _url_award(id_award: pd.Series) -> pd.Series:
    """Link ke halaman award di USAspending; kosong kalau id-nya tidak ada.

    Dulu id kosong menghasilkan URL_AWARD_AS saja, link yang tampil di tabel tetapi membuka halaman 404.
    """
    teks = id_award.map(lambda v: v.strip() if isinstance(v, str) else "")
    return teks.map(lambda v: URL_AWARD_AS + v if v else "")


def muat_transaksi_as() -> pd.DataFrame:
    """Satu baris = satu aksi kontrak (award baru, modifikasi, tambahan dana, atau koreksi negatif)."""
    df = pd.read_csv(DATA / "as_transaksi.csv", dtype={"kode_naics": "string", "modifikasi": "string"})
    # Satu tanggal rusak jangan sampai menggagalkan seluruh dashboard (berkas lain juga memakai coerce).
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")
    df["tahun"] = df["tanggal"].dt.year
    # Tahun fiskal federal AS dimulai 1 Oktober: 15 Okt 2025 masuk FY2026.
    df["tahun_fiskal"] = df["tahun"] + (df["tanggal"].dt.month >= 10).astype(int)
    df["nilai_usd"] = _uang(df["nilai_usd"])
    df["deskripsi"] = df["deskripsi"].fillna("")
    df["url"] = _url_award(df["id_usaspending"])
    return tambah_sektor_as(df)


def muat_kontrak_as() -> pd.DataFrame:
    """Satu baris = satu kontrak; nilai_usd = total dana yang sudah diikat (obligated) sampai hari ini."""
    df = pd.read_csv(DATA / "as_kontrak.csv")
    for kol in ["mulai", "selesai"]:
        df[kol] = pd.to_datetime(df[kol], errors="coerce")
    df["tahun_mulai"] = df["mulai"].dt.year
    # Dulu nilai kontrak dibaca apa adanya: satu sel rusak ("-") membuat kolomnya teks dan sum()
    # menyambung string; "inf" membuat total kontrak tak hingga. Disamakan dengan berkas transaksi.
    for kol in ["nilai_usd", "dibayar_usd"]:
        if kol in df.columns:
            df[kol] = _uang(df[kol])
    df["deskripsi"] = df["deskripsi"].fillna("")
    df["url"] = _url_award(df["id_usaspending"])
    return tambah_sektor_as(df)


def muat_idv_as() -> pd.DataFrame:
    """Kontrak payung: plafon (batas atas) dibandingkan dengan dana yang sudah diikat lewat pesanan."""
    df = pd.read_csv(DATA / "as_idv.csv")
    for kol in ["mulai", "batas_pesan"]:
        df[kol] = pd.to_datetime(df[kol], errors="coerce")
    # Plafon "inf" dulu membuat terpakai_persen 0% dan sisa tak hingga di tabel kontrak payung.
    df["plafon_usd"] = _uang(df["plafon_usd"])
    df["diikat_usd"] = _uang(df["diikat_usd"])
    df["multi_vendor"] = df["tipe_award"].fillna("").str.upper().str.startswith("MULTIPLE")
    df["deskripsi"] = df["deskripsi"].fillna("")
    df["url"] = _url_award(df["id_usaspending"])
    return tambah_sektor_as(df)


def muat_kurs() -> pd.DataFrame:
    return pd.read_csv(DATA / "kurs_gbp_usd.csv")


def kurs_tahunan(tahun: pd.Series, kurs: pd.DataFrame) -> pd.Series:
    """Kurs GBP->USD untuk tiap tahun. Tahun di luar tabel memakai tahun terdekat yang ada.

    Sebelumnya cadangannya baris terakhir CSV, yang belum tentu tahun terbaru kalau urutannya
    berubah, dan kontrak sebelum tahun pertama tabel ikut memakai kurs paling baru.
    """
    k = kurs.dropna(subset=["tahun", "gbp_ke_usd"]).sort_values("tahun").set_index("tahun")["gbp_ke_usd"]
    if k.empty:
        # Tanpa satu pun kurs, nilai USD memang tidak bisa dihitung; k.iloc[-1] di bawah akan IndexError.
        return pd.Series(float("nan"), index=tahun.index)
    hasil = tahun.map(k)
    kosong = hasil.isna() & tahun.notna()
    if kosong.any():
        hasil[kosong] = tahun[kosong].clip(k.index.min(), k.index.max()).map(k)
    return hasil.fillna(k.iloc[-1])


def muat_kontrak_uk() -> pd.DataFrame:
    """
    Satu baris = satu pengumuman kontrak di Contracts Finder.
    nilai_gbp = nilai kontrak yang diumumkan (bisa multi-tahun), BUKAN uang yang sudah dibayar.
    """
    df = pd.read_csv(DATA / "uk_kontrak.csv")
    for kol in ["diumumkan", "tanggal_award", "mulai", "selesai"]:
        df[kol] = pd.to_datetime(df[kol], errors="coerce")
    df["tanggal"] = df["tanggal_award"].fillna(df["diumumkan"])
    df["tahun"] = df["tanggal"].dt.year
    # Sama seperti nilai AS: "inf" lolos to_numeric dan fillna, lalu total Inggris jadi tak hingga.
    df["nilai_gbp"] = _uang(df["nilai_gbp"])
    # Suntingan manual seperti "TRUE ", "Yes", atau "1" tetap dibaca framework; dulu hanya "true" persis
    # yang dikenali, sehingga plafon framework ikut terhitung sebagai kontrak dan total Inggris membengkak.
    df["framework"] = df["framework"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "ya", "y"])
    df["pembeli"] = df["pembeli"].fillna("").str.strip()
    df["pembeli_rapi"] = df["pembeli"].map(rapikan_pembeli)
    df["sektor"] = df["pembeli"].map(sektor.sektor_uk)
    df["kurs"] = kurs_tahunan(df["tahun"], muat_kurs())
    df["nilai_usd"] = df["nilai_gbp"] * df["kurs"]
    return df


SINGKATAN_UK = {"NHS", "HM", "UK", "MOD", "HMRC", "DVLA", "GDS", "CSU", "ICB", "CCG", "DWP", "FCDO"}


def _judul(kata: str) -> str:
    """Seperti str.title(), tetapi huruf setelah apostrof tetap kecil: "MAJESTY'S" -> "Majesty's"."""
    return re.sub(r"[A-Za-z]+(?:'[A-Za-z]+)?", lambda m: m.group(0).capitalize(), kata)


def rapikan_pembeli(nama: str) -> str:
    """'MINISTRY OF DEFENCE' dan 'Ministry of Defence' digabung; huruf kapital semua dijadikan Title Case."""
    # Spasi ganda/tab dari CSV dirapikan dulu: "MINISTRY  OF DEFENCE" sama dengan "MINISTRY OF DEFENCE".
    nama = " ".join(nama.split()) if isinstance(nama, str) else ""
    # Nama yang ditulis huruf kecil semua diperlakukan sama seperti yang huruf besar semua.
    if nama.islower() and len(nama) > 4:
        nama = nama.upper()
    if nama.isupper() and len(nama) > 4:
        # Singkatan resmi tetap huruf besar: "HM TREASURY" -> "HM Treasury", bukan "Hm Treasury".
        # Tanda baca di sekitar singkatan diabaikan saat dicek: "(MOD)" dan "NHS," tetap huruf besar.
        kata = [k if k.strip("(),.&/") in SINGKATAN_UK else _judul(k) for k in nama.split(" ")]
        nama = " ".join(kata)
        # Kata sambung di tengah nama ditulis kecil, seperti di situs pemerintah Inggris.
        for sambung in ("Of", "And", "For", "The", "In", "On", "To"):
            nama = nama.replace(f" {sambung} ", f" {sambung.lower()} ")
    alias = {"Defra": "Department for Environment, Food & Rural Affairs", "GDS": "Government Digital Service",
             "NHS North of England CSU": "North of England Commissioning Support",
             "North of England Commissioning Support": "North of England Commissioning Support"}
    return alias.get(nama, nama)


def muat_momen() -> pd.DataFrame:
    df = pd.read_csv(DATA / "momen_penting.csv")
    # Momen dengan tanggal rusak tidak bisa digambar di linimasa; buang saja daripada aplikasi gagal.
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")
    return df.dropna(subset=["tanggal"]).sort_values("tanggal").reset_index(drop=True)
