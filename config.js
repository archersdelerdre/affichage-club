/* Réglages de l'écran. Modifier ici, pas dans index.html. */
window.CONFIG = {
  CLUB_NOM: "Archers de l'Erdre",
  CLUB_LABEL: "Archers de l'Erdre, résultats du week-end",
  DUREE_SECONDES: 14,          // durée d'un écran
  RECHARGE_MINUTES: 15,        // la page relit les données toutes les 15 minutes

  NB_WEEKENDS: 3,              // les 3 derniers week-end qui ont des résultats (une page par concours)
  ARCHERS_PAR_PAGE: 24,        // au-delà de 24 archers du club, un concours passe sur 2 pages
  MAX_JOURS: 45,               // on n'affiche pas de résultats plus vieux que 45 jours
  EVENEMENTS_HORIZON_JOURS: 10, // on affiche les événements du jour jusqu'à 10 jours à venir

  /* Liens CSV de Google Sheets (Fichier > Partager > Publier sur le Web > un onglet > CSV).
     On accepte aussi un fichier .ics / URL iCal publique. */
  SHEET_EVENEMENTS_CSV: "data/evenements.csv",
  SHEET_INDISPOS_CSV: "",

  /* Ordre des pages. Retirer un mot pour masquer cette page. */
  ORDRE: ["resultats", "evenements"]
};
/* Logo du club en filigrane */
(function () {
  var s = document.createElement("style");
  s.textContent =
    'body::before{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;' +
    'background:url("logo-fond.png") center / auto 88% no-repeat;opacity:.15}' +
    '#scene{z-index:1}';
  document.head.appendChild(s);
})();
