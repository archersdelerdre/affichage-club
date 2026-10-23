#!/usr/bin/env python3
"""
Copie le tableur des admins (Google Sheet publié en CSV) dans le dépôt :
  data/evenements.csv  et  data/indisponibilites.csv

Les liens sont lus dans config.js (SHEET_EVENEMENTS_CSV et SHEET_INDISPOS_CSV).
Ces copies servent de secours : si la page ne peut pas joindre Google (Raspberry sans internet),
elle lit ces fichiers.
"""
import re
import sys
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
SOURCES = [("SHEET_EVENEMENTS_CSV", "evenements.csv"), ("SHEET_INDISPOS_CSV", "indisponibilites.csv")]


def lien(config, cle):
    m = re.search(cle + r'\s*:\s*"([^"]*)"', config)
    return m.group(1).strip() if m else ""


def main():
    config = (RACINE / "config.js").read_text(encoding="utf-8")
    for cle, fichier in SOURCES:
        url = lien(config, cle)
        if not url:
            print(f"{cle} : lien vide, ignoré")
            continue
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            texte = r.content.decode("utf-8-sig")
        except Exception as e:
            print(f"! {cle} : {e}", file=sys.stderr)
            continue
        if texte.lstrip().startswith("<") or "date_debut" not in texte.splitlines()[0].lower():
            print(f"! {cle} : le lien ne renvoie pas un CSV avec les bonnes colonnes (publié en CSV ? bon onglet ?)", file=sys.stderr)
            continue
        (RACINE / "data" / fichier).write_text(texte, encoding="utf-8")
        print(f"{fichier} : {len(texte.splitlines()) - 1} ligne(s)")


if __name__ == "__main__":
    main()
