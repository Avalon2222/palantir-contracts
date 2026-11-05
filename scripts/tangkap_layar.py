"""
scripts/tangkap_layar.py - Membuat screenshot README dengan Playwright (Chromium headless)
=========================================================================================
1. Jalankan aplikasi:   streamlit run app.py --server.port 8599 --server.headless true
2. Jalankan skrip ini:  python scripts/tangkap_layar.py  [path-chromium-opsional]

Hasil: docs/screenshots/*.png (1440x900).
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

URL = "http://localhost:8599"
FOLDER = Path(__file__).resolve().parents[1] / "docs" / "screenshots"


def buka_tab(page: Page, nama: str) -> None:
    page.get_by_role("tab", name=nama).click()
    page.wait_for_timeout(3500)


def gulir_ke(page: Page, teks: str, offset: int = 70) -> None:
    """Gulir kontainer utama Streamlit sampai elemen berisi `teks` berada di atas layar."""
    page.evaluate(
        """([teks, offset]) => {
            const el = [...document.querySelectorAll('h1,h2,h3,h4,p,div.kartu,[data-testid=stMarkdownContainer] span')]
                .find(e => e.offsetParent !== null && e.textContent.includes(teks));
            if (!el) return;
            el.scrollIntoView({block: 'start'});
            const main = document.querySelector('[data-testid=stMain]') || document.scrollingElement;
            main.scrollBy(0, -offset);
        }""",
        [teks, offset],
    )
    page.wait_for_timeout(1200)


def simpan(page: Page, nama: str) -> None:
    page.screenshot(path=str(FOLDER / nama))
    print("tersimpan", nama)


def main() -> None:
    FOLDER.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        exe = sys.argv[1] if len(sys.argv) > 1 else None
        browser = p.chromium.launch(executable_path=exe)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(URL)
        page.wait_for_timeout(10000)

        simpan(page, "01_peta.png")
        gulir_ke(page, "Di mana kontraknya dikerjakan", 20)
        simpan(page, "02_peta_dunia.png")

        buka_tab(page, "📈 Timeline")
        gulir_ke(page, "Dari startup kecil")
        simpan(page, "03_timeline.png")
        gulir_ke(page, "Momen penting")
        simpan(page, "04_momen.png")

        buka_tab(page, "🏛️ Per instansi")
        gulir_ke(page, "Siapa pelanggan terbesarnya")
        simpan(page, "05_instansi.png")
        gulir_ke(page, "Kapan setiap instansi mulai membeli")
        simpan(page, "06_heatmap.png")

        buka_tab(page, "💰 Plafon vs realisasi")
        gulir_ke(page, "Plafon miliaran")
        simpan(page, "07_plafon.png")

        buka_tab(page, "🇬🇧 Inggris")
        gulir_ke(page, "Inggris: dari pandemi")
        page.wait_for_timeout(3000)  # peta MapLibre butuh waktu memuat tile
        simpan(page, "08_inggris.png")

        buka_tab(page, "🔎 Cari kontrak")
        page.get_by_placeholder("contoh: Maven").fill("Maven")
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)
        gulir_ke(page, "Cari kontrak")
        simpan(page, "09_cari.png")

        page.get_by_text("🎓 Learning mode").click()
        page.wait_for_timeout(4000)
        buka_tab(page, "💰 Plafon vs realisasi")
        gulir_ke(page, "Persentase bisa lebih dari 100%", 10)
        simpan(page, "10_learning_mode.png")
        browser.close()


if __name__ == "__main__":
    main()
