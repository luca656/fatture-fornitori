"""
Uses Claude to match raw invoice item descriptions to canonical products,
recognising the same product even when described differently by different suppliers.
"""
import os
import json
import re
import anthropic
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def match_items_to_products(
    new_items: list[dict],
    existing_products: list[dict],
) -> list[dict]:
    """
    Given a list of new invoice items and existing canonical products,
    returns a mapping: for each item index → matched product id or None.

    new_items: [{"index": 0, "description": "...", "unit": "..."}, ...]
    existing_products: [{"id": 1, "name": "...", "description": "...", "unit": "..."}, ...]

    Returns: [{"item_index": 0, "canonical_product_id": 5, "confidence": "high"}, ...]
    """
    if not new_items:
        return []

    items_text = json.dumps(new_items, ensure_ascii=False, indent=2)
    products_text = (
        json.dumps(existing_products, ensure_ascii=False, indent=2)
        if existing_products
        else "[]"
    )

    prompt = f"""Hai una lista di articoli estratti da una fattura e un catalogo di prodotti canonici già esistenti nel database.

ARTICOLI NUOVI (dalla fattura):
{items_text}

PRODOTTI CANONICI ESISTENTI:
{products_text}

Per ogni articolo nuovo, determina se corrisponde a un prodotto canonico esistente.
Due prodotti sono lo stesso se descrivono lo stesso bene/servizio, anche se il nome è diverso
(es. "Pasta spaghetti n.5 500g" e "Spaghetti De Cecco 500g" sono lo stesso prodotto).

Rispondi SOLO con un array JSON:
[
  {{
    "item_index": 0,
    "canonical_product_id": 3,
    "confidence": "high"
  }},
  {{
    "item_index": 1,
    "canonical_product_id": null,
    "confidence": "none"
  }}
]

Usa canonical_product_id: null quando non c'è corrispondenza (il prodotto è nuovo).
confidence può essere: "high", "medium", "low", "none".
Rispondi SOLO con il JSON, nessun testo aggiuntivo."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=(
            "Sei un esperto nel riconoscimento di prodotti commerciali italiani. "
            "Identifica prodotti identici anche se descritti in modo diverso da fornitori diversi. "
            "Rispondi sempre e solo con JSON valido."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text.strip()
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)
    return json.loads(raw_text)


def suggest_canonical_name(descriptions: list[str]) -> str:
    """
    Given multiple descriptions of the same product from different suppliers,
    return a clean canonical name.
    """
    if not descriptions:
        return "Prodotto sconosciuto"
    if len(descriptions) == 1:
        return descriptions[0]

    descriptions_text = "\n".join(f"- {d}" for d in descriptions)
    prompt = f"""Questi sono nomi dello stesso prodotto usati da fornitori diversi:
{descriptions_text}

Crea un nome canonico breve e chiaro che identifichi univocamente questo prodotto.
Rispondi SOLO con il nome, nessun testo aggiuntivo."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def suggest_product_category(product_name: str, description: str) -> str:
    """Suggest a category for a product."""
    prompt = f"""Categorizza questo prodotto con una categoria breve (max 3 parole in italiano):
Nome: {product_name}
Descrizione: {description or 'N/A'}

Esempi di categorie: Alimentari, Bevande, Materiali da costruzione, Cancelleria,
Elettronica, Abbigliamento, Pulizia, Macchinari, Servizi, Altro

Rispondi SOLO con la categoria, nessun testo aggiuntivo."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
