# ETF Quotazioni Downloader

Software che scarica ogni giorno le quotazioni di un paniere di ETF da
**Yahoo Finance** e mette in evidenza quelli con il grafico giornaliero più
"pulito": un andamento rialzista o ribassista costante, senza scatti
improvvisi.

Genera un **report HTML interattivo** (apribile con doppio click, anche senza
connessione internet: non serve alcun server) con:

- la classifica dei migliori ETF a trend **rialzista** "pulito"
- la classifica dei migliori ETF a trend **ribassista** "pulito"
- l'elenco completo di tutti gli ETF monitorati, con i relativi indicatori,
  inclusa la **variazione percentuale da inizio anno** (YTD)
- per i primi 5 di ciascuna classifica, una scheda con **4 grafici a
  scheda/tab** selezionabili con un click, raggiungibile anche cliccando
  direttamente sul ticker nella tabella:
  - andamento a **90 giorni** con la retta di tendenza
  - **1 giorno** (intraday) con l'indicatore **MACD**
  - **7 giorni** con l'indicatore **MACD**
  - **12 mesi** con l'indicatore **MACD**

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

Un ETF entra nelle due classifiche principali solo se soddisfa **entrambe** le
soglie: R² ≥ 0,55 e punteggio di pulizia ≥ 10. Servono tutte e due, perché un
ETF può avere una direzione ben riconoscibile (R² alto) pur muovendosi a strappi
del 10% al giorno: il trend c'è, ma il grafico è tutt'altro che pulito, ed è
esattamente il caso che queste classifiche devono escludere.

Ogni tabella ha anche una colonna **Valutazione** a semaforo, per un giudizio
a colpo d'occhio senza dover interpretare i numeri:

| Pallino | Giudizio | Punteggio |
|---|---|---|
| 🟢 | Pulito | ≥ 50 |
| 🟡 | Discreto | 20-49 |
| 🔴 | Rumoroso | < 20 |

Le due soglie sono modificabili in `config/settings.ini`
(`soglia_semaforo_verde` e `soglia_semaforo_giallo`).

Tutte le soglie sono modificabili nel file `config/settings.ini`, senza
bisogno di toccare il codice.

## La variazione da inizio anno (YTD)

La colonna **Var. da inizio anno** mostra quanto è salito o sceso il prezzo
dal primo giorno di borsa dell'anno a oggi (in inglese: Year To Date). È
calcolata con una richiesta separata da quella usata per il punteggio di
pulizia, apposta: il punteggio deve restare basato su una finestra breve e
recente (~90 giorni), mentre lo YTD copre l'intero anno in corso. Se il dato
non è disponibile per un ETF, la cella mostra "n/d" invece di un numero.

## I grafici a 1 giorno, 7 giorni e 12 mesi con MACD

Per non moltiplicare inutilmente le richieste a Yahoo Finance, i grafici
intraday (1 giorno), a 7 giorni e a 12 mesi, tutti con l'indicatore **MACD**
(Moving Average Convergence Divergence, parametri classici 12/26/9), vengono
generati solo per i primi 5 ETF di ciascuna classifica (rialzista e
ribassista). Nel report, ogni scheda ETF ha quattro pulsanti — **90 giorni**,
**1 giorno + MACD**, **7 giorni + MACD**, **12 mesi + MACD** — che permettono
di passare da un grafico all'altro con un click, senza ricaricare la pagina.

Nelle tre tabelle, il ticker di un ETF che ha una scheda-grafico in pagina è
cliccabile: porta direttamente alla scheda corrispondente, più in basso nella
stessa pagina.

Se per un ETF Yahoo Finance non fornisce dati infragiornalieri sufficienti
(capita fuori dagli orari di mercato o per ETF poco scambiati), la scheda
mostra un messaggio al posto del grafico mancante, mentre gli altri grafici
restano disponibili.

Gli intervalli usati per scaricare i dati intraday e i parametri del MACD si
possono modificare in `config/settings.ini`. Sono elencati dal più fitto al più
largo (1m, 2m, 5m) e viene usato il primo che fornisce abbastanza rilevazioni
per calcolare il MACD: al mattino presto, con poche ore di contrattazioni alle
spalle, solo un intervallo fitto produce punti a sufficienza.

I grafici intraday usano un asse orizzontale posizionale invece delle date vere.
È un accorgimento necessario: con le date vere, le ore di mercato chiuso — notti
e weekend — verrebbero colmate da lunghe rette diagonali, facendo sembrare che
il prezzo si muova quando invece la borsa era ferma. Le date restano come
diciture sotto l'asse.

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

## Installazione su NAS Synology (consigliata)

Far girare il software sul NAS invece che sul PC ha due vantaggi concreti: il
NAS è sempre acceso, quindi l'aggiornamento non salta mai perché il computer
era spento; e il report diventa consultabile da qualsiasi dispositivo di casa,
telefono compreso, senza copiare file.

### Passo 1 — copia la cartella sul NAS

Da File Station, copia l'intera cartella `etf-quotazioni-downloader` dentro una
cartella condivisa, ad esempio in `docker/etf-quotazioni-downloader`.

### Passo 2 — imposta il tuo utente

Apri `docker-compose.yml` con l'editor di testo di File Station e controlla le
righe `PUID` e `PGID`. I valori predefiniti (1026 e 100) sono quelli del primo
utente Synology e vanno bene nella maggior parte dei casi. Se i file generati
risultassero poi non modificabili, ricava i valori giusti collegandoti in SSH
al NAS ed eseguendo `id iltuonome`.

Nello stesso file puoi cambiare gli orari degli aggiornamenti (`ORARI`,
separati da virgola — di default tre al giorno in orario lavorativo:
`09:30,13:30,17:30`) e la porta del server web (`PORTA_WEB`).

### Passo 3 — crea il progetto in Container Manager

Apri **Container Manager** → **Progetto** → **Crea**:

- **Nome progetto**: `etf-quotazioni-downloader`
- **Percorso**: la cartella copiata al passo 1
- **Origine**: *Usa il file docker-compose.yml esistente* (viene rilevato da solo)

Conferma e attendi la compilazione: la prima volta richiede qualche minuto,
perché scarica Python e le librerie necessarie.

### Passo 4 — apri il report

A compilazione finita il container genera subito un primo report, senza
aspettare l'orario impostato. Da qualsiasi browser di casa apri:

```
http://INDIRIZZO-DEL-NAS:8099
```

(sostituisci `INDIRIZZO-DEL-NAS` con l'IP del tuo NAS, per esempio
`192.168.1.50`). La pagina mostra sempre il report più recente. Puoi salvarla
tra i preferiti, anche sul telefono.

I file restano comunque anche nelle cartelle `report`, `data` e `log` sul NAS,
raggiungibili da File Station.

### Verificare che funzioni

In Container Manager, apri il container e guarda la scheda **Log**: dovresti
vedere righe come

```
[2026-08-18 09:21:32] ETF Quotazioni Downloader - fuso orario Europe/Rome, aggiornamenti ogni giorno alle 09:30,13:30,17:30.
[2026-08-18 09:21:40] Aggiornamento completato.
[2026-08-18 09:21:40] Prossimo aggiornamento tra 0h 8m.
```

### Aggiornare il software a una nuova versione

Quando sostituisci dei file del programma (`main.py`, `docker/entrypoint.sh`,
`Dockerfile`...), non basta riavviare il container: quei file vengono copiati
**dentro** l'immagine al momento della compilazione, e Container Manager tende
a riusare l'immagine già compilata. La sequenza corretta è:

1. carica i file nuovi in File Station, sovrascrivendo i vecchi
2. **Container** → seleziona il container → **Azione** → **Interrompi**, poi **Elimina**
3. **Immagine** → elimina `etf-quotazioni-downloader-etf-downloader:latest`
4. **Progetto** → **Azione** → **Costruzione**: devono riapparire gli step
   `1/14, 2/14...` — è il segno che sta ricostruendo davvero

I file in `config`, `data`, `report` e `log` non vengono toccati: vivono sul
NAS, fuori dall'immagine.

### Senza Docker

Se preferisci non usare Docker, sul NAS puoi installare il pacchetto Python 3
dal Centro pacchetti e usare `scripts/esegui.sh`, pianificandolo con
**Pannello di controllo → Utilità di pianificazione → Attività pianificate**.

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

L'elenco predefinito contiene 51 ETF: azionari (globali, USA, Europa, Giappone,
emergenti, settoriali), obbligazionari (governativi euro suddivisi per scadenza,
corporate, high yield, inflazione, Treasury USA, emergenti, globali), oro fisico
e minerarie aurifere, argento, materie prime, immobiliare e liquidità.

> Un'avvertenza sui fondi monetari: `XEON.MI` è un fondo di liquidità, quindi il
> suo grafico è una retta quasi perfetta e ottiene un punteggio vicino a 100,
> occupando stabilmente il primo posto tra i rialzisti. È corretto — è davvero
> il grafico più "pulito" possibile — ma non rappresenta un'opportunità di
> investimento: rende semplicemente il tasso di mercato monetario. Se lo trovi
> di disturbo in cima alla classifica, elimina la sua riga dal file.

Aggiungi o rimuovi righe liberamente e salva il file: alla successiva
esecuzione lo strumento userà il nuovo elenco.

## Struttura della cartella

```
etf-quotazioni-downloader/
├── main.py                    programma principale
├── requirements.txt           librerie Python richieste
├── Dockerfile                 immagine per l'esecuzione su NAS
├── docker-compose.yml         configurazione per Container Manager (Synology)
├── config/
│   ├── etf_list.csv           elenco ETF monitorati (modificabile)
│   └── settings.ini           soglie e parametri dell'analisi (modificabile)
├── docker/
│   └── entrypoint.sh          pianificazione e server web dentro il container
├── scripts/
│   ├── 1_installa.bat         Windows: installazione (una volta sola)
│   ├── 2_pianifica_task.bat   Windows: programmazione giornaliera (una volta sola)
│   ├── esegui.bat             Windows: esecuzione manuale / Task Scheduler
│   └── esegui.sh              Linux/NAS: esecuzione manuale senza Docker
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
- **Un ETF risulta sempre "saltato" con l'errore `Quote not found`**: quel
  ticker non esiste su Yahoo Finance. Cercalo su
  [finance.yahoo.com](https://finance.yahoo.com) e correggilo in
  `config/etf_list.csv`: lo stesso ETF è spesso quotato su più borse con
  sigle diverse.
- **Il grafico a 1 giorno resta vuoto**: succede quando l'ETF è poco
  scambiato, o quando il report gira poco dopo l'apertura dei mercati: in
  entrambi i casi le rilevazioni non bastano per calcolare il MACD. Il
  grafico a 7 giorni e quello a 90 giorni restano comunque disponibili.
- **Sul NAS, i file generati non sono modificabili da File Station**:
  correggi `PUID` e `PGID` in `docker-compose.yml` con i valori del tuo
  utente (in SSH: `id iltuonome`), poi riavvia il container.
- **Sul NAS, dopo aver aggiornato `main.py` il report non cambia**: il file
  viene copiato dentro l'immagine Docker al momento della compilazione, quindi
  né un riavvio né a volte una nuova "Costruzione" bastano — Container Manager
  può riutilizzare l'immagine già compilata senza accorgersi che i file sono
  cambiati. La procedura sicura è: **Container** → elimina il container fermo
  → **Immagine** → elimina l'immagine `etf-quotazioni-downloader-...` →
  **Progetto** → **Azione** → **Costruzione**. Se nella finestra di
  compilazione non vedi scorrere le righe "Step 1/14, 2/14...", l'immagine non
  è stata davvero ricostruita.
- **Sul NAS, l'errore "unable to prepare context / Dockerfile" alla
  compilazione**: il progetto punta a una cartella che non contiene
  direttamente i file. Capita quando l'estrazione dello zip su Windows crea
  una cartella dentro l'altra: controlla in File Station che `Dockerfile`,
  `main.py` e `docker-compose.yml` siano al primo livello della cartella del
  progetto, non in una sottocartella.
