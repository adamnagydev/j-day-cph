const VERSION = "jday-6";
const SHELL = [
  "./",
  "./index.html",
  "./styles.css",
  "./styles.css?v=6",
  "./app.js",
  "./app.js?v=6",
  "./data/pubs.json",
  "./data/pubs.json?v=6",
  "./data/metro.json",
  "./data/metro.json?v=6",
  "./favicon.svg",
  "./vendor/leaflet/leaflet.css",
  "./vendor/leaflet/leaflet.js",
  "./vendor/leaflet.markercluster.js",
  "./vendor/MarkerCluster.css",
  "./vendor/MarkerCluster.Default.css",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== VERSION && key !== "jday-tiles").map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  if (url.hostname.includes("arcgisonline.com")) {
    event.respondWith(cacheTile(event.request));
    return;
  }
  if (url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(VERSION).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match("./index.html")))
  );
});

async function cacheTile(request) {
  const cache = await caches.open("jday-tiles");
  const hit = await cache.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}
