from pathlib import Path
import sys

root=Path(sys.argv[1])

r16=(root/"web"/"r16.js").read_text(encoding="utf-8")

required=[
    "function r16MenuCapability(route)",
    "function r16MenuAllowed(route)",
    "r16MenuAllowed(route)",
    "data-r16-route=",
    "hotlists:'hotlists'",
    "employees:'assignments'",
    "newCandidateR16:'candidates'",
    "newJobR16:'jobs'",
    "divaBuzzR16:'communications'",
]

for marker in required:
    if marker not in r16:
        raise SystemExit(
            "ROLE_MENU_GATE_MISSING="+marker
        )

if "group[2].filter(" not in r16:
    raise SystemExit(
        "R16_MENU_NOT_FILTERING_ITEMS"
    )

print("R16_ROLE_MENU_STATIC_GATE=PASS")
print("FINANCE_HOTLIST_VISIBILITY_EXPECTED=NO")
print("ROLE_MENU_AUTHORITY=NAV")
