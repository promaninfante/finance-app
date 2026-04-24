"""
Local eval script for extract_transactions.

Usage:
    AWS_PROFILE=finance python scripts/eval_extraction.py path/to/statement.pdf [model_id]

Prints extracted transactions as a table for manual comparison against the real statement.
Run with different model_ids to compare quality:
    eu.amazon.nova-micro-v1:0          (default, cheapest)
    amazon.nova-lite-v1:0              (step up)
    anthropic.claude-3-haiku-20240307-v1:0
"""

import sys
import os

# Allow running from repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
from ingest.extract import _MODEL_ID, _call_bedrock, _extract_text, _validate


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/eval_extraction.py <pdf_path> [model_id]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    model_override = sys.argv[2] if len(sys.argv) > 2 else None

    if model_override:
        import ingest.extract as ext
        ext._MODEL_ID = model_override
        print(f"Model : {model_override}")
    else:
        print(f"Model : {_MODEL_ID}")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    print(f"PDF   : {pdf_path}  ({len(pdf_bytes):,} bytes)")

    text = _extract_text(pdf_bytes)
    print(f"Text  : {len(text):,} chars extracted by pypdf\n")

    if not text.strip():
        print("ERROR: pypdf extracted no text — scanned PDF not supported.")
        sys.exit(1)

    print("Calling Bedrock…")
    raw = _call_bedrock(text)

    try:
        txs = _validate(raw)
    except ValueError as exc:
        print(f"\nValidation error: {exc}")
        print("\nRaw LLM output:\n", raw)
        sys.exit(1)

    print(f"\n{'#':<4} {'Date':<12} {'Amount':>10} {'Cur':<5} Description")
    print("-" * 80)
    total = 0.0
    for i, tx in enumerate(txs, 1):
        print(f"{i:<4} {tx['date']:<12} {tx['amount']:>10.2f} {tx['currency']:<5} {tx['description'][:45]}")
        total += float(tx["amount"])
    print("-" * 80)
    print(f"{'Total':>16} {total:>10.2f}   ({len(txs)} transactions)\n")

    out_path = pdf_path.replace(".pdf", "_extracted.json")
    with open(out_path, "w") as f:
        json.dump(txs, f, indent=2)
    print(f"Full output saved to: {out_path}")


if __name__ == "__main__":
    main()
