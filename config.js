/* Réglages de l'écran. Modifier ici, pas dans index.html. */
window.CONFIG = {
  CLUB_NOM: "Archers de l'Erdre",
  CLUB_LABEL: "Archers de l'Erdre, résultats du week-end",
  DUREE_SECONDES: 14,          // durée d'un écran
  RECHARGE_MINUTES: 15,        // la page relit les données toutes les 15 minutes

  /* Liens CSV de Google Sheets (Fichier > Partager > Publier sur le Web > un onglet > CSV).
     Laisser vide pour ne pas afficher la page correspondante. */
  SHEET_EVENEMENTS_CSV: "",
  SHEET_INDISPOS_CSV: "",

  /* Ordre des pages. Retirer un mot pour masquer cette page. */
  ORDRE: ["resultats", "indispos", "evenements"]
};
