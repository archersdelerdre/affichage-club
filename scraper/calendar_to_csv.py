#!/usr/bin/env python3
"""Télécharge le calendrier public Google et le transforme en CSV pour la page d'affichage.

Colonnes de data/evenements.csv : date_debut, date_fin, heure, titre, lieu, details, couleur, type
- les événements récurrents sont dépliés (bibliothèque recurring-ical-events) ;
- un événement « toute la journée » finit la veille de la date de fin du calendrier (la fin y est exclusive) ;
- le « type » est deviné d'après le titre et la description, à chaque mise à jour.
"""
import csv
import html
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "evenements.csv"
DEFAULT_URL = "https://calendar.google.com/calendar/ical/secretaire.archerserdre%40gmail.com/public/basic.ics"
LOCAL_TZ = ZoneInfo("Europe/Paris")
JOURS_PASSE = 7        # on garde les événements des 7 derniers jours
JOURS_FUTUR = 400      # et ceux des 400 prochains
FERIES_AUTOMATIQUES = True   # ajoute chaque jour férié français comme « pas de tir »
CHAMPS = ["date_debut", "date_fin", "heure", "titre", "lieu", "details", "couleur", "type"]

# Les mots sont cherchés « entiers » : « concours » ne doit pas être pris pour « cours ».
TYPES = [
    # orange : un cours ou un entraînement n'a pas lieu (quelle qu'en soit la raison)
    ("annule", r"annul[ée]|pas d['e ]?\s?entra[iî]nement|pas de cours|cours supprim"),
    # rouge : pas de tir (salle ou terrain inutilisable, jour férié)
    ("indisponible", r"(salle|gymnase|terrain|stand|local|complexe|site)\b[^.\n]{0,40}(indisponib|ferm[ée]|occup[ée]|inaccessible|inond)"
                     r"|indisponibilit[ée] (de la |du |de l')?(salle|gymnase|terrain|stand)|fermeture|\bferm[ée]e?s?\b|terrain inond"),
    ("ferie", r"f[ée]ri[ée]"),
    ("vacances", r"vacances"),
    ("concours", r"\bconcours\b"),
    ("stage", r"\bstages?\b"),
    ("tournoi", r"\btournois?\b"),
    ("formation", r"\bformations?\b|\barbitres?\b"),
    ("reunion", r"assembl[ée]e|\br[ée]unions?\b"),
    ("soiree", r"soir[ée]e"),
    ("examen", r"\bexamens?\b"),
    ("cours", r"\bcours\b"),
]

# Couleur du petit bandeau de chaque événement selon son type (rouge = salle indisponible)
COULEURS_TYPES = {
    "indisponible": "#D9442F", "ferie": "#D9442F", "annule": "#F08A24", "vacances": "#CD8B4A",
    "concours": "#F2C230", "tournoi": "#F2C230", "stage": "#4CAF7A",
    "formation": "#8E6BD1", "examen": "#8E6BD1", "reunion": "#A9BACB",
    "soiree": "#E26FA6", "cours": "#3B8BD1",
}


def paques(annee):
    """Date de Pâques (calendrier grégorien)."""
    a, b, c = annee % 19, annee // 100, annee % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = (h + l - 7 * m + 114) % 31 + 1
    return date(annee, mois, jour)


def jours_feries(annee):
    """Les 11 jours fériés de la France métropolitaine : {date: nom}."""
    p = paques(annee)
    return {
        date(annee, 1, 1): "Jour de l'An",
        p + timedelta(days=1): "Lundi de Pâques",
        date(annee, 5, 1): "Fête du Travail",
        date(annee, 5, 8): "Victoire 1945",
        p + timedelta(days=39): "Ascension",
        p + timedelta(days=50): "Lundi de Pentecôte",
        date(annee, 7, 14): "Fête nationale",
        date(annee, 8, 15): "Assomption",
        date(annee, 11, 1): "Toussaint",
        date(annee, 11, 11): "Armistice 1918",
        date(annee, 12, 25): "Noël",
    }


def as_text(value):
    if value is None:
        return ""
    text = str(value).replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def clean_description(value):
    text = as_text(value)
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.replace("\n ", "\n").strip()


def infer_type(summary, location="", description=""):
    texte = f"{summary} {location} {description}".lower()
    for nom, motif in TYPES:
        if re.search(motif, texte):
            return nom
    return ""


def normalize_color(valeur):
    v = as_text(valeur).strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", v):
        return "#" + v.lstrip("#").upper()
    return ""


def to_local(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ)


def dates_et_heure(debut, fin):
    """Retourne (date_debut, date_fin ou None, heure) en heure de Paris.

    Journée entière : la fin du calendrier est exclusive, donc on retire un jour.
    Événement horaire : une fin à minuit pile compte pour la veille.
    """
    if isinstance(debut, datetime):
        d = to_local(debut)
        f = to_local(fin) if isinstance(fin, datetime) else None
        fin_date = f.date() if f else d.date()
        if f and f.time() == datetime.min.time() and fin_date > d.date():
            fin_date -= timedelta(days=1)
        return d.date(), (fin_date if fin_date != d.date() else None), d.strftime("%H:%M")
    fin_date = fin - timedelta(days=1) if isinstance(fin, date) and fin > debut else debut
    return debut, (fin_date if fin_date != debut else None), ""


def main():
    import recurring_ical_events
    import requests
    from icalendar import Calendar

    url = os.environ.get("CALENDAR_URL", DEFAULT_URL)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    cal = Calendar.from_ical(r.content)
    couleur_calendrier = normalize_color(cal.get("X-APPLE-CALENDAR-COLOR") or cal.get("COLOR") or "")

    aujourdhui = date.today()
    evenements = recurring_ical_events.of(cal).between(
        aujourdhui - timedelta(days=JOURS_PASSE), aujourdhui + timedelta(days=JOURS_FUTUR))

    lignes, vus, feries_calendrier = [], set(), set()
    for ev in evenements:
        if as_text(ev.get("status")).upper() == "CANCELLED":
            continue
        titre = as_text(ev.get("summary"))
        if not titre:
            continue
        lieu = as_text(ev.get("location"))
        details = clean_description(ev.get("description"))
        debut = ev.get("dtstart").dt
        fin = ev.get("dtend").dt if ev.get("dtend") else None
        if fin is None:
            duree = ev.get("duration")
            fin = debut + (duree.dt if duree else (timedelta(days=1) if not isinstance(debut, datetime) else timedelta(hours=1)))
        d1, d2, heure = dates_et_heure(debut, fin)
        cle = (d1.isoformat(), d2.isoformat() if d2 else "", titre, lieu)
        if cle + (details,) in vus:
            continue
        vus.add(cle + (details,))
        type_ev = infer_type(titre, lieu, details)
        if type_ev == "ferie":                      # jour férié : on n'affiche que « Pas de tir indisponible »
            feries_calendrier.add(d1.isoformat())
            titre, lieu, details, type_ev = "Pas de tir indisponible", "", "", "indisponible"
        lignes.append({
            "date_debut": cle[0], "date_fin": cle[1], "heure": heure,
            "titre": titre, "lieu": lieu, "details": details,
            "couleur": COULEURS_TYPES.get(type_ev) or normalize_color(ev.get("color")) or couleur_calendrier or "#3B8BD1",
            "type": type_ev,
        })

    if FERIES_AUTOMATIQUES:
        debut_f, fin_f = aujourdhui - timedelta(days=JOURS_PASSE), aujourdhui + timedelta(days=JOURS_FUTUR)
        deja = set(feries_calendrier)
        for annee in range(debut_f.year, fin_f.year + 1):
            for jour, nom in sorted(jours_feries(annee).items()):
                if debut_f <= jour <= fin_f and jour.isoformat() not in deja:
                    lignes.append({
                        "date_debut": jour.isoformat(), "date_fin": "", "heure": "",
                        "titre": "Pas de tir indisponible", "lieu": "", "details": "",
                        "couleur": COULEURS_TYPES["indisponible"], "type": "indisponible",
                    })

    lignes.sort(key=lambda x: (x["date_debut"], x["heure"], x["titre"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        ecrivain = csv.DictWriter(fh, fieldnames=CHAMPS)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"{len(lignes)} événements écrits dans {OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        raise
