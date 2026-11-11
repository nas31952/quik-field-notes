// Quik Field Notes - Offline Service Worker (v2.5.0)
const CACHE_NAME = 'quik-field-notes-v2.5.0';
const STATIC_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './favicon.ico',
  './icon-192.png',
  './icon-512.png',
  './vendor/leaflet.css',
  './vendor/leaflet.js',
  './vendor/leaflet-rotate.js',
  './vendor/jszip.min.js',
  './vendor/shp.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      // Fault-tolerant caching: cache each file without failing all on a single error
      await Promise.allSettled(
        STATIC_ASSETS.map((url) =>
          cache.add(url).catch((err) => console.warn('SW pre-cache warning for', url, err))
        )
      );
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
  const req = event.request;

  // 1. Navigation requests (visiting or refreshing the web app)
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => {
        return caches.match('./index.html').then((res) => res || caches.match('./'));
      })
    );
    return;
  }

  // 2. Static assets & map vendor libraries (Cache-First strategy)
  event.respondWith(
    caches.match(req).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(req).then((networkResponse) => {
        if (
          networkResponse &&
          networkResponse.status === 200 &&
          (req.url.includes('/vendor/') ||
            req.url.endsWith('.png') ||
            req.url.endsWith('.css') ||
            req.url.endsWith('.js') ||
            req.url.endsWith('.json'))
        ) {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, responseClone));
        }
        return networkResponse;
      }).catch(() => {
        return cachedResponse || new Response('Offline', { status: 503, statusText: 'Offline' });
      });
    })
  );
});
