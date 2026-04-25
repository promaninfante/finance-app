import re

_STRIP_PATTERNS = [
    r'\b\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?\b',   # dates DD/MM, DD/MM/YYYY
    r'\b\d{1,2}:\d{2}(?::\d{2})?\b',                   # times HH:MM
    r'\b\d{6,}\b',                                      # long digit refs
    r'\*[A-Z0-9]{4,}',                                  # *REFCODE suffixes
    r'\b(?:COMPRA|TARJETA|PAGO|RECIBO|TRANSFERENCIA|TRASPASO|CARGO|ABONO|'
    r'COMISION|LIQUIDACION|MOVIMIENTO|REF|OFI|BIZUM|SEPA|CXC)\b',
    r'\b(?:PURCHASE|PAYMENT|CARD|DEBIT|CREDIT|TRANSFER|'
    r'DIRECT\s+DEBIT|STANDING\s+ORDER|POS|ATM|VISA|MASTERCARD)\b',
    r'\b[A-Z]{1,3}\d{5,}\b',       # short-prefix numeric refs (e.g. ES12345)
    r'\b[A-Z0-9]{8,}\b',           # generic alphanumeric codes
    r'(?:EUR|USD|GBP|€|\$|£)\s*\d+(?:[.,]\d{2})?',  # leaked amounts
]
_COMPILED = [re.compile(p) for p in _STRIP_PATTERNS]


def normalize_merchant(description: str) -> str:
    """Strip transaction noise from a bank description and return UPPERCASE.

    Never raises — returns uppercased input as fallback if everything strips away.
    """
    text = description.upper()
    for pattern in _COMPILED:
        text = pattern.sub(' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text or description.upper().strip()
