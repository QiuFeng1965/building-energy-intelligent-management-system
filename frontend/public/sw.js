// ============================================================
// 擎翼数字中枢 - Service Worker
// 支持：Web Push 推送通知 + 基础离线缓存
// ============================================================

const CACHE_NAME = 'nova-energy-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/favicon.svg',
];

// ===== 安装：预缓存静态资源 =====
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => {}))
  );
  self.skipWaiting();
});

// ===== 激活：清理旧缓存 =====
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
    ))
  );
  self.clients.claim();
});

// ===== Push 事件：接收服务端推送 =====
self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (e) {
    payload = { title: '擎翼数字中枢', body: event.data ? event.data.text() : '新消息' };
  }

  const title = payload.title || '擎翼数字中枢告警';
  const options = {
    body: payload.body || payload.message || '收到新通知',
    icon: '/favicon.svg',
    badge: '/favicon.svg',
    tag: payload.tag || 'nova-alert',
    renotify: payload.renotify || true,
    data: payload.data || payload.url || '/',
    requireInteraction: payload.level === 'critical',
    actions: [
      { action: 'view', title: '查看详情' },
      { action: 'dismiss', title: '忽略' }
    ]
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// ===== 通知点击：跳转到相关页面 =====
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const targetUrl = event.notification.data?.url || event.notification.data || '/advanced/ops';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      // 优先复用已打开的窗口
      for (const client of clients) {
        if (client.url.includes(self.location.origin)) {
          client.navigate(targetUrl);
          client.focus();
          return;
        }
      }
      // 没有则打开新窗口
      return self.clients.openWindow(targetUrl);
    })
  );
});

// ===== Fetch 事件：离线缓存策略 =====
self.addEventListener('fetch', (event) => {
  // API 请求不缓存（实时数据）
  if (event.request.url.includes('/api/')) return;
  // WebSocket 不处理
  if (event.request.url.includes('/ws')) return;

  // 静态资源：缓存优先
  if (event.request.method === 'GET') {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        return cached || fetch(event.request).then((response) => {
          // 缓存新的静态资源
          if (response.status === 200 && response.type === 'basic') {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
          }
          return response;
        }).catch(() => cached);
      })
    );
  }
});
