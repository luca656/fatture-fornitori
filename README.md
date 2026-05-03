# Fatture Fornitori

Strumento AI per caricare fatture di acquisto, costruire un database di prodotti con prezzi unitari e confrontare i fornitori.

## Funzionalità

- **Caricamento fatture** (PDF, JPG, PNG, WEBP) tramite drag-and-drop
- **Estrazione AI** con Claude Vision: fornitore, articoli, quantità, prezzi
- **Riconoscimento prodotti**: Claude abbina automaticamente lo stesso prodotto descritto da fornitori diversi
- **Confronto prezzi**: tabella con prezzi affiancati per fornitore, indicazione del prezzo migliore e risparmio percentuale
- **Gestione prodotti**: merge manuale di duplicati, assegnazione categorie
- **Database SQLite** locale — nessuna dipendenza esterna

## Requisiti

- Python 3.11+
- Chiave API Anthropic

## Installazione

```bash
pip install -r requirements.txt
cp .env.example .env
# Inserisci la tua chiave API in .env
```

## Avvio

```bash
python run.py
```

Apri [http://localhost:8000](http://localhost:8000)

## Struttura

```
backend/
  main.py          – FastAPI app
  models.py        – Tabelle SQLAlchemy (suppliers, invoices, invoice_items, canonical_products)
  ai_extractor.py  – Estrazione dati fattura con Claude Vision
  ai_matcher.py    – Matching prodotti tra fornitori con Claude
  routers/
    invoices.py    – Upload e gestione fatture
    products.py    – Prodotti canonici e confronto prezzi
    suppliers.py   – Gestione fornitori
frontend/
  index.html / css/style.css / js/app.js
uploads/           – File fatture (esclusi da git)
```

## Flusso di elaborazione

1. Caricamento file → `ai_extractor.py` invia l'immagine a Claude Vision
2. Claude restituisce JSON strutturato (fornitore + articoli)
3. `ai_matcher.py` confronta i nuovi articoli con i prodotti già nel DB
4. I prodotti non riconosciuti vengono creati come nuovi `CanonicalProduct`
5. La scheda "Confronto Prezzi" mostra la tabella aggiornata
