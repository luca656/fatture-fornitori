# ETF Quotazioni Downloader

Software che scarica ogni giorno le quotazioni di un paniere di ETF da
**Yahoo Finance** e mette in evidenza quelli con il grafico giornaliero più
"pulito": un andamento rialzista o ribassista costante, senza scatti
improvvisi.

Genera un **report HTML interattivo** (apribile con doppio click, anche senza
connessione internet: non serve alcun server) con:

- la classifica dei migliori ETF a trend **rialzista** "pulito"
- la classifica dei migliori ETF a trend **ribassista** "pulito"
- l'elenco completo di tutti gli ETF monitorati, con i relativi indicatori
- per i primi 5 di ciascuna classifica, una scheda con **3 grafici a
  scheda/tab** selezionabili con un click:
  - andamento a **90 giorni** con la retta di tendenza
  - **1 giorno** (intraday) con l'indicatore **MACD**
  - **7 giorni** con l'indicatore **MACD**

## Come funziona il "punteggio di pulizia"

Per ogni ETF, sugli ultimi ~90 giorni di borsa, vengono calcolati tre indicatori:

1. **R²** (0-1): quanto il prezzo segue fedelmente una retta di tendenza.
   Vicino a 1 = trend molto lineare e prevedibile.
2. **Volatilità**: la deviazione standard dei rendimenti giornalieri (quanto
   "balla" il prezzo giorno per giorno).
3. **Salto massimo**: la variazione più ampia registrata in un singolo giorno
   nel periodo (per intercettare gli "scatti" improvvisi che si vogliono escludere).

Questi tre valori vengono combinati in un **punteggio di pulizia** da 0 a 100:
più è alto, più il grafico è lineare, poco volatile e privo di salti anomali.
Un ETF entra nelle due classifiche principali solo se il suo R² supera la
soglia minima impostata (di default 0,55).

Tutte le soglie sono modificabili nel file `config/settings.ini`, senza
bisogno di toccare il codice.

## I grafici a 1 e 7 giorni con MACD

Per non moltiplicare inutilmente le richieste a Yahoo Finance, i grafici
intraday (1 giorno) e a 7 giorni, entrambi con l'indicatore **MACD**
(Moving Average Convergence Divergence, parametri classici 12/26/9), vengono
generati solo per i primi 5 ETF di ciascuna classifica (rialzista e
ribassista). Nel report, ogni scheda ETF ha tre pulsanti — **90 giorni**,
**1 giorno + MACD**, **7 giorni + MACD** — che permettono di passare da un
grafico all'altro con un click, senza ricaricare la pagina.

Se per un ETF Yahoo Finance non fornisce dati infragiornalieri sufficienti
(capita fuori dagli orari di mercato o per ETF poco scambiati), la scheda
mostra un messaggio al posto del grafico mancante, mentre gli altri grafici
restano disponibili.

Gli intervalli usati per scaricare i dati intraday (5 minuti per il grafico
a 1 giorno, 30 minuti per quello a 7 giorni) e i parametri del MACD si
possono modificare in `config/settings.ini`.

> **Attenzione**: questo strumento è puramente informativo e statistico.
> Non è consulenza finanziaria e un grafico "pulito" nel passato non
> garantisce che l'ETF continuerà ad avere lo stesso andamento in futuro.

## Installazione (Windows)

1. Se non lo hai già, installa **Python 3.10 o superiore** da
   [python.org/downloads](https://www.python.org/downloads/). Durante
   l'installazione, spunta la casella **"Add Python to PATH"**.
2. Copia l'intera cartella `ETF-Quotazioni-Downloader` sul tuo Desktop
   (o dove preferisci).
3. Apri la cartella `scripts` ed esegui con doppio click **`1_installa.bat`**.
   Questo crea un ambiente Python dedicato e installa le librerie necessarie
   (potrebbe richiedere qualche minuto la prima volta).
4. Esegui con doppio click **`2_pianifica_task.bat`**: registra un'attività
   nel Task Scheduler di Windows che lancerà il download automaticamente
   ogni giorno alle 19:30 (orario modificabile aprendo il file con un editor
   di testo e cambiando la riga `set ORARIO=19:30`).

Da questo momento, ogni giorno il report si aggeggia da solo. Per vederlo,
apri con il browser:

```
report\ultimo_report.html
```

(puoi anche metterci un collegamento sul Desktop, o salvarlo tra i preferiti
del browser: il contenuto si aggiorna automaticamente ogni giorno).

## Esecuzione manuale

Per aggiornare i dati subito, senza aspettare l'orario pianificato, apri con
doppio click **`scripts\esegui.bat`**.

## Modificare l'elenco degli ETF monitorati

Apri `config\etf_list.csv` con Excel o con un editor di testo. Ogni riga è un
ETF, con tre colonne: `ticker`, `nome`, `categoria`.

Il `ticker` deve essere quello usato da **Yahoo Finance** (puoi verificarlo
cercando l'ETF su [finance.yahoo.com](https://finance.yahoo.com)). Ad
esempio:

| Borsa | Suffisso ticker | Esempio |
|---|---|---|
| Borsa Italiana | `.MI` | `SWDA.MI` |
| Xetra (Germania) | `.DE` | `VWCE.DE` |
| Euronext Amsterdam | `.AS` | `IWDA.AS` |
| Euronext Parigi | `.PA` | `MEUD.PA` |
| Borse USA | nessun suffisso | `SPY` |

Aggiungi o rimuovi righe liberamente e salva il file: alla successiva
esecuzione lo strumento userà il nuovo elenco.

## Struttura della cartella

```
ETF-Quotazioni-Downloader/
├── main.py                    programma principale
├── requirements.txt           librerie Python richieste
├── config/
│   ├── etf_list.csv           elenco ETF monitorati (modificabile)
│   └── settings.ini           soglie e parametri dell'analisi (modificabile)
├── scripts/
│   ├── 1_installa.bat         installazione (una volta sola)
│   ├── 2_pianifica_task.bat   programmazione giornaliera (una volta sola)
│   └── esegui.bat             esecuzione manuale / usato dal Task Scheduler
├── data/                      storico grezzo scaricato (un CSV per ETF)
├── report/                    report HTML e classifiche CSV generati ogni giorno
└── log/                       log di esecuzione, un file per giorno
```

## Disattivare l'aggiornamento automatico

Apri **"Utilità di pianificazione"** di Windows (cerca "Utilità di
pianificazione" o "Task Scheduler" nel menu Start), trova l'attività
**"ETF Quotazioni Downloader"** e disattivala o eliminala. In alternativa,
apri il Prompt dei comandi ed esegui:

```
schtasks /Delete /TN "ETF Quotazioni Downloader" /F
```

## Risoluzione problemi

- **"Python non risulta installato o non è nel PATH"**: reinstalla Python
  spuntando "Add Python to PATH", poi riesegui `1_installa.bat`.
- **Alcuni ETF non compaiono nel report**: controlla `log\log_AAAA-MM-GG.txt`.
  Le cause più comuni sono un ticker scritto male in `etf_list.csv` o una
  quotazione con troppo poco storico (l'ETF è stato quotato da poco).
- **Nessun dato scaricato per nessun ETF**: verifica la connessione
  internet del computer nell'orario in cui gira l'attività pianificata.
