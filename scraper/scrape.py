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
  python scraper/scrape.py --debut 2026-01-01   # rattrapage de toute l'année (long : à lancer par tranches)
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
LISTE_URL = "https://www.ffta.fr/competitions"
HEADERS = {"User-Agent": "Mozilla/5.0 (affichage-club; usage associatif, 1 passage par jour)"}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]
PETITS = {"a", "à", "au", "aux", "de", "des", "du", "la", "le", "les", "sur", "sous", "et", "en", "d", "l"}
ACCENTS_MAJ = "ÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ"

# rang, « nom + club », licence, catégorie, puis tous les nombres (manches, total, nb de 10/9 ou 6/5)
# (le club et la licence sont parfois collés dans le PDF : « MONTLOUIS-SURLOIRE0421335Y »)
LIGNE_RESULTAT = re.compile(r"^(\d+)\s+(.+?)\s*(\d{7}[A-Z])\s+(\S+)((?:\s+\d+)+)\s*$")

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
        if mot in ("TIR", "ARC"):
            mots.append(mot.capitalize())
        elif bas in PETITS or bas in ("un", "une"):
            mots.append(bas)
        elif "'" in mot:
            avant, apres = mot.split("'", 1)
            mots.append(avant.lower() + "'" + apres.capitalize())
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
        liaison = "et" if (d2 - d1).days == 1 else "au"
        debut = "" if liaison == "et" else "du "
        return f"{debut}{d1.day} {liaison} {d2.day} {MOIS[d1.month - 1]} {d1.year}"
    return f"{d1.day} {MOIS[d1.month - 1]} au {d2.day} {MOIS[d2.month - 1]} {d2.year}"


def type_arc(titre):
    t = titre.lower()
    if "poulies" in t:
        return "poulies"
    if "arc nu" in t:
        return "nu"
    if "arc droit" in t:
        return "droit"
    if "classique" in t:
        return "classique"
    return "autre"                                   # Promotion, Pro-first, etc.


def titre_court(titre):
    t = re.sub(r"\s*\(Suite\)\s*$", "", titre).strip()
    t = re.sub(r"\s+(Arc\s+(?:Classique|à Poulies|a Poulies|Nu|Droit)|Classique)(\s+20\d\d)?.*$", "", t).strip()
    return re.sub(r"\s+20\d\d$", "", t).strip()


def lire_entete(ligne):
    """Lit l'en-tête du tableau.
    ('total', n)       : n manches puis une colonne Total   (salle, extérieur, campagne)
    ('multi', [noms])  : colonnes de résultat sans Total, ex. ['H.', 'P.'] (Beursault)
    """
    t = ligne.split()
    if "Cat" not in t:
        return ("total", 2)
    apres = t[t.index("Cat") + 1:]
    if "Total" in apres:
        return ("total", apres.index("Total"))
    noms = []
    for x in apres:
        if x.startswith("Nb"):
            break
        noms.append(x)
    return ("multi", noms) if noms else ("total", 2)


# ----------------------------------------------------------------- lecture d'un PDF
def lire_pdf(contenu):
    """Retourne un dict concours, {"vide": True} si aucun archer du club, None si format inconnu."""
    with pdfplumber.open(io.BytesIO(contenu)) as pdf:
        texte = "\n".join((p.extract_text() or "") for p in pdf.pages)

    m = re.search(
        r"Classement Officiel\s+(.+?)\s+(?:du\s+(\d\d)/(\d\d)/(\d{4})\s+au\s+(\d\d)/(\d\d)/(\d{4})|le\s+(\d\d)/(\d\d)/(\d{4}))",
        texte, re.S)
    if not m:
        return None
    bloc = re.sub(r"\s+", " ", m.group(1)).strip(" -")
    parties = [p.strip() for p in re.split(r"\s+-\s+", bloc)]
    if m.group(2):
        d1 = dt.date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
        d2 = dt.date(int(m.group(7)), int(m.group(6)), int(m.group(5)))
    else:
        d1 = d2 = dt.date(int(m.group(10)), int(m.group(9)), int(m.group(8)))

    groupes, tampon, courant, arret, dernier, prec, entete = {}, [], None, False, None, None, ("total", 2)
    for ligne in (l.strip() for l in texte.splitlines()):
        if not ligne:
            continue
        if ligne.startswith("Autres tirs"):          # 2e/3e tirs : on garde le classement général
            arret = True
        if arret:
            continue
        if ligne.startswith(("Clt ", "Tir ")):       # en-tête de tableau : la ligne d'avant est le titre de la catégorie
            if prec:
                courant = re.sub(r"\s*\(Suite\)\s*$", "", prec).strip()
            entete = lire_entete(ligne)
            tampon, dernier = [], None
            continue
        if ligne.startswith(("Nbre d'archers", "Classement Officiel")) or re.search(r"Page \d+/\d+$", ligne):
            tampon, dernier = [], None
            continue
        r = LIGNE_RESULTAT.match(" ".join(tampon + [ligne]))
        if r:
            nombres = [int(x) for x in re.findall(r"\d+", r.group(5))]
            if courant is not None and nombres:
                reste = r.group(2)
                club = next((c for c in CLUBS if reste.upper().endswith(c)), None)
                nom = reste[: -len(club)].strip() if club else reste
                if entete[0] == "total":
                    # Les manches vides ne laissent aucun nombre dans le texte : on ne peut pas compter les colonnes.
                    # Le total est le plus grand des (manches + 1) premiers nombres (il est >= à chaque manche).
                    fenetre = nombres[: entete[1] + 1]
                    total_ligne = max(fenetre)
                    pos = max(i for i, v in enumerate(fenetre) if v == total_ligne)
                    valeurs, extra, affichage = [total_ligne], nombres[pos + 1:], None
                else:
                    # Colonnes de résultat sans total (Beursault : H. puis P.) : classement sur la 1re, puis la 2e...
                    k = len(entete[1])
                    valeurs, extra = nombres[:k], nombres[k:]
                    affichage = ", ".join(f"{v} {n.rstrip('.')}" for n, v in zip(entete[1], valeurs))
                if len(extra) >= 2:
                    nb_haut, nb_bas = extra[0], extra[1]
                else:                                 # une seule valeur : on la compte comme 2e colonne
                    nb_haut, nb_bas = 0, (extra[0] if extra else 0)
                dernier = {"licence": r.group(3), "total": valeurs[0], "cle": tuple(valeurs) + (nb_haut, nb_bas),
                           "affichage": affichage, "club": club, "nom": nom}
                groupes.setdefault(courant, []).append(dernier)
            tampon = []
        elif dernier is not None and not re.search(r"\d", ligne) and len(ligne) < 40:
            dernier["nom"] = f"{dernier['nom']} {ligne}".strip()   # prénom ou club coupé sur la ligne suivante
            dernier = None
        elif re.match(r"^\d+\s", ligne):
            tampon, dernier = [ligne], None          # début d'une ligne coupée sur plusieurs lignes
        else:
            tampon, dernier, prec = (tampon + [ligne])[-3:], None, ligne

    sorties = []
    for titre, lignes in groupes.items():
        meilleurs = {}
        for l in lignes:                              # un archer présent 2 fois : on garde le meilleur
            if l["licence"] not in meilleurs or l["cle"] > meilleurs[l["licence"]]["cle"]:
                meilleurs[l["licence"]] = l
        classes = sorted(meilleurs.values(), key=lambda l: l["cle"], reverse=True)
        rang, precedent, resultat = 0, None, []
        for pos, l in enumerate(classes, start=1):
            cle = l["cle"]
            if cle != precedent:
                rang, precedent = pos, cle
            if l["club"]:
                nom = formater_nom(l["nom"])
                resultat.append([CORRECTIONS.get(nom, nom), rang, l["total"]] + ([l["affichage"]] if l["affichage"] else []))
        if resultat:
            sorties.append({"arc": type_arc(titre), "titre": titre_court(titre), "lignes": resultat})
    if not sorties:
        return {"vide": True}

    ordre = {"classique": 0, "poulies": 1, "nu": 2, "droit": 3, "autre": 4}
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
def fenetres(debut, fin, pas=14):
    """Découpe une longue période en tranches de 14 jours (la liste FFTA est paginée)."""
    d, f = dt.date.fromisoformat(debut), dt.date.fromisoformat(fin)
    while d <= f:
        e = min(d + dt.timedelta(days=pas - 1), f)
        yield d.isoformat(), e.isoformat()
        d = e + dt.timedelta(days=1)


def lister_fenetre(debut, fin):
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


def lister_pdfs(debut, fin):
    liens = []
    for d, f in fenetres(debut, fin):
        trouves = lister_fenetre(d, f)
        print(f"  {d} -> {f} : {len(trouves)} PDF")
        liens += [u for u in trouves if u not in liens]
    return liens


# ----------------------------------------------------------------- programme principal
def charger(chemin, defaut):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return defaut


def sauver(par_id, vus):
    """Écrit tout l'historique des concours (rien n'est effacé)."""
    concours = sorted(par_id.values(), key=lambda c: c["fin"], reverse=True)
    FICHIER.parent.mkdir(exist_ok=True)
    FICHIER.write_text(json.dumps({"maj": dt.date.today().isoformat(), "concours": concours},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    VUS.write_text(json.dumps(sorted(vus), indent=1), encoding="utf-8")
    return len(concours)


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
    a_faire = [u for u in liens if u not in vus]
    print(f"{len(liens)} PDF de résultats publiés, {len(a_faire)} à lire")
    for n, url in enumerate(a_faire, start=1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=90)
            r.raise_for_status()
            res = lire_pdf(r.content)
        except Exception as e:                       # on réessaiera au prochain passage
            print(f"  ! {url} : {e}", file=sys.stderr)
            continue
        vus.add(url)
        if res is None:
            print(f"  ? format non reconnu : {url}")
        elif res.get("vide"):
            print(f"  - aucun archer du club : {url}")
        if res and not res.get("vide"):
            res["id"] = url
            par_id[url] = res
            print(f"  + {res['nom']} ({res['dates']}) : {sum(len(g['lignes']) for g in res['groupes'])} archers du club")
        if n % 25 == 0:                              # sauvegarde régulière pour les longs rattrapages
            sauver(par_id, vus)
            print(f"  ... {n}/{len(a_faire)}")
        time.sleep(0.5)

    print(f"{sauver(par_id, vus)} concours avec des archers du club dans data/resultats.json")


if __name__ == "__main__":
    main()

