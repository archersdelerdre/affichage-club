/* Réglages de l'écran. Modifier ici, pas dans index.html. */
window.CONFIG = {
  CLUB_NOM: "Archers de l'Erdre",
  CLUB_LABEL: "Archers de l'Erdre, résultats du week-end",
  DUREE_SECONDES: 5,          // durée d'un écran
  RECHARGE_MINUTES: 15,        // la page relit les données toutes les 15 minutes

  NB_WEEKENDS: 3,              // les 3 derniers week-ends qui ont des résultats (liste des concours + podiums)
  MAX_JOURS: 45,               // on n'affiche pas de résultats plus vieux que 45 jours
  DETAIL_WEEKENDS: 3,          // détail archer par archer pour les N week-ends les plus récents

  /* Liens CSV de Google Sheets (Fichier > Partager > Publier sur le Web > un onglet > CSV).
     Laisser vide pour ne pas afficher la page correspondante. */
  SHEET_EVENEMENTS_CSV: "",
  SHEET_INDISPOS_CSV: "",

  /* Ordre des pages. Retirer un mot pour masquer cette page. */
  ORDRE: ["resultats", "indispos", "evenements"]
};
