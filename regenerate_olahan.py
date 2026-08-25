#!/usr/bin/env python3
"""Regenerate file olahan harian dari csv/YYMMDD-Flightradar.csv.

Output (format tanggal dd-mmm-yy, sesuai file lama):
  domestik-landed-departed-harian.csv    tanggal, landed_arrivals, departed, domestik_berhasil
  domestik-maskapai-harian.csv           tanggal, <semua maskapai>..., TOTAL
  domestik-maskapai-5besar-harian.csv    tanggal, 5 besar, Lainnya, TOTAL

Definisi (sesuai CATATAN-DATA.md):
  Domestik  = bandara ∈ 8 bandara Indonesia DAN asal_tujuan_iata ∈ bandara Indonesia
  Berhasil  = arrivals berstatus 'Landed' + departures berstatus 'Departed'
  Maskapai  = nama dinormalisasi (buang livery dalam kurung, satukan alias)

Daftar ID_APT tervalidasi: mereproduksi file lama 62/62 tanggal PERSIS.
Hari gagal/parsial dibuang.

Pakai:  python3 regenerate_olahan.py            (dry-run: hanya lapor)
        python3 regenerate_olahan.py --write    (tulis file)
"""
import csv, glob, os, sys, datetime
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
WRITE = "--write" in sys.argv

# JANGAN TAMBAH BANDARA DI SINI. Sengaja dibekukan pada 8 bandara awal.
# Sejak 25 Agt 2026 scraper juga memantau LOP, KOE, LBJ, tapi file olahan
# tetap memakai 8 bandara ini supaya deret waktu/grafik KONTINU — kalau
# cakupan ditambah di tengah jalan, angka harian melonjak dan patahannya
# terbaca seolah trafik naik. Data 3 bandara baru tetap tersimpan lengkap
# di csv/ & excel/ untuk analisis terpisah.
ID8 = {"CGK", "DPS", "BPN", "KNO", "PKU", "SUB", "UPG", "YIA"}
ID_APT = set("""CGK HLP DPS SUB UPG KNO PKU PLM PDG BTH BDJ BPN BIK MDC AMQ DJJ SOC JOG YIA SRG
MLG BWX LOP KOE MOF TIM SOQ MKW KDI PLW GTO TTE LUW PNK TRK BEJ KTG SMQ PKY ENE WGP BUW KAZ NBX
MKQ FLZ GNS TJQ PGK DJB BKS TKG LSW BTJ MEQ SBG TNJ NTX DUM SIQ RGT PSU LLJ TJG SRI PWL SXK DTB
DOB ARD LBJ WGA TMC BJW RTG SWQ LKA MJU PSJ TTR SQR BXB FKQ NAH GLX TLI PUM RSK SEQ TJS DTD MWK
BTW TXE LAH LUV WMX AAP TSY CBN SGQ PPJ NNX TQQ RAQ ONI KEQ ZRI OKL WET EWE BUI
BMU APD KXB KJT LNU MOH BUU LLO PKN TJB LKI SKJ GHS DHX TRT JBB MWS""".split())

# hari gagal / parsial -> jangan dipakai (CATATAN-DATA.md)
BAD = {"2026-05-06", "2026-05-24"}

ALIAS = {"Indonesia AirAsia": "AirAsia",
         "Citilink Garuda Indonesia": "Citilink",
         "NAM Air": "Nam Air"}


def norm_airline(s):
    s = (s or "").split("(")[0].strip()
    return ALIAS.get(s, s)


def fmt(d):
    return datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%d-%b-%y")


def main():
    la = defaultdict(int); de = defaultdict(int)
    per_air = defaultdict(Counter)
    for fn in sorted(glob.glob(os.path.join(HERE, "csv", "*-Flightradar.csv"))):
        for r in csv.DictReader(open(fn, encoding="utf-8-sig")):
            t = r.get("tanggal", "")
            if not t or t in BAD:
                continue
            if r.get("bandara") not in ID8:
                continue
            if r.get("asal_tujuan_iata", "").strip() not in ID_APT:
                continue
            st = (r.get("status") or "").strip()
            tipe = r.get("tipe")
            if tipe == "arrivals" and st.startswith("Landed"):
                la[t] += 1
            elif tipe == "departures" and st.startswith("Departed"):
                de[t] += 1
            else:
                continue
            per_air[t][norm_airline(r.get("maskapai"))] += 1

    tgl = sorted(set(la) | set(de))
    if not tgl:
        raise SystemExit("tidak ada data.")
    print(f"[info] {len(tgl)} tanggal: {tgl[0]} .. {tgl[-1]}")

    # 1) harian total
    rows1 = [(fmt(t), la[t], de[t], la[t] + de[t]) for t in tgl]

    # 2) per maskapai (wide)
    total = Counter()
    for t in tgl:
        total.update(per_air[t])
    airlines = [a for a, _ in total.most_common()]
    rows2 = [[fmt(t)] + [per_air[t].get(a, 0) for a in airlines] + [sum(per_air[t].values())]
             for t in tgl]

    # 3) 5 besar + lainnya
    top5 = airlines[:5]
    rows3 = []
    for t in tgl:
        v = [per_air[t].get(a, 0) for a in top5]
        tot = sum(per_air[t].values())
        rows3.append([fmt(t)] + v + [tot - sum(v), tot])

    print(f"[info] 5 besar: {', '.join(top5)}")
    print(f"[info] terakhir {rows1[-1][0]}: landed={rows1[-1][1]} departed={rows1[-1][2]} total={rows1[-1][3]}")

    if not WRITE:
        print("(dry-run; pakai --write untuk menulis file)")
        return
    def tulis(nama, header, rows):
        p = os.path.join(HERE, nama)
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(header); w.writerows(rows)
        print("  ditulis:", nama, f"({len(rows)} baris)")
    tulis("domestik-landed-departed-harian.csv",
          ["tanggal", "landed_arrivals", "departed", "domestik_berhasil"], rows1)
    tulis("domestik-maskapai-harian.csv", ["tanggal"] + airlines + ["TOTAL"], rows2)
    tulis("domestik-maskapai-5besar-harian.csv",
          ["tanggal"] + top5 + ["Lainnya", "TOTAL"], rows3)


if __name__ == "__main__":
    main()
