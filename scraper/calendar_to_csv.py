#!/usr/bin/env python3
"""Télécharge le calendrier public Google et le transforme en CSV pour la page d'affichage.

Colonnes de data/evenements.csv : date_debut, date_fin, heure, titre, lieu, details, couleur, type
- les événements récurrents sont dépliés (bibliothèque recurring-ical-events) ;
- un événement « toute la journée » finit la veille de la date de fin du calendrier (la fin y est exclusive) ;
- le « type » est deviné d'après le titre ; une valeur corrigée à la main dans le CSV est conservée.
- la couleur du bandeau dépend du type (rouge = salle indisponible).
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
CHAMPS = ["date_debut", "date_fin", "heure", "titre", "lieu", "details", "couleur", "type"]

# Les mots sont cherchés « entiers » : « concours » ne doit pas être pris pour « cours ».
TYPES = [
    # rouge : la salle ou le terrain n'est pas utilisable
    ("indisponible", r"indisponib|salle ferm[ée]e?|\bferm[ée]e?s?\b|fermeture|salle occup[ée]e?|pas d['e ]?\s?entra[iî]nement|annul[ée]"),
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
    "indisponible": "#D9442F", "ferie": "#D9442F", "vacances": "#CD8B4A",
    "concours": "#F2C230", "tournoi": "#F2C230", "stage": "#4CAF7A",
    "formation": "#8E6BD1", "examen": "#8E6BD1", "reunion": "#A9BACB",
    "soiree": "#E26FA6", "cours": "#3B8BD1",
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


def read_existing_types(chemin):
    """Types corrigés à la main dans le CSV : on les garde à chaque régénération."""
    surcharges = {}
    if not chemin.exists():
        return surcharges
    try:
        with chemin.open("r", encoding="utf-8", newline="") as fh:
            lecteur = csv.DictReader(fh)
            if not lecteur.fieldnames or "type" not in lecteur.fieldnames:
                return surcharges
            for ligne in lecteur:
                cle = tuple((ligne.get(c) or "").strip() for c in ("date_debut", "date_fin", "titre", "lieu"))
                valeur = (ligne.get("type") or "").strip()
                if valeur:
                    surcharges[cle] = valeur
    except Exception:
        return {}
    return surcharges


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

    surcharges = read_existing_types(OUT)
    lignes, vus = [], set()
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
        type_ev = surcharges.get(cle) or infer_type(titre, lieu, details)
        lignes.append({
            "date_debut": cle[0], "date_fin": cle[1], "heure": heure,
            "titre": titre, "lieu": lieu, "details": details,
            "couleur": COULEURS_TYPES.get(type_ev) or normalize_color(ev.get("color")) or couleur_calendrier or "#3B8BD1",
            "type": type_ev,
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
