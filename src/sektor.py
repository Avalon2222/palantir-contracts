"""
src/sektor.py - Memetakan instansi pemerintah ke sektor
=======================================================
USAspending dan Contracts Finder hanya mencatat NAMA instansi (mis. "Department of the Army",
"U.S. Immigration and Customs Enforcement", "NHS England"). Agar bisa menjawab pertanyaan
"uang Palantir datang dari militer, imigrasi, atau kesehatan?", setiap instansi dipetakan ke satu sektor
dengan aturan sederhana yang bisa dibaca manusia (bukan model ML). Aturan dicek berurutan, aturan
pertama yang cocok menang.
"""

from __future__ import annotations

import re

MILITER = "Militer & pertahanan"
IMIGRASI = "Imigrasi & perbatasan"
HUKUM = "Keamanan dalam negeri & hukum"
KESEHATAN = "Kesehatan"
KEUANGAN = "Keuangan & pajak"
LUAR_NEGERI = "Diplomasi & luar negeri"
SIPIL = "Sipil lainnya"

URUTAN_SEKTOR = [MILITER, IMIGRASI, HUKUM, KESEHATAN, KEUANGAN, LUAR_NEGERI, SIPIL]
WARNA_SEKTOR = {
    MILITER: "#fb923c",
    IMIGRASI: "#f43f5e",
    HUKUM: "#a78bfa",
    KESEHATAN: "#34d399",
    KEUANGAN: "#facc15",
    LUAR_NEGERI: "#38bdf8",
    SIPIL: "#94a3b8",
}

# (pola instansi, pola sub-instansi, sektor). Pola None = cocok dengan apa saja.
ATURAN_AS: list[tuple[str | None, str | None, str]] = [
    (r"Department of Defense", None, MILITER),
    (r"Homeland Security", r"Immigration and Customs|Customs and Border|Citizenship and Immigration", IMIGRASI),
    (r"Homeland Security", None, HUKUM),
    (r"Department of Justice", None, HUKUM),
    (r"Health and Human Services|Veterans Affairs", None, KESEHATAN),
    (r"Treasury|Securities and Exchange|Federal Deposit|Consumer Financial|Federal Reserve", None, KEUANGAN),
    (r"Department of State|International Development|Agency for International", None, LUAR_NEGERI),
]

# Pembeli Inggris: satu kolom nama organisasi.
ATURAN_UK: list[tuple[str, str]] = [
    (r"defen[cs]e|\bMOD\b|army|royal navy|royal air force", MILITER),
    (r"home office|border force", IMIGRASI),
    (r"police|crime agency|justice", HUKUM),
    (r"\bNHS\b|health|ambulance|commissioning support|social care|hospital", KESEHATAN),
    (r"financial conduct|treasury|HMRC|revenue", KEUANGAN),
    (r"foreign|FCDO|international development", LUAR_NEGERI),
]


def _cocok(pola: str | None, teks: str) -> bool:
    return pola is None or re.search(pola, teks or "", flags=re.I) is not None


def sektor_as(instansi: str, sub_instansi: str = "") -> str:
    """Sektor untuk satu instansi federal AS."""
    for p_instansi, p_sub, sektor in ATURAN_AS:
        if _cocok(p_instansi, instansi) and _cocok(p_sub, sub_instansi):
            return sektor
    return SIPIL


def sektor_uk(pembeli: str) -> str:
    """Sektor untuk satu pembeli sektor publik Inggris."""
    for pola, sektor in ATURAN_UK:
        if _cocok(pola, pembeli):
            return sektor
    return SIPIL


# Nama pendek agar label grafik tidak kepanjangan.
SINGKATAN = {
    "Department of the Army": "US Army",
    "Department of the Air Force": "US Air Force",
    "Department of the Navy": "US Navy",
    "U.S. Special Operations Command": "SOCOM",
    "U.S. Immigration and Customs Enforcement": "ICE",
    "U.S. Citizenship and Immigration Services": "USCIS",
    "U.S. Customs and Border Protection": "CBP",
    "Internal Revenue Service": "IRS",
    "National Institutes of Health": "NIH",
    "Centers for Disease Control and Prevention": "CDC",
    "Food and Drug Administration": "FDA",
    "Federal Bureau of Investigation": "FBI",
    "Drug Enforcement Administration": "DEA",
    "Department of Veterans Affairs": "Veterans Affairs (VA)",
    "Department of State": "State Department",
    "Federal Aviation Administration": "FAA",
    "Securities and Exchange Commission": "SEC",
    "Defense Counterintelligence and Security Agency": "DCSA",
    "Missile Defense Agency": "Missile Defense Agency",
    "Defense Information Systems Agency": "DISA",
    "Defense Logistics Agency": "DLA",
    "U.S. Secret Service": "Secret Service",
    "U.S. Coast Guard": "Coast Guard",
    "Federal Emergency Management Agency": "FEMA",
    "National Aeronautics and Space Administration": "NASA",
    "Office of the Chief Financial Officer": "USDA (Office of the CFO)",
    "Offices, Boards and Divisions": "DOJ (Offices, Boards & Divisions)",
    "Office of Procurement Operations": "DHS (department-wide)",
    "Office of the Assistant Secretary for Administration": "HHS (Administration)",
    "Office of the Assistant Secretary for Financial Resources": "HHS (Financial Resources)",
    "Federal Acquisition Service": "GSA",
    "Department of Energy": "Department of Energy",
}


def singkat(nama: str) -> str:
    return SINGKATAN.get(nama, nama)
