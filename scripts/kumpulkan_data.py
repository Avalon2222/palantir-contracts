"""
scripts/kumpulkan_data.py - Kumpulkan kontrak pemerintah Palantir dari sumber publik
====================================================================================
Jalankan dari folder utama repo:

    python scripts/kumpulkan_data.py

Yang diambil (semuanya gratis, tanpa API key):
  1. USAspending.gov (Amerika Serikat)
       - setiap transaksi kontrak (obligasi dana) ke entitas Palantir  -> data/as_transaksi.csv
       - ringkasan per kontrak (award)                               -> data/as_kontrak.csv
       - kontrak payung / IDV beserta plafonnya                      -> data/as_idv.csv
  2. Contracts Finder (Inggris)
       - pengumuman kontrak yang dimenangkan Palantir                -> data/uk_kontrak.csv
  3. Frankfurter (kurs ECB) untuk rata-rata kurs GBP->USD per tahun  -> data/kurs_gbp_usd.csv

Hasil mentah ditulis apa adanya; pembersihan dan pemetaan sektor dilakukan di src/.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

AKAR = Path(__file__).resolve().parents[1]
DATA = AKAR / "data"
API_AS = "https://api.usaspending.gov/api/v2"
API_UK = "https://www.contractsfinder.service.gov.uk/api/rest/2/search_notices/json"
API_KURS = "https://api.frankfurter.dev/v1"
HEADER = {"User-Agent": "palantir-contracts/1.0 (portfolio project)", "Content-Type": "application/json"}

# Nama penerima di USAspending yang benar-benar Palantir Technologies.
# Pencarian teks "Palantir" juga menemukan perusahaan lain (mis. "Lonely Mountain Palantir Enterprises",
# "Palantir.net Inc"), jadi kita saring dengan daftar putih ini.
PENERIMA_PALANTIR = re.compile(r"^PALANTIR (TECHNOLOGIES|USG|USA)\b", re.I)
TIPE_KONTRAK = ["A", "B", "C", "D"]
TIPE_IDV = ["IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B", "IDV_B_C", "IDV_C", "IDV_D", "IDV_E"]
AWAL = "2007-10-01"  # data USAspending dimulai tahun fiskal 2008


def post(url: str, payload: dict, percobaan: int = 4) -> dict:
    """POST dengan retry sederhana (API publik kadang lambat)."""
    for i in range(percobaan):
        try:
            r = requests.post(url, json=payload, headers=HEADER, timeout=90)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if i == percobaan - 1:
                raise
            print(f"  ulang ({e.__class__.__name__}), tunggu {2 ** i} detik...")
            time.sleep(2 ** i)
    return {}


def get(url: str, params: dict | None = None) -> dict:
    for i in range(4):
        try:
            r = requests.get(url, params=params, headers=HEADER, timeout=90)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if i == 3:
                raise
            time.sleep(2 ** i)
    return {}


def halaman_semua(endpoint: str, payload: dict) -> list[dict]:
    """Ambil semua halaman dari endpoint pencarian USAspending (100 baris per halaman)."""
    hasil, halaman = [], 1
    while True:
        res = post(f"{API_AS}/{endpoint}/", {**payload, "limit": 100, "page": halaman})
        hasil += res.get("results", [])
        if not res.get("page_metadata", {}).get("hasNext"):
            return hasil
        halaman += 1


def filter_as(tipe: list[str]) -> dict:
    hari_ini = date.today().isoformat()
    return {"recipient_search_text": ["Palantir"], "award_type_codes": tipe,
            "time_period": [{"start_date": AWAL, "end_date": hari_ini}]}


# ----------------------------------------------------------------------------
# 1. USASPENDING
# ----------------------------------------------------------------------------
def ambil_transaksi_as() -> pd.DataFrame:
    print("USAspending: transaksi kontrak...")
    kolom = ["Action Date", "Award ID", "Recipient Name", "Transaction Amount", "Awarding Agency",
             "Awarding Sub Agency", "Funding Agency", "Funding Sub Agency", "Transaction Description", "Mod",
             "Action Type", "pop_state_code", "pop_country_name", "pop_city_name", "product_or_service_code",
             "product_or_service_description", "naics_code", "generated_internal_id"]
    baris = halaman_semua("search/spending_by_transaction", {
        "filters": filter_as(TIPE_KONTRAK), "fields": kolom, "sort": "Action Date", "order": "asc"})
    df = pd.DataFrame(baris)
    df = df[df["Recipient Name"].fillna("").str.match(PENERIMA_PALANTIR)]
    df = df.rename(columns={
        "Action Date": "tanggal", "Award ID": "award_id", "Recipient Name": "penerima",
        "Transaction Amount": "nilai_usd", "Awarding Agency": "instansi", "Awarding Sub Agency": "sub_instansi",
        "Funding Agency": "instansi_pendana", "Funding Sub Agency": "sub_instansi_pendana",
        "Transaction Description": "deskripsi", "Mod": "modifikasi", "Action Type": "jenis_aksi",
        "pop_state_code": "negara_bagian", "pop_country_name": "negara_pelaksanaan", "pop_city_name": "kota_pelaksanaan",
        "product_or_service_code": "kode_psc", "product_or_service_description": "deskripsi_psc",
        "naics_code": "kode_naics", "generated_internal_id": "id_usaspending"})
    df = df.drop(columns=[c for c in df.columns if c not in kolom_transaksi()], errors="ignore")
    print(f"  {len(df):,} transaksi")
    return df.sort_values(["tanggal", "award_id"]).reset_index(drop=True)


def kolom_transaksi() -> list[str]:
    return ["tanggal", "award_id", "penerima", "nilai_usd", "instansi", "sub_instansi", "instansi_pendana",
            "sub_instansi_pendana", "deskripsi", "modifikasi", "jenis_aksi", "negara_bagian", "negara_pelaksanaan",
            "kota_pelaksanaan", "kode_psc", "deskripsi_psc", "kode_naics", "id_usaspending"]


def ambil_kontrak_as() -> pd.DataFrame:
    print("USAspending: ringkasan kontrak...")
    kolom = ["Award ID", "Recipient Name", "Award Amount", "Total Outlays", "Awarding Agency", "Awarding Sub Agency",
             "Start Date", "End Date", "Description", "Contract Award Type", "Place of Performance State Code",
             "Place of Performance Country Code", "psc_description", "naics_description", "generated_internal_id"]
    df = pd.DataFrame(halaman_semua("search/spending_by_award", {
        "filters": filter_as(TIPE_KONTRAK), "fields": kolom, "sort": "Award Amount", "order": "desc"}))
    df = df[df["Recipient Name"].fillna("").str.match(PENERIMA_PALANTIR)]
    df = df.rename(columns={
        "Award ID": "award_id", "Recipient Name": "penerima", "Award Amount": "nilai_usd",
        "Total Outlays": "dibayar_usd", "Awarding Agency": "instansi", "Awarding Sub Agency": "sub_instansi",
        "Start Date": "mulai", "End Date": "selesai", "Description": "deskripsi", "Contract Award Type": "jenis",
        "Place of Performance State Code": "negara_bagian", "Place of Performance Country Code": "kode_negara",
        "psc_description": "deskripsi_psc", "naics_description": "deskripsi_naics",
        "generated_internal_id": "id_usaspending"})
    df = df.drop(columns=["internal_id", "awarding_agency_id", "agency_slug"], errors="ignore")
    print(f"  {len(df):,} kontrak")
    return df.reset_index(drop=True)


def ambil_idv_as() -> pd.DataFrame:
    """
    IDV (Indefinite Delivery Vehicle) = kontrak payung. Nilainya bukan uang yang sudah dibayar, melainkan
    plafon: batas atas pesanan (task order) yang boleh dibuat di bawahnya. Jumlah yang sudah diikat
    dihitung dari pesanan-pesanan anaknya.
    """
    print("USAspending: kontrak payung (IDV)...")
    kolom = ["Award ID", "Recipient Name", "Awarding Agency", "Awarding Sub Agency", "Start Date",
             "Last Date to Order", "Description", "Contract Award Type", "generated_internal_id"]
    df = pd.DataFrame(halaman_semua("search/spending_by_award", {
        "filters": filter_as(TIPE_IDV), "fields": kolom, "sort": "Award ID", "order": "asc"}))
    df = df[df["Recipient Name"].fillna("").str.match(PENERIMA_PALANTIR)].reset_index(drop=True)
    rinci = []
    for gid in df["generated_internal_id"]:
        detail = get(f"{API_AS}/awards/{gid}/")          # plafon = base_and_all_options
        jumlah = get(f"{API_AS}/idvs/amounts/{gid}/")     # total pesanan anak dan cucu
        rinci.append({
            "generated_internal_id": gid,
            "plafon_usd": detail.get("base_and_all_options"),
            "diikat_usd": (jumlah.get("child_award_total_obligation") or 0)
                          + (jumlah.get("grandchild_award_total_obligation") or 0),
            "jumlah_pesanan": (jumlah.get("child_award_count") or 0) + (jumlah.get("grandchild_award_count") or 0),
            # MULTIPLE AWARD = plafon dibagi bersama banyak vendor, jadi bukan "milik" Palantir sendiri
            "tipe_award": (detail.get("latest_transaction_contract_data") or {}).get(
                "multiple_or_single_award_description"),
        })
        time.sleep(0.2)
    df = df.merge(pd.DataFrame(rinci), on="generated_internal_id", how="left")
    df = df.rename(columns={
        "Award ID": "award_id", "Recipient Name": "penerima", "Awarding Agency": "instansi",
        "Awarding Sub Agency": "sub_instansi", "Start Date": "mulai", "Last Date to Order": "batas_pesan",
        "Description": "deskripsi", "Contract Award Type": "jenis", "generated_internal_id": "id_usaspending"})
    df = df.drop(columns=["internal_id", "awarding_agency_id", "agency_slug"], errors="ignore")
    print(f"  {len(df):,} IDV")
    return df.sort_values("plafon_usd", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------
# 2. CONTRACTS FINDER (INGGRIS)
# ----------------------------------------------------------------------------
KOLOM_UK = ["id", "id_pengumuman", "diumumkan", "tanggal_award", "mulai", "selesai", "pembeli", "judul", "deskripsi",
            "pemasok", "nilai_gbp", "framework", "cpv", "kode_pos", "lat", "lon", "wilayah", "url"]


def ambil_kontrak_uk() -> pd.DataFrame:
    """
    Contracts Finder memuat pengumuman kontrak sektor publik Inggris (nilai di atas ~£12 ribu sejak 2015).
    Pencarian kata kunci "Palantir" juga menangkap kontrak orang lain yang hanya menyebut Palantir
    (mis. migrasi keluar dari Palantir), jadi disaring: pemenangnya harus Palantir dan hanya satu pemasok.
    Kerangka (framework) multi-pemasok seperti CCS Back Office Software disimpan terpisah (kolom framework).
    """
    print("Contracts Finder: pengumuman kontrak...")
    res = post(API_UK, {"searchCriteria": {"keyword": "Palantir", "types": ["Contract"], "statuses": ["Awarded"]},
                        "size": 1000})
    baris = []
    for n in res.get("noticeList", []):
        i = n["item"]
        pemasok = (i.get("awardedSupplier") or "").strip()
        if "palantir" not in pemasok.lower():
            continue
        framework = pemasok.count(",") >= 3  # daftar panjang nama pemasok = framework
        bagian = (i.get("coordinates") or "").split(",")
        lat, lon = (bagian[0].strip(), bagian[1].strip()) if len(bagian) >= 2 else (None, None)
        baris.append({
            "id": i["id"], "id_pengumuman": i.get("noticeIdentifier"),
            "diumumkan": (i.get("publishedDate") or "")[:10], "tanggal_award": (i.get("awardedDate") or "")[:10],
            "mulai": (i.get("start") or "")[:10], "selesai": (i.get("end") or "")[:10],
            "pembeli": i.get("organisationName"), "judul": i.get("title"), "deskripsi": i.get("description"),
            "pemasok": pemasok if not framework else "Palantir (salah satu pemasok framework)",
            "nilai_gbp": i.get("awardedValue"), "framework": framework,
            "cpv": i.get("cpvDescription"), "kode_pos": i.get("postcode"), "lat": lat or None, "lon": lon or None,
            "wilayah": i.get("regionText"),
            "url": f"https://www.contractsfinder.service.gov.uk/Notice/{i['id']}",
        })
    # Kolom ditulis eksplisit supaya hasil pencarian kosong tetap menghasilkan tabel yang utuh.
    df = pd.DataFrame(baris, columns=KOLOM_UK)
    for kol in ["judul", "deskripsi", "pembeli", "pemasok"]:
        df[kol] = (df[kol].fillna("").str.replace("&amp;", "&", regex=False)
                   .str.replace("&#39;", "'", regex=False).str.replace(r"\s+", " ", regex=True).str.strip())
    print(f"  {len(df):,} pengumuman ({int(df['framework'].sum())} framework)")
    return df.sort_values("diumumkan").reset_index(drop=True)


# ----------------------------------------------------------------------------
# 3. KURS GBP -> USD
# ----------------------------------------------------------------------------
def ambil_kurs(tahun_awal: int = 2015) -> pd.DataFrame:
    print("Frankfurter: kurs GBP->USD...")
    akhir = date.today().isoformat()
    res = get(f"{API_KURS}/{tahun_awal}-01-01..{akhir}", {"from": "GBP", "to": "USD"})
    harian = pd.Series({k: v["USD"] for k, v in res["rates"].items()})
    harian.index = pd.to_datetime(harian.index)
    tahunan = harian.groupby(harian.index.year).mean().round(4)
    return pd.DataFrame({"tahun": tahunan.index, "gbp_ke_usd": tahunan.values})


def main() -> int:
    DATA.mkdir(exist_ok=True)
    trx = ambil_transaksi_as()
    kontrak = ambil_kontrak_as()
    idv = ambil_idv_as()
    uk = ambil_kontrak_uk()
    kurs = ambil_kurs()

    trx.to_csv(DATA / "as_transaksi.csv", index=False)
    kontrak.to_csv(DATA / "as_kontrak.csv", index=False)
    idv.to_csv(DATA / "as_idv.csv", index=False)
    uk.to_csv(DATA / "uk_kontrak.csv", index=False)
    kurs.to_csv(DATA / "kurs_gbp_usd.csv", index=False)

    meta = {
        "diperbarui": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "transaksi_as": len(trx), "kontrak_as": len(kontrak), "idv_as": len(idv), "kontrak_uk": len(uk),
        "sumber": ["api.usaspending.gov", "contractsfinder.service.gov.uk", "api.frankfurter.dev"],
    }
    (DATA / "META.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("Selesai:", meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
