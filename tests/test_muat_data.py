"""Uji data asli di folder data/: memastikan snapshot yang dikomit masuk akal."""
import pandas as pd

from src import muat_data, analisis


def test_transaksi_hanya_entitas_palantir():
    trx = muat_data.muat_transaksi_as()
    assert len(trx) > 1000
    assert trx["penerima"].str.match(r"^PALANTIR (TECHNOLOGIES|USG|USA)").all()
    assert trx["nilai_usd"].sum() > 1e9


def test_tahun_fiskal_mulai_oktober():
    trx = muat_data.muat_transaksi_as()
    okt = trx[trx["tanggal"].dt.month >= 10]
    assert (okt["tahun_fiskal"] == okt["tahun"] + 1).all()
    sep = trx[trx["tanggal"].dt.month < 10]
    assert (sep["tahun_fiskal"] == sep["tahun"]).all()


def test_total_kontrak_sesuai_transaksi():
    """Jumlah obligasi per kontrak (award) harus kurang lebih sama dengan jumlah transaksinya."""
    trx, kontrak = muat_data.muat_transaksi_as(), muat_data.muat_kontrak_as()
    assert abs(trx["nilai_usd"].sum() - kontrak["nilai_usd"].sum()) / kontrak["nilai_usd"].sum() < 0.01


def test_semua_baris_punya_sektor_dan_url():
    trx = muat_data.muat_transaksi_as()
    assert trx["sektor"].notna().all()
    assert trx["url"].str.startswith("https://www.usaspending.gov/award/CONT_").all()


def test_uk_hanya_dimenangkan_palantir():
    uk = muat_data.muat_kontrak_uk()
    assert uk["pemasok"].str.contains("palantir", case=False).all()
    assert uk["framework"].sum() >= 1
    assert (uk["nilai_usd"] >= uk["nilai_gbp"]).all()  # GBP selalu lebih mahal dari USD sejak 2015


def test_idv_punya_flag_multi_vendor():
    idv = muat_data.muat_idv_as()
    assert idv["multi_vendor"].any() and (~idv["multi_vendor"]).any()
    terbesar = analisis.plafon_vs_diikat(idv).iloc[0]
    assert terbesar["award_id"] == "W519TC25D0039"  # Army Enterprise Agreement $10 miliar


def test_momen_penting_bersumber():
    m = muat_data.muat_momen()
    assert m["sumber"].str.startswith("https://").all()
    assert set(m["negara"]) <= {"AS", "UK"}
    assert m["tanggal"].is_monotonic_increasing


def test_rapikan_pembeli():
    assert muat_data.rapikan_pembeli("MINISTRY OF DEFENCE") == "Ministry of Defence"
    assert muat_data.rapikan_pembeli("NHS England") == "NHS England"
    assert muat_data.rapikan_pembeli("Defra").startswith("Department for Environment")


def test_meta():
    meta = muat_data.muat_meta()
    assert meta.get("transaksi_as", 0) > 0
    assert isinstance(pd.Timestamp(meta["diperbarui"]), pd.Timestamp)
