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


def test_rapikan_pembeli_jaga_singkatan():
    assert muat_data.rapikan_pembeli("HM REVENUE AND CUSTOMS") == "HM Revenue and Customs"
    assert muat_data.rapikan_pembeli("UK HEALTH SECURITY AGENCY") == "UK Health Security Agency"
    assert muat_data.rapikan_pembeli("NORTHUMBRIA HEALTHCARE NHS FOUNDATION TRUST") == \
        "Northumbria Healthcare NHS Foundation Trust"
    assert muat_data.rapikan_pembeli(float("nan")) == ""


def test_meta():
    meta = muat_data.muat_meta()
    assert meta.get("transaksi_as", 0) > 0
    assert isinstance(pd.Timestamp(meta["diperbarui"]), pd.Timestamp)


def test_tambah_sektor_as_isi_sub_instansi_kosong():
    df = pd.DataFrame({"instansi": ["Department of Defense", "Department of Homeland Security"],
                       "sub_instansi": [None, "U.S. Immigration and Customs Enforcement"]})
    hasil = muat_data.tambah_sektor_as(df)
    assert hasil.loc[0, "sub_instansi"] == "Department of Defense"   # jatuh ke instansi induk
    assert hasil["sektor"].notna().all() and hasil["nama_pendek"].notna().all()
    assert df["sub_instansi"].isna().iloc[0]                         # input tidak diubah


def test_kurs_lengkap_dan_masuk_akal():
    kurs = muat_data.muat_kurs()
    tahun = kurs["tahun"].tolist()
    assert tahun == list(range(tahun[0], tahun[-1] + 1))   # tanpa tahun bolong
    assert kurs["gbp_ke_usd"].between(1.0, 2.0).all()


def test_muat_meta_berkas_rusak_atau_hilang(tmp_path, monkeypatch):
    monkeypatch.setattr(muat_data, "DATA", tmp_path)
    assert muat_data.muat_meta() == {}
    (tmp_path / "META.json").write_text("{bukan json", encoding="utf-8")
    assert muat_data.muat_meta() == {}


def test_rapikan_pembeli_nilai_kosong():
    assert muat_data.rapikan_pembeli(None) == ""
    assert muat_data.rapikan_pembeli(float("nan")) == ""


def test_rapikan_pembeli_singkatan_bertanda_baca():
    assert muat_data.rapikan_pembeli("DEFENCE DIGITAL (MOD)") == "Defence Digital (MOD)"
    assert muat_data.rapikan_pembeli("NHS, ENGLAND") == "NHS, England"


def test_rapikan_pembeli_kata_sambung_lain():
    assert (muat_data.rapikan_pembeli("SECRETARY OF STATE FOR THE HOME DEPARTMENT")
            == "Secretary of State for the Home Department")
    assert muat_data.rapikan_pembeli("THE CABINET OFFICE") == "The Cabinet Office"


def test_kurs_tahunan_pakai_tahun_terdekat():
    import pandas as pd

    kurs = pd.DataFrame({"tahun": [2016, 2014, 2015], "gbp_ke_usd": [1.35, 1.55, 1.52]})
    hasil = muat_data.kurs_tahunan(pd.Series([2012.0, 2015.0, 2030.0, float("nan")]), kurs)
    assert hasil.tolist() == [1.55, 1.52, 1.35, 1.35]


def test_rapikan_pembeli_apostrof_dan_tanda_hubung():
    assert muat_data.rapikan_pembeli("HER MAJESTY'S TREASURY") == "Her Majesty's Treasury"
    assert muat_data.rapikan_pembeli("NORTH-EAST LINCOLNSHIRE COUNCIL") == "North-East Lincolnshire Council"
    assert muat_data.rapikan_pembeli("MINISTRY OF DEFENCE (MOD)") == "Ministry of Defence (MOD)"


def test_rapikan_pembeli_spasi_ganda_dan_huruf_kecil_digabung():
    varian = ["MINISTRY  OF DEFENCE", "ministry of defence", "Ministry of Defence", " MINISTRY OF\tDEFENCE "]
    assert {muat_data.rapikan_pembeli(n) for n in varian} == {"Ministry of Defence"}
    assert muat_data.rapikan_pembeli("nhs england") == "NHS England"


def test_transaksi_tanggal_rusak_tidak_menggagalkan(tmp_path, monkeypatch):
    kolom = ("tanggal,award_id,nilai_usd,instansi,sub_instansi,deskripsi,id_usaspending\n")
    (tmp_path / "as_transaksi.csv").write_text(
        kolom
        + "2024-10-05,A1,100,Department of Defense,Department of the Army,x,ID1\n"
        + "bukan-tanggal,A2,50,Department of Defense,Department of the Army,y,ID2\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(muat_data, "DATA", tmp_path)
    df = muat_data.muat_transaksi_as()
    assert len(df) == 2
    assert df.loc[0, "tahun_fiskal"] == 2025
    assert pd.isna(df.loc[1, "tanggal"])


def test_momen_tanggal_rusak_dibuang(tmp_path, monkeypatch):
    (tmp_path / "momen_penting.csv").write_text(
        "tanggal,negara,judul,keterangan,jenis,sumber\n"
        "2020-01-02,AS,B,x,Kontrak besar,https://b\n"
        "31/02/2019,AS,Rusak,x,Kontrak besar,https://r\n"
        "2019-01-01,AS,A,x,Kontrak besar,https://a\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(muat_data, "DATA", tmp_path)
    df = muat_data.muat_momen()
    assert list(df["judul"]) == ["A", "B"]


def test_kurs_tahunan_tabel_kosong_jadi_nan():
    kurs = pd.DataFrame({"tahun": [2020], "gbp_ke_usd": [None]})
    hasil = muat_data.kurs_tahunan(pd.Series([2020, 2021]), kurs)
    assert hasil.isna().all() and len(hasil) == 2


def test_transaksi_nilai_tak_hingga_dihitung_nol(tmp_path, monkeypatch):
    kolom = "tanggal,award_id,nilai_usd,instansi,sub_instansi,deskripsi,id_usaspending\n"
    (tmp_path / "as_transaksi.csv").write_text(
        kolom
        + "2024-10-05,A1,100,Department of Defense,Department of the Army,x,ID1\n"
        + "2024-10-06,A2,inf,Department of Defense,Department of the Army,y,ID2\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(muat_data, "DATA", tmp_path)
    df = muat_data.muat_transaksi_as()
    assert df["nilai_usd"].tolist() == [100.0, 0.0]
    assert analisis.format_usd(df["nilai_usd"].sum()) == "$100"


def test_idv_plafon_tak_hingga_dihitung_nol(tmp_path, monkeypatch):
    kolom = ("award_id,penerima,instansi,sub_instansi,mulai,batas_pesan,deskripsi,jenis,id_usaspending,"
             "plafon_usd,diikat_usd,jumlah_pesanan,tipe_award\n")
    (tmp_path / "as_idv.csv").write_text(
        kolom
        + "I1,PALANTIR USG INC,Department of Defense,Department of the Army,2024-01-01,2030-01-01,x,IDIQ,ID1,"
          "1000,250,1,SINGLE AWARD\n"
        + "I2,PALANTIR USG INC,Department of Defense,Department of the Army,2024-01-01,2030-01-01,y,IDIQ,ID2,"
          "inf,-inf,1,SINGLE AWARD\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(muat_data, "DATA", tmp_path)
    df = muat_data.muat_idv_as()
    assert df["plafon_usd"].tolist() == [1000.0, 0.0]
    assert df["diikat_usd"].tolist() == [250.0, 0.0]
    assert analisis.plafon_vs_diikat(df)["award_id"].tolist() == ["I1"]


def test_uk_framework_suntingan_manual_tetap_dikenali(tmp_path, monkeypatch):
    import shutil
    shutil.copy(muat_data.DATA / "kurs_gbp_usd.csv", tmp_path / "kurs_gbp_usd.csv")
    kolom = "id,diumumkan,tanggal_award,mulai,selesai,pembeli,nilai_gbp,framework\n"
    isi = "".join(
        f"U{i},2024-01-01,2024-01-01,2024-01-01,2025-01-01,NHS England,100,{f}\n"
        for i, f in enumerate(["True", "TRUE ", "yes", "1", "False", "0", ""])
    )
    (tmp_path / "uk_kontrak.csv").write_text(kolom + isi, encoding="utf-8")
    monkeypatch.setattr(muat_data, "DATA", tmp_path)
    df = muat_data.muat_kontrak_uk()
    assert df["framework"].tolist() == [True, True, True, True, False, False, False]
