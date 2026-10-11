---
name: build
description: Guide pas à pas un membre du club, débutant en développement, qui veut construire son idée dans affichage-club (l'écran du club), de l'installation des outils jusqu'à la pull request. L'agent lance lui-même toutes les commandes. À utiliser quand quelqu'un dit vouloir ajouter, changer ou proposer quelque chose sur l'écran ou dans le script des résultats.
---

# Construire une idée dans affichage-club

Tu accompagnes un membre des Archers de l'Erdre qui veut développer son idée pour l'écran du club. Il connaît peu ou
pas Git, GitHub, le terminal ni la programmation. **C'est toi qui fais tout le travail technique** : il apporte
l'idée, regarde le résultat dans son navigateur et dit ce qu'il en pense. Tu avances une étape à la fois et tu
vérifies que tout marche avant de passer à la suite.

## Règles absolues

- **Parle TOUJOURS en français** avec la personne, même si elle t'écrit en anglais, même si un outil répond en
  anglais (traduis et explique).
- **Dans ce projet, tout est en français** : noms dans le code, commentaires, textes à l'écran, messages de commit
  (voir `AGENTS.md`).
- **Toutes les commandes, c'est toi qui les lances** : installation, Git, GitHub, lancement de la page, vérifications,
  commit, pull request. Ne demande **jamais** à la personne d'ouvrir un terminal ni de taper une commande. Elle
  n'intervient que pour ce qu'une machine ne peut pas faire à sa place : se connecter à GitHub dans son navigateur,
  taper le mot de passe de son ordinateur, cliquer sur une fenêtre du système. Dans ces cas, dis-lui exactement quoi
  faire, en une ou deux phrases.
- Mots simples, phrases courtes. Raconte ce que tu fais sans jargon (« je crée une copie de travail du code, une
  branche, pour que tu puisses tout essayer sans rien casser »). Pas besoin de montrer les commandes, sauf si elle
  le demande.
- Avant une action importante qui sort de sa machine (publier sur GitHub, ouvrir la pull request), dis ce que tu vas
  faire et attends son accord.
- Lis `AGENTS.md` à la racine avant tout : il décrit le projet, son architecture et ses règles. Respecte-le.
- **La branche `main`, c'est la production** : tout ce qui arrive sur `main` s'affiche sur la télé du club quelques
  minutes après (GitHub Pages). **Ne jamais** pousser sur `main` ni fusionner une pull request : seul Jonas le fait.
  Le travail s'arrête à la pull request.
- **Ne jamais** committer les changements de `data/resultats.json` ni de `data/vus.json` faits en local : ces
  fichiers sont mis à jour par le robot GitHub. Seule exception : l'idée change justement leur format.
- **Ne jamais** committer d'environnement Python (`.venv/`), de PDF de test ni de `__pycache__/` : le dépôt n'a pas de
  `.gitignore`, donc vérifie à la main.

## Étape 1 : comprendre l'idée

Fais raconter l'idée : quel problème, pour qui (membres qui regardent l'écran, bénévoles qui remplissent les tableurs),
à quoi ça ressemblerait à l'écran.
Reformule-la en 2 ou 3 phrases et fais-la valider.

Vérifie dans `AGENTS.md` qu'elle respecte les choix du projet : pas de npm, pas de framework, pas de bibliothèque JS
externe, réglages dans `config.js`, page lisible de loin sur une télé 1920×1080. Si elle les contredit, dis-le
simplement et propose d'en parler à Jonas avant de coder.

Situe l'idée :

- **la page** (`index.html`, `config.js`) : ce qui s'affiche, l'ordre, la durée des écrans ;
- **le script des résultats** (`scraper/scrape.py`) : ce qui est lu sur le site de la FFTA et dans les PDF ;
- **les tableurs** (`modele-tableur/`) : les colonnes des événements et des indisponibilités.

Si l'idée est grosse, découpe-la en petits morceaux, chacun utile tout seul. On commence par le plus petit.

## Étape 2 : préparer la machine

Vérifie toi-même chaque outil et installe ce qui manque. Dis en une phrase à quoi il sert.

| Outil | Pourquoi | Vérifier | Installer si absent |
|---|---|---|---|
| Git | garder l'historique du code | `git --version` | macOS : `xcode-select --install` (une fenêtre s'ouvre : dis-lui de cliquer sur « Installer ») ; Linux : paquet `git` ; Windows : WSL conseillé |
| Python 3 (3.12 conseillé) | montrer la page en local, lancer le script des résultats | `python3 --version` | macOS : `brew install python@3.12` si Homebrew est là, sinon python.org ; Linux : paquet `python3` |
| GitHub CLI (`gh`) | parler à GitHub | `gh --version` | `brew install gh` si Homebrew est là, sinon le paquet de cli.github.com |
| Compte GitHub connecté | proposer son travail | `gh auth status` | voir ci-dessous |

- **Connexion GitHub** : si elle n'a pas de compte, dis-lui d'en créer un sur github.com et de revenir. Puis lance
  `gh auth login --hostname github.com --git-protocol https --web` : un code à usage unique s'affiche et le navigateur
  s'ouvre. Donne-lui le code et dis-lui de le coller dans la page, puis de valider. Vérifie avec `gh auth status`.
- **Identité Git** : si `git config --global user.name` ou `user.email` est vide, demande-lui son prénom, son nom et
  l'e-mail de son compte GitHub, et règle-les toi-même (`git config --global …`).
- Si une installation demande le mot de passe de l'ordinateur (`sudo`), dis-lui que c'est normal et qu'elle doit le
  taper quand il est demandé (rien ne s'affiche pendant la frappe).
- Les bibliothèques Python (`scraper/requirements.txt`) ne servent que si l'idée touche au script des résultats :
  installe-les à l'étape 5 seulement dans ce cas.

## Étape 3 : récupérer le code

Le dépôt est `archersdelerdre/affichage-club`. La personne n'a sûrement pas le droit d'y écrire directement : elle
travaille sur **sa copie sur GitHub** (un « fork ») et propose ses changements par pull request.

1. Si le projet n'est pas encore sur sa machine : `gh repo fork archersdelerdre/affichage-club --clone` dans un
   dossier simple (par exemple son dossier personnel), puis travaille dans `affichage-club`. `gh` crée sa copie,
   la télécharge, et relie le dépôt du club sous le nom `upstream`.
2. Si le projet est déjà là : vérifie `git remote -v`. Il faut `origin` (sa copie) et `upstream` (le dépôt du club).
   Si `upstream` manque : `git remote add upstream https://github.com/archersdelerdre/affichage-club.git`. Si `origin`
   est déjà `archersdelerdre/affichage-club` et qu'elle peut y écrire
   (`gh repo view archersdelerdre/affichage-club --json viewerPermission` rend `WRITE`, `MAINTAIN` ou `ADMIN`), il n'y
   a pas de fork : dans la suite, `upstream` désigne `origin`. Dans ce cas, redouble d'attention : elle peut pousser
   sur `main`, et `main` part directement sur la télé du club.
3. `git fetch upstream`.

Dans la suite, **la base** est la branche principale du club : `upstream/main` (ou `origin/main` sans fork). Vérifie
son nom avec `git remote show upstream` (ligne « HEAD branch ») et utilise-le partout.

Le robot GitHub peut ajouter des commits « Résultats mis à jour » sur `main` quand on le lance à la main : c'est normal.

## Étape 4 : une branche neuve pour chaque idée

Fais-le **à chaque lancement du skill**, même si la personne est déjà sur une branche : une nouvelle idée part
toujours d'une branche neuve, basée sur la base à jour.

1. `git fetch upstream`.
2. Si `git status --porcelain` montre des changements non enregistrés sur la branche actuelle, ne les perds pas :
   enregistre-les sur cette branche (`git add -A` puis `git commit -m "Travail en cours"`), en vérifiant d'abord qu'il
   n'y a ni `.venv/`, ni PDF, ni `__pycache__/`, ni changement de `data/` fait en local. Dis-lui que son travail
   précédent est gardé sur son ancienne branche.
3. Choisis un nom court, sans accent, d'après ce qu'elle veut faire : `feature/ecran-meteo`. S'il existe déjà, ajoute
   `-2`.
4. `git switch -c feature/<nom> upstream/main` (avec le nom réel de la base).

Explique-lui en une phrase : « J'ai créé une copie de travail toute neuve pour ton idée, à partir de la dernière
version du club. »

## Étape 5 : des données pour essayer

- **Résultats** : `data/resultats.json` contient déjà des résultats d'exemple ou les vrais résultats récents. Rien à
  faire.
- **Événements et indisponibilités** : sans lien de tableur dans `config.js`, ces écrans sont cachés. Pour les voir en
  local, mets **temporairement** dans `config.js` :
  `SHEET_EVENEMENTS_CSV: "modele-tableur/evenements.csv"` et
  `SHEET_INDISPOS_CSV: "modele-tableur/indisponibilites.csv"`. Si les dates de ces fichiers sont passées (les
  événements passés sont cachés, les indisponibilités ne s'affichent que 45 jours avant), copie-les dans un fichier
  hors du dépôt, avec des dates proches d'aujourd'hui, et pointe vers lui via un chemin servi par le serveur local.
  **Remets `config.js` comme avant avant le commit**, sauf si l'idée change justement ces réglages.
- **Script des résultats** (seulement si l'idée le touche) : crée un environnement Python **hors du dépôt** et
  installe les bibliothèques :

  ```bash
  python3 -m venv ~/.venvs/affichage-club
  ~/.venvs/affichage-club/bin/pip install -r scraper/requirements.txt
  ```

  Pour essayer, il faut un PDF « Classement Officiel » de la FFTA : demande-lui un lien vers un concours récent, ou
  télécharge-en un toi-même depuis ffta.fr/competitions, et range-le **hors du dépôt**. Puis :
  `~/.venvs/affichage-club/bin/python scraper/scrape.py --pdf <chemin du PDF>` affiche le résultat sans rien écrire.
  Lancer le script sans `--pdf` interroge le site de la FFTA et réécrit `data/` : à éviter, sauf besoin réel.

## Étape 6 : lancer la page

Lance toi-même, à la racine du projet, `python3 -m http.server 8000`, **en arrière-plan** (c'est un programme qui
tourne en continu : ne bloque pas la conversation). Vérifie que `http://localhost:8000` répond, puis ouvre-le dans
son navigateur (`open http://localhost:8000` sur macOS, `xdg-open` sous Linux). Dis-lui : « L'écran du club tourne,
il vient de s'ouvrir dans ton navigateur. »

- Ouvrir `index.html` en double-cliquant dessus ne marche pas : le navigateur bloque la lecture des données. Il faut
  passer par le serveur local.
- Les écrans défilent tout seuls ; les flèches gauche et droite du clavier, ou un clic, changent d'écran.
- Après un changement de code, dis-lui de recharger la page (Cmd+R ou F5).
- Pour voir la page comme sur la télé, mets la fenêtre en plein écran, ou utilise la vue responsive du navigateur
  en 1920×1080.
- « Port déjà utilisé » (`Address already in use`) : regarde qui l'occupe (`lsof -i :8000`). Si c'est un ancien
  serveur de la page, arrête-le ; sinon, prends un autre port (`python3 -m http.server 8001`).
- Page blanche ou erreur : regarde la console du navigateur (demande-lui une capture si besoin) et la sortie du
  serveur. Une erreur dans `data/resultats.json` suffit à vider l'écran. Corrige, puis explique simplement ce qui
  n'allait pas.
- À la fin de la session, arrête le serveur toi-même.

Vérifie avec elle qu'elle voit bien défiler les écrans avant de continuer.

## Étape 7 : construire

- Dis où tu vas changer quelque chose, en mots simples (`index.html` = la page et son style, `config.js` = les
  réglages, `scraper/scrape.py` = le script qui lit les PDF de la FFTA ; détails dans `AGENTS.md`).
- Avance par petits pas. Après chaque pas, demande-lui de recharger la page et de dire si c'est ce qu'elle voulait.
- Suis les règles d'`AGENTS.md` :
  - tout texte mis dans la page passe par `esc()` ;
  - un nouveau réglage va dans `config.js`, avec sa valeur par défaut recopiée dans `CFG` ;
  - garde le style existant (noms en français, couleurs `--or`, `--rouge`, polices Barlow) ;
  - le texte doit rester lisible de loin sur une télé.
- Si l'idée change le format de `data/resultats.json`, change le script et la page ensemble.
- Si l'idée ajoute une colonne aux tableurs, mets à jour `modele-tableur/*.csv` et le `README.md`.
- Explique chaque changement en une ou deux phrases. Si elle veut écrire du code elle-même, laisse-la faire et
  aide-la.

## Étape 8 : vérifier

Il n'y a pas de tests automatiques : tout se vérifie à la main, par toi puis par elle.

1. Si `scraper/scrape.py` a changé : `python3 -m py_compile scraper/scrape.py`, puis relance
   `scrape.py --pdf <PDF>` et compare le résultat à ce qui est attendu.
2. Recharge la page et fais défiler **tous** les écrans : récapitulatif, ouverture de chaque concours, classements
   longs coupés sur plusieurs écrans, indisponibilités, événements.
3. Vérifie aussi l'écran vide : mets temporairement `ORDRE: []` dans `config.js`, recharge, puis remets la valeur.
4. Vérifie la vue téléphone (fenêtre étroite) : un seul écran par colonne, défilement possible.
5. La console du navigateur ne doit montrer aucune erreur.

Corrige ce qui ne va pas et recommence. Dis-lui seulement le résultat (« tout marche ») ou ce que tu as dû corriger.
Puis demande-lui un dernier essai complet dans son navigateur.

## Étape 9 : enregistrer (commit)

Remets d'abord `config.js` comme avant si tu l'as changé seulement pour essayer (étapes 5 et 8). Puis relis toi-même
les changements (`git status`, `git diff`). Vérifie qu'il n'y a ni `.venv/`, ni PDF, ni `__pycache__/`, ni changement
de `data/resultats.json` ou `data/vus.json` fait en local. Ajoute les fichiers un par un (`git add <fichier>`), pas
avec `git add -A`.

Message de commit **en français**, court : une ligne de titre, puis une ou deux lignes au plus. Jamais de ligne
`Co-Authored-By`. Lis-lui le message.

## Étape 10 : proposer (pull request)

Demande-lui son accord, puis :

```bash
git push -u origin feature/<nom>
gh pr create --repo archersdelerdre/affichage-club --base main --title "<titre>" --body "<description>"
```

Écris la description **en français**, pour Jonas :

```markdown
## L'idée
Pourquoi ce changement, pour qui.

## Ce qui change
- …

## Comment l'essayer
1. …

## Captures
```

Si elle a fait des captures d'écran, dis-lui de les glisser dans la pull request sur GitHub (donne-lui le lien). Puis
explique : Jonas va relire et peut demander des changements. Quand elle revient avec ses remarques, fais les
changements sur la même branche, refais les étapes 8 et 9, puis `git push` : la pull request se met à jour toute
seule. Quand Jonas fusionne, le changement arrive sur la télé du club tout seul.

## Pour l'idée suivante

Relancer le skill : l'étape 4 crée automatiquement une nouvelle branche à partir de la dernière version du club.
