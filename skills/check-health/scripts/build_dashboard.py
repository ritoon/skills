#!/usr/bin/env python3
"""Build the check-health dashboard: inject a data.json payload into the HTML template.

Usage:
    python3 build_dashboard.py data.json [output.html] [--template path]

Stdlib only. The template must contain the placeholder __CHECK_HEALTH_DATA__
exactly once, inside a <script type="application/json"> tag.
"""
import argparse
import json
import sys
from pathlib import Path

PLACEHOLDER = "__CHECK_HEALTH_DATA__"
DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "dashboard-template.html"


def main() -> None:
    parser = argparse.ArgumentParser(description="Injecte data.json dans le template du dashboard check-health.")
    parser.add_argument("data", help="chemin du data.json (schéma : references/dashboard.md)")
    parser.add_argument("output", nargs="?", default="dashboard.html", help="fichier HTML de sortie")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="template HTML alternatif")
    args = parser.parse_args()

    try:
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"erreur : {args.data} introuvable")
    except json.JSONDecodeError as exc:
        sys.exit(f"erreur : {args.data} n'est pas un JSON valide — {exc}")

    for key in ("generated_at", "organization", "counterparties"):
        if key not in data:
            sys.exit(f"erreur : clé requise absente de {args.data} : {key!r}")

    template = Path(args.template).read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        sys.exit(f"erreur : le template doit contenir {PLACEHOLDER} exactement une fois "
                 f"({template.count(PLACEHOLDER)} occurrence(s) trouvée(s))")

    # "</" escaped so a counterparty name can never close the <script> block.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = Path(args.output)
    out.write_text(template.replace(PLACEHOLDER, payload), encoding="utf-8")
    print(f"OK : {out} généré ({len(data.get('counterparties', []))} contrepartie(s), "
          f"{len(data.get('alerts', []))} alerte(s))")


if __name__ == "__main__":
    main()
