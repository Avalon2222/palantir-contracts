from src import sektor


def test_militer():
    assert sektor.sektor_as("Department of Defense", "Department of the Army") == sektor.MILITER
    assert sektor.sektor_as("Department of Defense", "U.S. Special Operations Command") == sektor.MILITER


def test_imigrasi_dipisah_dari_dhs_lain():
    assert sektor.sektor_as("Department of Homeland Security",
                            "U.S. Immigration and Customs Enforcement") == sektor.IMIGRASI
    assert sektor.sektor_as("Department of Homeland Security", "U.S. Customs and Border Protection") == sektor.IMIGRASI
    assert sektor.sektor_as("Department of Homeland Security", "U.S. Secret Service") == sektor.HUKUM


def test_kesehatan_keuangan_luar_negeri():
    assert sektor.sektor_as("Department of Health and Human Services", "National Institutes of Health") == sektor.KESEHATAN
    assert sektor.sektor_as("Department of Veterans Affairs", "Department of Veterans Affairs") == sektor.KESEHATAN
    assert sektor.sektor_as("Department of the Treasury", "Internal Revenue Service") == sektor.KEUANGAN
    assert sektor.sektor_as("Department of State", "Department of State") == sektor.LUAR_NEGERI


def test_sisanya_sipil():
    assert sektor.sektor_as("National Aeronautics and Space Administration") == sektor.SIPIL
    assert sektor.sektor_as("") == sektor.SIPIL


def test_sektor_uk():
    assert sektor.sektor_uk("MINISTRY OF DEFENCE") == sektor.MILITER
    assert sektor.sektor_uk("NHS England") == sektor.KESEHATAN
    assert sektor.sektor_uk("London Ambulance Service NHS Trust") == sektor.KESEHATAN
    assert sektor.sektor_uk("METROPOLITAN POLICE SERVICE") == sektor.HUKUM
    assert sektor.sektor_uk("Financial Conduct Authority") == sektor.KEUANGAN
    assert sektor.sektor_uk("Coventry City Council") == sektor.SIPIL


def test_setiap_sektor_punya_warna():
    assert set(sektor.URUTAN_SEKTOR) == set(sektor.WARNA_SEKTOR)


def test_singkat():
    assert sektor.singkat("U.S. Immigration and Customs Enforcement") == "ICE"
    assert sektor.singkat("Nama Tidak Dikenal") == "Nama Tidak Dikenal"
