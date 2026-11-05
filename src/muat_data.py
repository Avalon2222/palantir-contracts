"""
src/muat_data.py - Membaca CSV di data/ dan menambahkan kolom turunan
=====================================================================
Fungsi di sini murni pandas (tanpa Streamlit) supaya bisa diuji dengan pytest.
"""

from __future__ import annotations

import json
from pathlib import Path

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


def muat_transaksi_as() -> pd.DataFrame:
    """Satu baris = satu aksi kontrak (award baru, modifikasi, tambahan dana, atau koreksi negatif)."""
    df = pd.read_csv(DATA / "as_transaksi.csv", dtype={"kode_naics": "string", "modifikasi": "string"})
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    df["tahun"] = df["tanggal"].dt.year
    # Tahun fiskal federal AS dimulai 1 Oktober: 15 Okt 2025 masuk FY2026.
    df["tahun_fiskal"] = df["tahun"] + (df["tanggal"].dt.month >= 10).astype(int)
    df["nilai_usd"] = pd.to_numeric(df["nilai_usd"], errors="coerce").fillna(0.0)
    df["deskripsi"] = df["deskripsi"].fillna("")
    df["url"] = URL_AWARD_AS + df["id_usaspending"].fillna("")
    return tambah_sektor_as(df)


def muat_kontrak_as() -> pd.DataFrame:
    """Satu baris = satu kontrak; nilai_usd = total dana yang sudah diikat (obligated) sampai hari ini."""
    df = pd.read_csv(DATA / "as_kontrak.csv")
    for kol in ["mulai", "selesai"]:
        df[kol] = pd.to_datetime(df[kol], errors="coerce")
    df["tahun_mulai"] = df["mulai"].dt.year
    df["deskripsi"] = df["deskripsi"].fillna("")
    df["url"] = URL_AWARD_AS + df["id_usaspending"].fillna("")
    return tambah_sektor_as(df)


def muat_idv_as() -> pd.DataFrame:
    """Kontrak payung: plafon (batas atas) dibandingkan dengan dana yang sudah diikat lewat pesanan."""
    df = pd.read_csv(DATA / "as_idv.csv")
    for kol in ["mulai", "batas_pesan"]:
        df[kol] = pd.to_datetime(df[kol], errors="coerce")
    df["plafon_usd"] = pd.to_numeric(df["plafon_usd"], errors="coerce").fillna(0.0)
    df["diikat_usd"] = pd.to_numeric(df["diikat_usd"], errors="coerce").fillna(0.0)
    df["multi_vendor"] = df["tipe_award"].fillna("").str.upper().str.startswith("MULTIPLE")
    df["deskripsi"] = df["deskripsi"].fillna("")
    df["url"] = URL_AWARD_AS + df["id_usaspending"].fillna("")
    return tambah_sektor_as(df)


def muat_kurs() -> pd.DataFrame:
    return pd.read_csv(DATA / "kurs_gbp_usd.csv")


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
    df["nilai_gbp"] = pd.to_numeric(df["nilai_gbp"], errors="coerce").fillna(0.0)
    df["framework"] = df["framework"].astype(str).str.lower().eq("true")
    df["pembeli"] = df["pembeli"].fillna("").str.strip()
    df["pembeli_rapi"] = df["pembeli"].map(rapikan_pembeli)
    df["sektor"] = df["pembeli"].map(sektor.sektor_uk)
    kurs = muat_kurs().set_index("tahun")["gbp_ke_usd"]
    df["kurs"] = df["tahun"].map(kurs).fillna(kurs.iloc[-1])
    df["nilai_usd"] = df["nilai_gbp"] * df["kurs"]
    return df


def rapikan_pembeli(nama: str) -> str:
    """'MINISTRY OF DEFENCE' dan 'Ministry of Defence' digabung; huruf kapital semua dijadikan Title Case."""
    nama = (nama or "").strip()
    if nama.isupper() and len(nama) > 4:
        nama = nama.title().replace("Nhs ", "NHS ").replace(" Of ", " of ").replace(" And ", " and ")
        nama = nama.replace(" For ", " for ")
    alias = {"Defra": "Department for Environment, Food & Rural Affairs", "GDS": "Government Digital Service",
             "NHS North of England CSU": "North of England Commissioning Support",
             "North of England Commissioning Support": "North of England Commissioning Support"}
    return alias.get(nama, nama)


def muat_momen() -> pd.DataFrame:
    df = pd.read_csv(DATA / "momen_penting.csv")
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    return df.sort_values("tanggal").reset_index(drop=True)
