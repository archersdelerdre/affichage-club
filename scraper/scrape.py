#!/usr/bin/env python3
"""
Récupère les résultats FFTA des archers du club et écrit data/resultats.json.

Principe :
  1. liste les compétitions de la période sur ffta.fr/competitions
  2. télécharge les PDF « Résultats » publiés
  3. garde les archers dont le club est dans CLUBS
  4. recalcule les rangs entre tous les archers de la catégorie (score, puis 10, puis 9)

Usage :
  python scraper/scrape.py                      # 9 derniers jours
  python scraper/scrape.py --debut 2026-10-10 --fin 2026-10-12
  python scraper/scrape.py --pdf resultats.pdf  # test sur un PDF local (affiche le JSON)
  python scraper/scrape.py --tout               # retélécharge aussi les PDF déjà vus

Variable d'environnement : CLUBS="CARQUEFOU" (plusieurs clubs séparés par des virgules).
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "data" / "resultats.json"
VUS = RACINE / "data" / "vus.json"

CLUBS = [c.strip().upper() for c in os.environ.get("CLUBS", "CARQUEFOU").split(",") if c.strip()]
JOURS_GARDES = 10
LISTE_URL = "https://www.ffta.fr/competitions"
HEADERS = {"User-Agent": "Mozilla/5.0 (affichage-club; usage associatif, 1 passage par jour)"}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]
PETITS = {"a", "à", "au", "aux", "de", "des", "du", "la", "le", "les", "sur", "sous", "et", "en", "d", "l"}
ACCENTS_MAJ = "ÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ"

# rang, « nom + club », licence, catégorie, m1, m2, total, [nb10] [nb9]
LIGNE_RESULTAT = re.compile(
    r"^(\d+)\s+(.+?)\s+(\d{7}[A-Z])\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)((?:\s+\d+){0,2})\s*$"
)
ENTETE_GROUPE = re.compile(r"^([A-Za-zÀ-ÿ].*?\s20\d\d)(?:\s*\(Suite\))?$")

# Corrections de noms à la main : data/corrections.json  {"Raphaêl SEROC": "Raphaël SEROC"}
try:
    CORRECTIONS = json.loads((RACINE / "data" / "corrections.json").read_text(encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    CORRECTIONS = {}


# ----------------------------------------------------------------- mise en forme
def joli(texte):
    """« CONCOURS SALLE CARQUEFOU » -> « Concours Salle Carquefou »."""
    mots = []
    for mot in texte.split():
        bas = mot.lower()
        if bas in PETITS:
            mots.append(bas)
        elif any(c.isdigit() for c in mot) or (len(mot) <= 3 and mot.isupper()):
            mots.append(mot.upper())
        else:
            mots.append("-".join(p.capitalize() for p in bas.split("-")))
    if mots:
        mots[0] = mots[0][0].upper() + mots[0][1:]
    return " ".join(mots)


def corriger_accents(mot):
    """Le PDF écrit « ClÉmence » : on remet en minuscule les accents après la 1re lettre."""
    return "".join(c.lower() if i > 0 and c in ACCENTS_MAJ else c for i, c in enumerate(mot))


def formater_nom(brut):
    """« MARTIN DONGEON ThÉa » -> « Théa MARTIN DONGEON »."""
    mots = brut.split()
    i = 0
    while i < len(mots) and mots[i].upper() == mots[i]:
        i += 1
    nom, prenom = mots[:i], mots[i:]
    if not prenom:
        return " ".join(nom)
    return " ".join(corriger_accents(m) for m in prenom) + " " + " ".join(nom)


def dates_fr(d1, d2):
    if d1 == d2:
        return f"{d1.day} {MOIS[d1.month - 1]} {d1.year}"
    if (d1.month, d1.year) == (d2.month, d2.year):
        return f"{d1.day} et {d2.day} {MOIS[d1.month - 1]} {d1.year}"
    return f"{d1.day} {MOIS[d1.month - 1]} au {d2.day} {MOIS[d2.month - 1]} {d2.year}"


def type_arc(titre):
    t = titre.lower()
    if "poulies" in t:
        return "poulies"
    if "arc nu" in t:
        return "nu"
    return "classique"


def titre_court(titre):
    t = re.sub(r"\s+(Arc\s+(?:Classique|à Poulies|a Poulies|Nu)|Classique)\s+20\d\d.*$", "", titre).strip()
    return re.sub(r"\s+20\d\d.*$", "", t).strip()


# ----------------------------------------------------------------- lecture d'un PDF
def lire_pdf(contenu):
    """Retourne un dict concours, {"vide": True} si aucun archer du club, None si format inconnu."""
    with pdfplumber.open(io.BytesIO(contenu)) as pdf:
        texte = "\n".join((p.extract_text() or "") for p in pdf.pages)

    m = re.search(r"Classement Officiel\s+(.+?)\s+du\s+(\d\d)/(\d\d)/(\d{4})\s+au\s+(\d\d)/(\d\d)/(\d{4})", texte, re.S)
    if not m:
        return None
    bloc = re.sub(r"\s+", " ", m.group(1)).strip(" -")
    parties = [p.strip() for p in re.split(r"\s+-\s+", bloc)]
    d1 = dt.date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
    d2 = dt.date(int(m.group(7)), int(m.group(6)), int(m.group(5)))

    groupes, tampon, courant, arret, dernier = {}, [], None, False, None
    for ligne in (l.strip() for l in texte.splitlines()):
        if not ligne:
            continue
        if ligne.startswith("Autres tirs"):          # 2e/3e tirs : on garde le classement général
            arret = True
        if arret:
            continue
        if ligne.startswith(("Clt ", "Tir ", "Nbre d'archers", "Classement Officiel")) or re.search(r"Page \d+/\d+$", ligne):
            tampon, dernier = [], None
            continue
        if " - " not in ligne and not re.search(r"\d{7}[A-Z]", ligne):
            g = ENTETE_GROUPE.match(ligne)
            if g:
                courant = g.group(1)
                tampon, dernier = [], None
                continue
        if courant is None:
            continue
        r = LIGNE_RESULTAT.match(" ".join(tampon + [ligne]))
        if r:
            reste = r.group(2)
            club = next((c for c in CLUBS if reste.upper().endswith(c)), None)
            nom = reste[: -len(club)].strip() if club else reste
            extra = re.findall(r"\d+", r.group(8))
            if len(extra) == 2:
                nb10, nb9 = int(extra[0]), int(extra[1])
            else:                                     # une seule valeur : on la compte comme nb de 9
                nb10, nb9 = 0, (int(extra[0]) if extra else 0)
            dernier = {
                "licence": r.group(3), "total": int(r.group(7)),
                "nb10": nb10, "nb9": nb9, "club": club, "nom": nom,
            }
            groupes.setdefault(courant, []).append(dernier)
            tampon = []
        elif dernier is not None and not re.search(r"\d", ligne) and len(ligne) < 40:
            dernier["nom"] = f"{dernier['nom']} {ligne}".strip()   # prénom coupé sur la ligne suivante
            dernier = None
        elif re.match(r"^\d+\s", ligne):
            tampon, dernier = [ligne], None          # début d'une ligne coupée sur plusieurs lignes
        else:
            tampon, dernier = (tampon + [ligne])[-3:], None

    sorties = []
    for titre, lignes in groupes.items():
        meilleurs = {}
        for l in lignes:                              # un archer présent 2 fois : on garde le meilleur
            if l["licence"] not in meilleurs or l["total"] > meilleurs[l["licence"]]["total"]:
                meilleurs[l["licence"]] = l
        classes = sorted(meilleurs.values(), key=lambda l: (-l["total"], -l["nb10"], -l["nb9"]))
        rang, precedent, resultat = 0, None, []
        for pos, l in enumerate(classes, start=1):
            cle = (l["total"], l["nb10"], l["nb9"])
            if cle != precedent:
                rang, precedent = pos, cle
            if l["club"]:
                nom = formater_nom(l["nom"])
                resultat.append([CORRECTIONS.get(nom, nom), rang, l["total"]])
        if resultat:
            sorties.append({"arc": type_arc(titre), "titre": titre_court(titre), "lignes": resultat})
    if not sorties:
        return {"vide": True}

    ordre = {"classique": 0, "poulies": 1, "nu": 2}
    sorties.sort(key=lambda g: ordre[g["arc"]])      # tri stable : l'ordre du PDF reste dans chaque type

    total = re.search(r"Nombre total d'archers\s*:\s*(\d+)", texte)
    pied = re.search(r"(\d{1,2})\s+([A-Za-zéûè]+)\s+(20\d\d)\s+Page\s+\d+/\d+", texte)
    source = (f"Source : classement officiel FFTA du {int(pied.group(1))} {pied.group(2).lower()} {pied.group(3)}"
              if pied else "Source : classement officiel FFTA")
    return {
        "nom": joli(parties[0]),
        "format": parties[1] if len(parties) > 1 else "",
        "dates": dates_fr(d1, d2),
        "fin": d2.isoformat(),
        "totalArchers": int(total.group(1)) if total else 0,
        "source": source,
        "groupes": sorties,
    }


# ----------------------------------------------------------------- liste des compétitions
def lister_pdfs(debut, fin):
    liens, epreuves_vues = [], set()
    for page in range(60):
        r = requests.get(LISTE_URL, headers=HEADERS, timeout=30, params={
            "discipline": "All", "start": debut, "end": fin,
            "sort_by": "start", "sort_order": "DESC", "page": page,
        })
        r.raise_for_status()
        soupe = BeautifulSoup(r.text, "html.parser")
        ids = {a["href"] for a in soupe.select('a[href*="/epreuve/"]')}
        if not ids or ids <= epreuves_vues:
            break
        epreuves_vues |= ids
        for a in soupe.find_all("a", href=True):
            if "pdfresultats" in a["href"]:
                url = urljoin(LISTE_URL, a["href"])
                if url not in liens:
                    liens.append(url)
        time.sleep(0.5)
    return liens


# ----------------------------------------------------------------- programme principal
def charger(chemin, defaut):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return defaut


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--debut")
    ap.add_argument("--fin")
    ap.add_argument("--jours", type=int, default=9)
    ap.add_argument("--pdf", help="tester sur un PDF local")
    ap.add_argument("--tout", action="store_true", help="ignorer la liste des PDF déjà vus")
    a = ap.parse_args()

    if a.pdf:
        print(json.dumps(lire_pdf(Path(a.pdf).read_bytes()), ensure_ascii=False, indent=1))
        return

    aujourdhui = dt.date.today()
    fin = a.fin or aujourdhui.isoformat()
    debut = a.debut or (aujourdhui - dt.timedelta(days=a.jours)).isoformat()
    print(f"Période : {debut} -> {fin}  |  clubs : {', '.join(CLUBS)}")

    donnees = charger(FICHIER, {"concours": []})
    vus = set() if a.tout else set(charger(VUS, []))
    par_id = {c["id"]: c for c in donnees.get("concours", [])}

    liens = lister_pdfs(debut, fin)
    print(f"{len(liens)} PDF de résultats publiés sur la période")
    for url in liens:
        if url in vus:
            continue
        try:
            r = requests.get(url, headers=HEADERS, timeout=90)
            r.raise_for_status()
            res = lire_pdf(r.content)
        except Exception as e:                       # on réessaiera au prochain passage
            print(f"  ! {url} : {e}", file=sys.stderr)
            continue
        vus.add(url)
        if res and not res.get("vide"):
            res["id"] = url
            par_id[url] = res
            print(f"  + {res['nom']} ({res['dates']}) : {sum(len(g['lignes']) for g in res['groupes'])} archers du club")
        time.sleep(0.5)

    limite = (aujourdhui - dt.timedelta(days=JOURS_GARDES)).isoformat()
    concours = sorted((c for c in par_id.values() if c["fin"] >= limite), key=lambda c: c["fin"], reverse=True)
    FICHIER.parent.mkdir(exist_ok=True)
    FICHIER.write_text(json.dumps({"maj": aujourdhui.isoformat(), "concours": concours}, ensure_ascii=False, indent=1), encoding="utf-8")
    VUS.write_text(json.dumps(sorted(vus), indent=1), encoding="utf-8")
    print(f"{len(concours)} concours dans data/resultats.json")


if __name__ == "__main__":
    main()
