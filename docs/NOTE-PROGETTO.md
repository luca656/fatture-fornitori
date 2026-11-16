# Ricettario: appunti del progetto (aggiornati al 16/11/2026)

## Cosa è stato fatto
1. Il repository `luca656/fatture-fornitori` era vuoto (solo README). Non contiene altri programmi.
2. Creata l'app **Ricettario** (`index.html`): ricette divise per portata (Antipasti, Primi, Secondi,
   Contorni, Dolci, Pane e pizza, Altro), con ingredienti, procedimento, note, data, foto del risultato,
   ricerca per nome/ingrediente, backup JSON (Esporta/Importa).
3. Stile ispirato all'app **Investimenti** (sul NAS RSNAS): sfondo scuro, titoli serif, accenti oro,
   indicatore "Salvato sul NAS · ultima modifica".
4. Aggiunto `server.js` (Node, nessuna dipendenza): salva dati in `data/ricette.json`, foto in
   `data/photos/`, backup giornaliero in `data/backups/` (ultime 30).
5. Sicurezza: password obbligatoria (`RICETTE_PASSWORD`, utente `luca`), blocco 15 minuti dopo
   8 tentativi sbagliati, HTTPS opzionale (`TLS_KEY` + `TLS_CERT`).
6. Avvio automatico: `Dockerfile` + `docker-compose.yml`, oppure `deploy/ricettario.service` (systemd).
   Docker non è stato provato (non disponibile nella sessione di sviluppo); il server Node sì.
7. Tutto è nella pull request (bozza) #3 del repository, ramo `ccr-d49a560c-hop4fi`.

## Come avviarlo sul NAS
    RICETTE_PASSWORD='password-lunga' docker compose up -d --build
oppure `RICETTE_PASSWORD='...' node server.js`, poi `http://<indirizzo-interno-NAS>:8080`.

## Accesso da fuori casa: decisione sulla sicurezza
- **Scelta: NON aprire porte** verso il NAS. Usare la **VPN WireGuard del Fritz!Box**.
- Router: FRITZ!Box 7590 AX, FRITZ!OS 8.25 (supporta WireGuard).
- Passi: Internet > Abilitazioni > VPN (WireGuard) > Aggiungi connessione > "Collega un singolo
  dispositivo" > scansionare il QR con l'app WireGuard sul telefono. Fuori casa: accendere la VPN e
  aprire l'indirizzo interno del NAS.
- Prima verificare l'IP pubblico (Internet > Informazioni di accesso): se inizia con 100.64-100.127,
  10. o 192.168. si è dietro CGNAT o dietro un altro router (forse un modem TIM davanti): la VPN
  e l'accesso da fuori non funzionano finché non si risolve (chiedere IP pubblico all'operatore).

## Da controllare sul Fritz!Box (visto nella schermata Panoramica)
- [ ] "Abilitazione porte: 2 abilitazioni configurate": vedere a cosa puntano e chiudere quelle inutili
      (Internet > Abilitazioni > Abilitazione porte).
- [ ] "Servizi FRITZ!Box raggiungibile da Internet (HTTPS)": disattivare se non serve, DOPO aver
      verificato che la VPN funzioni (Internet > Abilitazioni > Servizi FRITZ!Box).
- [ ] Tre voci "Accesso remoto" già presenti (una collegata): non toccarle senza sapere a cosa servono.

## Cose che non si sono potute fare
- Collegare questa sessione al Chrome/computer: l'estensione Claude in Chrome e la condivisione
  cartelle (Impostazioni > Claude Code > Remote Control) non risultavano collegate. Alternativa:
  usare il pannello laterale di Claude nel Chrome, che vede la pagina aperta.
- Scrivere direttamente sul NAS: nessun accesso alla rete di casa dalla sessione cloud.

## Prossimi passi
1. Verificare IP pubblico (CGNAT?) e le 2 abilitazioni porte.
2. Attivare WireGuard e provarlo dal telefono con i dati mobili.
3. Installare il ricettario sul NAS (Docker o systemd) e provarlo dalla VPN.
4. Solo dopo, chiudere l'accesso da internet alla pagina del Fritz!Box e le porte inutili.
5. Fare Esporta backup dal ricettario ogni tanto, oltre al backup automatico.
