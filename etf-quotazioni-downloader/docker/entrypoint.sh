#!/bin/sh
# ============================================================
#  entrypoint.sh
#  Avviato automaticamente quando parte il container.
#
#  Fa due cose:
#   1. mette online un piccolo server web, cosi' il report e'
#      consultabile dal browser di qualsiasi dispositivo di casa;
#   2. lancia l'aggiornamento delle quotazioni agli orari del
#      giorno indicati dalla variabile ORARI (separati da virgola,
#      es. "09:30,13:30,17:30"). Per compatibilita' con le vecchie
#      configurazioni, se ORARI non e' impostata si usa ORARIO
#      (un solo orario al giorno).
# ============================================================

set -eu

CARTELLA_REPORT=/app/report

# Elenco degli orari di aggiornamento: ORARI ha la precedenza, poi ORARIO,
# altrimenti il vecchio valore predefinito delle 19:30.
ELENCO_ORARI="${ORARI:-${ORARIO:-19:30}}"

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

# Quanti secondi mancano al piu' vicino tra gli orari elencati (oggi o domani).
# Gli orari gia' passati oggi contano per domani.
# Gli avvisi vanno su stderr: lo stdout di questa funzione viene catturato
# dal chiamante e deve contenere solo il numero di secondi.
secondi_al_prossimo_avvio() {
    elenco="$1"
    adesso=$(date +%s)
    migliore=""

    for orario in $(echo "$elenco" | tr ',' ' '); do
        previsto=$(date -d "today ${orario}" +%s 2>/dev/null || echo 0)
        if [ "$previsto" -le "$adesso" ]; then
            previsto=$(date -d "tomorrow ${orario}" +%s 2>/dev/null || echo 0)
        fi
        if [ "$previsto" -gt "$adesso" ]; then
            if [ -z "$migliore" ] || [ "$previsto" -lt "$migliore" ]; then
                migliore=$previsto
            fi
        else
            messaggio "ATTENZIONE: orario '${orario}' non valido, lo ignoro." >&2
        fi
    done

    if [ -z "$migliore" ]; then
        messaggio "ATTENZIONE: nessun orario valido in '${elenco}', uso 1 ora di attesa." >&2
        echo 3600
    else
        echo $((migliore - adesso))
    fi
}

messaggio "ETF Quotazioni Downloader - fuso orario ${TZ:-non impostato}, aggiornamenti ogni giorno alle ${ELENCO_ORARI}."

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
    attesa=$(secondi_al_prossimo_avvio "$ELENCO_ORARI")
    messaggio "Prossimo aggiornamento tra $((attesa / 3600))h $(((attesa % 3600) / 60))m."
    sleep "$attesa"
    esegui_aggiornamento
done
