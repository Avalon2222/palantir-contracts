"""
app.py - Follow the Contracts
=============================
Jalankan dengan:   streamlit run app.py

Alur besar file ini (baca dari atas ke bawah):
  1. Import library + konfigurasi halaman
  2. Muat data kontrak AS (USAspending) dan Inggris (Contracts Finder) dari folder data/
  3. Sidebar: rentang tahun, basis tahun, sektor, learning mode
  4. Angka ringkasan di bagian atas
  5. Tab: Peta / Timeline / Per instansi / Plafon vs realisasi / Inggris / Cari kontrak / Data & sumber / Cara kerja

Semua hitungan ada di src/ (bisa diuji dengan pytest); file ini hanya mengatur tampilan.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analisis, muat_data, sektor
from src.analisis import format_gbp, format_usd
from src.sektor import URUTAN_SEKTOR, WARNA_SEKTOR

# ----------------------------------------------------------------------------
# 0. KONFIGURASI HALAMAN
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Follow the Contracts", page_icon="🔮", layout="wide")

TEMPLATE = "plotly_dark"
WARNA_UTAMA = "#fb923c"
WARNA_AS, WARNA_UK = "#fb923c", "#38bdf8"
DISCLAIMER = (
    "ℹ️ Seluruh angka berasal dari **catatan pengadaan resmi** yang dibuka untuk publik: USAspending.gov (pemerintah "
    "federal AS) dan Contracts Finder (sektor publik Inggris). Kontrak rahasia (mis. badan intelijen) tidak tercatat, "
    "jadi angka di sini adalah **batas bawah**. Proyek edukatif dan portofolio pribadi, tidak berafiliasi dengan "
    "Palantir atau instansi mana pun."
)

st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] {font-size: 1.65rem;}
    .kartu {border:1px solid #262c38; border-left:4px solid #fb923c; border-radius:8px; padding:0.7rem 0.9rem;
            margin-bottom:0.6rem; background:#11151c;}
    .kartu b {color:#fb923c;}
    .kecil {color:#9aa3b2; font-size:0.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def rapikan(fig: go.Figure, tinggi: int = 430) -> go.Figure:
    """Gaya seragam untuk semua grafik Plotly: latar gelap transparan, grid tipis, legenda di atas."""
    fig.update_layout(
        template=TEMPLATE, height=tinggi,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=20, t=90, b=10),
        title=dict(y=0.98, yanchor="top", x=0, xanchor="left", font=dict(size=15)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None),
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif"),
        hoverlabel=dict(font_size=13),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#262c38", zeroline=False)
    return fig


def belajar(judul: str, isi: str, kode: str | None = None) -> None:
    """Kotak penjelasan yang hanya muncul saat Learning mode aktif."""
    if not mode_belajar:
        return
    with st.expander(f"🎓 {judul}", expanded=True):
        st.markdown(isi)
        if kode:
            st.code(kode, language="python")


def md(teks: str) -> str:
    """Streamlit membaca $...$ sebagai rumus LaTeX; tanda dolar di teks biasa harus di-escape."""
    return teks.replace("$", "\\$")


def label_juta(nilai: pd.Series) -> pd.Series:
    return (nilai / 1e6).round(1)


# ----------------------------------------------------------------------------
# 1. MUAT DATA
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner="Membaca data kontrak...")
def muat_semua():
    return (muat_data.muat_transaksi_as(), muat_data.muat_kontrak_as(), muat_data.muat_idv_as(),
            muat_data.muat_kontrak_uk(), muat_data.muat_momen(), muat_data.muat_meta())


trx_semua, kontrak_semua, idv_semua, uk_semua, momen, meta = muat_semua()
TAHUN_MIN, TAHUN_MAKS = int(trx_semua["tahun"].min()), int(trx_semua["tahun"].max())

# ----------------------------------------------------------------------------
# 2. SIDEBAR
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title("🔮 Follow the Contracts")
    st.caption("Ke mana uang pemerintah mengalir ke Palantir: dari Pentagon, ICE, sampai NHS.")

    st.subheader("Filter")
    rentang = st.slider("Rentang tahun", TAHUN_MIN, TAHUN_MAKS, (TAHUN_MIN, TAHUN_MAKS))
    basis = st.radio("Basis tahun (data AS)", ["Kalender", "Fiskal AS"], horizontal=True,
                     help="Tahun fiskal federal AS dimulai 1 Oktober. Contoh: transaksi 15 Okt 2025 masuk FY2026.")
    sektor_pilih = st.multiselect("Sektor", URUTAN_SEKTOR, default=URUTAN_SEKTOR,
                                  help="Setiap instansi dipetakan ke satu sektor dengan aturan di src/sektor.py.")
    mode_belajar = st.toggle("🎓 Learning mode", value=False,
                             help="Tampilkan penjelasan istilah, rumus, dan potongan kode di setiap bagian.")
    st.caption(
        f"Data: {meta.get('transaksi_as', len(trx_semua)):,} transaksi AS".replace(",", ".") + f", {len(uk_semua)} pengumuman Inggris. "
        f"Diperbarui {str(meta.get('diperbarui', '-'))[:10]}. Perbarui dengan `python scripts/kumpulkan_data.py`."
    )

KOLOM_TAHUN = "tahun" if basis == "Kalender" else "tahun_fiskal"
trx = trx_semua.copy()
trx["tahun"] = trx[KOLOM_TAHUN]  # semua hitungan memakai kolom 'tahun' sesuai basis yang dipilih
trx = trx[trx["tahun"].between(*rentang) & trx["sektor"].isin(sektor_pilih)]
kontrak = kontrak_semua[kontrak_semua["sektor"].isin(sektor_pilih)]
idv = idv_semua[idv_semua["sektor"].isin(sektor_pilih)]
uk = uk_semua[uk_semua["tahun"].between(*rentang) & uk_semua["sektor"].isin(sektor_pilih)]

if trx.empty:
    st.warning("Tidak ada transaksi untuk filter ini. Longgarkan rentang tahun atau pilih sektor lain.")
    st.stop()

T = analisis.temuan_utama(trx, uk, idv)
TAHUN_BERJALAN = TAHUN_MAKS  # tahun terakhir di data belum selesai

# ----------------------------------------------------------------------------
# 3. HEADER + ANGKA RINGKASAN
# ----------------------------------------------------------------------------
st.title("🔮 Follow the Contracts")
st.markdown("##### Palantir menjual software untuk *melihat semuanya*. Dashboard ini melihat balik: siapa yang membayar, "
            "berapa, dan untuk apa.")
st.caption(DISCLAIMER)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Dana federal AS ke Palantir", format_usd(T["total_as"]),
          help="Total obligasi (dana yang sudah diikat secara hukum) di semua kontrak, sesuai filter.")
k2.metric("Kontrak Inggris", format_gbp(T["total_uk_gbp"]),
          help="Nilai kontrak yang diumumkan di Contracts Finder (tanpa framework multi-pemasok).")
k3.metric("Porsi militer (AS)", f"{T['persen_militer']:.0f}%", help="Department of Defense: Army, Air Force, SOCOM, Navy, dll.")
k4.metric(f"Dua tahun terakhir", f"{T['persen_dua_tahun_terakhir']:.0f}%",
          help="Persentase seluruh dana pada rentang terpilih yang jatuh di dua tahun terakhir rentang itu.")
k5.metric("Top-5 instansi", f"{T['konsentrasi_top5']:.0f}%",
          help="Persentase dana dari lima sub-instansi terbesar. Makin tinggi, makin bergantung pada sedikit klien.")

tab_peta, tab_waktu, tab_instansi, tab_plafon, tab_uk, tab_cari, tab_data, tab_cara = st.tabs([
    "🗺️ Peta", "📈 Timeline", "🏛️ Per instansi", "💰 Plafon vs realisasi", "🇬🇧 Inggris",
    "🔎 Cari kontrak", "🧾 Data & sumber", "⚙️ Cara kerja",
])

# ----------------------------------------------------------------------------
# TAB 1. PETA
# ----------------------------------------------------------------------------
with tab_peta:
    st.subheader("Di mana kontraknya dikerjakan")
    st.markdown(
        f"<div class='kartu'>Sejak {rentang[0]}, pemerintah AS mengikat <b>{format_usd(T['total_as'])}</b> untuk Palantir "
        f"lewat <b>{T['jumlah_kontrak_as']}</b> kontrak di <b>{T['jumlah_instansi']}</b> instansi. Klien terbesar: "
        f"<b>{T['instansi_teratas']}</b> ({T['persen_instansi_teratas']:.0f}% dari total). Rekor tahunan terjadi pada "
        f"<b>{T['tahun_rekor']}</b> dengan <b>{format_usd(T['nilai_rekor'])}</b>"
        f"{' (dan tahunnya belum selesai)' if T['tahun_rekor'] == TAHUN_BERJALAN else ''}.</div>",
        unsafe_allow_html=True,
    )

    negara = analisis.per_negara(trx, uk)
    fig = px.scatter_geo(
        negara, locations="iso3", size="nilai_usd", color="sumber", hover_name="negara", size_max=60,
        color_discrete_map={"Kontrak federal AS": WARNA_AS, "Kontrak sektor publik Inggris": WARNA_UK},
        custom_data=["kontrak", "nilai_usd"], projection="natural earth",
        title="Lokasi pelaksanaan kontrak (ukuran gelembung = nilai, skala akar)",
    )
    fig.update_traces(hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]} kontrak<br>$%{customdata[1]:,.0f}<extra></extra>",
                      marker=dict(line=dict(width=0.5, color="#0a0c10"), opacity=0.85))
    fig.update_geos(bgcolor="rgba(0,0,0,0)", showland=True, landcolor="#1a1f29", showocean=True, oceancolor="#0d1117",
                    showcountries=True, countrycolor="#2f3644", showcoastlines=False, showframe=False,
                    lataxis_range=[-35, 75], lonaxis_range=[-140, 150])
    fig = rapikan(fig, 540)
    fig.update_layout(margin=dict(l=0, r=0, t=70, b=0))
    st.plotly_chart(fig, use_container_width=True)
    luar_negeri = negara[~negara["iso3"].isin(["USA", "GBR"])]
    if not luar_negeri.empty:
        st.caption(md("Di luar AS dan Inggris, place of performance mencatat pekerjaan di: "
                      + ", ".join(f"{r.negara} ({format_usd(r.nilai_usd)})" for r in luar_negeri.itertuples())
                      + ". Hampir semuanya kontrak Army di zona operasi militer AS."))

    kiri, kanan = st.columns([3, 2])
    with kiri:
        bagian = analisis.per_negara_bagian(trx)
        fig = px.choropleth(bagian, locations="negara_bagian", locationmode="USA-states", scope="usa",
                            color="nilai_usd", color_continuous_scale=["#1f2430", "#7c2d12", "#fb923c", "#fed7aa"],
                            custom_data=["kontrak"], title="Amerika Serikat per negara bagian (place of performance)")
        fig.update_traces(hovertemplate="<b>%{location}</b><br>$%{z:,.0f}<br>%{customdata[0]} kontrak<extra></extra>",
                          marker_line_color="#0a0c10")
        fig.update_geos(bgcolor="rgba(0,0,0,0)", lakecolor="#0d1117", landcolor="#1a1f29", showlakes=True)
        fig.update_layout(coloraxis_colorbar=dict(title="USD", tickformat="$.2s"))
        st.plotly_chart(rapikan(fig, 420), use_container_width=True)
    with kanan:
        top = bagian.head(8).copy()
        top["Nilai"] = top["nilai_usd"].map(format_usd)
        top["Porsi"] = (100 * top["nilai_usd"] / bagian["nilai_usd"].sum()).round(1).astype(str) + "%"
        st.markdown("**Negara bagian teratas**")
        st.dataframe(top[["negara_bagian", "Nilai", "Porsi", "kontrak"]].rename(
            columns={"negara_bagian": "Negara bagian", "kontrak": "Kontrak"}), hide_index=True, use_container_width=True)
        st.caption("Catatan: *place of performance* sering kali kantor Palantir sendiri (Palo Alto CA, Washington DC, "
                   "Denver CO, McLean VA), bukan lokasi instansi pembeli. Peta ini menunjukkan di mana pekerjaan "
                   "dicatat, bukan di mana data diproses.")

    belajar("Kenapa gelembung, bukan warna?",
            "Untuk peta dunia, nilai AS (miliaran) dan negara lain (jutaan) berbeda ribuan kali lipat. Bila diwarnai, "
            "semua negara selain AS akan tampak sama gelap. Gelembung memakai **luas** sebanding nilai, sehingga "
            "perbedaan tetap terbaca. Kode negara diubah ke ISO-3 dengan kamus kecil di `src/analisis.py`.",
            "negara = analisis.per_negara(trx, uk)   # kolom iso3, nilai_usd, sumber\n"
            "px.scatter_geo(negara, locations='iso3', size='nilai_usd', color='sumber')")

# ----------------------------------------------------------------------------
# TAB 2. TIMELINE
# ----------------------------------------------------------------------------
with tab_waktu:
    st.subheader("Dari startup kecil ke kontraktor perang")
    per_th = analisis.per_tahun_sektor(trx)
    per_th = per_th[per_th["sektor"].isin(sektor_pilih)]
    per_th["juta"] = label_juta(per_th["nilai_usd"])
    fig = px.bar(per_th, x="tahun", y="nilai_usd", color="sektor", color_discrete_map=WARNA_SEKTOR,
                 category_orders={"sektor": URUTAN_SEKTOR}, custom_data=["sektor", "juta"],
                 title=f"Dana federal AS ke Palantir per tahun {basis.lower()}, menurut sektor")
    fig.update_traces(hovertemplate="<b>%{x}</b> · %{customdata[0]}<br>$%{customdata[1]:,.1f} juta<extra></extra>")
    fig.update_layout(barmode="relative", yaxis_title=None, xaxis_title=None, yaxis_tickformat="$.2s",
                      bargap=0.18)
    if TAHUN_BERJALAN <= rentang[1]:
        fig.add_annotation(x=TAHUN_BERJALAN, y=1.0, yref="paper", text="berjalan", showarrow=False,
                           font=dict(color="#9aa3b2", size=11), yanchor="bottom")
    st.plotly_chart(rapikan(fig, 460), use_container_width=True)

    rasio = analisis.pertumbuhan(trx, max(rentang[0], 2020), min(rentang[1], 2025))
    laju = analisis.cagr(trx, max(rentang[0], 2016), min(rentang[1], 2025))
    c1, c2, c3 = st.columns(3)
    c1.metric("2025 vs 2020", f"{rasio:.1f}×" if rasio else "-", help="Total tahun 2025 dibagi total tahun 2020.")
    c2.metric("Pertumbuhan rata-rata 2016–2025", f"{laju * 100:.0f}% / tahun" if laju else "-",
              help="CAGR: (nilai akhir / nilai awal)^(1/jumlah tahun) - 1.")
    c3.metric("Transaksi negatif (de-obligasi)", f"{(trx['nilai_usd'] < 0).sum()} baris",
              help="Dana yang ditarik kembali (pembatalan, koreksi). Ikut dihitung agar total sesuai USAspending.")

    st.markdown("#### Momen penting")
    tampil_momen = st.checkbox("Tandai momen penting di grafik kumulatif", value=True)
    kum = analisis.kumulatif(trx)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=kum["tanggal"], y=kum["kumulatif_usd"], mode="lines", name="Kumulatif AS",
                             line=dict(color=WARNA_UTAMA, width=3), fill="tozeroy", fillcolor="rgba(251,146,60,0.12)",
                             hovertemplate="%{x|%b %Y}<br>Total berjalan $%{y:,.0f}<extra></extra>"))
    if tampil_momen:
        m = momen[momen["tanggal"].dt.year.between(*rentang)].copy()
        m["y"] = [kum.loc[kum["tanggal"] <= t, "kumulatif_usd"].max() if (kum["tanggal"] <= t).any() else 0
                  for t in m["tanggal"]]
        m["y"] = m["y"].fillna(0)
        for negara_m, warna in [("AS", "#fef3c7"), ("UK", WARNA_UK)]:
            mm = m[m["negara"] == negara_m]
            fig.add_trace(go.Scatter(
                x=mm["tanggal"], y=mm["y"], mode="markers", name=f"Momen ({negara_m})",
                marker=dict(size=12, color=warna, symbol="diamond", line=dict(width=1, color="#0a0c10")),
                customdata=mm[["judul", "keterangan"]].values,
                hovertemplate="<b>%{customdata[0]}</b><br>%{x|%d %b %Y}<br>%{customdata[1]}<extra></extra>"))
    fig.update_layout(title="Total berjalan dana federal AS (hover berlian untuk cerita di baliknya)",
                      yaxis_tickformat="$.2s", hovermode="closest")
    st.plotly_chart(rapikan(fig, 440), use_container_width=True)

    for r in momen[momen["tanggal"].dt.year.between(*rentang)].iloc[::-1].itertuples():
        bendera = "🇺🇸" if r.negara == "AS" else "🇬🇧"
        st.markdown(f"<div class='kartu'>{bendera} <b>{r.tanggal:%d %b %Y} · {r.judul}</b><br>{r.keterangan} "
                    f"<a href='{r.sumber}' target='_blank'>sumber ↗</a></div>", unsafe_allow_html=True)

    belajar("Obligasi, bukan pembayaran",
            "Setiap baris USAspending adalah **aksi kontrak**: award baru, tambahan dana, opsi yang diambil, atau koreksi. "
            "Kolom `Transaction Amount` adalah **obligasi**, yaitu dana yang sudah diikat secara hukum untuk kontrak itu. "
            "Uang yang benar-benar dibayar (*outlay*) bisa datang belakangan. Grafik ini menjumlahkan obligasi per tahun.",
            "per_th = trx.pivot_table(index='tahun', columns='sektor', values='nilai_usd', aggfunc='sum')\n"
            "kumulatif = trx.set_index('tanggal')['nilai_usd'].resample('MS').sum().cumsum()")

# ----------------------------------------------------------------------------
# TAB 3. PER INSTANSI
# ----------------------------------------------------------------------------
with tab_instansi:
    st.subheader("Siapa pelanggan terbesarnya")
    inst = analisis.per_instansi(trx)
    kiri, kanan = st.columns([1, 1])
    with kiri:
        porsi = analisis.porsi_sektor(trx)
        fig = px.bar(porsi.iloc[::-1], x="nilai_usd", y="sektor", orientation="h", color="sektor",
                     color_discrete_map=WARNA_SEKTOR, text=porsi.iloc[::-1]["persen"].map(lambda p: f"{p:.1f}%"),
                     title="Porsi dana per sektor")
        fig.update_traces(hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>", textposition="outside", cliponaxis=False)
        fig.update_layout(showlegend=False, xaxis_tickformat="$.2s", yaxis_title=None, xaxis_title=None,
                          xaxis_range=[0, porsi["nilai_usd"].max() * 1.2])
        st.plotly_chart(rapikan(fig, 400), use_container_width=True)
    with kanan:
        fig = px.treemap(inst, path=[px.Constant("Pemerintah AS"), "sektor", "nama_pendek"], values="nilai_usd",
                         color="sektor", color_discrete_map={**WARNA_SEKTOR, "(?)": "#1a1f29"},
                         title="Peta pohon: sektor → instansi")
        fig.update_traces(hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>", root_color="#11151c",
                          marker=dict(line=dict(color="#0a0c10", width=1)))
        st.plotly_chart(rapikan(fig, 400), use_container_width=True)

    n_top = st.slider("Jumlah instansi di grafik", 5, min(30, len(inst)), min(15, len(inst)))
    top = inst.head(n_top).iloc[::-1]
    fig = px.bar(top, x="nilai_usd", y="nama_pendek", orientation="h", color="sektor", color_discrete_map=WARNA_SEKTOR,
                 custom_data=["sub_instansi", "kontrak", "tahun_pertama", "tahun_terakhir"],
                 title=f"{n_top} instansi dengan dana terbesar")
    fig.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>$%{x:,.0f}<br>%{customdata[1]} kontrak, "
                                    "%{customdata[2]}–%{customdata[3]}<extra></extra>")
    fig.update_layout(yaxis_title=None, xaxis_title=None, xaxis_tickformat="$.2s",
                      yaxis_categoryorder="total ascending")
    st.plotly_chart(rapikan(fig, 140 + 28 * n_top), use_container_width=True)

    st.markdown("#### Kapan setiap instansi mulai membeli")
    teratas = inst.head(14)["sub_instansi"].tolist()
    panas = (trx[trx["sub_instansi"].isin(teratas)].pivot_table(index="nama_pendek", columns="tahun", values="nilai_usd",
                                                                aggfunc="sum", fill_value=0.0))
    panas = panas.loc[[sektor.singkat(s) for s in teratas]].clip(lower=0)
    # Dinormalisasi per baris: setiap instansi dibandingkan dengan dirinya sendiri, supaya Army tidak menenggelamkan yang lain.
    persen = panas.div(panas.sum(axis=1), axis=0) * 100
    fig = px.imshow(persen, aspect="auto", color_continuous_scale=["#11151c", "#7c2d12", "#fb923c", "#fff7ed"],
                    labels=dict(color="% dana<br>instansi", x="", y=""),
                    title="Sebaran dana tiap instansi per tahun (% dari total instansi itu)")
    fig.update_traces(customdata=(panas / 1e6).values, xgap=2, ygap=2,
                      hovertemplate="<b>%{y}</b> · %{x}<br>%{z:.0f}% dana instansi ini<br>$%{customdata:,.1f} juta<extra></extra>")
    st.plotly_chart(rapikan(fig, 480), use_container_width=True)
    st.caption("Pola yang terlihat: pelanggan awal Palantir adalah SOCOM, FBI, dan DOJ (puncak 2014–2018). NIH melonjak "
               "sejak pandemi 2020, Air Force masuk besar mulai 2021, lalu Army, ICE, State Department, dan VA meledak "
               "setelah 2024. Dua tahun terakhir saja menyumbang lebih dari separuh seluruh dana.")

    belajar("Peta sektor dibuat dengan aturan, bukan model",
            "USAspending hanya punya nama instansi. `src/sektor.py` berisi daftar aturan regex yang dicek berurutan: "
            "Department of Defense → Militer, ICE/CBP/USCIS → Imigrasi, sisa DHS + DOJ → Keamanan dalam negeri & hukum, "
            "HHS + VA → Kesehatan, Treasury/SEC → Keuangan, State/USAID → Diplomasi, sisanya → Sipil lainnya. "
            "Aturan seperti ini mudah diperiksa dan diuji, cocok untuk data yang jumlah instansinya puluhan saja.",
            "def sektor_as(instansi, sub_instansi=''):\n"
            "    for p_inst, p_sub, nama in ATURAN_AS:\n"
            "        if cocok(p_inst, instansi) and cocok(p_sub, sub_instansi):\n"
            "            return nama\n"
            "    return 'Sipil lainnya'")

# ----------------------------------------------------------------------------
# TAB 4. PLAFON VS REALISASI
# ----------------------------------------------------------------------------
with tab_plafon:
    st.subheader("Plafon miliaran, realisasi berapa?")
    st.markdown("Berita sering menulis *“Palantir dapat kontrak \\$10 miliar”*. Angka itu biasanya **plafon** kontrak payung "
                "(IDV): batas atas pesanan yang *boleh* dibuat, bukan uang yang sudah keluar. Grafik ini membandingkan "
                "plafon dengan dana yang benar-benar sudah diikat lewat pesanan.")
    multi = st.toggle("Sertakan kontrak multi-vendor", value=False,
                      help="Plafon kontrak multi-vendor dibagi dengan puluhan perusahaan lain (mis. MDA SHIELD \\$151 miliar), "
                           "sehingga sangat menyesatkan bila dibaca sebagai milik Palantir.")
    pv = analisis.plafon_vs_diikat(idv, termasuk_multi=multi).head(15)
    if pv.empty:
        st.info("Tidak ada kontrak payung untuk sektor terpilih.")
    else:
        pv["label"] = pv["award_id"] + " · " + pv["nama_pendek"]
        pv["judul_pendek"] = pv["deskripsi"].str.slice(0, 70)
        urut = pv.iloc[::-1]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=urut["plafon_usd"], y=urut["label"], orientation="h", name="Plafon",
                             marker_color="#2f3644", customdata=urut[["judul_pendek"]].values,
                             hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>Plafon $%{x:,.0f}<extra></extra>"))
        fig.add_trace(go.Bar(x=urut["diikat_usd"], y=urut["label"], orientation="h", name="Sudah diikat lewat pesanan",
                             marker_color=WARNA_UTAMA, customdata=urut[["terpakai_persen"]].values,
                             hovertemplate="<b>%{y}</b><br>Diikat $%{x:,.0f} (%{customdata[0]:.0f}% plafon)<extra></extra>"))
        fig.update_layout(barmode="overlay", xaxis_tickformat="$.2s", yaxis_title=None,
                          xaxis_type="log" if multi else "linear",
                          title="Plafon kontrak payung vs dana yang sudah diikat" + (" (skala log)" if multi else ""))
        st.plotly_chart(rapikan(fig, 140 + 30 * len(pv)), use_container_width=True)

        tot_plafon, tot_diikat = pv["plafon_usd"].sum(), pv["diikat_usd"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total plafon (grafik)", format_usd(tot_plafon))
        c2.metric("Sudah diikat", format_usd(tot_diikat))
        c3.metric("Terpakai", f"{100 * tot_diikat / tot_plafon:.0f}%")
        tabel = pv[["award_id", "nama_pendek", "mulai", "batas_pesan", "plafon_usd", "diikat_usd", "terpakai_persen",
                    "jumlah_pesanan", "tipe_award", "deskripsi", "url"]].copy()
        tabel["mulai"] = tabel["mulai"].dt.strftime("%Y-%m-%d")
        tabel["batas_pesan"] = tabel["batas_pesan"].dt.strftime("%Y-%m-%d")
        st.dataframe(tabel, hide_index=True, use_container_width=True, column_config={
            "award_id": "Kontrak", "nama_pendek": "Instansi", "mulai": "Mulai", "batas_pesan": "Batas pesan",
            "plafon_usd": st.column_config.NumberColumn("Plafon", format="dollar"),
            "diikat_usd": st.column_config.NumberColumn("Diikat", format="dollar"),
            "terpakai_persen": st.column_config.ProgressColumn("Terpakai", format="%.0f%%", min_value=0, max_value=100),
            "jumlah_pesanan": "Pesanan", "tipe_award": "Tipe", "deskripsi": "Deskripsi",
            "url": st.column_config.LinkColumn("USAspending", display_text="buka ↗")})
        st.caption("Persentase bisa lebih dari 100% pada kontrak lama: plafon awalnya kecil lalu dinaikkan lewat modifikasi "
                   "yang tidak selalu tercermin di kolom plafon terbaru.")

    belajar("Tiga angka yang sering tertukar",
            "- **Plafon** (*ceiling*, `base_and_all_options`): batas atas nilai kontrak bila semua opsi diambil.\n"
            "- **Obligasi** (*obligated*): dana yang sudah diikat secara hukum, angka utama dashboard ini.\n"
            "- **Outlay**: uang yang benar-benar sudah dibayarkan ke rekening Palantir.\n\n"
            "Plafon diambil dari `GET /api/v2/awards/{id}/`, total pesanan dari `GET /api/v2/idvs/amounts/{id}/`.")

# ----------------------------------------------------------------------------
# TAB 5. INGGRIS
# ----------------------------------------------------------------------------
with tab_uk:
    st.subheader("Inggris: dari pandemi ke NHS dan Kementerian Pertahanan")
    uk_inti = uk[~uk["framework"]]
    if uk_inti.empty:
        st.info("Tidak ada kontrak Inggris untuk filter ini.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Nilai kontrak", format_gbp(uk_inti["nilai_gbp"].sum()), help="Nilai yang diumumkan, bukan pembayaran.")
        porsi_uk = uk_inti.groupby("sektor")["nilai_gbp"].sum()
        c2.metric("Porsi kesehatan", f"{100 * porsi_uk.get(sektor.KESEHATAN, 0) / porsi_uk.sum():.0f}%")
        c3.metric("Pembeli berbeda", uk_inti["pembeli_rapi"].nunique())

        kiri, kanan = st.columns([1, 1])
        with kiri:
            peta = uk_inti.dropna(subset=["lat", "lon"]).copy()
            peta["ukuran"] = peta["nilai_gbp"].clip(lower=50_000) ** 0.5
            peta["nilai_teks"] = peta["nilai_gbp"].map(format_gbp)
            fig = px.scatter_map(peta, lat="lat", lon="lon", size="ukuran", color="sektor", color_discrete_map=WARNA_SEKTOR,
                                 hover_name="pembeli_rapi", custom_data=["judul", "nilai_teks", "tahun"],
                                 zoom=4.6, center=dict(lat=53.4, lon=-2.0), map_style="carto-darkmatter", size_max=38,
                                 title="Kantor pembeli (kode pos pengumuman)")
            fig.update_traces(hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]}<br>%{customdata[1]} · %{customdata[2]}<extra></extra>")
            st.plotly_chart(rapikan(fig, 520), use_container_width=True)
        with kanan:
            per_pembeli = (uk_inti.groupby(["pembeli_rapi", "sektor"], as_index=False)["nilai_gbp"].sum()
                           .sort_values("nilai_gbp").tail(12))
            per_pembeli["pembeli_rapi"] = per_pembeli["pembeli_rapi"].map(lambda n: n if len(n) <= 34 else n[:32] + "…")
            fig = px.bar(per_pembeli, x="nilai_gbp", y="pembeli_rapi", orientation="h", color="sektor",
                         color_discrete_map=WARNA_SEKTOR, title="Pembeli terbesar (GBP)")
            fig.update_traces(hovertemplate="<b>%{y}</b><br>£%{x:,.0f}<extra></extra>")
            fig.update_layout(yaxis_title=None, xaxis_title=None, xaxis_tickprefix="£", xaxis_tickformat=".2s",
                              showlegend=False, yaxis_categoryorder="total ascending")
            st.plotly_chart(rapikan(fig, 520), use_container_width=True)

        gab = analisis.gabung_as_uk(trx, uk)
        fig = px.bar(gab, x="tahun", y="nilai_usd", color="negara", barmode="group",
                     color_discrete_map={"Amerika Serikat": WARNA_AS, "Inggris": WARNA_UK},
                     title="AS vs Inggris per tahun (USD; Inggris dikonversi dengan kurs rata-rata tahunan)")
        fig.update_traces(hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>")
        fig.update_layout(yaxis_tickformat="$.2s", xaxis_title=None, yaxis_title=None)
        st.plotly_chart(rapikan(fig, 380), use_container_width=True)

        tabel = uk.sort_values("tanggal", ascending=False)[
            ["tanggal", "pembeli_rapi", "judul", "nilai_gbp", "sektor", "framework", "url"]].copy()
        tabel["tanggal"] = tabel["tanggal"].dt.strftime("%Y-%m-%d")
        st.dataframe(tabel, hide_index=True, use_container_width=True, column_config={
            "tanggal": "Tanggal", "pembeli_rapi": "Pembeli", "judul": "Judul",
            "nilai_gbp": st.column_config.NumberColumn("Nilai (GBP)", format="localized"),
            "sektor": "Sektor", "framework": st.column_config.CheckboxColumn("Framework"),
            "url": st.column_config.LinkColumn("Contracts Finder", display_text="buka ↗")})
        st.caption("Framework (mis. CCS Back Office Software £1,2 miliar) adalah daftar pemasok bersama puluhan perusahaan, "
                   "jadi tidak dihitung dalam total. Contracts Finder juga tidak memuat kontrak NHS lokal yang di bawah "
                   "ambang pelaporan.")

    belajar("Kenapa angka Inggris tidak bisa langsung dijumlah dengan AS",
            "Contracts Finder mencatat **nilai kontrak saat diumumkan** (sering untuk beberapa tahun sekaligus), "
            "sedangkan USAspending mencatat **obligasi per transaksi**. Karena itu grafik AS vs Inggris hanya untuk "
            "melihat skala, bukan perbandingan apel dengan apel. Kurs GBP→USD memakai rata-rata tahunan kurs ECB "
            "(Frankfurter API).",
            "uk['nilai_usd'] = uk['nilai_gbp'] * uk['tahun'].map(kurs_tahunan)")

# ----------------------------------------------------------------------------
# TAB 6. CARI KONTRAK
# ----------------------------------------------------------------------------
with tab_cari:
    st.subheader("Cari kontrak")
    c1, c2 = st.columns([3, 1])
    kata = c1.text_input("Kata kunci (deskripsi, instansi, nomor kontrak)", placeholder="contoh: Maven, Vantage, ICE, COVID")
    sumber_cari = c2.radio("Sumber", ["AS", "Inggris"], horizontal=True)
    if sumber_cari == "AS":
        hasil = analisis.cari(kontrak, kata, ["award_id", "deskripsi", "instansi", "sub_instansi", "nama_pendek"])
        hasil = hasil.sort_values("nilai_usd", ascending=False)
        st.caption(md(f"{len(hasil):,} kontrak · total {format_usd(hasil['nilai_usd'].sum())}".replace(",", ".", 1)))
        tampil = hasil[["award_id", "url", "nama_pendek", "nilai_usd", "mulai", "deskripsi", "sektor", "jenis", "selesai"]].copy()
        tampil["mulai"] = tampil["mulai"].dt.strftime("%Y-%m-%d")
        tampil["selesai"] = tampil["selesai"].dt.strftime("%Y-%m-%d")
        st.dataframe(tampil, hide_index=True, use_container_width=True, height=520, column_config={
            "award_id": "Kontrak", "mulai": "Mulai", "selesai": "Selesai", "nama_pendek": "Instansi", "sektor": "Sektor",
            "nilai_usd": st.column_config.NumberColumn("Diikat (USD)", format="dollar"), "jenis": "Jenis",
            "deskripsi": st.column_config.TextColumn("Deskripsi", width="large"),
            "url": st.column_config.LinkColumn("USAspending", display_text="buka ↗")})
        st.download_button("⬇️ Unduh hasil (CSV)", hasil.drop(columns=["url"]).to_csv(index=False).encode("utf-8"),
                           "kontrak_palantir_as.csv", "text/csv")
    else:
        hasil = analisis.cari(uk_semua[uk_semua["sektor"].isin(sektor_pilih)], kata, ["judul", "deskripsi", "pembeli"])
        st.caption(f"{len(hasil):,} pengumuman")
        tampil = hasil[["tanggal", "url", "pembeli_rapi", "judul", "nilai_gbp", "deskripsi"]].copy()
        tampil["tanggal"] = tampil["tanggal"].dt.strftime("%Y-%m-%d")
        st.dataframe(tampil, hide_index=True, use_container_width=True, height=520, column_config={
            "tanggal": "Tanggal", "pembeli_rapi": "Pembeli", "judul": "Judul",
            "nilai_gbp": st.column_config.NumberColumn("Nilai (GBP)", format="localized"),
            "deskripsi": st.column_config.TextColumn("Deskripsi", width="large"),
            "url": st.column_config.LinkColumn("Contracts Finder", display_text="buka ↗")})
    belajar("Pencarian sederhana",
            "Tidak ada mesin pencari khusus: semua kolom teks digabung jadi satu string per baris, lalu dicari dengan "
            "`str.contains` yang tidak peka huruf besar-kecil.",
            "gabungan = df[kolom].fillna('').astype(str).agg(' '.join, axis=1)\n"
            "df[gabungan.str.contains(kata, case=False, regex=False)]")

# ----------------------------------------------------------------------------
# TAB 7. DATA & SUMBER
# ----------------------------------------------------------------------------
with tab_data:
    st.subheader("Data & sumber")
    st.markdown(
        f"""
| File | Isi | Baris |
|---|---|---|
| `data/as_transaksi.csv` | Setiap aksi kontrak federal AS ke Palantir Technologies Inc., Palantir USG Inc., dan Palantir USA Inc. | {len(trx_semua):,} |
| `data/as_kontrak.csv` | Ringkasan per kontrak (award): instansi, tanggal, deskripsi, total diikat | {len(kontrak_semua):,} |
| `data/as_idv.csv` | Kontrak payung (IDV/BPA) dengan plafon dan total pesanan | {len(idv_semua):,} |
| `data/uk_kontrak.csv` | Pengumuman kontrak Inggris yang dimenangkan Palantir | {len(uk_semua):,} |
| `data/kurs_gbp_usd.csv` | Rata-rata kurs GBP→USD per tahun (ECB) | - |
| `data/momen_penting.csv` | Momen penting yang dikurasi manual, masing-masing dengan tautan sumber | {len(momen)} |

**Sumber**
- [USAspending.gov API](https://api.usaspending.gov/) (Department of the Treasury), endpoint `search/spending_by_transaction`,
  `search/spending_by_award`, `awards/{{id}}`, `idvs/amounts/{{id}}`. Domain publik.
- [Contracts Finder API](https://www.contractsfinder.service.gov.uk/apidocumentation) (Cabinet Office),
  Open Government Licence v3.0.
- [Frankfurter](https://frankfurter.dev/) untuk kurs referensi ECB.

**Batasan yang perlu diingat**
1. Kontrak rahasia (CIA, NSA, NRO, sebagian SOCOM) tidak muncul di USAspending, jadi semua angka AS adalah batas bawah.
2. Penjualan lewat reseller atau integrator (mis. sub-kontrak di bawah perusahaan lain) tercatat atas nama perusahaan itu.
3. Contracts Finder hanya memuat kontrak di atas ambang pelaporan dan sejak 2015; Skotlandia dan Wales punya portal sendiri.
4. Pemetaan sektor dibuat dengan aturan sederhana dan bisa diperdebatkan (mis. Coast Guard dimasukkan ke keamanan dalam negeri).
        """
    )
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ Transaksi AS", trx_semua.drop(columns=["url"]).to_csv(index=False).encode("utf-8"),
                       "as_transaksi.csv", "text/csv")
    c2.download_button("⬇️ Kontrak payung AS", idv_semua.drop(columns=["url"]).to_csv(index=False).encode("utf-8"),
                       "as_idv.csv", "text/csv")
    c3.download_button("⬇️ Kontrak Inggris", uk_semua.to_csv(index=False).encode("utf-8"), "uk_kontrak.csv", "text/csv")

# ----------------------------------------------------------------------------
# TAB 8. CARA KERJA
# ----------------------------------------------------------------------------
with tab_cara:
    st.subheader("Cara kerja")
    st.markdown(
        """
```
USAspending API ──┐                                   ┌── src/sektor.py      instansi → sektor (aturan regex)
Contracts Finder ─┼─► scripts/kumpulkan_data.py ─► data/*.csv ─► src/muat_data.py ─► src/analisis.py ─► app.py
Frankfurter (ECB)─┘        (sekali seminggu via GitHub Actions)        kolom turunan      agregasi         Plotly + Streamlit
```

1. **Kumpulkan.** `scripts/kumpulkan_data.py` memanggil API pencarian USAspending dengan teks penerima "Palantir",
   lalu menyaring hanya entitas resmi Palantir (daftar putih nama). Pencarian teks juga menemukan perusahaan lain
   seperti *Palantir.net Inc* atau *Lonely Mountain Palantir Enterprises*, jadi penyaringan ini penting.
2. **Inggris.** Contracts Finder dicari dengan kata kunci "Palantir" untuk kontrak berstatus *Awarded*, lalu disaring:
   pemenangnya harus Palantir. Kontrak yang hanya *menyebut* Palantir (mis. migrasi keluar dari Palantir) dibuang.
3. **Rapikan.** `src/muat_data.py` menambahkan tahun kalender dan tahun fiskal AS, sektor, nama pendek instansi,
   tautan ke halaman resmi, dan konversi GBP→USD.
4. **Hitung.** `src/analisis.py` berisi fungsi murni (tanpa Streamlit) untuk agregasi per tahun, sektor, instansi,
   negara bagian, plafon vs realisasi, dan angka ringkasan. Semuanya diuji di `tests/`.
5. **Tampilkan.** `app.py` hanya mengatur tata letak dan grafik.
        """
    )
    aturan = pd.DataFrame([{"Instansi (regex)": a or "apa saja", "Sub-instansi (regex)": b or "apa saja", "Sektor": s}
                           for a, b, s in sektor.ATURAN_AS] + [{"Instansi (regex)": "lainnya", "Sub-instansi (regex)": "-",
                                                                "Sektor": sektor.SIPIL}])
    st.markdown("**Aturan sektor untuk instansi AS** (dicek dari atas, aturan pertama yang cocok menang)")
    st.dataframe(aturan, hide_index=True, use_container_width=True)
    belajar("Memanggil API USAspending sendiri",
            "API ini gratis dan tanpa key. Hasilnya dibagi per halaman (100 baris); `page_metadata.hasNext` memberi tahu "
            "apakah masih ada halaman berikutnya.",
            "import requests\n"
            "payload = {\n"
            "    'filters': {'recipient_search_text': ['Palantir'], 'award_type_codes': ['A', 'B', 'C', 'D']},\n"
            "    'fields': ['Action Date', 'Award ID', 'Transaction Amount', 'Awarding Sub Agency'],\n"
            "    'limit': 100, 'page': 1,\n"
            "}\n"
            "r = requests.post('https://api.usaspending.gov/api/v2/search/spending_by_transaction/', json=payload)\n"
            "r.json()['results'][:3]")
