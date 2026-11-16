# Ricettario

App web per tenere traccia delle ricette che fai, nello stesso stile dell'app Investimenti.

- Ricette divise per portata: Antipasti, Primi, Secondi, Contorni, Dolci, Pane e pizza, Altro
- Per ogni ricetta: ingredienti, procedimento, note, data e foto del risultato
- Ricerca per nome o ingrediente
- Backup manuale in JSON (Esporta / Importa)

## Sul NAS

Serve solo Node.js (nessuna dipendenza da installare). La password è obbligatoria:

    RICETTE_PASSWORD='scegli-una-password-lunga' node server.js

Utente: `luca` (cambiabile con `RICETTE_USER`). Poi apri `http://IP-DEL-NAS:8080` da PC o telefono in rete.

- Dati in `data/ricette.json`, foto in `data/photos/`
- Copia di sicurezza giornaliera in `data/backups/` (ultime 30)
- Dopo 8 password sbagliate l'indirizzo viene bloccato per 15 minuti
- Variabili opzionali: `PORT` (default 8080), `DATA_DIR` (default `./data`)

## Accesso da fuori casa

1. **Indirizzo IP pubblico**: il router deve avere un IP pubblico. Se l'IP "WAN" del router è diverso da quello
   che mostra un sito tipo "qual è il mio IP", sei dietro CGNAT e l'apertura porte non funziona (chiedi
   all'operatore l'IP pubblico, oppure usa la VPN qui sotto).
2. **Apri la porta sul router**: inoltro porta (port forwarding) TCP, porta esterna a scelta (es. 8443)
   verso `IP-DEL-NAS:8080`. Dai al NAS un IP fisso in casa.
3. **Raggiungilo da fuori**: `http://IP-PUBBLICO:8443`. L'IP di casa può cambiare: un DNS dinamico
   (DuckDNS, No-IP, o quello del NAS) dà un nome fisso.
4. **HTTPS (consigliato)**: con HTTP la password viaggia in chiaro. Avvia con
   `TLS_KEY=chiave.pem TLS_CERT=certificato.pem`. Con un nome DNS puoi avere un certificato gratuito
   (Let's Encrypt); con il solo IP resta il certificato autofirmato, che il browser segnala come non attendibile.

**Alternativa più sicura:** Tailscale o la VPN del router. Non apri nessuna porta su internet e da
telefono usi comunque l'indirizzo del NAS come se fossi a casa.

## Senza server

Aprendo `index.html` direttamente, le ricette restano solo nel browser di quel dispositivo
(la pagina lo segnala con il pallino arancione). Usa Esporta per fare backup.
