from pathlib import Path
import re
import sys

repo=Path(sys.argv[1]).resolve()

parity=(repo/"parity_api.py").read_text(encoding="utf-8")
r18=(repo/"r18_api.py").read_text(encoding="utf-8")

m=re.search(
    r"CREATE TABLE IF NOT EXISTS invoice_lines\((.*?)\);",
    parity,
    re.S
)

if not m:
    raise SystemExit("PARITY_INVOICE_LINES_SCHEMA_NOT_FOUND")

schema=m.group(1)

required=[
    "invoice_id",
    "line_type",
    "description",
    "quantity",
    "rate",
    "amount",
    "tax",
    "created_at",
    "tenant_id",
]

for col in required:
    if col not in schema:
        raise SystemExit("CANONICAL_COLUMN_MISSING="+col)

if "unit_price" in schema:
    raise SystemExit("UNEXPECTED_UNIT_PRICE_IN_CANONICAL_SCHEMA")

if "INSERT INTO invoice_lines" not in r18:
    raise SystemExit("R18_INVOICE_LINE_INSERT_MISSING")

if "rate,amount,line_type" not in r18:
    raise SystemExit("R18_NOT_USING_CANONICAL_RATE_COLUMN")

print("CANONICAL_INVOICE_LINES_SCHEMA=PASS")
print("R18_INVOICE_LINE_COMPATIBILITY=PASS")
