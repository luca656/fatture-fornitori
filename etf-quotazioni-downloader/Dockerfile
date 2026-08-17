# Immagine per far girare ETF Quotazioni Downloader su NAS (Synology, QNAP,
# o qualsiasi sistema con Docker). Il container resta acceso e lancia
# l'aggiornamento una volta al giorno all'orario impostato.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# tzdata serve per rispettare il fuso orario italiano nella pianificazione;
# libgomp1 e' richiesta da numpy/pandas per il calcolo parallelo.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY config ./config
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
 && mkdir -p /app/data /app/report /app/log

# Valori predefiniti, tutti sovrascrivibili da docker-compose.yml
ENV TZ=Europe/Rome \
    ORARIO=19:30 \
    ESEGUI_SUBITO=1 \
    PORTA_WEB=8099

EXPOSE 8099

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
