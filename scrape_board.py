"""
Scraping Arrival & Departure Board FlightRadar24
Bandara: CGK, DPS, BPN, KNO, PKU, SUB, UPG, YIA, SIN, KUL
- Mode 24 jam (uncheck 12-hour clock)
- Data H-1 via klik "Load earlier flights"
- Intercept respons JSON langsung dari dalam browser Playwright
"""

import json
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
from playwright.sync_api import sync_playwright, Response

WIB = timezone(timedelta(hours=7))

AIRPORTS = {
    "CGK": "Jakarta Soekarno-Hatta",
    "DPS": "Denpasar Ngurah Rai",
    "BPN": "Balikpapan Sultan Aji Muhammad Sulaiman",
    "KNO": "Medan Kualanamu",
    "PKU": "Pekanbaru Sultan Syarif Kasim II",
    "SUB": "Surabaya Juanda",
    "UPG": "Makassar Sultan Hasanuddin",
    "YIA": "Yogyakarta International",
    "SIN": "Singapore Changi",
    "KUL": "Kuala Lumpur International",
}
BOARDS = {
    "arrivals":   "Arrivals",
    "departures": "Departures",
}

import sys
# Argumen: "today" atau "yesterday" (default: yesterday)
MODE = sys.argv[1] if len(sys.argv) > 1 else "yesterday"
TARGET_DATE = (
    datetime.now(WIB).strftime("%Y-%m-%d")
    if MODE == "today"
    else (datetime.now(WIB) - timedelta(days=1)).strftime("%Y-%m-%d")
)
YESTERDAY = TARGET_DATE  # alias agar kode di bawah tidak perlu diubah


def parse_schedule(data: dict, iata: str, board_type: str) -> list[dict]:
    """Ekstrak baris dari JSON respons airport.json FR24."""
    rows = []
    try:
        flights = (
            data["result"]["response"]["airport"]
                ["pluginData"]["schedule"][board_type]["data"]
        )
    except (KeyError, TypeError):
        return rows

    for item in flights:
        try:
            flight  = item.get("flight", {})
            ident   = flight.get("identification", {}) or {}
            status  = flight.get("status", {}) or {}
            airline = flight.get("airline", {}) or {}
            apt     = flight.get("airport", {}) or {}
            ac      = flight.get("aircraft", {}) or {}
            times   = flight.get("time", {}) or {}

            origin = apt.get("origin", {}) or {}
            dest   = apt.get("destination", {}) or {}

            def ts2hm(ts):
                if not ts:
                    return ""
                try:
                    return datetime.fromtimestamp(int(ts), tz=WIB).strftime("%H:%M")
                except Exception:
                    return ""

            def ts2date(ts):
                if not ts:
                    return ""
                try:
                    return datetime.fromtimestamp(int(ts), tz=WIB).strftime("%Y-%m-%d")
                except Exception:
                    return ""

            sched = times.get("scheduled", {}) or {}
            real  = times.get("real", {}) or {}
            est   = times.get("estimated", {}) or {}

            sched_dep, sched_arr = sched.get("departure"), sched.get("arrival")
            real_dep,  real_arr  = real.get("departure"),  real.get("arrival")
            est_dep,   est_arr   = est.get("departure"),   est.get("arrival")

            if board_type == "arrivals":
                jadwal = ts2hm(sched_arr)
                aktual = ts2hm(real_arr or est_arr)
                tanggal = ts2date(sched_arr)
            else:
                jadwal = ts2hm(sched_dep)
                aktual = ts2hm(real_dep or est_dep)
                tanggal = ts2date(sched_dep)

            row = {
                "bandara":       iata,
                "tipe":          board_type,
                "tanggal":       tanggal,
                "waktu_jadwal":  jadwal,
                "waktu_aktual":  aktual,
                "nomor_flight":  (ident.get("number", {}) or {}).get("default", ""),
                "callsign":      ident.get("callsign", "") or "",
                "asal_iata":     ((origin.get("code", {}) or {}).get("iata", "")),
                "asal_nama":     origin.get("name", "") or "",
                "tujuan_iata":   ((dest.get("code", {}) or {}).get("iata", "")),
                "tujuan_nama":   dest.get("name", "") or "",
                "maskapai":      airline.get("name", "") or "",
                "maskapai_iata": ((airline.get("code", {}) or {}).get("iata", "")),
                "kode_pesawat":  ((ac.get("model", {}) or {}).get("code", "")),
                "nama_pesawat":  ((ac.get("model", {}) or {}).get("text", "")),
                "registrasi":    ac.get("registration", "") or "",
                "status":        status.get("text", "") or "",
                "scraped_at":    datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S"),
            }
            rows.append(row)
        except Exception:
            continue
    return rows


def scrape_airport_board(iata: str, board_type: str) -> list[dict]:
    """
    Buka halaman board FR24 di Playwright, intercept API response,
    lalu klik 'Load earlier flights' sampai data H-1 terkumpul.
    """
    url = f"https://www.flightradar24.com/data/airports/{iata.lower()}/{board_type}"
    collected_rows: list[dict] = []
    api_responses: list[dict] = []

    def on_response(resp: Response):
        if "api.flightradar24.com/common/v1/airport.json" in resp.url:
            try:
                data = resp.json()
                api_responses.append(data)
            except Exception:
                pass

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
        page.on("response", on_response)

        print(f"\n  Membuka: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Tutup cookie/overlay jika ada
        for sel in [
            "button:has-text('Accept')", "button:has-text('I agree')",
            "button:has-text('Accept all')", "button:has-text('OK')",
            "button:has-text('Got it')", "[aria-label='Close']",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1500):
                    btn.click()
                    page.wait_for_timeout(400)
            except Exception:
                pass

        # Tunggu API response pertama (data hari ini)
        page.wait_for_timeout(6000)

        # ── Set 24-jam clock via localStorage (lebih andal dari UI) ──────
        page.evaluate("""() => {
            try {
                let s = JSON.parse(localStorage.getItem('fr24_settings') || '{}');
                s['time_mode'] = '24h';
                localStorage.setItem('fr24_settings', JSON.stringify(s));
            } catch(e) {}
        }""")

        # ── Klik "Load earlier flights" sampai mencapai data H-1 ─────────
        max_clicks = 20
        clicks = 0
        reached_yesterday = False

        for _ in range(max_clicks):
            # Parse response yang sudah terkumpul
            for resp_data in api_responses:
                rows = parse_schedule(resp_data, iata, board_type)
                for r in rows:
                    if r["tanggal"] == YESTERDAY:
                        reached_yesterday = True
                    if r not in collected_rows:
                        collected_rows.append(r)
            api_responses.clear()

            if reached_yesterday:
                # Pastikan semua data H-1 sudah termuat
                # Klik sekali lagi untuk lihat apakah ada lebih
                pass

            # Cari tombol "Load earlier flights"
            try:
                btn = page.locator("button:has-text('Load earlier flights'), "
                                   "a:has-text('Load earlier flights'), "
                                   "[class*='earlier']").first
                if btn.is_visible(timeout=3000):
                    btn.scroll_into_view_if_needed()
                    btn.click()
                    page.wait_for_timeout(3000)
                    clicks += 1
                    print(f"    → Klik 'Load earlier flights' #{clicks}", end=" | ", flush=True)

                    # Cek apakah sudah melampaui H-1
                    oldest = min(
                        (r["tanggal"] for r in collected_rows if r["tanggal"]),
                        default=""
                    )
                    if oldest and oldest < YESTERDAY:
                        print(f"sudah melewati {YESTERDAY}, stop.")
                        break
                else:
                    print("    → Tombol tidak ditemukan, selesai.")
                    break
            except Exception as e:
                print(f"    → Error: {e}")
                break

        # Ambil sisa response
        page.wait_for_timeout(2000)
        for resp_data in api_responses:
            rows = parse_schedule(resp_data, iata, board_type)
            for r in rows:
                if r not in collected_rows:
                    collected_rows.append(r)

        browser.close()

    # Filter hanya data H-1
    h1_rows = [r for r in collected_rows if r["tanggal"] == YESTERDAY]
    print(f"\n    Total terkumpul: {len(collected_rows)} | H-1: {len(h1_rows)}")
    return h1_rows


def save(all_rows: list):
    if not all_rows:
        print("\n[!] Tidak ada data H-1 yang berhasil diambil.")
        return

    # Format nama file: YYMMDD-Flightradar (tanggal data yang diambil)
    date_str = datetime.strptime(TARGET_DATE, "%Y-%m-%d").strftime("%y%m%d")
    xlsx     = f"{date_str}-Flightradar.xlsx"
    json_f   = f"{date_str}-Flightradar.json"

    df = pd.DataFrame(all_rows)
    # Urutkan: bandara → tipe → tanggal → waktu_jadwal
    df = df.sort_values(["bandara", "tipe", "waktu_jadwal"], ignore_index=True)

    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Semua Data", index=False)
        for iata in AIRPORTS:
            for board in BOARDS:
                sub = df[(df["bandara"] == iata) & (df["tipe"] == board)]
                if not sub.empty:
                    sub.to_excel(writer,
                                 sheet_name=f"{iata} {BOARDS[board]}",
                                 index=False)

        # Auto-fit lebar kolom semua sheet
        for sheet in writer.book.worksheets:
            for col in sheet.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        max_len = max(max_len, len(str(cell.value or "")))
                    except Exception:
                        pass
                sheet.column_dimensions[col_letter].width = min(max_len + 2, 50)
            # Freeze baris pertama (header)
            sheet.freeze_panes = "A2"

    with open(json_f, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)

    print(f"\n  [OK] Excel : {xlsx}")
    print(f"  [OK] JSON  : {json_f}")

    # Ringkasan
    lbl2 = "Hari Ini" if MODE == "today" else "H-1"
    print(f"\n{'='*60}")
    print(f"  RINGKASAN DATA {lbl2} ({TARGET_DATE})")
    print(f"{'='*60}")
    print(f"  {'Bandara':<34} {'Arrivals':>9} {'Departures':>11}")
    print(f"  {'-'*56}")
    for iata, name in AIRPORTS.items():
        arr = len(df[(df["bandara"] == iata) & (df["tipe"] == "arrivals")])
        dep = len(df[(df["bandara"] == iata) & (df["tipe"] == "departures")])
        print(f"  {name} ({iata}){'':>4} {arr:>9} {dep:>11}")
    print(f"  {'-'*56}")
    arr_tot = len(df[df["tipe"] == "arrivals"])
    dep_tot = len(df[df["tipe"] == "departures"])
    print(f"  {'TOTAL':<34} {arr_tot:>9} {dep_tot:>11}")

    # Preview beberapa baris
    print(f"\n  Preview 5 baris pertama:")
    cols = ["tipe", "waktu_jadwal", "waktu_aktual", "nomor_flight",
            "asal_nama", "tujuan_nama", "maskapai", "kode_pesawat", "status"]
    print(df[cols].head(5).to_string(index=False))


def main():
    label = "Hari Ini" if MODE == "today" else "H-1"
    print("=" * 60)
    print(f"  FlightRadar24 Board Scraper — CGK & DPS ({label})")
    print(f"  Waktu   : {datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S WIB')}")
    print(f"  Target  : {label} = {TARGET_DATE}")
    print("=" * 60)

    all_rows = []
    for iata in AIRPORTS:
        print(f"\n{'='*60}")
        print(f"  Bandara: {AIRPORTS[iata]} ({iata})")
        print(f"{'='*60}")
        for board in BOARDS:
            rows = scrape_airport_board(iata, board)
            all_rows.extend(rows)
            time.sleep(2)

    save(all_rows)
    print(f"\n  Selesai: {datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S WIB')}")


if __name__ == "__main__":
    main()
