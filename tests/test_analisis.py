import pandas as pd
import pytest

from src import analisis, sektor


def trx_contoh() -> pd.DataFrame:
    baris = [
        ("2020-03-01", "A1", 100.0, "Department of Defense", "Department of the Army", "CA", "UNITED STATES"),
        ("2020-11-01", "A1", 50.0, "Department of Defense", "Department of the Army", "CA", "UNITED STATES"),
        ("2021-05-01", "B1", 200.0, "Department of Homeland Security", "U.S. Immigration and Customs Enforcement",
         "DC", "UNITED STATES"),
        ("2022-01-15", "C1", 300.0, "Department of Health and Human Services", "National Institutes of Health",
         "MD", "UNITED STATES"),
        ("2022-06-01", "D1", 40.0, "Department of Defense", "Department of the Army", None, "AFGHANISTAN"),
        ("2022-07-01", "C1", -20.0, "Department of Health and Human Services", "National Institutes of Health",
         "MD", "UNITED STATES"),
    ]
    df = pd.DataFrame(baris, columns=["tanggal", "award_id", "nilai_usd", "instansi", "sub_instansi",
                                      "negara_bagian", "negara_pelaksanaan"])
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    df["tahun"] = df["tanggal"].dt.year
    df["sektor"] = [sektor.sektor_as(a, b) for a, b in zip(df["instansi"], df["sub_instansi"])]
    df["nama_pendek"] = df["sub_instansi"].map(sektor.singkat)
    return df


def uk_contoh() -> pd.DataFrame:
    return pd.DataFrame({"tahun": [2020, 2021, 2021], "nilai_gbp": [10.0, 20.0, 1000.0],
                         "nilai_usd": [13.0, 26.0, 1300.0], "framework": [False, False, True]})


def test_format_usd():
    assert analisis.format_usd(6_140_000_000) == "$6,14 M"
    assert analisis.format_usd(45_600_000) == "$45,6 jt"
    assert analisis.format_usd(-2_400) == "-$2 rb"
    assert analisis.format_gbp(1_200_000_000) == "£1,20 M"


def test_format_usd_pembulatan_naik_satuan():
    assert analisis.format_usd(999_999_999) == "$1,00 M"
    assert analisis.format_usd(999_960) == "$1,0 jt"
    assert analisis.format_usd(999.7) == "$1 rb"
    assert analisis.format_usd(0) == "$0"


def test_per_tahun_sektor_lengkap_dan_total_sama():
    df = trx_contoh()
    hasil = analisis.per_tahun_sektor(df)
    assert set(hasil["sektor"]) == set(sektor.URUTAN_SEKTOR)
    assert hasil["nilai_usd"].sum() == pytest.approx(df["nilai_usd"].sum())
    assert hasil.query("tahun == 2022 and sektor == 'Kesehatan'")["nilai_usd"].iloc[0] == pytest.approx(280.0)


def test_porsi_sektor_100_persen():
    hasil = analisis.porsi_sektor(trx_contoh())
    assert hasil["persen"].sum() == pytest.approx(100.0)
    assert list(hasil["sektor"]) == [sektor.KESEHATAN, sektor.IMIGRASI, sektor.MILITER]  # 280 > 200 > 190
    assert list(hasil["nilai_usd"]) == sorted(hasil["nilai_usd"], reverse=True)


def test_per_instansi_dan_konsentrasi():
    inst = analisis.per_instansi(trx_contoh())
    assert inst.iloc[0]["nama_pendek"] == "NIH"
    army = inst[inst["nama_pendek"] == "US Army"].iloc[0]
    assert army["nilai_usd"] == pytest.approx(190.0)
    assert army["kontrak"] == 2
    assert army["tahun_pertama"] == 2020 and army["tahun_terakhir"] == 2022
    assert analisis.konsentrasi(trx_contoh(), 3) == pytest.approx(100.0)


def test_pertumbuhan_dan_cagr():
    df = trx_contoh()
    assert analisis.pertumbuhan(df, 2020, 2022) == pytest.approx(320 / 150)
    assert analisis.pertumbuhan(df, 2019, 2022) is None
    assert analisis.cagr(df, 2020, 2022) == pytest.approx((320 / 150) ** 0.5 - 1)


def test_kumulatif_naik_ke_total():
    kum = analisis.kumulatif(trx_contoh())
    assert kum["kumulatif_usd"].iloc[-1] == pytest.approx(670.0)


def test_per_negara_bagian_dan_negara():
    nb = analisis.per_negara_bagian(trx_contoh())
    assert set(nb["negara_bagian"]) == {"CA", "DC", "MD"}
    neg = analisis.per_negara(trx_contoh(), uk_contoh())
    assert set(neg["iso3"]) == {"USA", "AFG", "GBR"}
    assert neg.set_index("iso3").loc["GBR", "nilai_usd"] == pytest.approx(39.0)  # framework dibuang


def test_gabung_as_uk():
    g = analisis.gabung_as_uk(trx_contoh(), uk_contoh())
    assert g.query("negara == 'Inggris' and tahun == 2021")["nilai_usd"].iloc[0] == pytest.approx(26.0)


def test_plafon_vs_diikat_saring_multi_vendor():
    idv = pd.DataFrame({"award_id": ["X", "Y", "Z"], "plafon_usd": [1000.0, 10_000.0, 0.0],
                        "diikat_usd": [250.0, 1.0, 5.0], "multi_vendor": [False, True, False]})
    hasil = analisis.plafon_vs_diikat(idv)
    assert list(hasil["award_id"]) == ["X"]
    assert hasil.iloc[0]["terpakai_persen"] == pytest.approx(25.0)
    assert hasil.iloc[0]["sisa_usd"] == pytest.approx(750.0)
    assert len(analisis.plafon_vs_diikat(idv, termasuk_multi=True)) == 2


def test_cari_tidak_peka_huruf():
    df = pd.DataFrame({"deskripsi": ["MAVEN SMART SYSTEM", "Army Vantage"], "instansi": ["DoD", "DoD"]})
    assert len(analisis.cari(df, "maven", ["deskripsi", "instansi"])) == 1
    assert len(analisis.cari(df, "", ["deskripsi"])) == 2
    assert len(analisis.cari(df, "(", ["deskripsi"])) == 0  # karakter regex aman


def test_kontrak_terbesar_urut_menurun():
    hasil = analisis.kontrak_terbesar(trx_contoh(), n=2)
    assert list(hasil["nilai_usd"]) == [300.0, 200.0]
    assert list(hasil.index) == [0, 1]


def test_temuan_utama_angka_kunci():
    idv = pd.DataFrame({"award_id": ["X", "Y"], "plafon_usd": [1000.0, 10_000.0],
                        "diikat_usd": [250.0, 1.0], "multi_vendor": [False, True]})
    t = analisis.temuan_utama(trx_contoh(), uk_contoh(), idv)
    assert t["total_as"] == pytest.approx(670.0)
    assert t["jumlah_kontrak_as"] == 4               # A1 muncul dua kali tapi dihitung sekali
    assert t["total_uk_gbp"] == pytest.approx(30.0)  # kontrak framework tidak ikut dijumlah
    assert t["jumlah_kontrak_uk"] == 2
    assert t["tahun_rekor"] == 2022 and t["nilai_rekor"] == pytest.approx(320.0)
    assert t["persen_dua_tahun_terakhir"] == pytest.approx(100 * 520 / 670)
    assert t["plafon_aktif"] == pytest.approx(1000.0)  # plafon multi-vendor tidak dihitung
    assert 0 <= t["persen_militer"] <= 100
