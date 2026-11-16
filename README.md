# Ricettario

App web per tenere traccia delle ricette che fai, nello stesso stile dell'app Investimenti.

- Ricette divise per portata: Antipasti, Primi, Secondi, Contorni, Dolci, Pane e pizza, Altro
- Per ogni ricetta: ingredienti, procedimento, note, data e foto del risultato
- Ricerca per nome o ingrediente
- Backup manuale in JSON (Esporta / Importa)

## Sul NAS (consigliato)

Serve solo Node.js (nessuna dipendenza da installare):

    node server.js

Poi apri `http://IP-DEL-NAS:8080` da qualsiasi PC o telefono in rete.

- Dati in `data/ricette.json`, foto in `data/photos/`
- Copia di sicurezza giornaliera in `data/backups/` (ultime 30)
- Variabili opzionali: `PORT` (default 8080), `DATA_DIR` (default `./data`)

## Senza server

Aprendo `index.html` direttamente, le ricette restano solo nel browser di quel dispositivo
(la pagina lo segnala con il pallino arancione). Usa Esporta per fare backup.
