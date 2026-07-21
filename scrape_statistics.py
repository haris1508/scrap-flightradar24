"""
Scraping statistik global FlightRadar24
Sumber: https://www.flightradar24.com/data/statistics

Halaman memuat 2 grafik Highcharts:
  chart 0 = Total flights      (semua jenis penerbangan)
  chart 1 = Commercial flights (penumpang + kargo + charter + sebagian bizjet)

Catatan penting soal sumbu waktu:
  Semua tahun DITUMPUK pada sumbu tanggal tahun berjalan supaya bisa
  dibandingkan. Jadi tanggal asli harus dipetakan ulang memakai tahun
  dari nama seri ("2024 Number of flights" -> tahun 2024).

Seri harian selain tahun berjalan disembunyikan di UI (hanya moving average
yang tampil), sehingga getCSV() bawaan Highcharts tidak memuatnya. Karena itu
data diambil langsung dari objek seri, bukan dari tombol export.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
from playwright.sync_api import sync_playwright

WIB = timezone(timedelta(hours=7))
URL = "https://www.flightradar24.com/data/statistics"

# Ambil hanya seri angka harian; moving average diabaikan (bisa dihitung sendiri)
JS_EXTRACT = """() => {
    const H = window.Highcharts;
    if (!H || !H.charts) return null;
    const charts = H.charts.filter(Boolean);
    if (charts.length < 2) return null;

    const ambil = (chart) => {
        const hasil = [];
        chart.series.forEach(s => {
            const m = /^(\\d{4}) Number of flights$/.exec(s.name || "");
            if (!m) return;                       // lewati moving average
            const tahun = parseInt(m[1], 10);
            // Tanggal ditentukan dari URUTAN titik (hari ke-n sejak 1 Jan),
            // bukan dari nilai x. Sumbu tumpuk memakai tahun berjalan yang
            // belum tentu kabisat, sehingga 29 Feb bisa hilang/tergeser.
            const titik = s.data.slice().sort((a, b) => a.x - b.x);
            titik.forEach((p, i) => {
                if (p.y === null || p.y === undefined) return;
                const iso = new Date(Date.UTC(tahun, 0, 1 + i))
                    .toISOString().slice(0, 10);
                hasil.push([iso, p.y]);
            });
        });
        return hasil;
    };

    return { total: ambil(charts[0]), commercial: ambil(charts[1]) };
}"""


def scrape() -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="en-US",
            timezone_id="Asia/Jakarta",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        print(f"  Membuka: {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        # Tutup cookie/overlay bila muncul
        for sel in [
            "button:has-text('Accept')", "button:has-text('I agree')",
            "button:has-text('Accept all')", "button:has-text('OK')",
            "[aria-label='Close']",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1500):
                    btn.click()
                    page.wait_for_timeout(400)
            except Exception:
                pass

        # Tunggu Highcharts selesai membangun kedua grafik
        try:
            page.wait_for_function(
                "() => window.Highcharts && window.Highcharts.charts "
                "&& window.Highcharts.charts.filter(Boolean).length >= 2",
                timeout=45000,
            )
        except Exception:
            browser.close()
            raise RuntimeError("Grafik Highcharts tidak muncul (halaman berubah / diblokir).")

        page.wait_for_timeout(2000)
        data = page.evaluate(JS_EXTRACT)
        browser.close()

    if not data:
        raise RuntimeError("Gagal membaca data dari grafik.")
    return data


def save(data: dict):
    def to_series(pairs, nama):
        df = pd.DataFrame(pairs, columns=["tanggal", nama])
        # 29 Feb tahun kabisat bisa menimpa saat ditumpuk; ambil nilai pertama
        return df.drop_duplicates(subset="tanggal", keep="first").set_index("tanggal")[nama]

    total = to_series(data["total"], "total_flights")
    comm = to_series(data["commercial"], "commercial_flights")

    df = pd.concat([comm, total], axis=1).sort_index()
    df = df.dropna(how="all")
    df.index.name = "tanggal"
    df = df.reset_index()

    # Kolom bantu untuk analisis
    df["share_commercial_%"] = (
        100 * df["commercial_flights"] / df["total_flights"]
    ).round(1)

    os.makedirs("csv", exist_ok=True)
    out = os.path.join("csv", "fr24-statistics-harian.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")

    print(f"\n  [OK] Tersimpan: {out}")
    print(f"  Baris   : {len(df)}")
    print(f"  Rentang : {df['tanggal'].iloc[0]} -> {df['tanggal'].iloc[-1]}")
    print("\n  Cakupan per tahun:")
    for th, n in df["tanggal"].str[:4].value_counts().sort_index().items():
        print(f"    {th}: {n} hari")
    print("\n  5 baris terakhir:")
    print(df.tail(5).to_string(index=False))
    return df


def main():
    print("=" * 60)
    print("  FlightRadar24 — Statistik Global (Total & Commercial)")
    print(f"  Waktu: {datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S WIB')}")
    print("=" * 60)

    data = scrape()
    if not data.get("commercial"):
        print("\n[GAGAL] Data commercial kosong.")
        sys.exit(1)

    save(data)
    print(f"\n  Selesai: {datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S WIB')}")


if __name__ == "__main__":
    main()
