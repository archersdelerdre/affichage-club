/* Service worker de l'application du club : permet l'installation et le fonctionnement hors connexion.
   Stratégie : on va toujours chercher la version en ligne ; si le réseau est coupé, on utilise la dernière copie gardée. */
const CACHE = "club-v1";
const A_GARDER = ["./telephone.html", "./config.js", "./manifest.json", "./logo-fond.png", "./icone-192.png",
  "./data/resultats.json", "./data/evenements.csv", "./data/infos.csv"];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => Promise.all(A_GARDER.map(u => c.add(u).catch(() => {}))))   /* un fichier absent n'empêche pas l'installation */
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(noms => Promise.all(noms.filter(n => n !== CACHE).map(n => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;                 /* polices Google, etc. : le navigateur s'en occupe */
  const cle = url.origin + url.pathname;                      /* on ignore « ?t=... » pour ne pas remplir le cache */
  e.respondWith(
    fetch(req)
      .then(rep => {
        if (rep && rep.ok) { const copie = rep.clone(); caches.open(CACHE).then(c => c.put(cle, copie)); }
        return rep;
      })
      .catch(() => caches.match(cle).then(r => r || caches.match("./telephone.html")))
  );
});
