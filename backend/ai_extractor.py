"""
Uses Claude Vision to extract structured data from invoice files (PDF or image).
"""
import os
import base64
import json
import re
from pathlib import Path
from typing import Optional
import anthropic

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

EXTRACTION_PROMPT = """Analizza questa fattura e restituisci un JSON con la seguente struttura esatta:

{
  "supplier": {
    "name": "Nome fornitore",
    "vat_number": "Partita IVA o null",
    "address": "Indirizzo o null",
    "email": "Email o null",
    "phone": "Telefono o null"
  },
  "invoice": {
    "invoice_number": "Numero fattura o null",
    "invoice_date": "Data in formato YYYY-MM-DD o null",
    "total_amount": numero_float_o_null
  },
  "items": [
    {
      "raw_description": "Descrizione completa del prodotto/servizio",
      "quantity": numero_float_o_null,
      "unit": "unità di misura (pz, kg, lt, m, etc.) o null",
      "unit_price": prezzo_unitario_float_o_null,
      "total_price": prezzo_totale_riga_float_o_null
    }
  ]
}

Regole importanti:
- I prezzi devono essere numeri float (es. 12.50), non stringhe
- La quantità deve essere un numero float
- Se un campo non è presente, usa null
- Includi TUTTI i prodotti/servizi presenti nella fattura
- Per unit_price: se non è esplicitamente indicato ma puoi calcolarlo da totale/quantità, calcolalo
- Rispondi SOLO con il JSON, nessun testo aggiuntivo
"""


def _pdf_to_images_base64(file_path: str) -> list[str]:
    """Convert PDF pages to base64-encoded PNG images."""
    if not HAS_PYMUPDF:
        raise RuntimeError("PyMuPDF non installato. Installa con: pip install pymupdf")
    doc = fitz.open(file_path)
    images = []
    for page in doc:
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR quality
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        images.append(base64.standard_b64encode(img_bytes).decode())
    doc.close()
    return images


def _image_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode()


def _get_media_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")


def extract_invoice_data(file_path: str) -> dict:
    """
    Extract structured data from an invoice file using Claude Vision.
    Supports PDF and image formats.
    """
    ext = Path(file_path).suffix.lower()
    content_blocks = []

    if ext == ".pdf":
        images_b64 = _pdf_to_images_base64(file_path)
        for img_b64 in images_b64:
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            })
    else:
        img_b64 = _image_to_base64(file_path)
        media_type = _get_media_type(file_path)
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": img_b64,
            },
        })

    content_blocks.append({"type": "text", "text": EXTRACTION_PROMPT})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": content_blocks}],
        system=(
            "Sei un esperto contabile italiano specializzato nell'analisi di fatture. "
            "Estrai con precisione tutti i dati richiesti. "
            "Rispondi sempre e solo con JSON valido."
        ),
    )

    raw_text = response.content[0].text.strip()
    # Strip markdown code fences if present
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    return json.loads(raw_text)
