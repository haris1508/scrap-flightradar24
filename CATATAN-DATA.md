# Catatan Data — FlightRadar24

Repo ini berisi **2 dataset berbeda**. Jangan dicampur: skala dan cakupannya jauh berbeda.

---

## Dataset A — Papan Arrival/Departure per Bandara (utama, otomatis)

Scraper: [`scrape_board.py`](scrape_board.py) · Otomatis tiap hari 05.00 WIB via GitHub Actions ([`.github/workflows/scrape.yml`](.github/workflows/scrape.yml)), mengambil data **H-1**.

**Output harian:**
- `csv/YYMMDD-Flightradar.csv`
- `excel/YYMMDD-Flightradar.xlsx`

**Cakupan:** 10 bandara — 8 Indonesia (CGK, DPS, BPN, KNO, PKU, SUB, UPG, YIA) + 2 luar negeri (SIN, KUL). Mulai 5 Mei 2026.

**Kolom:** bandara, tipe (arrivals/departures), tanggal, waktu_jadwal, waktu_aktual, nomor_flight, callsign, asal_tujuan_iata, asal_tujuan_nama, maskapai, maskapai_iata, kode_pesawat, nama_pesawat, registrasi, status, scraped_at.

**Arsip historis (format lebih sederhana, hanya CGK & DPS):**
- `260504-DataLama.csv` — per penerbangan, 2020-09-14 → 2026-05-04, sampling **mingguan**. Tanpa waktu_aktual/pesawat/registrasi.
- `200101-DataCovid.csv` — agregat rata-rata harian per minggu (CGK, DPS) sejak 2020.

### Definisi baku yang dipakai (penting, sudah disepakati)

- **Domestik** = kedua ujung penerbangan di Indonesia. Praktisnya: `bandara` ∈ 8 bandara Indonesia **dan** `asal_tujuan_iata` ∈ daftar bandara Indonesia. SIN & KUL tidak pernah domestik.
- **Direct** = semua baris papan FR24 memang segmen point-to-point (bukan transit).
- **Berhasil / realized** = arrival berstatus `Landed` + departure berstatus `Departed`. Status lain (Canceled, Diverted, Estimated, Scheduled, Unknown) dibuang.
- **Normalisasi maskapai** = buang embel-embel livery dalam kurung; `Indonesia AirAsia`→`AirAsia`, `Citilink Garuda Indonesia`→`Citilink`, `Nam Air`/`NAM Air` disatukan.

### Peringatan hitung ganda

Menjumlah Landed + Departed menghasilkan **gerakan (movements)**, bukan penerbangan unik:
- Rute antar-2 bandara terpantau (mis. CGK↔SUB) terhitung **2×**
- Rute ke bandara tak terpantau (mis. CGK→PLM) terhitung **1×**

Kalau butuh penerbangan unik, jangan pakai penjumlahan ini apa adanya.

### File olahan (di root)

| File | Isi |
|---|---|
| `domestik-landed-departed-harian.csv` / `.xlsx` | Per tanggal: landed_arrivals, departed, domestik_berhasil |
| `domestik-maskapai-harian.csv` | Wide: baris=tanggal, kolom=17 maskapai + TOTAL |
| `domestik-maskapai-5besar-harian.csv` | Wide: 5 besar + Lainnya + TOTAL |

Format tanggal file olahan: `dd-mmm-yy`. Hari gagal scrape **sudah dibuang**.

### Tanggal yang hilang (tak bisa dipulihkan — FR24 tak simpan histori)

- Tidak pernah ter-scrape: `260507`–`260510`, `260528`, `260602`, `260624`, `260626`, `260702`, `260713`, `260715`, `260717`
- Ter-scrape tapi **parsial/gagal**, jangan dipakai: `260506`, `260524`

---

## Dataset B — Statistik Global FR24 (sekali ambil, bukan otomatis)

Scraper: [`scrape_statistics.py`](scrape_statistics.py) · Sumber: <https://www.flightradar24.com/data/statistics>

**Output:** `csv/fr24-statistics-harian.csv`

**Cakupan:** harian (UTC) 2022-01-01 → sekarang. **GLOBAL/seluruh dunia**, bukan Indonesia.

| Kolom | Arti |
|---|---|
| `tanggal` | Harian UTC |
| `commercial_flights` | Komersial: penumpang + kargo + charter + sebagian bizjet (~140–150 rb/hari) |
| `total_flights` | Semua: komersial + private + glider + heli + militer + drone (~240–280 rb/hari) |
| `share_commercial_%` | Porsi komersial terhadap total |

**Catatan teknis:** FR24 menumpuk semua tahun pada satu sumbu tanggal, jadi tanggal asli dipetakan ulang dari nama seri + urutan hari (bukan dari nilai sumbu — kalau dari sumbu, 29 Feb tahun kabisat hilang). Tombol `Download CSV` bawaan Highcharts **tidak memadai** karena hanya mengekspor seri yang terlihat, sedangkan seri harian tahun-tahun lama disembunyikan.

---

## Alur kerja rutin

```bash
git pull                      # tarik data terbaru dari GitHub Actions
python scrape_statistics.py   # (opsional) perbarui statistik global
```

File olahan Dataset A perlu digenerate ulang setelah `git pull` agar ikut tanggal terbaru.

Automation hanya meng-commit `csv/` dan `excel/`. File olahan disimpan **lokal saja** (tidak di-push) sesuai preferensi.
