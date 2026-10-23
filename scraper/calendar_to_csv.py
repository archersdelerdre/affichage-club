#!/usr/bin/env python3
"""Télécharge le calendrier public Google et le transforme en CSV exploitable par la page d'affichage."""

import csv
import html
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "evenements.csv"
DEFAULT_URL = "https://calendar.google.com/calendar/ical/secretaire.archerserdre%40gmail.com/public/basic.ics"
LOCAL_TZ = ZoneInfo("Europe/Paris")


def read_calendar(url: str) -> Calendar:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return Calendar.from_ical(r.content)


def to_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        text = value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text.strip()
    return str(value)


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


def normalize_local(dt):
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime.combine(dt, datetime.min.time(), tzinfo=LOCAL_TZ)
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ)


def extract_occurrences(event):
    start = event.get("dtstart")
    end = event.get("dtend")
    if start is None:
        return []

    dt_start = start.dt
    dt_end = end.dt if end else dt_start + timedelta(hours=1)
    duration = dt_end - dt_start

    window_start = datetime.utcnow() - timedelta(days=7)
    window_end = datetime.utcnow() + timedelta(days=3660)

    occurrences = []
    rrule = event.get("rrule")
    if rrule or event.get("rruleset"):
        candidates = []
        if event.get("rruleset"):
            try:
                candidates.extend(event.rruleset.between(window_start, window_end))
            except Exception:
                candidates = []
        if not candidates and rrule:
            try:
                candidates.extend(rrule.between(window_start, window_end))
            except Exception:
                candidates = []
        if not candidates:
            candidates = [dt_start]
        for occ in candidates:
            occ_start = occ if isinstance(occ, datetime) else datetime.combine(occ, datetime.min.time())
            occ_end = occ_start + duration
            occurrences.append((occ_start, occ_end))
    else:
        occurrences.append((dt_start, dt_end))

    return occurrences


def main():
    url = os.environ.get("CALENDAR_URL", DEFAULT_URL)
    cal = read_calendar(url)

    rows = []
    seen = set()
    for component in cal.walk("VEVENT"):
        summary = as_text(component.get("summary"))
        if not summary:
            continue
        location = as_text(component.get("location"))
        description = clean_description(component.get("description"))

        for occ_start, occ_end in extract_occurrences(component):
            occ_start = normalize_local(occ_start)
            occ_end = normalize_local(occ_end)

            start_date = to_date(occ_start)
            end_date = to_date(occ_end)
            if start_date is None:
                continue
            key = (summary, start_date.isoformat(), end_date.isoformat() if end_date else "", location, description)
            if key in seen:
                continue
            seen.add(key)

            heure = ""
            if isinstance(occ_start, datetime):
                heure = occ_start.strftime("%H:%M")

            rows.append({
                "date_debut": start_date.isoformat(),
                "date_fin": end_date.isoformat() if end_date and end_date != start_date else "",
                "heure": heure,
                "titre": summary,
                "lieu": location,
                "details": description,
            })

    rows.sort(key=lambda r: (r["date_debut"], r["titre"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["date_debut", "date_fin", "heure", "titre", "lieu", "details"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} événements écrits dans {OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        raise
