"""Tes bagian pengumpul data di scripts/kumpulkan_data.py yang bisa dicek tanpa internet."""

import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import requests

PATH = Path(__file__).resolve().parents[1] / "scripts" / "kumpulkan_data.py"
spec = importlib.util.spec_from_file_location("kumpulkan_data", PATH)
kd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kd)


@pytest.mark.parametrize("nama, cocok", [
    ("PALANTIR TECHNOLOGIES INC.", True),
    ("Palantir USG, Inc.", True),
    ("PALANTIR USA INC", True),
    ("LONELY MOUNTAIN PALANTIR ENTERPRISES", False),
    ("PALANTIR.NET INC", False),
])
def test_daftar_putih_penerima(nama, cocok):
    assert bool(kd.PENERIMA_PALANTIR.match(nama)) is cocok


def test_filter_as_sampai_hari_ini():
    f = kd.filter_as(kd.TIPE_KONTRAK)
    assert f["recipient_search_text"] == ["Palantir"]
    assert f["award_type_codes"] == ["A", "B", "C", "D"]
    assert f["time_period"] == [{"start_date": kd.AWAL, "end_date": date.today().isoformat()}]


def test_halaman_semua_ikuti_has_next(monkeypatch):
    diminta = []

    def palsu(url, payload):
        diminta.append(payload["page"])
        return {"results": [{"id": payload["page"]}], "page_metadata": {"hasNext": payload["page"] < 3}}

    monkeypatch.setattr(kd, "post", palsu)
    hasil = kd.halaman_semua("search/spending_by_award", {"filters": {}})
    assert diminta == [1, 2, 3]
    assert [h["id"] for h in hasil] == [1, 2, 3]


def test_post_ulang_lalu_berhasil(monkeypatch):
    class Respons:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    percobaan = []

    def palsu(url, json, headers, timeout):
        percobaan.append(1)
        if len(percobaan) < 3:
            raise requests.ConnectionError("putus")
        return Respons()

    monkeypatch.setattr(kd.requests, "post", palsu)
    monkeypatch.setattr(kd.time, "sleep", lambda s: None)
    assert kd.post("https://contoh", {}) == {"ok": True}
    assert len(percobaan) == 3


def test_post_menyerah_setelah_batas(monkeypatch):
    def gagal(url, json, headers, timeout):
        raise requests.Timeout("lambat")

    monkeypatch.setattr(kd.requests, "post", gagal)
    monkeypatch.setattr(kd.time, "sleep", lambda s: None)
    with pytest.raises(requests.Timeout):
        kd.post("https://contoh", {}, percobaan=2)


def test_ambil_kurs_rata_rata_per_tahun(monkeypatch):
    rates = {"2023-01-02": {"USD": 1.20}, "2023-06-01": {"USD": 1.30}, "2024-01-02": {"USD": 1.27}}
    monkeypatch.setattr(kd, "get", lambda url, params=None: {"rates": rates})
    df = kd.ambil_kurs(2023)
    assert df["tahun"].tolist() == [2023, 2024]
    assert df["gbp_ke_usd"].tolist() == [1.25, 1.27]


def _pengumuman(id_, pemasok, koordinat="51.5,-0.12", **ubah):
    item = {"id": id_, "noticeIdentifier": f"N-{id_}", "publishedDate": "2024-03-01T10:00:00Z",
            "awardedDate": "2024-02-20T00:00:00Z", "start": "2024-04-01", "end": "2027-03-31",
            "organisationName": "NHS England", "title": "Data &amp; analytics  platform",
            "description": "Federated   data platform", "awardedSupplier": pemasok, "awardedValue": 1000.0,
            "cpvDescription": "Software", "postcode": "LS1", "coordinates": koordinat, "regionText": "England"}
    item.update(ubah)
    return {"item": item}


def test_ambil_kontrak_uk_saring_dan_rapikan(monkeypatch):
    daftar = [
        _pengumuman("a", "Palantir Technologies UK Ltd"),
        _pengumuman("b", "Accenture"),                                   # bukan Palantir
        _pengumuman("c", "A Ltd, B Ltd, Palantir Ltd, C Ltd", koordinat="51.5"),  # framework, koordinat rusak
    ]
    monkeypatch.setattr(kd, "post", lambda url, payload: {"noticeList": daftar})
    df = kd.ambil_kontrak_uk()
    assert df["id"].tolist() == ["a", "c"]
    a, c = df.iloc[0], df.iloc[1]
    assert a["judul"] == "Data & analytics platform" and a["deskripsi"] == "Federated data platform"
    assert a["lat"] == "51.5" and a["lon"] == "-0.12" and not a["framework"]
    assert c["framework"] and c["pemasok"].startswith("Palantir (salah satu")
    assert pd.isna(c["lat"]) and pd.isna(c["lon"])


def test_ambil_kontrak_uk_tanpa_hasil_tetap_tabel_utuh(monkeypatch):
    monkeypatch.setattr(kd, "post", lambda url, payload: {"noticeList": [_pengumuman("x", "Accenture")]})
    df = kd.ambil_kontrak_uk()
    assert df.empty and list(df.columns) == kd.KOLOM_UK


def test_ambil_transaksi_as_cuma_palantir_dan_kolom_rapi(monkeypatch):
    baris = [
        {"Action Date": "2020-05-02", "Award ID": "B2", "Recipient Name": "PALANTIR USG, INC.", "Transaction Amount": 5.0,
         "internal_id": 1, "Mod": "P00001"},
        {"Action Date": "2020-05-01", "Award ID": "A1", "Recipient Name": "Palantir Technologies Inc.",
         "Transaction Amount": 10.0, "internal_id": 2, "Mod": "0"},
        {"Action Date": "2020-05-01", "Award ID": "Z9", "Recipient Name": "PALANTIRI CONSULTING", "Transaction Amount": 1.0},
        {"Action Date": "2020-05-01", "Award ID": "Y8", "Recipient Name": None, "Transaction Amount": 1.0},
    ]
    monkeypatch.setattr(kd, "halaman_semua", lambda endpoint, payload: baris)
    df = kd.ambil_transaksi_as()
    assert df["award_id"].tolist() == ["A1", "B2"]          # urut tanggal, nama mirip tidak ikut
    assert set(df.columns) <= set(kd.kolom_transaksi())    # kolom internal API dibuang
    assert df.loc[0, "nilai_usd"] == 10.0 and df.loc[1, "modifikasi"] == "P00001"


def test_ambil_kontrak_as_ganti_nama_kolom(monkeypatch):
    baris = [{"Award ID": "K1", "Recipient Name": "PALANTIR TECHNOLOGIES INC.", "Award Amount": 9.0,
              "Total Outlays": 4.0, "internal_id": 7, "agency_slug": "army"},
             {"Award ID": "K2", "Recipient Name": "LOCKHEED MARTIN", "Award Amount": 99.0, "Total Outlays": 0.0}]
    monkeypatch.setattr(kd, "halaman_semua", lambda endpoint, payload: baris)
    df = kd.ambil_kontrak_as()
    assert df["award_id"].tolist() == ["K1"]
    assert {"nilai_usd", "dibayar_usd", "penerima"} <= set(df.columns)
    assert not {"internal_id", "agency_slug"} & set(df.columns)
