#!/bin/sh
# ============================================================
#  esegui.sh
#  Esecuzione manuale su Linux / NAS senza Docker.
#  Crea l'ambiente Python al primo avvio, poi genera il report.
#
#  Uso:  ./esegui.sh
#  (se serve, rendilo eseguibile una volta sola:  chmod +x esegui.sh)
# ============================================================

set -eu

cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERRORE: python3 non e' installato su questo sistema."
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Primo avvio: creo l'ambiente Python e installo le librerie..."
    python3 -m venv .venv
    ".venv/bin/python" -m pip install --upgrade pip
    ".venv/bin/python" -m pip install -r requirements.txt
fi

".venv/bin/python" main.py
