#!/bin/bash
# Auto-update lokal: tarik data terbaru dari GitHub lalu regenerasi file olahan.
# Dipanggil LaunchAgent com.haris.flightradar-pull (08.00 / 14.00 / 20.00 WIB).
#
# Tiga kali sehari karena jadwal GitHub Actions sering tertunda 1-6 jam, jadi
# data bisa mendarat kapan saja: pagi, siang, atau malam.
#
# Sengaja memakai /usr/bin/python3 (python bawaan macOS) — regenerate_olahan.py
# hanya butuh pustaka standar, jadi tidak bergantung pada Anaconda yang mungkin
# tidak ada di PATH saat dijalankan launchd.

set -uo pipefail

REPO="/Users/haris/Library/Mobile Documents/com~apple~CloudDocs/Haris Eko Faruddin/claude/flightradar24"
GIT=/usr/bin/git
PY=/usr/bin/python3

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

cd "$REPO" 2>/dev/null || { log "FATAL: folder tidak ada -> $REPO"; exit 1; }

sebelum=$("$GIT" rev-parse --short HEAD 2>/dev/null) || { log "FATAL: bukan repo git"; exit 1; }

if ! "$GIT" pull --ff-only >/dev/null 2>&1; then
    log "GAGAL: git pull (kemungkinan ada perubahan lokal / riwayat menyimpang)"
    exit 1
fi

sesudah=$("$GIT" rev-parse --short HEAD)
if [ "$sebelum" = "$sesudah" ]; then
    log "tidak ada data baru ($sebelum)"
    exit 0
fi

terakhir=$(ls -1 csv/26*-Flightradar.csv 2>/dev/null | tail -1 | xargs -I{} basename {} .csv)
log "data baru: $sebelum -> $sesudah | file terakhir: ${terakhir:-?}"

if "$PY" regenerate_olahan.py --write >/dev/null 2>&1; then
    log "olahan diperbarui s/d $(tail -1 domestik-landed-departed-harian.csv | cut -d, -f1)"
else
    log "PERINGATAN: regenerate_olahan.py gagal"
fi
