"""
src/analisis.py - Hitungan inti dashboard
=========================================
Semua fungsi menerima DataFrame dan mengembalikan DataFrame/angka, tanpa Streamlit.
"""

from __future__ import annotations

import pandas as pd

from src.sektor import URUTAN_SEKTOR

# Nama negara di USAspending -> kode ISO-3 untuk peta dunia.
ISO3 = {
    "UNITED STATES": "USA", "UNITED STATES OF AMERICA": "USA", "USA": "USA",
    "AFGHANISTAN": "AFG", "GERMANY": "DEU", "KOREA, SOUTH": "KOR", "SOUTH KOREA": "KOR", "IRAQ": "IRQ",
    "UNITED KINGDOM": "GBR", "JAPAN": "JPN", "ITALY": "ITA", "BELGIUM": "BEL", "KUWAIT": "KWT", "QATAR": "QAT",
    "BAHRAIN": "BHR", "UKRAINE": "UKR", "POLAND": "POL", "AUSTRALIA": "AUS", "CANADA": "CAN", "ISRAEL": "ISR",
}
NAMA_NEGARA = {"USA": "Amerika Serikat", "AFG": "Afganistan", "DEU": "Jerman", "KOR": "Korea Selatan",
               "IRQ": "Irak", "GBR": "Inggris", "JPN": "Jepang", "ITA": "Italia", "BEL": "Belgia", "KWT": "Kuwait",
               "QAT": "Qatar", "BHR": "Bahrain", "UKR": "Ukraina", "POL": "Polandia", "AUS": "Australia",
               "CAN": "Kanada", "ISR": "Israel"}


def format_usd(x: float) -> str:
    """1_234_567_890 -> '$1,23 M' (miliar), 45_600_000 -> '$45,6 jt'. Gaya angka Indonesia."""
    tanda = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e9:
        teks = f"{x / 1e9:,.2f} M"
    elif x >= 1e6:
        teks = f"{x / 1e6:,.1f} jt"
    elif x >= 1e3:
        teks = f"{x / 1e3:,.0f} rb"
    else:
        teks = f"{x:,.0f}"
    return tanda + "$" + teks.replace(",", "#").replace(".", ",").replace("#", ".")


def format_gbp(x: float) -> str:
    return format_usd(x).replace("$", "£")


def per_tahun_sektor(trx: pd.DataFrame, kolom_tahun: str = "tahun") -> pd.DataFrame:
    """Tabel panjang: tahun x sektor -> total obligasi (USD). Semua sektor selalu muncul (nilai 0 bila kosong)."""
    if trx.empty:
        return pd.DataFrame(columns=[kolom_tahun, "sektor", "nilai_usd"])
    tabel = trx.pivot_table(index=kolom_tahun, columns="sektor", values="nilai_usd", aggfunc="sum", fill_value=0.0)
    tabel = tabel.reindex(columns=URUTAN_SEKTOR, fill_value=0.0)
    return tabel.reset_index().melt(id_vars=kolom_tahun, var_name="sektor", value_name="nilai_usd")


def porsi_sektor(trx: pd.DataFrame) -> pd.DataFrame:
    """Total dan persentase per sektor, urut dari terbesar."""
    tot = trx.groupby("sektor", as_index=False)["nilai_usd"].sum()
    tot = tot[tot["nilai_usd"] > 0].sort_values("nilai_usd", ascending=False)
    tot["persen"] = 100 * tot["nilai_usd"] / tot["nilai_usd"].sum()
    return tot.reset_index(drop=True)


def per_instansi(trx: pd.DataFrame, n: int | None = None) -> pd.DataFrame:
    """Total per sub-instansi (Army, ICE, IRS, ...), dengan tahun pertama dan terakhir dapat kontrak."""
    g = trx.groupby(["sektor", "instansi", "sub_instansi", "nama_pendek"], as_index=False).agg(
        nilai_usd=("nilai_usd", "sum"), transaksi=("nilai_usd", "size"),
        kontrak=("award_id", "nunique"), tahun_pertama=("tahun", "min"), tahun_terakhir=("tahun", "max"))
    g = g[g["nilai_usd"] > 0].sort_values("nilai_usd", ascending=False).reset_index(drop=True)
    g["persen"] = 100 * g["nilai_usd"] / g["nilai_usd"].sum()
    return g.head(n) if n else g


def konsentrasi(trx: pd.DataFrame, n: int = 5) -> float:
    """Persentase dana dari n sub-instansi terbesar. Tinggi = Palantir bergantung pada sedikit klien."""
    g = per_instansi(trx)
    return float(g["persen"].head(n).sum()) if not g.empty else 0.0


def pertumbuhan(trx: pd.DataFrame, awal: int, akhir: int) -> float | None:
    """Rasio total tahun akhir terhadap tahun awal (2,0 = dua kali lipat). None bila tahun awal nol."""
    per_th = trx.groupby("tahun")["nilai_usd"].sum()
    a, b = per_th.get(awal, 0.0), per_th.get(akhir, 0.0)
    return None if a <= 0 else float(b / a)


def cagr(trx: pd.DataFrame, awal: int, akhir: int) -> float | None:
    """Compound annual growth rate: rata-rata pertumbuhan per tahun antara dua tahun."""
    rasio = pertumbuhan(trx, awal, akhir)
    if rasio is None or akhir <= awal or rasio <= 0:
        return None
    return rasio ** (1 / (akhir - awal)) - 1


def kumulatif(trx: pd.DataFrame) -> pd.DataFrame:
    """Total berjalan per bulan, untuk garis 'sudah berapa banyak sejak awal'."""
    bulanan = (trx.set_index("tanggal")["nilai_usd"].resample("MS").sum().rename("nilai_usd").reset_index())
    bulanan["kumulatif_usd"] = bulanan["nilai_usd"].cumsum()
    return bulanan


def per_negara_bagian(trx: pd.DataFrame) -> pd.DataFrame:
    """Total per negara bagian tempat pekerjaan dilaksanakan (place of performance)."""
    d = trx.dropna(subset=["negara_bagian"])
    d = d[d["negara_pelaksanaan"].fillna("UNITED STATES").str.upper().map(ISO3).eq("USA")]
    g = d.groupby("negara_bagian", as_index=False).agg(nilai_usd=("nilai_usd", "sum"),
                                                      kontrak=("award_id", "nunique"))
    return g[g["nilai_usd"] > 0].sort_values("nilai_usd", ascending=False).reset_index(drop=True)


def per_negara(trx: pd.DataFrame, uk: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Total per negara pelaksanaan. Kontrak AS memakai place of performance; kontrak Inggris dihitung di GBR
    (dikonversi ke USD dengan kurs rata-rata tahunan). Kolom 'sumber' membedakan keduanya.
    """
    d = trx.copy()
    d["iso3"] = d["negara_pelaksanaan"].fillna("UNITED STATES").str.upper().map(ISO3).fillna("USA")
    g = d.groupby("iso3", as_index=False).agg(nilai_usd=("nilai_usd", "sum"), kontrak=("award_id", "nunique"))
    g["sumber"] = "Kontrak federal AS"
    if uk is not None and not uk.empty:
        u = uk[~uk["framework"]]
        g = pd.concat([g, pd.DataFrame([{"iso3": "GBR", "nilai_usd": u["nilai_usd"].sum(), "kontrak": len(u),
                                         "sumber": "Kontrak sektor publik Inggris"}])], ignore_index=True)
    g["negara"] = g["iso3"].map(NAMA_NEGARA).fillna(g["iso3"])
    return g[g["nilai_usd"] > 0].sort_values("nilai_usd", ascending=False).reset_index(drop=True)


def gabung_as_uk(trx: pd.DataFrame, uk: pd.DataFrame) -> pd.DataFrame:
    """Total tahunan AS (obligasi) dan Inggris (nilai kontrak, USD) berdampingan."""
    a = trx.groupby("tahun", as_index=False)["nilai_usd"].sum().assign(negara="Amerika Serikat")
    u = uk[~uk["framework"]].groupby("tahun", as_index=False)["nilai_usd"].sum().assign(negara="Inggris")
    return pd.concat([a, u], ignore_index=True).sort_values(["tahun", "negara"]).reset_index(drop=True)


def plafon_vs_diikat(idv: pd.DataFrame, termasuk_multi: bool = False) -> pd.DataFrame:
    """
    Kontrak payung: plafon (batas atas) vs dana yang sudah diikat lewat pesanan.
    Kontrak multi-vendor disaring secara bawaan karena plafonnya dibagi dengan banyak perusahaan lain.
    """
    d = idv if termasuk_multi else idv[~idv["multi_vendor"]]
    d = d[d["plafon_usd"] > 0].copy()
    d["terpakai_persen"] = (100 * d["diikat_usd"] / d["plafon_usd"]).clip(upper=999)
    d["sisa_usd"] = (d["plafon_usd"] - d["diikat_usd"]).clip(lower=0)
    return d.sort_values("plafon_usd", ascending=False).reset_index(drop=True)


def kontrak_terbesar(kontrak: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return kontrak.sort_values("nilai_usd", ascending=False).head(n).reset_index(drop=True)


def cari(df: pd.DataFrame, kata: str, kolom: list[str]) -> pd.DataFrame:
    """Pencarian teks sederhana (tidak peka huruf besar) di beberapa kolom sekaligus."""
    kata = (kata or "").strip()
    if not kata:
        return df
    gabungan = df[kolom].fillna("").astype(str).agg(" ".join, axis=1)
    return df[gabungan.str.contains(kata, case=False, regex=False)]


def temuan_utama(trx: pd.DataFrame, uk: pd.DataFrame, idv: pd.DataFrame) -> dict:
    """Angka-angka kunci untuk kartu ringkasan dan README."""
    porsi = porsi_sektor(trx).set_index("sektor")["persen"]
    per_th = trx.groupby("tahun")["nilai_usd"].sum()
    th_akhir = int(trx["tahun"].max())
    dua_th = per_th.loc[[t for t in per_th.index if t >= th_akhir - 1]].sum()
    instansi = per_instansi(trx)
    plafon = plafon_vs_diikat(idv)
    return {
        "total_as": float(trx["nilai_usd"].sum()),
        "total_uk_gbp": float(uk.loc[~uk["framework"], "nilai_gbp"].sum()),
        "jumlah_kontrak_as": int(trx["award_id"].nunique()),
        "jumlah_kontrak_uk": int((~uk["framework"]).sum()),
        "jumlah_instansi": int(instansi["sub_instansi"].nunique()),
        "persen_militer": float(porsi.get("Militer & pertahanan", 0.0)),
        "persen_dua_tahun_terakhir": float(100 * dua_th / per_th.sum()),
        "tahun_rekor": int(per_th.idxmax()),
        "nilai_rekor": float(per_th.max()),
        "instansi_teratas": instansi.iloc[0]["nama_pendek"] if not instansi.empty else "-",
        "persen_instansi_teratas": float(instansi.iloc[0]["persen"]) if not instansi.empty else 0.0,
        "konsentrasi_top5": konsentrasi(trx, 5),
        "plafon_aktif": float(plafon["plafon_usd"].sum()),
    }
