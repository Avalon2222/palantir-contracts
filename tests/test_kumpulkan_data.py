"""Tes bagian pengumpul data di scripts/kumpulkan_data.py yang bisa dicek tanpa internet."""

import importlib.util
from datetime import date
from pathlib import Path

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
