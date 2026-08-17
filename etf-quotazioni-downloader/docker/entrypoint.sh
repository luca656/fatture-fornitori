#!/bin/sh
# ============================================================
#  entrypoint.sh
#  Avviato automaticamente quando parte il container.
#
#  Fa due cose:
#   1. mette online un piccolo server web, cosi' il report e'
#      consultabile dal browser di qualsiasi dispositivo di casa;
#   2. lancia l'aggiornamento delle quotazioni una volta al giorno
#      all'orario indicato dalla variabile ORARIO.
# ============================================================

set -eu

CARTELLA_REPORT=/app/report

messaggio() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# I file creati dentro il container appartengono a root: se PUID e PGID sono
# impostati, li riassegniamo all'utente del NAS, altrimenti da File Station
# non si riuscirebbero a spostare o cancellare.
sistema_permessi() {
    if [ -n "${PUID:-}" ] && [ -n "${PGID:-}" ]; then
        chown -R "${PUID}:${PGID}" /app/data /app/report /app/log 2>/dev/null || true
    fi
}

esegui_aggiornamento() {
    messaggio "Avvio l'aggiornamento delle quotazioni..."
    if python /app/main.py; then
        messaggio "Aggiornamento completato."
    else
        messaggio "Aggiornamento terminato con errori: controlla la cartella log."
    fi
    sistema_permessi
}

# Quanti secondi mancano al prossimo orario di aggiornamento.
# Se l'orario di oggi e' gia' passato, punta a quello di domani.
secondi_al_prossimo_avvio() {
    orario="$1"
    adesso=$(date +%s)
    previsto_oggi=$(date -d "today ${orario}" +%s 2>/dev/null || echo 0)

    if [ "$previsto_oggi" -gt "$adesso" ]; then
        echo $((previsto_oggi - adesso))
    else
        previsto_domani=$(date -d "tomorrow ${orario}" +%s 2>/dev/null || echo 0)
        if [ "$previsto_domani" -gt "$adesso" ]; then
            echo $((previsto_domani - adesso))
        else
            # Orario non valido: ripiego su un controllo ogni ora.
            messaggio "ATTENZIONE: orario '${orario}' non valido, uso 1 ora di attesa."
            echo 3600
        fi
    fi
}

messaggio "ETF Quotazioni Downloader - fuso orario ${TZ:-non impostato}, aggiornamento giornaliero alle ${ORARIO:-19:30}."

if [ "${PORTA_WEB:-0}" != "0" ]; then
    messaggio "Server web attivo sulla porta ${PORTA_WEB}: apri http://INDIRIZZO-DEL-NAS:${PORTA_WEB} per vedere il report."
    cd "$CARTELLA_REPORT" && python -m http.server "${PORTA_WEB}" --bind 0.0.0.0 >/dev/null 2>&1 &
    cd /app
fi

# Al primo avvio genera subito un report, senza aspettare l'orario previsto,
# cosi' si vede immediatamente se tutto funziona.
if [ "${ESEGUI_SUBITO:-1}" = "1" ]; then
    esegui_aggiornamento
fi

while true; do
    attesa=$(secondi_al_prossimo_avvio "${ORARIO:-19:30}")
    messaggio "Prossimo aggiornamento tra $((attesa / 3600))h $(((attesa % 3600) / 60))m."
    sleep "$attesa"
    esegui_aggiornamento
done
