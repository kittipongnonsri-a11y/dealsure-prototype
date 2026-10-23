/* DealSure service worker v15 – network-first สำหรับหน้า, ไม่แคช API (ข้อมูลดีล/เงินต้องสดเสมอ) */
const C = 'dealsure-v15.1';
const SHELL = ['/', '/app', '/static/app.css?v=15.1', '/static/app.js?v=15.1', '/static/icons/icon-192.png', '/manifest.json'];
self.addEventListener('install', e => { e.waitUntil(caches.open(C).then(c => c.addAll(SHELL)).catch(() => {})); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/') || u.pathname.startsWith('/uploads/')) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok && (u.pathname.startsWith('/static/') || e.request.mode === 'navigate')) { const cp = r.clone(); caches.open(C).then(c => c.put(e.request, cp)); }
    return r;
  }).catch(() => caches.match(e.request).then(r => r || (e.request.mode === 'navigate' ? caches.match('/app') : Response.error()))));
});
