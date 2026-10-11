# Écran du club : résultats du week-end, agenda et indisponibilités

Une page web plein écran qui défile toute seule :

1. **Résultats** des archers du club (lus automatiquement dans les PDF de la FFTA) : la liste des concours avec le nombre d'archers et de podiums, puis le détail de chaque concours
2. **Indisponible** : salle ou terrain fermé (tableur rempli par les admins)
3. **À venir** : événements du club (tableur rempli par les admins)

```
index.html          la page d'affichage (ne pas toucher)
config.js           réglages : nom du club, durée des écrans, liens des tableurs
data/resultats.json les résultats (écrit tout seul par le script)
data/corrections.json  noms à corriger à la main (accents manquants dans les PDF)
scraper/scrape.py   lit la FFTA et écrit data/resultats.json
.github/workflows/  lance le script (à la main pour l'instant)
modele-tableur/     modèles à importer dans Google Sheets
```

Le fichier `data/resultats.json` fourni contient un exemple (Concours salle Carquefou, janvier 2026) pour voir le rendu. Il sera remplacé au premier passage du script.

## 1. Mettre en ligne (une seule fois)

1. Créer un dépôt GitHub (par exemple `affichage-club`) et y déposer tous ces fichiers.
2. **Settings > Pages** : Source = « Deploy from a branch », branche `main`, dossier `/ (root)`. L'adresse sera `https://VOTRE-NOM.github.io/affichage-club/`.
3. **Settings > Actions > General > Workflow permissions** : choisir « Read and write permissions ».
4. **Actions > Résultats FFTA > Run workflow** pour lancer un passage à la main. Le lancement automatique est coupé pour l'instant.

Pour changer de club, modifier `CLUBS: "CARQUEFOU"` dans `.github/workflows/resultats.yml` (le nom tel qu'il apparaît dans la colonne Club des PDF).

## 2. Le tableur des admins

1. Créer un Google Sheet avec deux onglets, en important `modele-tableur/evenements.csv` et `modele-tableur/indisponibilites.csv` (Fichier > Importer). Ne pas changer les titres des colonnes.
2. Pour chaque onglet : **Fichier > Partager > Publier sur le Web**, choisir l'onglet, format **CSV**, Publier. Copier le lien.
3. Coller les liens dans `config.js` (`SHEET_EVENEMENTS_CSV` et `SHEET_INDISPOS_CSV`).
4. Partager le tableur en modification avec les admins du club.

Colonnes : dates au format `2026-10-24` ou `24/10/2026`. `date_fin` est facultative.
Les lignes passées disparaissent toutes seules de l'écran. Une indisponibilité s'affiche à partir de 45 jours avant son début. La page relit le tableau toutes les 15 minutes.

## 3. Le Raspberry Pi

Un Pi 4 ou Pi 5 (2 Go ou plus) convient. Avec Raspberry Pi OS (Bookworm) :

1. Écran : `sudo raspi-config` > Display Options > Screen Blanking > No.
2. Créer `~/.config/labwc/autostart` avec cette ligne (en mettant la vraie adresse) :

```
chromium-browser --kiosk --noerrdialogs --disable-infobars https://VOTRE-NOM.github.io/affichage-club/ &
```

3. Redémarrer. La page s'ouvre en plein écran et se met à jour seule. Pour quitter le mode plein écran : Alt+F4.

## 4. Tester sans rien installer

- Le script sur un PDF : `pip install -r scraper/requirements.txt` puis `python scraper/scrape.py --pdf resultats.pdf`
- La page en local : `python -m http.server` dans le dossier, puis ouvrir `http://localhost:8000`. Ouvrir `index.html` directement ne marche pas (le navigateur bloque la lecture des données).
- Touches flèches gauche et droite pour changer d'écran.

## Ce qu'il faut savoir

- **Rangs recalculés** : les rangs imprimés dans les PDF ont des trous et des erreurs quand un archer tire deux fois. Le script reclasse tous les archers de la catégorie (score, puis nombre de 10, puis de 9). Les 2es et 3es tirs ("Autres tirs") sont ignorés : le classement général fait foi.
- **Formats gérés** : PDF « Classement Officiel » avec colonnes de scores par manche (tir à 18 m, tir extérieur). Les PDF de tir en campagne, 3D ou nature ont un autre format : ils sont lus mais risquent de ne rien donner. À adapter quand on aura un exemple.
- **Accents** : les PDF abîment certains accents ou en oublient. Ajouter les cas dans `data/corrections.json` (`"Angele CHALET": "Angèle CHALET"`).
- **Non testé en vrai** : le script a été testé sur un PDF réel, mais pas sur le site de la FFTA lui-même. Au premier lancement, regarder les journaux dans l'onglet Actions : ils indiquent combien de PDF ont été trouvés.
