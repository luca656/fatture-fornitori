#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF Quotazioni Downloader
==========================

Scarica ogni giorno le quotazioni di un paniere di ETF da Yahoo Finance,
calcola per ciascuno un "punteggio di pulizia" del grafico giornaliero
(trend lineare, poca volatilita', assenza di scatti improvvisi) e produce
un report HTML interattivo che mette in evidenza gli ETF con l'andamento
piu' costante e prevedibile, sia rialzisti che ribassisti. Per i migliori
ETF individuati, il report include anche i grafici a 1 giorno e a 7 giorni
con l'indicatore MACD.

Uso:
    python main.py

Configurazione:
    config/etf_list.csv   -> elenco dei ticker da monitorare
    config/settings.ini   -> parametri dell'analisi e del MACD

Il report del giorno viene salvato in report/report_AAAA-MM-GG.html
(file singolo, apribile con doppio click, senza bisogno di connessione
per essere visualizzato: i grafici sono incorporati nel file).
"""

import base64
import configparser
import csv
import io
import logging
import sys
import time
from datetime import datetime
from itertools import chain
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("ERRORE: la libreria 'yfinance' non e' installata.")
    print("Esegui prima: pip install -r requirements.txt")
    sys.exit(1)

import matplotlib
matplotlib.use("Agg")  # nessuna finestra grafica: generiamo solo immagini
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Percorsi e costanti
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "report"
LOG_DIR = BASE_DIR / "log"

ETF_LIST_FILE = CONFIG_DIR / "etf_list.csv"
SETTINGS_FILE = CONFIG_DIR / "settings.ini"

for d in (DATA_DIR, REPORT_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

TODAY = datetime.now().strftime("%Y-%m-%d")

# Palette colori del report (tono unico, coerente in tutte le pagine)
COLOR_SURFACE = "#fcfcfb"
COLOR_PAGE = "#f9f9f7"
COLOR_INK_PRIMARY = "#0b0b0b"
COLOR_INK_SECONDARY = "#52514e"
COLOR_INK_MUTED = "#898781"
COLOR_GRID = "#e1e0d9"
COLOR_BASELINE = "#c3c2b7"
COLOR_SERIES_PRICE = "#2a78d6"   # linea prezzo
COLOR_TREND_LINE = "#898781"     # linea di tendenza tratteggiata
COLOR_GOOD = "#0ca30c"           # rialzista pulito / semaforo verde
COLOR_WARNING = "#c98500"        # semaforo giallo (versione leggibile su sfondo chiaro)
COLOR_CRITICAL = "#d03b3b"       # ribassista pulito / semaforo rosso
COLOR_MACD_LINEA = "#eb6834"     # linea MACD
COLOR_MACD_SEGNALE = "#4a3aa7"   # linea di segnale MACD
# rampa sequenziale blu (chiaro -> scuro) per il punteggio in tabella
SCORE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]

# Numero di ETF (per direzione di trend) per cui generare anche i grafici
# di dettaglio a 1 e 7 giorni con MACD, oltre al grafico a 90 giorni.
NUM_GRAFICI_DETTAGLIO = 5

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"log_{TODAY}.txt", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("etf-downloader")


# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

def carica_impostazioni():
    cfg = configparser.ConfigParser()
    if SETTINGS_FILE.exists():
        cfg.read(SETTINGS_FILE, encoding="utf-8")
    analisi = cfg["analisi"] if "analisi" in cfg else {}
    rete = cfg["rete"] if "rete" in cfg else {}
    macd = cfg["macd"] if "macd" in cfg else {}
    intraday = cfg["intraday"] if "intraday" in cfg else {}
    return {
        "giorni_storico": int(analisi.get("giorni_storico", 130)),
        "giorni_minimi": int(analisi.get("giorni_minimi", 40)),
        "r2_minimo": float(analisi.get("r2_minimo", 0.55)),
        "punteggio_minimo": float(analisi.get("punteggio_minimo", 0.10)),
        "soglia_semaforo_verde": float(analisi.get("soglia_semaforo_verde", 0.50)),
        "soglia_semaforo_giallo": float(analisi.get("soglia_semaforo_giallo", 0.20)),
        "volatilita_massima": float(analisi.get("volatilita_massima", 0.025)),
        "salto_massimo": float(analisi.get("salto_massimo", 0.07)),
        "top_n": int(analisi.get("top_n", 10)),
        "pausa_tra_richieste": float(rete.get("pausa_tra_richieste", 0.5)),
        "tentativi_massimi": int(rete.get("tentativi_massimi", 3)),
        "macd_veloce": int(macd.get("veloce", 12)),
        "macd_lento": int(macd.get("lento", 26)),
        "macd_segnale": int(macd.get("segnale", 9)),
        # Dal piu' fitto al piu' largo: un intervallo fitto produce piu' punti,
        # che e' cio' che serve quando i dati intraday sono ancora pochi.
        "intervalli_1g": [
            s.strip() for s in intraday.get("intervalli_1g", "1m,2m,5m").split(",") if s.strip()
        ],
        "intervalli_7g": [
            s.strip() for s in intraday.get("intervalli_7g", "15m,30m,60m").split(",") if s.strip()
        ],
    }


def carica_elenco_etf():
    if not ETF_LIST_FILE.exists():
        log.error("File elenco ETF non trovato: %s", ETF_LIST_FILE)
        sys.exit(1)
    with open(ETF_LIST_FILE, newline="", encoding="utf-8") as f:
        righe = list(csv.DictReader(f))
    return righe


# ---------------------------------------------------------------------------
# Download e analisi
# ---------------------------------------------------------------------------

def scarica_storico(ticker, giorni, tentativi_massimi, pausa):
    for tentativo in range(1, tentativi_massimi + 1):
        try:
            dati = yf.Ticker(ticker).history(
                period=f"{giorni}d", interval="1d", auto_adjust=True
            )
            if dati is None or dati.empty:
                raise ValueError("nessun dato restituito")
            return dati
        except Exception as exc:  # rete instabile, ticker non valido, ecc.
            log.warning(
                "Tentativo %d/%d fallito per %s: %s",
                tentativo, tentativi_massimi, ticker, exc,
            )
            time.sleep(pausa)
    return None


def scarica_variazione_ytd(ticker, tentativi_massimi, pausa):
    """Scarica lo storico da inizio anno e restituisce la variazione percentuale
    da inizio anno (YTD, Year To Date), oppure None se non disponibile.

    E' una richiesta separata dallo storico principale: usa il periodo "ytd"
    nativo di Yahoo Finance, che copre da gennaio a oggi indipendentemente dal
    numero di giorni impostato per l'analisi di 'pulizia' del trend (che deve
    restare una finestra breve e recente, non l'intero anno).
    """
    for tentativo in range(1, tentativi_massimi + 1):
        try:
            dati = yf.Ticker(ticker).history(period="ytd", interval="1d", auto_adjust=True)
            chiusura = dati["Close"].dropna() if dati is not None else None
            if chiusura is None or len(chiusura) < 2:
                raise ValueError("storico da inizio anno insufficiente")
            return float(chiusura.iloc[-1] / chiusura.iloc[0] - 1) * 100
        except Exception as exc:
            log.warning(
                "Tentativo %d/%d (YTD) fallito per %s: %s",
                tentativo, tentativi_massimi, ticker, exc,
            )
            time.sleep(pausa)
    return None


def calcola_metriche(storico, impostazioni):
    """Calcola il punteggio di 'pulizia' del grafico giornaliero.

    Un grafico e' considerato 'pulito' quando:
      - il prezzo segue fedelmente una retta di tendenza (R^2 alto)
      - la volatilita' dei rendimenti giornalieri e' bassa
      - non ci sono scatti (salti) giornalieri anomali
    """
    chiusura = storico["Close"].dropna()
    if len(chiusura) < impostazioni["giorni_minimi"]:
        return None

    rendimenti = chiusura.pct_change().dropna()
    volatilita = float(rendimenti.std())
    salto_max = float(rendimenti.abs().max())

    x = np.arange(len(chiusura))
    y = chiusura.values
    pendenza, intercetta = np.polyfit(x, y, 1)
    y_previsto = pendenza * x + intercetta
    ss_res = float(np.sum((y - y_previsto) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    r2 = max(0.0, min(1.0, r2))

    trend = "Rialzista" if pendenza > 0 else "Ribassista"

    vol_norm = min(volatilita / impostazioni["volatilita_massima"], 1.0)
    salto_norm = min(salto_max / impostazioni["salto_massimo"], 1.0)
    punteggio = max(0.0, r2 * (1 - vol_norm) * (1 - salto_norm))

    variazione_periodo = (chiusura.iloc[-1] / chiusura.iloc[0] - 1) * 100
    variazione_ultimo_giorno = float(rendimenti.iloc[-1]) * 100

    return {
        "r2": r2,
        "volatilita": volatilita,
        "salto_max": salto_max,
        "pendenza": pendenza,
        "trend": trend,
        "punteggio": punteggio,
        "ultimo_prezzo": float(chiusura.iloc[-1]),
        "variazione_ultimo_giorno": variazione_ultimo_giorno,
        "variazione_periodo": variazione_periodo,
        "giorni_analizzati": len(chiusura),
        "y_previsto": y_previsto,
        "x": x,
    }


def salva_storico_csv(ticker, storico):
    percorso = DATA_DIR / f"{ticker.replace('.', '_')}.csv"
    storico_da_salvare = storico[["Open", "High", "Low", "Close", "Volume"]].copy()
    storico_da_salvare.index.name = "Data"
    storico_da_salvare.to_csv(percorso)


def scarica_intraday(ticker, periodo, elenco_intervalli, punti_minimi, tentativi_massimi, pausa):
    """Scarica dati infragiornalieri per il periodo indicato (es. '1d', '7d').

    Prova gli intervalli in cascata e restituisce il primo che fornisce almeno
    'punti_minimi' rilevazioni: il MACD ha bisogno di un numero minimo di punti
    per essere calcolabile, quindi un intervallo che restituisce pochi dati non
    e' utilizzabile e va scartato in favore del successivo.

    Nota: gli intervalli vanno elencati dal piu' fitto al piu' largo (1m, 2m,
    5m...), perche' a parita' di periodo un intervallo piu' fitto produce piu'
    punti. E' il caso tipico del grafico a 1 giorno consultato poco dopo
    l'apertura dei mercati, quando le ore trascorse sono ancora poche.

    Restituisce (dati, intervallo_usato) oppure (None, None) se nessun
    intervallo ha fornito dati sufficienti.
    """
    for intervallo in elenco_intervalli:
        for tentativo in range(1, tentativi_massimi + 1):
            try:
                dati = yf.Ticker(ticker).history(
                    period=periodo, interval=intervallo, auto_adjust=True
                )
                if dati is None or dati.empty:
                    raise ValueError("nessun dato restituito")
                punti = len(dati["Close"].dropna())
                if punti >= punti_minimi:
                    return dati, intervallo
                # Dati validi ma troppo pochi: inutile insistere con altri
                # tentativi sullo stesso intervallo, si passa al successivo.
                log.info(
                    "Intraday (%s, %s) per %s: solo %d punti sui %d necessari, provo il prossimo intervallo.",
                    periodo, intervallo, ticker, punti, punti_minimi,
                )
                break
            except Exception as exc:
                log.warning(
                    "Tentativo %d/%d intraday (%s, %s) fallito per %s: %s",
                    tentativo, tentativi_massimi, periodo, intervallo, ticker, exc,
                )
                time.sleep(pausa)
    return None, None


def calcola_macd(chiusura, veloce, lento, segnale):
    """Calcola MACD, linea di segnale e istogramma con le medie mobili esponenziali."""
    ema_veloce = chiusura.ewm(span=veloce, adjust=False).mean()
    ema_lenta = chiusura.ewm(span=lento, adjust=False).mean()
    macd = ema_veloce - ema_lenta
    linea_segnale = macd.ewm(span=segnale, adjust=False).mean()
    istogramma = macd - linea_segnale
    return macd, linea_segnale, istogramma


# ---------------------------------------------------------------------------
# Grafici (incorporati nel report come immagini base64)
# ---------------------------------------------------------------------------

def genera_grafico_giornaliero_base64(ticker, nome, storico, metriche):
    """Grafico principale: prezzo di chiusura giornaliero + retta di tendenza (~90gg)."""
    chiusura = storico["Close"].dropna()
    colore_trend_line = COLOR_GOOD if metriche["trend"] == "Rialzista" else COLOR_CRITICAL

    fig, ax = plt.subplots(figsize=(6, 3), dpi=140)
    fig.patch.set_facecolor(COLOR_SURFACE)
    ax.set_facecolor(COLOR_SURFACE)

    ax.plot(chiusura.index, chiusura.values, color=COLOR_SERIES_PRICE, linewidth=1.6,
            label="Prezzo di chiusura")
    ax.plot(chiusura.index, metriche["y_previsto"], color=colore_trend_line,
            linewidth=1.4, linestyle="--", label="Tendenza lineare")

    ax.set_title(f"{ticker} — {nome} — ultimi {metriche['giorni_analizzati']} giorni di borsa",
                 fontsize=10, color=COLOR_INK_PRIMARY, loc="left")
    ax.grid(True, color=COLOR_GRID, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(COLOR_BASELINE)
    ax.tick_params(colors=COLOR_INK_MUTED, labelsize=8)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.legend(loc="upper left", fontsize=7, frameon=False, labelcolor=COLOR_INK_SECONDARY)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("ascii")


def etichette_asse_tempo(indice, numero_etichette=6):
    """Sceglie le posizioni e le diciture da mettere sull'asse orizzontale.

    I grafici intraday sono disegnati su un asse posizionale (0, 1, 2, ...)
    invece che sulle date vere: cosi' le ore di mercato chiuso — notti e
    weekend — non lasciano buchi che matplotlib colmerebbe con lunghe rette
    diagonali, facendo sembrare che il prezzo si muova quando invece la borsa
    era ferma. E' lo stesso accorgimento usato dalle piattaforme finanziarie.
    Le date vere restano, come diciture sotto l'asse.
    """
    if len(indice) == 0:
        return [], []

    # Sull'arco di una sola giornata conta l'ora; su piu' giorni conta la data,
    # e l'ora diventa un dettaglio che affolla l'asse senza aggiungere nulla.
    giorni = (indice[-1] - indice[0]).total_seconds() / 86400
    if giorni <= 1:
        formato = "%H:%M"
    elif giorni <= 3:
        formato = "%d/%m %H:%M"
    else:
        formato = "%d/%m"

    passo = max(len(indice) // numero_etichette, 1)
    posizioni = list(range(0, len(indice), passo))
    diciture = [indice[p].strftime(formato) for p in posizioni]
    return posizioni, diciture


def genera_grafico_macd_base64(ticker, nome, chiusura, macd, segnale, istogramma, sottotitolo):
    """Grafico a due pannelli: prezzo in alto, indicatore MACD in basso."""
    fig, (ax_prezzo, ax_macd) = plt.subplots(
        2, 1, figsize=(6, 4.4), dpi=140, sharex=True,
        gridspec_kw={"height_ratios": [2, 1.2]},
    )
    fig.patch.set_facecolor(COLOR_SURFACE)

    # Asse posizionale: una tacca per rilevazione, senza vuoti temporali.
    x = np.arange(len(chiusura))

    ax_prezzo.set_facecolor(COLOR_SURFACE)
    ax_prezzo.plot(x, chiusura.values, color=COLOR_SERIES_PRICE, linewidth=1.5, label="Prezzo")
    ax_prezzo.set_title(f"{ticker} — {nome} — {sottotitolo}", fontsize=10,
                         color=COLOR_INK_PRIMARY, loc="left")
    ax_prezzo.grid(True, color=COLOR_GRID, linewidth=0.6)
    ax_prezzo.spines[["top", "right"]].set_visible(False)
    ax_prezzo.spines[["left", "bottom"]].set_color(COLOR_BASELINE)
    ax_prezzo.tick_params(colors=COLOR_INK_MUTED, labelsize=8)
    ax_prezzo.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax_prezzo.legend(loc="upper left", fontsize=7, frameon=False, labelcolor=COLOR_INK_SECONDARY)

    colori_istogramma = [COLOR_GOOD if v >= 0 else COLOR_CRITICAL for v in istogramma.values]

    ax_macd.set_facecolor(COLOR_SURFACE)
    ax_macd.bar(x, istogramma.values, color=colori_istogramma,
                width=0.8, alpha=0.55, label="Istogramma")
    ax_macd.plot(x, macd.values, color=COLOR_MACD_LINEA, linewidth=1.3, label="MACD")
    ax_macd.plot(x, segnale.values, color=COLOR_MACD_SEGNALE, linewidth=1.1, label="Segnale")
    ax_macd.axhline(0, color=COLOR_BASELINE, linewidth=0.8)
    ax_macd.grid(True, color=COLOR_GRID, linewidth=0.6)
    ax_macd.spines[["top", "right"]].set_visible(False)
    ax_macd.spines[["left", "bottom"]].set_color(COLOR_BASELINE)
    ax_macd.tick_params(colors=COLOR_INK_MUTED, labelsize=8)
    ax_macd.legend(loc="upper left", fontsize=7, frameon=False, labelcolor=COLOR_INK_SECONDARY, ncol=3)

    posizioni, diciture = etichette_asse_tempo(chiusura.index)
    ax_macd.set_xticks(posizioni)
    ax_macd.set_xticklabels(diciture, rotation=30, ha="right")

    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("ascii")


# ---------------------------------------------------------------------------
# Report HTML
# ---------------------------------------------------------------------------

def colore_punteggio(punteggio):
    """Restituisce un colore della rampa sequenziale blu in base al punteggio (0-1)."""
    indice = min(int(punteggio * len(SCORE_RAMP)), len(SCORE_RAMP) - 1)
    return SCORE_RAMP[indice]


def valutazione_semaforo(punteggio, impostazioni):
    """Traduce il punteggio numerico in un giudizio a semaforo, per una lettura
    immediata senza dover interpretare i numeri: verde/giallo/rosso, sempre
    accompagnati da un'etichetta testuale (mai il colore da solo)."""
    if punteggio >= impostazioni["soglia_semaforo_verde"]:
        return COLOR_GOOD, "Pulito"
    if punteggio >= impostazioni["soglia_semaforo_giallo"]:
        return COLOR_WARNING, "Discreto"
    return COLOR_CRITICAL, "Rumoroso"


def id_scheda(ticker):
    """Identificativo HTML sicuro per la scheda-grafico di un ticker (senza punti)."""
    return f"scheda-{ticker.replace('.', '_')}"


def riga_tabella(riga, impostazioni, tickers_con_grafico):
    freccia = "▲" if riga["trend"] == "Rialzista" else "▼"
    colore_trend = COLOR_GOOD if riga["trend"] == "Rialzista" else COLOR_CRITICAL
    colore_punt = colore_punteggio(riga["punteggio"])
    colore_semaforo, etichetta_semaforo = valutazione_semaforo(riga["punteggio"], impostazioni)

    if riga["ticker"] in tickers_con_grafico:
        cella_ticker = f'<a class="link-grafico" href="#{id_scheda(riga["ticker"])}" title="Vai al grafico">{riga["ticker"]}</a>'
    else:
        cella_ticker = riga["ticker"]

    if riga["variazione_ytd"] is None:
        cella_ytd = '<span class="dato-assente">n/d</span>'
    else:
        colore_ytd = COLOR_GOOD if riga["variazione_ytd"] >= 0 else COLOR_CRITICAL
        cella_ytd = f'<span style="color:{colore_ytd};">{riga["variazione_ytd"]:+.2f}%</span>'

    return f"""
    <tr>
      <td class="mono">{cella_ticker}</td>
      <td>{riga['nome']}</td>
      <td>{riga['categoria']}</td>
      <td class="num">{riga['ultimo_prezzo']:.2f}</td>
      <td class="num" style="color:{colore_trend};">{riga['variazione_ultimo_giorno']:+.2f}%</td>
      <td class="num">{cella_ytd}</td>
      <td style="color:{colore_trend};">{freccia} {riga['trend']}</td>
      <td class="num">{riga['r2']:.2f}</td>
      <td class="num">{riga['volatilita']*100:.2f}%</td>
      <td class="num">{riga['salto_max']*100:.2f}%</td>
      <td class="num punteggio" style="background:{colore_punt};">{riga['punteggio']*100:.0f}</td>
      <td class="valutazione"><span class="pallino" style="background:{colore_semaforo};"></span><span style="color:{colore_semaforo};">{etichetta_semaforo}</span></td>
    </tr>"""


def intestazione_tabella():
    return """
    <tr>
      <th>Ticker</th><th>Nome</th><th>Categoria</th>
      <th class="num">Ultimo prezzo</th><th class="num">Var. ultimo giorno</th>
      <th class="num">Var. da inizio anno</th>
      <th>Trend</th><th class="num">R²</th><th class="num">Volatilità</th>
      <th class="num">Salto max</th><th class="num">Punteggio pulizia</th><th>Valutazione</th>
    </tr>"""


def seleziona_top(risultati, impostazioni):
    """Seleziona gli ETF a trend 'pulito' (R² sopra soglia), separati per direzione."""
    puliti = [
        r for r in risultati
        if r["r2"] >= impostazioni["r2_minimo"]
        and r["punteggio"] >= impostazioni["punteggio_minimo"]
    ]
    rialzisti = sorted(
        [r for r in puliti if r["trend"] == "Rialzista"],
        key=lambda r: r["punteggio"], reverse=True,
    )[: impostazioni["top_n"]]
    ribassisti = sorted(
        [r for r in puliti if r["trend"] == "Ribassista"],
        key=lambda r: r["punteggio"], reverse=True,
    )[: impostazioni["top_n"]]
    return rialzisti, ribassisti


def blocco_immagine_tab(tab_id, dati_base64, visibile, testo_alternativo):
    stile = "display:block;" if visibile else "display:none;"
    if dati_base64:
        return (f'<img data-tab="{tab_id}" class="tab-immagine" style="{stile}" '
                f'src="data:image/png;base64,{dati_base64}" alt="{testo_alternativo}">')
    return (f'<div data-tab="{tab_id}" class="tab-placeholder" style="{stile}">'
            f'Dati non disponibili per questo intervallo (mercato chiuso al momento del '
            f'download, o storico infragiornaliero non fornito da Yahoo Finance per questo ETF).'
            f'</div>')


def costruisci_scheda_etf(riga, grafico_90, grafico_1g, grafico_7g, grafico_12m):
    colore_punt = colore_punteggio(riga["punteggio"])
    return f"""
    <div class="scheda-etf" id="{id_scheda(riga['ticker'])}">
      <div class="scheda-intestazione">
        <span class="scheda-ticker">{riga['ticker']}</span>
        <span class="scheda-nome">{riga['nome']}</span>
        <span class="scheda-punteggio" style="background:{colore_punt};">{riga['punteggio']*100:.0f}</span>
      </div>
      <div class="scheda-tab-bar">
        <button type="button" class="tab-btn attivo" onclick="mostraTab(this, 'g90')">90 giorni</button>
        <button type="button" class="tab-btn" onclick="mostraTab(this, 'g1')">1 giorno + MACD</button>
        <button type="button" class="tab-btn" onclick="mostraTab(this, 'g7')">7 giorni + MACD</button>
        <button type="button" class="tab-btn" onclick="mostraTab(this, 'g12m')">12 mesi + MACD</button>
      </div>
      <div class="scheda-tab-contenuto">
        {blocco_immagine_tab('g90', grafico_90, True, riga['ticker'])}
        {blocco_immagine_tab('g1', grafico_1g, False, riga['ticker'])}
        {blocco_immagine_tab('g7', grafico_7g, False, riga['ticker'])}
        {blocco_immagine_tab('g12m', grafico_12m, False, riga['ticker'])}
      </div>
    </div>"""


def costruisci_report(risultati, impostazioni, grafici_90, grafici_1g, grafici_7g, grafici_12m):
    rialzisti, ribassisti = seleziona_top(risultati, impostazioni)
    tutti_ordinati = sorted(risultati, key=lambda r: r["punteggio"], reverse=True)

    # ETF che hanno effettivamente una scheda-grafico in pagina: solo per questi
    # il ticker in tabella diventa un link che porta al grafico corrispondente.
    tickers_con_grafico = {r["ticker"] for r in rialzisti[:NUM_GRAFICI_DETTAGLIO]} | \
        {r["ticker"] for r in ribassisti[:NUM_GRAFICI_DETTAGLIO]}

    sezioni_grafici_rialzisti = "".join(
        costruisci_scheda_etf(r, grafici_90.get(r["ticker"]), grafici_1g.get(r["ticker"]),
                               grafici_7g.get(r["ticker"]), grafici_12m.get(r["ticker"]))
        for r in rialzisti[:NUM_GRAFICI_DETTAGLIO]
    )
    sezioni_grafici_ribassisti = "".join(
        costruisci_scheda_etf(r, grafici_90.get(r["ticker"]), grafici_1g.get(r["ticker"]),
                               grafici_7g.get(r["ticker"]), grafici_12m.get(r["ticker"]))
        for r in ribassisti[:NUM_GRAFICI_DETTAGLIO]
    )

    html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Report ETF — {TODAY}</title>
<style>
  html {{ scroll-behavior: smooth; }}
  body {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: {COLOR_PAGE}; color: {COLOR_INK_PRIMARY};
    margin: 0; padding: 32px;
  }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .sottotitolo {{ color: {COLOR_INK_SECONDARY}; margin-top: 0; margin-bottom: 28px; font-size: 14px; }}
  h2 {{ font-size: 16px; margin-top: 40px; border-bottom: 1px solid {COLOR_GRID}; padding-bottom: 8px; }}
  .nota {{ color: {COLOR_INK_MUTED}; font-size: 12px; margin-bottom: 16px; }}
  table {{
    width: 100%; border-collapse: collapse; background: {COLOR_SURFACE};
    font-size: 13px; margin-bottom: 8px;
  }}
  th {{
    text-align: left; padding: 8px 10px; color: {COLOR_INK_SECONDARY};
    border-bottom: 1px solid {COLOR_BASELINE}; font-weight: 600;
  }}
  td {{ padding: 7px 10px; border-bottom: 1px solid {COLOR_GRID}; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.mono {{ font-family: ui-monospace, Consolas, monospace; }}
  a.link-grafico {{
    color: {COLOR_SERIES_PRICE}; text-decoration: none; border-bottom: 1px dashed {COLOR_SERIES_PRICE};
  }}
  a.link-grafico:hover {{ text-decoration: none; border-bottom-style: solid; }}
  .dato-assente {{ color: {COLOR_INK_MUTED}; }}
  td.punteggio {{ font-weight: 700; color: {COLOR_INK_PRIMARY}; border-radius: 4px; }}
  td.valutazione {{ font-weight: 600; font-size: 12px; white-space: nowrap; }}
  .pallino {{
    display: inline-block; width: 9px; height: 9px; border-radius: 50%;
    margin-right: 6px; vertical-align: middle;
  }}
  .schede-etf {{ display: flex; flex-wrap: wrap; gap: 16px; margin-top: 12px; }}
  .scheda-etf {{
    background: {COLOR_SURFACE}; border: 1px solid {COLOR_GRID}; border-radius: 8px;
    padding: 10px; flex: 1 1 420px; max-width: 480px;
  }}
  .scheda-intestazione {{
    display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;
  }}
  .scheda-ticker {{ font-family: ui-monospace, Consolas, monospace; font-weight: 700; font-size: 13px; }}
  .scheda-nome {{ color: {COLOR_INK_SECONDARY}; font-size: 12px; flex: 1; }}
  .scheda-punteggio {{
    font-weight: 700; font-size: 11px; color: {COLOR_INK_PRIMARY};
    padding: 2px 8px; border-radius: 10px;
  }}
  .scheda-tab-bar {{ display: flex; gap: 4px; margin-bottom: 8px; }}
  .tab-btn {{
    font-family: inherit; font-size: 11px; color: {COLOR_INK_SECONDARY};
    background: {COLOR_PAGE}; border: 1px solid {COLOR_GRID}; border-radius: 6px;
    padding: 4px 10px; cursor: pointer;
  }}
  .tab-btn:hover {{ border-color: {COLOR_BASELINE}; }}
  .tab-btn.attivo {{
    background: {COLOR_SERIES_PRICE}; border-color: {COLOR_SERIES_PRICE}; color: #ffffff;
  }}
  .scheda-tab-contenuto img, .scheda-tab-contenuto .tab-placeholder {{ width: 100%; }}
  .scheda-tab-contenuto img {{ height: auto; display: block; border-radius: 4px; }}
  .tab-placeholder {{
    box-sizing: border-box; min-height: 160px; display: flex; align-items: center;
    justify-content: center; text-align: center; color: {COLOR_INK_MUTED}; font-size: 12px;
    background: {COLOR_PAGE}; border: 1px dashed {COLOR_GRID}; border-radius: 4px; padding: 16px;
  }}
  footer {{ margin-top: 40px; color: {COLOR_INK_MUTED}; font-size: 11px; }}
</style>
</head>
<body>
  <h1>Report quotazioni ETF</h1>
  <p class="sottotitolo">Generato il {TODAY} — dati giornalieri da Yahoo Finance</p>

  <h2>▲ Top {len(rialzisti)} ETF con trend rialzista "pulito"</h2>
  <p class="nota">Ordinati per punteggio di pulizia (trend lineare, bassa volatilità, nessuno scatto anomalo).
  Per i primi {NUM_GRAFICI_DETTAGLIO}, clicca sulle schede qui sotto per vedere anche i grafici a 1 giorno, 7 giorni e 12 mesi con l'indicatore MACD.</p>
  <table>{intestazione_tabella()}{''.join(riga_tabella(r, impostazioni, tickers_con_grafico) for r in rialzisti)}</table>
  <div class="schede-etf">{sezioni_grafici_rialzisti}</div>

  <h2>▼ Top {len(ribassisti)} ETF con trend ribassista "pulito"</h2>
  <p class="nota">Ordinati per punteggio di pulizia (trend lineare, bassa volatilità, nessuno scatto anomalo).
  Per i primi {NUM_GRAFICI_DETTAGLIO}, clicca sulle schede qui sotto per vedere anche i grafici a 1 giorno, 7 giorni e 12 mesi con l'indicatore MACD.</p>
  <table>{intestazione_tabella()}{''.join(riga_tabella(r, impostazioni, tickers_con_grafico) for r in ribassisti)}</table>
  <div class="schede-etf">{sezioni_grafici_ribassisti}</div>

  <h2>Elenco completo</h2>
  <p class="nota">Tutti gli ETF monitorati, ordinati per punteggio di pulizia decrescente.
  Un ETF entra nelle classifiche sopra solo se ha R² ≥ {impostazioni['r2_minimo']:.2f}
  e punteggio di pulizia ≥ {impostazioni['punteggio_minimo']*100:.0f}.</p>
  <table>{intestazione_tabella()}{''.join(riga_tabella(r, impostazioni, tickers_con_grafico) for r in tutti_ordinati)}</table>

  <footer>
    Come leggere i dati: <b>R²</b> misura quanto il prezzo segue fedelmente una retta
    di tendenza (1 = perfettamente lineare); <b>Volatilità</b> è la deviazione standard
    dei rendimenti giornalieri; <b>Salto max</b> è la variazione più ampia registrata in
    un singolo giorno nel periodo osservato; <b>Punteggio pulizia</b> (0-100) combina i tre
    indicatori; <b>MACD</b> (Moving Average Convergence Divergence) è un indicatore di
    momentum calcolato sulle medie mobili esponenziali a 12 e 26 periodi, con linea di
    segnale a 9 periodi. La <b>Valutazione</b> traduce il punteggio in un giudizio
    immediato:
    <span class="pallino" style="background:{COLOR_GOOD};"></span>Pulito (punteggio ≥ {impostazioni['soglia_semaforo_verde']*100:.0f}),
    <span class="pallino" style="background:{COLOR_WARNING};"></span>Discreto (≥ {impostazioni['soglia_semaforo_giallo']*100:.0f}),
    <span class="pallino" style="background:{COLOR_CRITICAL};"></span>Rumoroso (sotto {impostazioni['soglia_semaforo_giallo']*100:.0f}).
    Questo report è generato automaticamente ed è solo a scopo
    informativo: non costituisce consulenza finanziaria.
  </footer>

  <script>
    function mostraTab(bottone, tab) {{
      var scheda = bottone.closest('.scheda-etf');
      scheda.querySelectorAll('.tab-btn').forEach(function (b) {{ b.classList.remove('attivo'); }});
      bottone.classList.add('attivo');
      scheda.querySelectorAll('.tab-immagine, .tab-placeholder').forEach(function (el) {{
        el.style.display = (el.getAttribute('data-tab') === tab) ? 'block' : 'none';
      }});
    }}
  </script>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Programma principale
# ---------------------------------------------------------------------------

def main():
    log.info("Avvio ETF Quotazioni Downloader — %s", TODAY)
    impostazioni = carica_impostazioni()
    elenco = carica_elenco_etf()
    log.info("ETF da elaborare: %d", len(elenco))

    risultati = []
    grafici_90 = {}

    for riga in elenco:
        ticker = riga["ticker"].strip()
        nome = riga.get("nome", ticker).strip()
        categoria = riga.get("categoria", "").strip()
        log.info("Elaboro %s (%s)...", ticker, nome)

        storico = scarica_storico(
            ticker,
            impostazioni["giorni_storico"],
            impostazioni["tentativi_massimi"],
            impostazioni["pausa_tra_richieste"],
        )
        if storico is None:
            log.error("Impossibile scaricare i dati per %s, ETF saltato.", ticker)
            continue

        salva_storico_csv(ticker, storico)

        metriche = calcola_metriche(storico, impostazioni)
        if metriche is None:
            log.warning("Dati insufficienti per %s, ETF saltato.", ticker)
            continue

        variazione_ytd = scarica_variazione_ytd(
            ticker, impostazioni["tentativi_massimi"], impostazioni["pausa_tra_richieste"],
        )
        if variazione_ytd is None:
            log.warning("Variazione da inizio anno non disponibile per %s.", ticker)

        risultati.append({
            "ticker": ticker, "nome": nome, "categoria": categoria,
            "variazione_ytd": variazione_ytd, **metriche,
        })

        try:
            grafici_90[ticker] = genera_grafico_giornaliero_base64(ticker, nome, storico, metriche)
        except Exception as exc:
            log.warning("Impossibile generare il grafico per %s: %s", ticker, exc)

        time.sleep(impostazioni["pausa_tra_richieste"])

    if not risultati:
        log.error("Nessun ETF elaborato con successo. Controlla la connessione e l'elenco ETF.")
        sys.exit(1)

    # Grafici a 1 e 7 giorni con MACD: solo per i migliori ETF individuati,
    # per non moltiplicare inutilmente le richieste a Yahoo Finance.
    rialzisti, ribassisti = seleziona_top(risultati, impostazioni)
    top_dettaglio = list(chain(rialzisti[:NUM_GRAFICI_DETTAGLIO], ribassisti[:NUM_GRAFICI_DETTAGLIO]))
    log.info("Scarico i dati infragiornalieri (1g/7g) per %d ETF selezionati...", len(top_dettaglio))

    grafici_1g = {}
    grafici_7g = {}
    # Il MACD non e' calcolabile con meno punti di quanti ne servono a far
    # partire la media lenta piu' la linea di segnale.
    punti_minimi = impostazioni["macd_lento"] + impostazioni["macd_segnale"]

    def genera_grafico_intraday(ticker, nome, periodo, intervalli, descrizione):
        """Scarica i dati intraday e restituisce il grafico con MACD, o None."""
        dati, intervallo = scarica_intraday(
            ticker, periodo, intervalli, punti_minimi,
            impostazioni["tentativi_massimi"], impostazioni["pausa_tra_richieste"],
        )
        if dati is None:
            log.warning("Dati intraday %s non disponibili per %s.", periodo, ticker)
            return None
        try:
            chiusura = dati["Close"].dropna()
            macd, segnale, istogramma = calcola_macd(
                chiusura, impostazioni["macd_veloce"],
                impostazioni["macd_lento"], impostazioni["macd_segnale"],
            )
            return genera_grafico_macd_base64(
                ticker, nome, chiusura, macd, segnale, istogramma,
                f"{descrizione} ({intervallo})",
            )
        except Exception as exc:
            log.warning("Impossibile generare il grafico %s/MACD per %s: %s", periodo, ticker, exc)
            return None

    for riga in top_dettaglio:
        ticker, nome = riga["ticker"], riga["nome"]

        grafico_1g = genera_grafico_intraday(
            ticker, nome, "1d", impostazioni["intervalli_1g"], "intraday 1 giorno")
        if grafico_1g:
            grafici_1g[ticker] = grafico_1g

        grafico_7g = genera_grafico_intraday(
            ticker, nome, "7d", impostazioni["intervalli_7g"], "ultimi 7 giorni")
        if grafico_7g:
            grafici_7g[ticker] = grafico_7g

        time.sleep(impostazioni["pausa_tra_richieste"])

    # Grafico a 12 mesi con MACD: dati giornalieri (non infragiornalieri) su un
    # anno, cosi' il MACD mostra i segnali di piu' lungo periodo oltre a quelli
    # ravvicinati dei grafici a 1 e 7 giorni. Anche questo solo per i migliori
    # ETF individuati.
    grafici_12m = {}
    for riga in top_dettaglio:
        ticker, nome = riga["ticker"], riga["nome"]
        storico_12m = scarica_storico(
            ticker, 370, impostazioni["tentativi_massimi"], impostazioni["pausa_tra_richieste"],
        )
        if storico_12m is None:
            log.warning("Dati a 12 mesi non disponibili per %s.", ticker)
            time.sleep(impostazioni["pausa_tra_richieste"])
            continue
        try:
            chiusura_12m = storico_12m["Close"].dropna()
            if len(chiusura_12m) < punti_minimi:
                log.warning(
                    "Storico a 12 mesi insufficiente per il MACD di %s (%d punti).",
                    ticker, len(chiusura_12m),
                )
            else:
                macd, segnale, istogramma = calcola_macd(
                    chiusura_12m, impostazioni["macd_veloce"],
                    impostazioni["macd_lento"], impostazioni["macd_segnale"],
                )
                grafici_12m[ticker] = genera_grafico_macd_base64(
                    ticker, nome, chiusura_12m, macd, segnale, istogramma, "ultimi 12 mesi",
                )
        except Exception as exc:
            log.warning("Impossibile generare il grafico 12m/MACD per %s: %s", ticker, exc)
        time.sleep(impostazioni["pausa_tra_richieste"])

    # Report HTML del giorno
    html = costruisci_report(risultati, impostazioni, grafici_90, grafici_1g, grafici_7g, grafici_12m)
    percorso_report = REPORT_DIR / f"report_{TODAY}.html"
    percorso_report.write_text(html, encoding="utf-8")
    log.info("Report salvato in: %s", percorso_report)

    # Copia sempre disponibile con nome fisso, comoda da tenere aperta/preferita
    (REPORT_DIR / "ultimo_report.html").write_text(html, encoding="utf-8")

    # Copia chiamata index.html: e' il nome che i browser aprono da soli quando
    # si visita un indirizzo, quindi con la versione su NAS basta digitare
    # http://indirizzo-del-nas:porta per vedere subito il report.
    (REPORT_DIR / "index.html").write_text(html, encoding="utf-8")

    # Classifica in CSV, utile per analisi ulteriori o storico
    df = pd.DataFrame(risultati).drop(columns=["y_previsto", "x"])
    df = df.sort_values("punteggio", ascending=False)
    df.to_csv(REPORT_DIR / f"classifica_{TODAY}.csv", index=False, encoding="utf-8-sig")

    log.info("Completato: %d ETF elaborati con successo.", len(risultati))


if __name__ == "__main__":
    main()
