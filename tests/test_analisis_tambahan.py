"""Tes tambahan untuk src/analisis.py: konsentrasi klien, kumulatif bulanan, kontrak terbesar, dan pencarian."""

import pandas as pd

from src import analisis


def _trx():
    return pd.DataFrame({
        "tanggal": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-03-02", "2024-03-30"]),
        "tahun": [2024, 2024, 2024, 2024],
        "award_id": ["A", "A", "B", "C"],
        "nilai_usd": [100.0, 50.0, 30.0, -10.0],
        "sektor": ["Militer", "Militer", "Imigrasi", "Kesehatan"],
        "instansi": ["DoD", "DoD", "DHS", "HHS"],
        "sub_instansi": ["Army", "Army", "ICE", "CDC"],
        "nama_pendek": ["Army", "Army", "ICE", "CDC"],
    })


def test_per_instansi_buang_total_negatif_dan_persen_100():
    g = analisis.per_instansi(_trx())
    assert g["sub_instansi"].tolist() == ["Army", "ICE"]          # CDC totalnya negatif (koreksi), tidak ditampilkan
    assert g.loc[0, "transaksi"] == 2 and g.loc[0, "kontrak"] == 1
    assert abs(g["persen"].sum() - 100) < 1e-9


def test_konsentrasi_satu_klien_dan_kosong():
    assert abs(analisis.konsentrasi(_trx(), n=1) - 150 / 180 * 100) < 1e-9
    assert analisis.konsentrasi(_trx().iloc[0:0]) == 0.0


def test_kumulatif_isi_bulan_kosong_dengan_nol():
    k = analisis.kumulatif(_trx())
    assert k["tanggal"].dt.month.tolist() == [1, 2, 3]
    assert k["nilai_usd"].tolist() == [150.0, 0.0, 20.0]
    assert k["kumulatif_usd"].tolist() == [150.0, 150.0, 170.0]
