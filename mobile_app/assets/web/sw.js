// Quik Field Notes - Offline Service Worker
const CACHE_NAME = 'quik-field-notes-v2.2';
const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './manifest.json',
  './vendor/leaflet.css',
  './vendor/leaflet.js',
  './vendor/leaflet-rotate.js',
  './vendor/jszip.min.js',
  './vendor/shp.js',
  './icon-192.png',
  './icon-512.png',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://unpkg.com/leaflet-rotate@0.2.8/dist/leaflet-rotate-src.js',
  'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js',
  'https://unpkg.com/shpjs@latest/dist/shp.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => console.log('SW cache partial:', err));
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).then((networkResponse) => {
        // Cache map tiles on the fly for offline mapping
        if (event.request.url.includes('tile') || event.request.url.includes('arcgisonline')) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      }).catch(() => {
        return cachedResponse;
      });
    })
  );
});
