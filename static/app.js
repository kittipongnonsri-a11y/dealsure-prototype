'use strict';
/* ดีลชัวร์ (DealSure) prototype – single-page app (no build step) */
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => { const v = Math.round((+n || 0) * 100) / 100; return v.toLocaleString('en-US', {minimumFractionDigits: v % 1 ? 2 : 0, maximumFractionDigits: 2}); };
const baht = n => fmt(n) + ' ฿';
const TZ = 'Asia/Bangkok';
const dShort = ts => new Intl.DateTimeFormat('th-TH', {weekday:'short', day:'numeric', month:'short', year:'numeric', timeZone:TZ}).format(new Date(ts * 1000));
const dTime = ts => new Intl.DateTimeFormat('th-TH', {day:'numeric', month:'short', hour:'2-digit', minute:'2-digit', timeZone:TZ}).format(new Date(ts * 1000));
const dFull = ts => new Intl.DateTimeFormat('th-TH', {day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit', timeZone:TZ}).format(new Date(ts * 1000));
const dDate = s => { const [y, m, d] = s.split('-').map(Number); return dShort(Date.UTC(y, m - 1, d, 5) / 1000); };
const ic = (id, s = 16, st = '') => `<svg width="${s}" height="${s}"${st ? ` style="${st}"` : ''}><use href="#${id}"/></svg>`;
const todayStr = (plusDays = 0) => new Intl.DateTimeFormat('en-CA', {timeZone: TZ}).format(new Date(Date.now() + plusDays * 864e5));
const ACTIVE = ['open', 'accepted', 'held', 'shipped', 'delivered', 'disputed'];
const DLV = {parcel: ['📦', 'ส่งพัสดุ', 'box'], meet: ['🤝', 'นัดรับด้วยตัวเอง', 'hand'], messenger: ['🛵', 'ส่งแมสเซนเจอร์', 'bike']};
const dlvLabel = k => DLV[k][0] + ' ' + DLV[k][1];
const FEEP = {buyer: 'ผู้ซื้อจ่าย', seller: 'ผู้ขายจ่าย', half: 'คนละครึ่ง'};
const hello = n => /^(คุณ|น้อง|พี่|ป้า|ลุง)/.test(n) ? n : 'คุณ' + n;
const S = {me: null, unread: 0, notifs: [], deal: null, offset: 0, after: null, F: null};

function since(ts) {
  const days = Math.max(0, (Date.now() / 1000 - ts) / 86400);
  if (days < 1) return 'วันนี้';
  if (days < 30) return Math.floor(days) + ' วัน';
  const mo = Math.floor(days / 30.4);
  if (mo < 12) return mo + ' เดือน';
  const y = Math.floor(mo / 12), m = mo % 12;
  return y + ' ปี' + (m ? ' ' + m + ' เดือน' : '');
}
function ago(ts) {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return 'เมื่อสักครู่';
  if (s < 3600) return Math.floor(s / 60) + ' นาทีที่แล้ว';
  if (s < 86400) return Math.floor(s / 3600) + ' ชม.ที่แล้ว';
  return dTime(ts);
}
function dur(sec) {
  sec = Math.max(0, Math.floor(sec));
  const d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  const p = n => String(n).padStart(2, '0');
  return (d ? d + ' วัน ' : '') + `${p(h)}:${p(m)}:${p(s)}`;
}
function durShort(sec) {
  sec = Math.max(0, sec); const d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60);
  return d ? `${d} วัน ${h} ชม.` : h ? `${h} ชม. ${m} นาที` : `${m} นาที`;
}
const stars = (r, size = 14) => { const n = Math.round(r || 0); return `<span class="stars" style="font-size:${size}px">${'★'.repeat(n)}<span style="color:#DCEDE7">${'★'.repeat(5 - n)}</span></span>`; };

async function api(path, body) {
  const opt = body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)};
  let r, j;
  try { r = await fetch('/api' + path, opt); } catch (e) { throw new Error('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ ลองใหม่อีกครั้ง'); }
  try { j = await r.json(); } catch (e) { j = {error: 'เซิร์ฟเวอร์ตอบกลับผิดปกติ'}; }
  if (!r.ok) { const e = new Error(j.error || 'เกิดข้อผิดพลาด'); e.status = r.status; throw e; }
  return j;
}
function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('show'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('show'), 2600); }
function openSheet(html) { $('#sheetBody').innerHTML = '<div class="grab"></div>' + html; $('#sheet').classList.add('open'); }
function closeSheet() { $('#sheet').classList.remove('open'); }
const sheetOpen = () => $('#sheet').classList.contains('open');
async function busy(btn, fn) {
  if (btn) { if (btn.disabled) return; btn.disabled = true; }
  try { await fn(); } catch (e) { handleErr(e); } finally { if (btn && document.body.contains(btn)) btn.disabled = false; }
}
function handleErr(e) {
  if (e.status === 401) { S.after = location.hash; closeSheet(); location.hash = '#/login'; toast('กรุณาเข้าสู่ระบบก่อน'); return; }
  if (/ยืนยันตัวตน/.test(e.message) && S.me && !S.me.verified) { idSheet(e.message); return; }
  toast(e.message);
}
function copyText(t, msg = 'คัดลอกแล้ว ✓') {
  const done = () => toast(msg);
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(done, () => fallbackCopy(t, done));
  else fallbackCopy(t, done);
}
function fallbackCopy(t, done) {
  const a = document.createElement('textarea'); a.value = t; a.style.position = 'fixed'; a.style.opacity = '0';
  document.body.appendChild(a); a.select(); try { document.execCommand('copy'); done(); } catch (e) { prompt('คัดลอกข้อความนี้', t); } a.remove();
}
function pickFiles(accept, multiple, cb) {
  const old = $('#filePick'), inp = old.cloneNode(); old.replaceWith(inp);
  inp.accept = accept; inp.multiple = multiple; inp.value = '';
  inp.onchange = () => cb([...inp.files]);
  inp.click();
}
function resizeImage(file, max = 1280) {
  return new Promise((res, rej) => {
    if (!file.type.startsWith('image/')) return rej(new Error('กรุณาเลือกไฟล์รูปภาพ'));
    const url = URL.createObjectURL(file), img = new Image();
    img.onload = () => {
      const k = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement('canvas'); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url);
      res(c.toDataURL('image/jpeg', 0.82));
    };
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('เปิดรูปนี้ไม่ได้ ลองรูปอื่น')); };
    img.src = url;
  });
}
const readDataUrl = f => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(f); });

/* ---------------- shared UI pieces ---------------- */
function bellBtn() {
  return `<button class="icon-btn" aria-label="การแจ้งเตือน" onclick="toggleNotif()">${ic('bell', 22)}${S.unread ? `<span class="dot">${S.unread > 9 ? '9+' : S.unread}</span>` : ''}</button>`;
}
function header({title = '', sub = '', back = false, hero = '', right = null}) {
  const lg = back ? 28 : 32;
  return `<div class="top"${hero ? ' style="padding-bottom:16px"' : ''}><div class="row">
    ${back ? `<button class="icon-btn" aria-label="ย้อนกลับ" onclick="goBack()">${ic('back', 20)}</button>` : ''}
    <div class="brand"${back ? ' style="font-size:15px"' : ''}><svg class="lg" width="${lg}" height="${lg}" role="img" aria-label="โลโก้ดีลชัวร์"><use href="#logoA"/></svg>ดีลชัวร์</div>
    ${right !== null ? right : S.me ? bellBtn() : `<a class="icon-btn" href="#/login" aria-label="เข้าสู่ระบบ">${ic('user', 20)}</a>`}
  </div>${title ? `<h1>${title}</h1>` : ''}${sub ? `<p class="sub">${sub}</p>` : ''}${hero}</div>`;
}
function hero(icon, color, line1, line2, badge = '') {
  return `<div class="status-hero"><svg width="30" height="30" style="color:${color}!important;flex:none"><use href="#${icon}"/></svg>
    <div style="flex:1;min-width:0"><div class="small muted">${line1}</div><div class="timer" style="font-size:18px">${line2}</div></div>${badge}</div>`;
}
function avatar(u, size = '', check = true) {
  return `<div class="avatar ${size}">${esc(u.initial)}${u.verified && check ? `<span class="v">${ic('check', 12, 'color:#fff')}</span>` : ''}</div>`;
}
function levelBadge(st) {
  if (st.level === 'gold') return '<span class="badge b-gold">★ ร้านทอง</span>';
  if (st.level === 'silver') return '<span class="badge b-silver">☆ ร้านเงิน</span>';
  return '<span class="badge b-silver">ร้านใหม่</span>';
}
const verBadge = u => u.verified ? `<span class="badge b-green">${ic('shield', 12)}ยืนยันตัวตนแล้ว</span>` : '<span class="badge b-silver">ยังไม่ยืนยันตัวตน</span>';
const demoTag = u => u.is_demo ? ' <span class="demo">ตัวอย่าง</span>' : '';
function stLabel(st, role) {
  const m = {
    open: ['รออีกฝ่ายกดรับ', 'sp-wait'], accepted: [role === 'buyer' ? 'รอคุณจ่ายเงิน' : 'รอผู้ซื้อจ่าย', 'sp-wait'],
    held: [role === 'seller' ? 'เงินพักไว้ · รอคุณส่ง' : 'เงินพักไว้ · รอส่งของ', 'sp-held'], shipped: ['กำลังจัดส่ง', 'sp-held'],
    delivered: [role === 'buyer' ? 'รอคุณยืนยันรับของ' : 'ของถึงแล้ว · รอยืนยัน', 'sp-wait'], disputed: ['กำลังตรวจสอบปัญหา', 'sp-red'],
    completed: ['สำเร็จ', 'sp-done'], refunded: ['คืนเงินแล้ว', 'sp-gray'], partial: ['คืนเงินบางส่วน', 'sp-gray'], cancelled: ['ยกเลิกแล้ว', 'sp-gray']};
  const [t, c] = m[st] || [st, 'sp-gray'];
  return `<span class="spill ${c}">${t}</span>`;
}
function thumb(photo, cls = 'thumb') {
  return photo ? `<div class="${cls} img" style="background-image:url('${esc(photo)}')"></div>` : `<div class="${cls}" style="background:#EAF6F2;display:grid;place-items:center;color:var(--tq-d)">${ic('box', 26)}</div>`;
}
function fakeQr(size, cells, seedStr) {
  let seed = [...String(seedStr)].reduce((a, c) => a + c.charCodeAt(0), 42) % 233280;
  const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280, c = size / cells; let s = '';
  const finder = (x, y) => `<rect x="${x*c}" y="${y*c}" width="${7*c}" height="${7*c}" fill="#134E4A"/><rect x="${(x+1)*c}" y="${(y+1)*c}" width="${5*c}" height="${5*c}" fill="#fff"/><rect x="${(x+2)*c}" y="${(y+2)*c}" width="${3*c}" height="${3*c}" fill="#134E4A"/>`;
  for (let y = 0; y < cells; y++) for (let x = 0; x < cells; x++) {
    if ((x < 8 && y < 8) || (x >= cells - 8 && y < 8) || (x < 8 && y >= cells - 8)) continue;
    if (rnd() > .52) s += `<rect x="${x*c}" y="${y*c}" width="${c+.3}" height="${c+.3}" fill="#134E4A"/>`;
  }
  s += finder(0, 0) + finder(cells - 7, 0) + finder(0, cells - 7);
  const m = size / 2; s += `<rect x="${m-20}" y="${m-20}" width="40" height="40" rx="10" fill="#fff"/><use href="#logoA" x="${m-16}" y="${m-16}" width="32" height="32"/>`;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="QR จำลอง">${s}</svg>`;
}
function calcFee(price, payer) {
  const fee = price > 0 ? Math.max(20, Math.round(price * 2) / 100) : 0;
  let b = 0, s = 0; if (payer === 'buyer') b = fee; else if (payer === 'seller') s = fee; else { b = Math.round(fee / 2 * 100) / 100; s = Math.round((fee - b) * 100) / 100; }
  return {fee, b, s, buyer: price + b, seller: price - s};
}
const noteHtml = (kind, html) => {
  const icon = kind === 'warn' || kind === 'err' ? 'warn' : 'info';
  const col = kind === 'warn' ? 'var(--amber)' : kind === 'err' ? 'var(--red)' : 'var(--tq-d)';
  return `<div class="note ${kind}">${ic(icon, 16, 'color:' + col)}<div>${html}</div></div>`;
};

/* ---------------- router ---------------- */
function route() { const h = location.hash.replace(/^#\/?/, ''); const [p, a] = h.split('/'); return {p: p || 'home', a: a ? decodeURIComponent(a) : ''}; }
let navDepth = 0;
function goBack() { if (navDepth > 0) history.back(); else location.hash = '#/'; }
const PUBLIC = ['login', 'd', 'shop', 'u'];
async function render() {
  const {p, a} = route();
  closeSheet(); toggleNotif(false); S.deal = null;
  if (!S.me && !PUBLIC.includes(p)) { S.after = location.hash; location.hash = '#/login'; return; }
  const tabs = {home: 'home', create: 'create', myshop: 'shop', me: 'me'};
  $('#tabbar').classList.toggle('hidden', !S.me || p === 'login');
  $('#app').classList.toggle('notabs', !S.me || p === 'login');
  $$('.tab').forEach(t => t.classList.toggle('on', t.dataset.t === (tabs[p] || (p === 'shop' && S.me && a == S.me.id ? 'shop' : ''))));
  const v = $('#view');
  try {
    if (p === 'login') vLogin();
    else if (p === 'home') await vHome();
    else if (p === 'create') vCreate();
    else if (p === 'd') await vDeal(a);
    else if (p === 'shop') await vShop(a);
    else if (p === 'myshop') { location.replace('#/shop/' + S.me.id); return; }
    else if (p === 'u') await vUser(a);
    else if (p === 'me') await vMe();
    else location.hash = '#/';
  } catch (e) {
    v.innerHTML = header({title: 'ขออภัย', back: true}) + `<div class="wrap"><div class="card">${noteHtml('err', esc(e.message))}<a class="btn ghost" href="#/">กลับหน้าหลัก</a></div></div>`;
  }
  window.scrollTo(0, 0);
}
async function loadMe() {
  const r = await api('/me'); S.me = r.user; S.unread = r.user ? r.user.unread : 0; updateDots();
}
function updateDots() {
  $$('.top .icon-btn .dot').forEach(d => d.remove());
  const b = $('.top .icon-btn[aria-label="การแจ้งเตือน"]');
  if (b && S.unread) b.insertAdjacentHTML('beforeend', `<span class="dot">${S.unread > 9 ? '9+' : S.unread}</span>`);
  $('#tdot') && $('#tdot').classList.toggle('hidden', !S.unread);
}

/* ---------------- notifications ---------------- */
const NIC = {box: ['#FFF4DB', 'var(--amber)'], truck: ['var(--tq-l)', 'var(--tq-t)'], lock: ['var(--tq-l)', 'var(--tq-t)'], wallet: ['var(--tq-l)', 'var(--tq-t)'],
  warn: ['var(--red-l)', 'var(--red)'], star: ['#FFF0CC', '#8A5A00'], check: ['var(--tq-l)', 'var(--tq-t)'], store: ['#FFEDE5', '#C2410C'],
  bike: ['#FFF4DB', 'var(--amber)'], shield: ['var(--tq-l)', 'var(--tq-t)'], info: ['var(--tq-l)', 'var(--tq-t)']};
async function toggleNotif(v) {
  const n = $('#notif'); const open = v === undefined ? !n.classList.contains('open') : v;
  n.classList.toggle('open', open);
  if (!open || !S.me) return;
  window.scrollTo(0, 0);
  n.innerHTML = '<div class="h">การแจ้งเตือน</div><div class="empty">กำลังโหลด…</div>';
  try {
    const r = await api('/notifications'); S.notifs = r.items; renderNotif();
    if (r.unread) { await api('/notifications/read', {}); S.unread = 0; updateDots(); }
  } catch (e) { handleErr(e); }
}
function renderNotif() {
  const n = $('#notif');
  n.innerHTML = `<div class="h">การแจ้งเตือน <button class="link" onclick="toggleNotif(false)">ปิด</button></div>` +
    (S.notifs.length ? S.notifs.map(x => { const [bg, c] = NIC[x.icon] || NIC.info;
      return `<div class="it ${x.read ? '' : 'unread'}" onclick="${x.deal_code ? `toggleNotif(false);location.hash='#/d/${esc(x.deal_code)}'` : 'toggleNotif(false)'}">
      <div class="ic" style="background:${bg};color:${c}">${ic(x.icon in NIC && x.icon !== 'info' ? x.icon : 'info', 16)}</div>
      <div>${esc(x.text)}<small>${ago(x.created_at)}</small></div></div>`; }).join('') : '<div class="empty">ยังไม่มีการแจ้งเตือน</div>');
}

/* ---------------- login ---------------- */
function vLogin(step = 1, data = {}) {
  const v = $('#view');
  S.login = data;
  const body = step === 1 ? `
    <div class="card">
      <div class="hero-logo"><svg class="lg-sheet" width="64" height="64" role="img" aria-label="โลโก้ดีลชัวร์"><use href="#logoA"/></svg></div>
      <label class="lb">ชื่อที่ใช้แสดง</label>
      <input class="input" id="lgName" maxlength="60" placeholder="เช่น สมชาย ใจดี" value="${esc(data.name || '')}" autocomplete="name">
      <label class="lb">เบอร์โทรศัพท์</label>
      <input class="input" id="lgPhone" type="tel" inputmode="numeric" maxlength="12" placeholder="0812345678" value="${esc(data.phone || '')}" autocomplete="tel">
      <p class="small muted mt8">เราจะส่งรหัส OTP 6 หลักให้คุณ (โหมดทดลอง: แสดงรหัสบนหน้าจอ ไม่ส่ง SMS จริง)</p>
      <button class="btn primary mt12" id="lgBtn" onclick="loginStart(this)">ขอรหัส OTP</button>
    </div>
    <div class="card">
      <h3>เข้าสู่ระบบด้วยบัญชีอื่น <span class="demo" style="margin-left:auto">เร็ว ๆ นี้</span></h3>
      <div class="soon">
        <button disabled><span class="ic" style="background:#06C755">LINE</span>LINE</button>
        <button disabled><span class="ic" style="background:#1877F2">f</span>Facebook</button>
      </div>
      <p class="small muted mt8">การเข้าสู่ระบบด้วย LINE / Facebook จะเปิดให้ใช้ในเวอร์ชันถัดไป</p>
    </div>` : `
    <div class="card">
      <h3>${ic('lock', 18)}กรอกรหัส OTP</h3>
      <p class="small muted">ส่งรหัสไปที่ ${esc(data.phone)} แล้ว <button class="link" onclick="vLogin(1, S.login)">เปลี่ยนเบอร์</button></p>
      <div class="note warn mt8">${ic('info', 16, 'color:var(--amber)')}<div><b>โหมดทดลอง – ไม่มี SMS จริง</b><br>รหัสของคุณคือ</div></div>
      <div class="otp-show" id="otpShow">${[...data.code].map(c => `<span>${c}</span>`).join('')}</div>
      <label class="lb">รหัส 6 หลัก</label>
      <input class="input otp-input" id="lgCode" inputmode="numeric" maxlength="6" placeholder="••••••" autocomplete="one-time-code">
      <button class="btn primary mt12" id="lgVerify" onclick="loginVerify(this)">ยืนยันและเข้าสู่ระบบ</button>
    </div>`;
  v.innerHTML = header({title: 'เข้าสู่ระบบ', sub: 'ซื้อขายกับคนในกลุ่มเฟซ / LINE ได้อย่างสบายใจ เงินถูกพักไว้จนกว่าผู้ซื้อจะได้ของ', right: ''}) +
    `<div class="wrap">${body}<p class="footer-note">ดีลชัวร์ (DealSure) · ต้นแบบสำหรับทดลองใช้ · ไม่มีเงินจริง</p></div>`;
  if (step === 2) $('#lgCode').addEventListener('keydown', e => { if (e.key === 'Enter') loginVerify($('#lgVerify')); });
}
function loginStart(btn) {
  busy(btn, async () => {
    const name = $('#lgName').value.trim(), phone = $('#lgPhone').value.trim();
    const r = await api('/login/start', {name, phone});
    vLogin(2, {name, phone: r.phone, code: r.demo_code});
  });
}
function loginVerify(btn) {
  busy(btn, async () => {
    await api('/login/verify', {phone: S.login.phone, code: $('#lgCode').value});
    await loadMe(); toast('เข้าสู่ระบบแล้ว ยินดีต้อนรับ ' + hello(S.me.name));
    const to = S.after && !S.after.includes('login') ? S.after : '#/'; S.after = null;
    if (location.hash === to) render(); else location.hash = to;
  });
}
async function logout() { await api('/logout', {}); S.me = null; S.unread = 0; location.hash = '#/login'; }

/* ---------------- home ---------------- */
async function vHome() {
  const [r, sh] = await Promise.all([api('/deals'), api('/shops')]);
  const act = r.deals.filter(d => ACTIVE.includes(d.status)), done = r.deals.filter(d => !ACTIVE.includes(d.status));
  const row = d => `<a class="dl" href="#/d/${esc(d.code)}">${thumb(d.photo)}
     <div class="grow"><b class="ell" style="display:block">${esc(d.title)}</b>
     <div class="small muted ell">${d.role === 'seller' ? 'คุณขาย' : 'คุณซื้อ'}${d.other ? ' · กับ ' + esc(d.other) : ' · รออีกฝ่าย'} · ${DLV[d.delivery][0]}</div>
     <div class="row2" style="margin-top:3px"><span class="price-tq">${baht(d.price)}</span>${stLabel(d.status, d.role)}</div></div></a>`;
  const shops = sh.shops.slice(0, 3).map(s => `<div class="shoprow" onclick="location.hash='#/shop/${s.id}'">${avatar(s, 'sm')}
     <div class="grow"><b class="prompt ell" style="display:block">${esc(s.shop_name)}</b>
     <div class="row2" style="flex-wrap:wrap;gap:4px">${levelBadge(s.stats)}<span class="small muted">${s.stats.rating ? '★ ' + s.stats.rating.toFixed(1) : 'ยังไม่มีรีวิว'} · ขายสำเร็จ ${fmt(s.stats.sales)}</span></div></div>
     <span class="link">ดูร้าน →</span></div>`).join('');
  $('#view').innerHTML = header({title: 'สวัสดี ' + esc(hello(S.me.name)), sub: 'เงินถูกพักไว้จนกว่าผู้ซื้อจะได้ของ ปลอดภัยทั้งสองฝ่าย',
      hero: `<a href="#/me" style="text-decoration:none">${hero('wallet', 'var(--tq)', 'เงินขาย รอโอนรอบถัดไป (วันละครั้ง)', baht(r.pending_payout), '<span class="badge b-green">จำลอง</span>')}</a>`}) + `
    <div class="wrap">
      <a class="btn primary" href="#/create">${ic('plus', 20)}สร้างดีลใหม่ & ส่งลิงก์</a>
      <div class="card mt12">
        <h3>${ic('list', 18)}ดีลที่กำลังดำเนินการ <span class="muted small" style="font-weight:400;margin-left:auto">${act.length} ดีล</span></h3>
        ${act.length ? act.map(row).join('') : `<div class="empty-st"><div class="big">🤝</div>ยังไม่มีดีล ลองสร้างดีลแล้วส่งลิงก์ให้อีกฝ่ายทาง LINE ดูสิ</div>`}
      </div>
      ${done.length ? `<div class="card"><h3>ดีลที่จบแล้ว</h3>${done.map(row).join('')}</div>` : ''}
      ${shops ? `<div class="card"><h3>${ic('store', 18)}ร้านแนะนำ</h3>${shops}</div>` : ''}
      ${noteHtml('info', '<b>โหมดทดลอง – ไม่มีเงินจริง</b> การจ่ายเงิน การโอน และการยืนยันตัวตนทั้งหมดเป็นการจำลอง ใช้ปุ่ม “เร่งเวลา (ทดสอบ)” ในหน้าดีลเพื่อข้ามเวลารอได้')}
    </div>`;
}

/* ---------------- create deal ---------------- */
function newForm() { return {role: 'seller', title: '', desc: '', price: '', photos: [], delivery: 'parcel', due: todayStr(3), fee: 'half'}; }
function vCreate() {
  const F = S.F || (S.F = newForm());
  $('#view').innerHTML = header({title: 'สร้างดีลใหม่', sub: 'เงินถูกพักไว้จนกว่าผู้ซื้อจะได้ของ ปลอดภัยทั้งสองฝ่าย'}) + `
  <div class="wrap">
    <div class="card">
      <label class="lb">ฉันเป็น…</label>
      <div class="seg" id="roleSeg"><button data-v="seller">ฉันเป็นผู้ขาย</button><button data-v="buyer">ฉันเป็นผู้ซื้อ</button></div>
      <p class="small muted mt8" id="roleHint"></p>
    </div>
    <div class="card">
      <h3>${ic('box', 18)}รายละเอียดสินค้า</h3>
      <label class="lb">ชื่อสินค้า</label>
      <input class="input" id="fTitle" maxlength="120" placeholder="เช่น กล้องฟิล์ม Olympus มือสอง" value="${esc(F.title)}">
      <label class="lb">รายละเอียด / สภาพ <span class="opt">(ไม่บังคับ)</span></label>
      <textarea class="input" id="fDesc" maxlength="500" placeholder="เช่น สภาพ 90% พร้อมสายคล้อง">${esc(F.desc)}</textarea>
      <label class="lb">ราคาที่ตกลงกัน</label>
      <div class="price-wrap"><input class="input" id="price" inputmode="numeric" placeholder="0" value="${F.price ? Number(F.price).toLocaleString('en-US') : ''}"><span>บาท</span></div>
      <label class="lb">รูปสินค้า <span class="opt">(ไม่บังคับ · สูงสุด 6 รูป)</span></label>
      <div class="photos" id="fPhotos"></div>
    </div>
    <div class="card">
      <h3>${ic('truck', 18)}การส่งมอบ</h3>
      <div class="chips" id="delivChips">
        <button class="chip" data-v="parcel">${ic('box')}ส่งพัสดุ</button>
        <button class="chip" data-v="meet">${ic('hand')}นัดรับด้วยตัวเอง</button>
        <button class="chip" data-v="messenger" style="flex-basis:100%">${ic('bike')}ส่งแมสเซนเจอร์ (Grab / Lalamove)</button>
      </div>
      <label class="lb" id="dueLbl">วันที่ตกลงส่งของ / นัดรับ</label>
      <div style="position:relative"><input class="input" id="fDue" type="date" min="${todayStr()}" value="${F.due}" style="padding-left:40px">${ic('cal', 20, 'position:absolute;left:12px;top:13px;color:var(--muted);pointer-events:none')}</div>
      <p class="small mt8" id="dueTh" style="color:var(--tq-t);font-weight:600"></p>
      <p class="small muted" id="delivHint"></p>
    </div>
    <div class="card">
      <h3>${ic('wallet', 18)}ใครจ่ายค่าธรรมเนียม?</h3>
      <div class="seg" id="feeSeg"><button data-v="buyer">ผู้ซื้อ</button><button data-v="seller">ผู้ขาย</button><button data-v="half">คนละครึ่ง</button></div>
      <div class="card fee mt12" style="margin-bottom:0;box-shadow:none">
        <div class="r"><span class="muted">ราคาสินค้า</span><b id="fPrice"></b></div>
        <div class="r"><span class="muted">ค่าธรรมเนียม 2% <span class="small">(ขั้นต่ำ 20 ฿)</span></span><b id="fFee"></b></div>
        <div class="r small"><span class="muted">แบ่งจ่าย</span><span id="fSplit"></span></div>
        <div class="r tot"><span>ผู้ซื้อจ่าย</span><b id="fBuyer"></b></div>
        <div class="r"><span class="muted">ผู้ขายได้รับ</span><b id="fSeller" style="color:var(--navy)"></b></div>
      </div>
    </div>
    <div id="limitNotes"></div>
    ${noteHtml('info', 'ดีลที่มีมูลค่า <b>เกิน 3,000 บาท</b> ต้องยืนยันตัวตนก่อน · ผู้ใช้ใหม่สร้างดีลได้ <b>สูงสุด 5,000 บาท/ดีล</b>')}
    <button class="btn primary mt8" id="createBtn" onclick="createDeal(this)">${ic('share', 20)}สร้างดีล & รับลิงก์</button>
    <p class="footer-note">ส่งลิงก์ให้อีกฝ่ายทาง LINE หรือ Facebook Messenger ได้ทันที</p>
  </div>`;
  const segSet = (id, val) => $$('#' + id + ' button').forEach(b => b.classList.toggle('on', b.dataset.v === val));
  const renderPhotos = () => {
    $('#fPhotos').innerHTML = F.photos.map((p, i) => `<div class="ph"><img src="${p}" alt="รูปสินค้า ${i + 1}"><button class="x" aria-label="ลบรูป" onclick="S.F.photos.splice(${i},1);vCreate()">✕</button></div>`).join('') +
      (F.photos.length < 6 ? `<div class="ph add" onclick="addPhotos()">＋<br>เพิ่มรูป</div>` : '');
  };
  const upd = () => {
    segSet('roleSeg', F.role); segSet('feeSeg', F.fee);
    $$('#delivChips .chip').forEach(c => c.classList.toggle('on', c.dataset.v === F.delivery));
    $('#roleHint').textContent = F.role === 'seller' ? 'คุณจะส่งลิงก์ให้ผู้ซื้อกดรับดีลและจ่ายเงินเข้าระบบพักเงิน' : 'คุณจะส่งลิงก์ให้ผู้ขายกดรับดีล แล้วคุณจ่ายเงินเข้าระบบพักเงิน';
    $('#delivHint').textContent = {parcel: 'ผู้ขายต้องกรอกเลขพัสดุภายในวันที่ตกลง ไม่งั้นผู้ซื้อขอเงินคืนได้', meet: 'ตอนเจอกัน ผู้ซื้อตรวจของ แล้วกรอกรหัส 4 หลักจากผู้ขาย เงินจะถูกปล่อยทันที', messenger: 'ผู้ขายแนบลิงก์ติดตามไรเดอร์หรือรูปตอนส่ง ระบบปล่อยเงินอัตโนมัติ 24 ชม. หลังส่ง'}[F.delivery];
    $('#dueLbl').textContent = F.delivery === 'meet' ? 'วันที่นัดรับ' : 'วันที่ตกลงส่งของ';
    $('#dueTh').textContent = F.due ? dDate(F.due) : '';
    const p = parseFloat(String(F.price).replace(/[^\d.]/g, '')) || 0, f = calcFee(p, F.fee);
    $('#fPrice').textContent = baht(p); $('#fFee').textContent = baht(f.fee);
    $('#fSplit').textContent = F.fee === 'half' ? `ผู้ซื้อ ${baht(f.b)} · ผู้ขาย ${baht(f.s)}` : F.fee === 'buyer' ? 'ผู้ซื้อจ่ายทั้งหมด' : 'ผู้ขายจ่ายทั้งหมด';
    $('#fBuyer').textContent = baht(f.buyer); $('#fSeller').textContent = baht(Math.max(0, f.seller));
    const st = S.me.stats, lim = F.role === 'seller' ? st.seller_limit : st.buyer_limit; let h = '';
    if (p > lim) h += noteHtml('err', F.role === 'seller' ? `วงเงินของ${st.level_name}คือ ${fmt(lim)} บาท/ดีล — ขายสำเร็จเพิ่มเพื่อเลื่อนระดับร้านและปลดล็อกวงเงิน` : `ผู้ใช้ใหม่สร้างดีลได้สูงสุด ${fmt(lim)} บาท/ดีล — ทำดีลสำเร็จครบ 5 ดีลเพื่อปลดล็อกวงเงิน`);
    else if (p > 3000 && !S.me.verified) h += noteHtml('warn', `ดีลนี้เกิน 3,000 บาท — ต้อง<b>ยืนยันตัวตน</b>ก่อน (ทดสอบ ใช้เวลาไม่ถึง 1 นาที) <button class="link" onclick="idSheet()">ยืนยันเลย →</button>`);
    else if (p > 3000) h += noteHtml('ok', 'คุณยืนยันตัวตนแล้ว สร้างดีลเกิน 3,000 บาทได้');
    if (p > 0 && p < 50) h += noteHtml('err', 'ราคาขั้นต่ำ 50 บาท');
    $('#limitNotes').innerHTML = h;
  };
  $$('#roleSeg button').forEach(b => b.onclick = () => { F.role = b.dataset.v; upd(); });
  $$('#feeSeg button').forEach(b => b.onclick = () => { F.fee = b.dataset.v; upd(); });
  $$('#delivChips .chip').forEach(c => c.onclick = () => { F.delivery = c.dataset.v; upd(); });
  $('#fTitle').oninput = e => F.title = e.target.value;
  $('#fDesc').oninput = e => F.desc = e.target.value;
  $('#fDue').onchange = e => { F.due = e.target.value; upd(); };
  $('#price').oninput = e => { const raw = e.target.value.replace(/[^\d]/g, ''); e.target.value = raw ? Number(raw).toLocaleString('en-US') : ''; F.price = raw; upd(); };
  renderPhotos(); upd();
}
function addPhotos() {
  pickFiles('image/*', true, async files => {
    try { for (const f of files.slice(0, 6 - S.F.photos.length)) S.F.photos.push(await resizeImage(f)); } catch (e) { toast(e.message); }
    const y = window.scrollY; vCreate(); window.scrollTo(0, y);
  });
}
function createDeal(btn) {
  const F = S.F;
  busy(btn, async () => {
    if (!F.title.trim()) throw new Error('กรุณากรอกชื่อสินค้า');
    if (!F.price) throw new Error('กรุณากรอกราคา');
    const r = await api('/deals', {role: F.role, title: F.title, description: F.desc, price: F.price, photos: F.photos, delivery: F.delivery, due_date: F.due, fee_payer: F.fee});
    const f = calcFee(+F.price, F.fee); const role = F.role, title = F.title;
    S.F = null; S.pendingShare = {code: r.code, role, title, amount: f.buyer};
    location.hash = '#/d/' + r.code;
  });
}
function shareSheet(code, role, title, amount, fresh) {
  const url = location.origin + '/d/' + code;
  const other = role === 'seller' ? 'ผู้ซื้อ' : 'ผู้ขาย';
  const msg = `ดีลชัวร์: ${title} ยอด ${baht(amount)}\nกดลิงก์เพื่อรับดีล${role === 'seller' ? 'และจ่ายเงินเข้าระบบพักเงิน' : ''} เงินถูกพักไว้จนกว่าผู้ซื้อจะได้ของ (โหมดทดลอง)\n${url}`;
  S.shareMsg = msg; S.shareUrl = url;
  openSheet(`<div style="text-align:center"><svg class="lg-sheet" width="64" height="64" role="img" aria-label="โลโก้ดีลชัวร์" style="display:block;margin:0 auto 10px"><use href="#logoA"/></svg>
    <h2>${fresh ? 'สร้างดีลสำเร็จ!' : 'แชร์ลิงก์ดีล'}</h2><p class="small muted">ส่งลิงก์นี้ให้${other} เพื่อกดรับดีล${role === 'seller' ? 'และจ่ายเงินเข้าระบบพักเงิน' : ''}</p></div>
    <div class="linkbox"><span id="shareUrl">${esc(url)}</span><button class="link" aria-label="คัดลอกลิงก์" onclick="copyText(S.shareUrl,'คัดลอกลิงก์แล้ว ✓')">${ic('copy', 18)}</button></div>
    <div class="share">
      <a id="lineShare" href="https://line.me/R/msg/text/?${encodeURIComponent(msg)}" target="_blank" rel="noopener"><span class="ic" style="background:#06C755">LINE</span>ส่งทาง LINE</a>
      <button onclick="copyText(S.shareMsg,'คัดลอกข้อความแล้ว ✓ วางในแชทหรือคอมเมนต์ได้เลย')"><span class="ic" style="background:#1877F2">f</span>คัดลอกข้อความ</button>
      <button onclick="navigator.share?navigator.share({title:'ดีลชัวร์',text:S.shareMsg}).catch(()=>{}):copyText(S.shareMsg)"><span class="ic" style="background:linear-gradient(135deg,#0866FF,#A033FF)">${ic('share', 18, 'color:#fff')}</span>แชร์อื่น ๆ</button>
    </div>
    <button class="btn primary mt12" onclick="copyText(S.shareUrl,'คัดลอกลิงก์แล้ว ✓')">${ic('copy', 20)}คัดลอกลิงก์</button>
    <button class="btn ghost mt8" onclick="closeSheet()">ดูหน้าดีล</button>`);
}

/* ---------------- ID verification (simulated) ---------------- */
function idSheet(reason) {
  S.idImg = null;
  openSheet(`<h2>ยืนยันตัวตน <span class="demo">ทดสอบ</span></h2>
    ${reason ? noteHtml('warn', esc(reason)) : ''}
    ${noteHtml('warn', '<b>โหมดทดลอง – อนุมัติอัตโนมัติ</b><br>ไม่ต้องใช้บัตรจริง อัปโหลดรูปอะไรก็ได้ <b>กรุณาอย่าอัปโหลดบัตรประชาชนจริง</b>')}
    <div class="idbox" id="idBox" onclick="pickId()">${ic('card', 28, 'color:var(--tq-d)')}<br><b>แตะเพื่อเลือกรูป (แทนบัตรประชาชน)</b><br><span class="small">ในแอปจริง: ถ่ายบัตร + เซลฟี่ ตรวจโดยระบบ KYC</span></div>
    <button class="btn primary mt12" onclick="submitId(this)">ส่งยืนยันตัวตน (ทดสอบ)</button>`);
}
function pickId() {
  pickFiles('image/*', false, async ([f]) => {
    if (!f) return;
    try { S.idImg = await resizeImage(f, 900); $('#idBox').classList.add('upload', 'ok'); $('#idBox').innerHTML = `<img src="${S.idImg}" style="max-height:110px;border-radius:12px"><br>เลือกรูปแล้ว แตะเพื่อเปลี่ยน`; } catch (e) { toast(e.message); }
  });
}
function submitId(btn) {
  busy(btn, async () => {
    if (!S.idImg) throw new Error('กรุณาเลือกรูปก่อน');
    await api('/me/verify-id', {image: S.idImg}); await loadMe();
    closeSheet(); toast('ยืนยันตัวตนสำเร็จ (ทดสอบ – อนุมัติอัตโนมัติ)');
    const {p} = route(); const y = window.scrollY;
    if (p === 'create') vCreate(); else if (p === 'd') await refreshDeal(); else if (p === 'me') await vMe(); else if (p === 'shop') await vShop(route().a);
    window.scrollTo(0, y);
  });
}

/* ---------------- deal page ---------------- */
async function vDeal(code) {
  const d = await api('/deals/' + encodeURIComponent(code));
  S.deal = d; S.offset = d.deal_now - Date.now() / 1000; S.dealSig = JSON.stringify(d);
  const role = d.my_role, st = d.status, A = a => d.actions.includes(a);
  const other = role === 'seller' ? d.buyer : role === 'buyer' ? d.seller : (d.seller || d.buyer);
  const otherRole = role === 'seller' ? 'buyer' : role === 'buyer' ? 'seller' : (d.seller ? 'seller' : 'buyer');
  const visitorRole = d.seller ? 'buyer' : 'seller';
  const amt = baht(d.buyer_pay);
  const wait = t => `<span class="badge" style="background:#FFD27A;color:#5A3A00">${t}</span>`;
  let H;
  if (st === 'open') H = role ? hero('clock', '#E9A23B', 'รออีกฝ่ายเปิดลิงก์และกดรับดีล', 'ส่งลิงก์ให้' + (role === 'seller' ? 'ผู้ซื้อ' : 'ผู้ขาย'), wait('รอรับดีล'))
    : `<div class="status-hero">${ic('lock', 30, 'color:var(--tq)!important;flex:none')}<div style="font-size:13.5px"><b class="prompt" style="font-size:15px">ดีลนี้ได้รับการคุ้มครอง</b><br>คุณได้รับลิงก์จาก <b>${esc(visitorRole === 'buyer' ? other.shop_name : other.name)}</b> · คุณจะเป็น<b>${visitorRole === 'buyer' ? 'ผู้ซื้อ' : 'ผู้ขาย'}</b></div></div>`;
  else if (st === 'accepted') H = hero('card', 'var(--tq)', role === 'buyer' ? 'ยอดที่ต้องจ่ายเข้าระบบพักเงิน' : 'รอผู้ซื้อจ่ายเงินเข้าระบบพักเงิน', amt, wait('รอจ่ายเงิน'));
  else if (st === 'held') H = d.overdue ? hero('warn', 'var(--red)', 'เลยวันที่ตกลงส่งของแล้ว', 'ผู้ซื้อขอเงินคืนได้', stLabel(st, role))
    : hero('lock', 'var(--tq)', `เงินพักไว้แล้ว · ${d.delivery === 'meet' ? 'นัดรับ' : 'ส่ง'}ภายใน ${dDate(d.due_date)}`, amt, '<span class="badge b-green">พักเงินไว้</span>');
  else if (st === 'shipped') H = hero('truck', 'var(--tq)', 'ผู้ขายส่งของแล้ว · ' + esc(d.carrier || ''), 'กำลังจัดส่ง', '<span class="badge b-green">เงินพักไว้</span>');
  else if (st === 'delivered') H = `<div class="status-hero">${ic('clock', 30, 'color:#E9A23B!important;flex:none')}<div style="flex:1"><div class="small muted">ระบบจะโอนเงินให้ผู้ขายอัตโนมัติใน</div><div class="timer" data-until="${d.auto_release_at}">${dur(d.auto_release_at - d.deal_now)}</div></div>${wait('รอยืนยัน')}</div>`;
  else if (st === 'disputed') H = hero('warn', 'var(--red)', 'ทีมงานกำลังตรวจสอบ (ภายใน 24 ชม.)', 'เงินยังพักไว้', '<span class="spill sp-red">ข้อพิพาท</span>');
  else if (st === 'completed') H = hero('check', 'var(--tq)', 'ดีลสำเร็จ · ปล่อยเงินให้ผู้ขายแล้ว', baht(d.seller_get), '<span class="spill sp-done">สำเร็จ</span>');
  else if (st === 'refunded') H = hero('wallet', 'var(--tq)', 'คืนเงินให้ผู้ซื้อแล้ว (จำลอง)', baht(d.refund_amount), '<span class="spill sp-gray">คืนเงิน</span>');
  else if (st === 'partial') H = hero('wallet', 'var(--tq)', 'ทีมงานตัดสินคืนเงินบางส่วน', 'คืนผู้ซื้อ ' + baht(d.refund_amount), '<span class="spill sp-gray">แบ่งเงิน</span>');
  else H = hero('info', 'var(--muted)', 'ดีลนี้ถูกยกเลิกแล้ว', 'ยกเลิก', '<span class="spill sp-gray">ยกเลิก</span>');

  let partyCard = '';
  if (other) {
    const s = other.stats, isSeller = otherRole === 'seller';
    partyCard = `<div class="card"><div class="small muted" style="margin-bottom:8px;font-family:Prompt">${isSeller ? 'ผู้ขาย' : 'ผู้ซื้อ'}${role ? '' : ' (คนส่งลิงก์ให้คุณ)'}</div>
      <div class="seller">${avatar(other)}
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap"><b class="prompt" style="font-size:16px">${esc(isSeller ? other.shop_name : other.name)}</b>${demoTag(other)}</div>
          <div style="display:flex;gap:6px;margin-top:3px;flex-wrap:wrap">${verBadge(other)}${isSeller ? levelBadge(s) : ''}</div>
          <div class="small" style="margin-top:4px">${isSeller ? (s.rating ? `${stars(s.rating)} <b>${s.rating.toFixed(1)}</b> <span class="muted">(${fmt(s.reviews)} รีวิว)</span>` : '<span class="muted">ยังไม่มีรีวิว</span>')
            : (s.buyer_rating ? `${stars(s.buyer_rating)} <b>${s.buyer_rating.toFixed(1)}</b> <span class="muted">(${s.buyer_reviews} รีวิวผู้ซื้อ)</span>` : '<span class="muted">ยังไม่มีรีวิวในฐานะผู้ซื้อ</span>')}</div>
        </div></div>
      <div class="stats">
        <div class="stat"><b>${fmt(isSeller ? s.sales : s.total)}</b><span>${isSeller ? 'ขายสำเร็จ' : 'ดีลสำเร็จ'}</span></div>
        <div class="stat"><b>${isSeller ? s.dispute_rate + '%' : fmt(s.buys)}</b><span>${isSeller ? 'อัตราข้อพิพาท' : 'ซื้อสำเร็จ'}</span></div>
        <div class="stat"><b>${since(other.member_since)}</b><span>ใช้งานมา</span></div>
      </div>
      <a class="link mt8" style="display:inline-block" href="#/${isSeller ? 'shop' : 'u'}/${other.id}">${isSeller ? 'ดูหน้าร้านและรีวิว →' : 'ดูโปรไฟล์และประวัติ →'}</a></div>`;
  } else if (role) {
    partyCard = `<div class="card"><div class="empty-st"><div class="big">📨</div>ยังไม่มี${role === 'seller' ? 'ผู้ซื้อ' : 'ผู้ขาย'}กดรับดีลนี้<br>
      <button class="btn ghost sm mt8" onclick="shareSheet(S.deal.code,'${role}',S.deal.title,S.deal.buyer_pay)">${ic('share', 16)}ส่งลิงก์อีกครั้ง</button></div></div>`;
  }

  let ac = '';
  if (A('accept')) {
    const needId = d.price > 3000 && S.me && !S.me.verified;
    ac += `<div class="card"><h3>${ic('hand', 18)}รับดีลนี้ในฐานะ${visitorRole === 'buyer' ? 'ผู้ซื้อ' : 'ผู้ขาย'}</h3>
      <p class="small muted">${visitorRole === 'buyer' ? 'เมื่อรับดีลแล้ว คุณจะจ่ายเงินเข้าระบบพักเงินของดีลชัวร์ ผู้ขายยังไม่ได้เงินจนกว่าคุณจะได้ของ' : 'เมื่อรับดีลแล้ว ผู้ซื้อจะจ่ายเงินเข้าระบบพักเงิน คุณส่งของเมื่อเงินพักไว้แล้วเท่านั้น'}</p>
      ${needId ? noteHtml('warn', 'ดีลนี้เกิน 3,000 บาท — ต้องยืนยันตัวตนก่อนรับดีล <button class="link" onclick="idSheet()">ยืนยันเลย →</button>') : ''}
      ${S.me ? `<button class="btn primary mt8" onclick="dealAct(this,'accept')">${ic('check', 20)}${visitorRole === 'buyer' ? 'รับดีล แล้วไปจ่ายเงิน' : 'รับดีลนี้'}</button>`
        : `<button class="btn primary mt8" onclick="S.after=location.hash;location.hash='#/login'">${ic('user', 20)}เข้าสู่ระบบเพื่อรับดีล</button><p class="small muted center mt8">ใช้แค่ชื่อ + เบอร์โทร ไม่ถึง 1 นาที</p>`}</div>`;
  }
  if (A('pay')) ac += `<button class="btn blue" onclick="paySheet()">${ic('qr', 20)}จ่ายด้วย <span class="pp-logo" style="background:#fff;color:#0B766E">PromptPay</span> QR</button>
    <div class="secure-row"><span>${ic('lock', 14)}โหมดทดลอง – ไม่มีเงินจริง</span><span>${ic('shield', 14)}คืนเงินได้หากไม่ได้ของ</span></div><div style="height:12px"></div>`;
  if (st === 'accepted' && role === 'seller') ac += noteHtml('info', 'รอผู้ซื้อจ่ายเงินเข้าระบบพักเงิน เราจะแจ้งเตือนคุณทันทีเมื่อจ่ายแล้ว <b>ยังไม่ต้องส่งของ</b>');
  if (A('ship_parcel')) ac += `<div class="card"><h3>${ic('truck', 18)}ส่งของให้ผู้ซื้อ</h3><p class="small muted">เงิน ${amt} พักไว้แล้ว ส่งพัสดุแล้วกรอกเลขพัสดุภายใน <b>${dDate(d.due_date)}</b></p><button class="btn primary mt8" onclick="shipSheet()">${ic('box', 20)}กรอกเลขพัสดุ</button></div>`;
  if (A('ship_messenger')) ac += `<div class="card"><h3>${ic('bike', 18)}ส่งแมสเซนเจอร์</h3><p class="small muted">เงินพักไว้แล้ว เรียกไรเดอร์แล้วแนบลิงก์ติดตาม / รูปตอนส่ง ภายใน <b>${dDate(d.due_date)}</b></p><button class="btn primary mt8" onclick="shipSheet()">${ic('bike', 20)}แนบหลักฐานการส่ง</button></div>`;
  if (A('meet_show')) ac += `<div class="card" style="border:1.5px solid #BFEDE6;background:linear-gradient(180deg,#F0FBF9,#fff)">
      <h3>${ic('qr', 18)}รหัสนัดรับของคุณ (ผู้ขาย)</h3>
      <div class="code-box"><div style="flex:none">${fakeQr(96, 21, d.code)}</div><div><div class="small muted">ตอนเจอกัน ให้ผู้ซื้อตรวจของก่อน แล้วบอกรหัสนี้ให้ผู้ซื้อกรอกในแอป</div>
      <div class="otp mt8" id="meetShow">${[...d.meet_code].map(c => `<span>${c}</span>`).join('')}</div></div></div>
      <div class="note warn mt12" style="margin-bottom:0">${ic('warn', 16, 'color:var(--amber)')}<div>เมื่อผู้ซื้อกรอกรหัสถูกต้อง เงินจะถูกปล่อยให้คุณทันที · นัดรับภายใน <b>${dDate(d.due_date)}</b></div></div></div>`;
  if (A('meet_enter')) ac += `<div class="card" style="border:1.5px solid #BFEDE6;background:linear-gradient(180deg,#F0FBF9,#fff)">
      <h3>${ic('hand', 18)}เจอผู้ขายแล้ว? ยืนยันรับของ</h3>
      <p class="small muted">ตรวจของให้เรียบร้อย แล้วขอรหัส 4 หลักจากผู้ขายมากรอก</p>
      <div class="codein mt8"><input class="input otp-input" id="meetCode" inputmode="numeric" maxlength="4" placeholder="••••" style="letter-spacing:8px"><button class="btn primary" style="flex:1" onclick="meetSubmit(this)">ยืนยันรับของ</button></div>
      <div class="note warn mt12" style="margin-bottom:0">${ic('warn', 16, 'color:var(--amber)')}<div>กรอกรหัสหลังเห็นและตรวจของจริงแล้วเท่านั้น — เงินจะถูกปล่อยให้ผู้ขายทันที</div></div></div>`;
  if (st === 'held' && role === 'buyer' && !d.overdue) ac += noteHtml('info', `ผู้ขายต้อง${d.delivery === 'meet' ? 'นัดรับ' : 'ส่งของ'}ภายใน <b>${dDate(d.due_date)}</b> ถ้าเลยกำหนด คุณกดขอเงินคืนได้ทันที`);
  if (A('late_refund')) ac += `<div class="card">${noteHtml('err', `เลยวันที่ตกลง (${dDate(d.due_date)}) แล้ว ผู้ขายยังไม่${d.delivery === 'meet' ? 'นัดรับ' : 'ส่งของ'} คุณขอเงินคืนเต็มจำนวนได้`)}
      <button class="btn danger" onclick="lateRefund(this)">${ic('wallet', 18)}ขอเงินคืน (ส่งช้าเกินกำหนด)</button></div>`;
  if (st === 'held' && role === 'seller' && d.overdue) ac += noteHtml('err', 'เลยวันที่ตกลงส่งของแล้ว ผู้ซื้อสามารถขอเงินคืนได้ รีบส่งของหรือคุยกับผู้ซื้อนะ');
  if (A('confirm')) ac += `${st === 'delivered' ? `<div class="countdown" style="margin:0 0 12px">⏳ ตรวจสอบของภายใน <b>${d.delivery === 'messenger' ? '24 ชม.' : '3 วัน'}</b> — เหลืออีก <b data-until-short="${d.auto_release_at}">${durShort(d.auto_release_at - d.deal_now)}</b> หากไม่กดอะไร ระบบจะปล่อยเงินให้ผู้ขายอัตโนมัติ</div>` : ''}
      <div class="twobtn">${A('dispute') ? `<button class="btn danger" onclick="disputeSheet()">${ic('warn', 18)}แจ้งปัญหา</button>` : '<span></span>'}
      <button class="btn primary" onclick="confirmSheet()">${ic('check', 18)}ยืนยันรับของ</button></div><div style="height:12px"></div>`;
  if (st === 'shipped' && role === 'seller') ac += noteHtml('info', 'รอพัสดุถึงผู้ซื้อ (ระบบจำลองว่าขนส่งแจ้งของถึงภายใน 2 วัน) จากนั้นผู้ซื้อมีเวลาตรวจของ 3 วัน');
  if (st === 'delivered' && role === 'seller') ac += noteHtml('info', `ของถึงผู้ซื้อแล้ว ระบบจะปล่อยเงินอัตโนมัติใน <b data-until-short="${d.auto_release_at}">${durShort(d.auto_release_at - d.deal_now)}</b> หากผู้ซื้อไม่แจ้งปัญหา`);
  if (A('review')) ac += `<button class="btn primary" onclick="reviewSheet()">${ic('star', 20)}ให้คะแนน${role === 'buyer' ? 'ผู้ขาย' : 'ผู้ซื้อ'}</button><div style="height:12px"></div>`;
  if (role === 'seller' && d.payout) ac += `<div class="card"><h3>${ic('wallet', 18)}เงินของคุณจากดีลนี้</h3><div class="row2"><b class="prompt grow" style="font-size:22px;color:var(--tq-t)">${baht(d.payout_amount)}</b>
      ${d.payout.status === 'pending' ? '<span class="spill sp-wait">รอโอนรอบถัดไป (วันละครั้ง)</span>' : '<span class="spill sp-done">โอนแล้ว (จำลอง)</span>'}</div>
      <p class="small muted mt8">${d.payout.status === 'pending' ? 'ระบบรวมยอดโอนวันละครั้ง ทุกวัน 18:00 น. เข้าบัญชีที่ผูกไว้ (จำลอง ไม่มีการโอนจริง)' : 'โอนเมื่อ ' + dFull(d.payout.paid_at) + ' (จำลอง)'}</p></div>`;

  let disp = '';
  if (d.disputed_at && role) {
    const RES = {refund: 'คืนเงินผู้ซื้อเต็มจำนวน', release: 'ปล่อยเงินให้ผู้ขาย', partial: `คืนผู้ซื้อ ${baht(d.refund_amount)} · ผู้ขายได้ ${baht(d.payout_amount)}`};
    disp = `<div class="card"><h3>${ic('warn', 18, 'color:var(--red)!important')}เรื่องที่แจ้ง: ${esc(d.dispute_reason)}</h3>
      <div class="small muted">แจ้งเมื่อ ${dFull(d.disputed_at)}</div>${d.dispute_detail ? `<div class="proof">${esc(d.dispute_detail)}</div>` : ''}
      <div class="gallery">${(d.dispute_files || []).map(f => /\.(mp4|webm|mov)$/.test(f) ? `<video src="${esc(f)}" controls playsinline preload="metadata"></video>` : `<a href="${esc(f)}" target="_blank"><img src="${esc(f)}" alt="หลักฐาน"></a>`).join('')}</div>
      <div class="mt12">${RES[d.resolution] ? noteHtml('ok', `<b>ผลการตัดสิน:</b> ${RES[d.resolution]}${d.resolution_note ? '<br>' + esc(d.resolution_note) : ''}`) : st === 'disputed' ? noteHtml('warn', 'ทีมงานกำลังตรวจสอบหลักฐานจากทั้งสองฝ่าย ระหว่างนี้เงินจะถูกพักไว้ ไม่โอนให้ผู้ขาย') : ''}</div></div>`;
  }

  const sum = `<div class="card sum"><h3>สรุปดีล <span class="muted small" style="font-weight:400;margin-left:auto">#${esc(d.code)}</span></h3>
    <div class="prod">${thumb(d.photos[0])}<div class="grow"><b>${esc(d.title)}</b>${d.is_demo ? ' <span class="demo">ตัวอย่าง</span>' : ''}<div class="small muted">${esc(d.description || '')}</div></div></div>
    ${d.photos.length > 1 ? `<div class="gallery" style="margin-bottom:6px">${d.photos.map(p => `<a href="${esc(p)}" target="_blank"><img src="${esc(p)}" alt="รูปสินค้า"></a>`).join('')}</div>` : ''}
    <div class="r"><span>การส่งมอบ</span><b>${dlvLabel(d.delivery)}</b></div>
    <div class="r"><span>${d.delivery === 'meet' ? 'นัดรับภายใน' : 'กำหนดส่งภายใน'}</span><b>${dDate(d.due_date)}</b></div>
    <div class="r"><span>ราคาสินค้า</span><b>${baht(d.price)}</b></div>
    <div class="r"><span>ค่าธรรมเนียม 2% (${FEEP[d.fee_payer]})</span><b>${baht(d.fee)}</b></div>
    <div class="r"><span>ผู้ขายได้รับ</span><b>${baht(d.seller_get)}</b></div>
    <div class="r" style="padding-top:10px"><span style="color:var(--ink);font-weight:600">ยอดที่ผู้ซื้อจ่าย</span><b class="prompt" style="font-size:22px;color:var(--tq-t)">${amt}</b></div></div>`;
  const protect = (['open', 'accepted'].includes(st) && (role === 'buyer' || (!role && visitorRole === 'buyer'))) ? `<div class="card">
      <h3>${ic('shield', 18)}เราคุ้มครองคุณยังไง?</h3>
      <div class="steps">
        <div class="step"><div class="n">1</div><div><b>จ่ายเงิน</b><p>สแกนจ่ายผ่านพร้อมเพย์ เงินไม่ได้เข้ากระเป๋าผู้ขายทันที</p></div></div>
        <div class="step"><div class="n">2</div><div><b>เงินถูกพักไว้</b><p>ดีลชัวร์ถือเงินไว้อย่างปลอดภัย ระหว่างรอผู้ขายส่งของ</p></div></div>
        <div class="step"><div class="n">3</div><div><b>ได้ของแล้ว กดยืนยัน</b><p>ผู้ขายได้รับเงินเมื่อคุณยืนยัน หรือระบบโอนให้อัตโนมัติ <b style="font-size:13px">3 วันหลังของถึง</b> หากไม่มีการแจ้งปัญหา</p></div></div>
      </div>
      <div class="note ok mt12" style="margin-bottom:0">${ic('info', 16)}<div>ของไม่ตรงปก / ไม่ได้ของ? แจ้งปัญหาได้ภายใน 3 วัน พร้อมแนบคลิปแกะกล่อง · ผู้ขายไม่ส่งตามวันที่ตกลง ขอเงินคืนได้</div></div></div>` : '';

  const test = A('skip') || A('sim_delivered') ? `<div class="card testbox"><h3>${ic('fast', 18, 'color:#B7791F!important')}เครื่องมือทดสอบ <span class="small" style="font-weight:400;margin-left:auto">ไม่มีในแอปจริง</span></h3>
      <p class="small" style="color:#7A4E0B">ข้ามเวลารอ เพื่อลองดูว่าระบบทำงานอย่างไรเมื่อเวลาผ่านไป (เฉพาะดีลนี้)</p>
      ${A('sim_delivered') ? `<button class="btn ghost sm mt8" onclick="dealAct(this,'simulate-delivered')">${ic('box', 16)}จำลอง: ขนส่งแจ้งว่าของถึงแล้ว</button>` : ''}
      ${A('skip') ? `<div class="twobtn mt8"><button class="btn ghost sm" onclick="dealAct(this,'skip',{hours:24})">${ic('fast', 16)}เร่งเวลา (ทดสอบ) +1 วัน</button><button class="btn ghost sm" onclick="dealAct(this,'skip',{hours:72})">${ic('fast', 16)}เร่งเวลา (ทดสอบ) +3 วัน</button></div>` : ''}
      ${d.skew ? `<div class="skewnote">⏩ ดีลนี้เร่งเวลาไปแล้ว ${durShort(d.skew)} · เวลาในดีลตอนนี้: ${dFull(d.deal_now)}</div>` : ''}</div>` : '';

  $('#view').innerHTML = header({title: `ดีล <small>#${esc(d.code)}</small>`, sub: `${esc(d.title)} · ${amt}`, back: true, hero: H}) +
    `<div class="wrap">${ac}${partyCard}${disp}${sum}${protect}${timeline(d)}${dealReviews(d)}${test}
     ${st === 'open' && role ? `<div class="twobtn"><button class="btn ghost sm" onclick="shareSheet(S.deal.code,'${role}',S.deal.title,S.deal.buyer_pay)">${ic('share', 16)}แชร์ลิงก์</button><button class="btn danger sm" onclick="cancelDeal(this)">ยกเลิกดีล</button></div>` : ''}
     ${st === 'accepted' && role ? `<button class="btn danger sm" onclick="cancelDeal(this)">ยกเลิกดีล (ก่อนจ่ายเงิน)</button>` : ''}
     <p class="footer-note">แจ้งปัญหาได้ภายใน 3 วันหลังของถึง · แนบคลิปแกะกล่องเพื่อใช้เป็นหลักฐาน</p></div>`;
  updateDots();
  if (S.pendingShare && S.pendingShare.code === d.code) { const p = S.pendingShare; S.pendingShare = null; shareSheet(p.code, p.role, p.title, p.amount, true); }
}
function timeline(d) {
  const it = [];
  const by = d.creator_role === 'seller' ? d.seller : d.buyer;
  it.push({t: d.source === 'shop' ? 'สั่งซื้อจากหน้าร้าน' : 'สร้างดีล', m: `${dFull(d.created_at)}${by ? ' โดย ' + esc(d.creator_role === 'seller' ? by.shop_name : by.name) : ''}`, done: true});
  if (d.source !== 'shop') it.push({t: (d.creator_role === 'seller' ? 'ผู้ซื้อ' : 'ผู้ขาย') + 'กดรับดีล', m: d.accepted_at ? dFull(d.accepted_at) : 'รออีกฝ่ายเปิดลิงก์', done: !!d.accepted_at});
  it.push({t: 'ผู้ซื้อจ่ายแล้ว – เงินพักไว้', m: d.paid_at ? `${dTime(d.paid_at)} · ยอด ${baht(d.buyer_pay)} ผ่านพร้อมเพย์ (จำลอง)` : 'ผู้ซื้อจ่ายเงินเข้าระบบพักเงิน', done: !!d.paid_at});
  if (d.delivery === 'parcel') {
    it.push({t: 'ผู้ขายส่งของแล้ว', m: d.shipped_at ? `${dTime(d.shipped_at)} · ${esc(d.carrier)}${d.on_time === 0 ? ' · ส่งช้ากว่ากำหนด' : ''}` : 'ภายใน ' + dDate(d.due_date), done: !!d.shipped_at,
      x: d.tracking ? `<div class="trk"><span>เลขพัสดุ <code>${esc(d.tracking)}</code></span><button class="link" onclick="copyText('${esc(d.tracking)}','คัดลอกเลขพัสดุแล้ว')">คัดลอก</button></div>` : ''});
    it.push({t: 'ของถึงแล้ว', m: d.delivered_at ? `${dTime(d.delivered_at)} · ขนส่งยืนยันการจัดส่ง (จำลอง)` : 'ขนส่งยืนยันการจัดส่ง', done: !!d.delivered_at,
      x: d.status === 'delivered' ? `<div class="countdown">⏳ ตรวจสอบของภายใน <b>3 วัน</b> — เหลืออีก <b data-until-short="${d.auto_release_at}">${durShort(d.auto_release_at - d.deal_now)}</b> หากไม่กดอะไร ระบบจะยืนยันให้อัตโนมัติ</div>` : ''});
  } else if (d.delivery === 'messenger') {
    it.push({t: 'ผู้ขายส่งแมสเซนเจอร์แล้ว', m: d.shipped_at ? dTime(d.shipped_at) : 'ภายใน ' + dDate(d.due_date), done: !!d.shipped_at,
      x: (d.proof_text ? `<div class="proof">${esc(d.proof_text)}</div>` : '') + (d.proof_photos && d.proof_photos.length ? `<div class="gallery">${d.proof_photos.map(p => `<a href="${esc(p)}" target="_blank"><img src="${esc(p)}" alt="หลักฐานการส่ง"></a>`).join('')}</div>` : '') +
        (d.status === 'delivered' ? `<div class="countdown">⏳ ระบบปล่อยเงินอัตโนมัติใน <b data-until-short="${d.auto_release_at}">${durShort(d.auto_release_at - d.deal_now)}</b> (24 ชม. หลังส่ง) หากไม่มีการแจ้งปัญหา</div>` : '')});
  } else {
    it.push({t: 'นัดรับ – ผู้ซื้อกรอกรหัส 4 หลัก', m: d.completed_at && d.release_reason === 'meet_code' ? `${dTime(d.completed_at)} · รหัสถูกต้อง ปล่อยเงินทันที` : 'ภายใน ' + dDate(d.due_date) + ' · ผู้ซื้อตรวจของแล้วกรอกรหัสจากผู้ขาย', done: !!d.completed_at});
  }
  if (d.disputed_at) it.push({t: 'ผู้ซื้อแจ้งปัญหา', m: `${dTime(d.disputed_at)} · ${esc(d.dispute_reason)}`, done: d.status !== 'disputed', now: d.status === 'disputed'});
  if (d.status === 'refunded') it.push({t: d.resolution === 'late' ? 'คืนเงินผู้ซื้อ (ส่งช้าเกินกำหนด)' : 'คืนเงินผู้ซื้อเต็มจำนวน', m: `${dTime(d.refunded_at)} · ${baht(d.refund_amount)} (จำลอง)`, done: true});
  else if (d.status === 'cancelled') it.push({t: 'ยกเลิกดีล', m: dTime(d.cancelled_at), done: true});
  else {
    if (d.delivery !== 'meet' || d.status === 'partial') it.push({t: d.status === 'partial' ? 'ทีมงานตัดสินแบ่งเงิน' : 'ยืนยันรับของ', m: d.completed_at ? `${dTime(d.completed_at)} · ${{buyer_confirm: 'ผู้ซื้อกดยืนยัน', auto: 'ระบบยืนยันอัตโนมัติ (ครบกำหนด)', admin: 'ทีมงานตัดสินให้ปล่อยเงิน'}[d.release_reason] || 'คืนผู้ซื้อ ' + baht(d.refund_amount)}` : 'ผู้ซื้อกดยืนยันว่าได้รับสินค้าครบถ้วน', done: !!d.completed_at});
    const paidOut = d.payout && d.payout.status === 'paid';
    it.push({t: 'โอนเงินให้ผู้ขาย', m: d.completed_at ? (d.payout ? (paidOut ? 'โอนแล้ว (จำลอง)' : `${baht(d.payout_amount)} · รอโอนรอบถัดไป (วันละครั้ง)`) : 'รวมยอดโอนวันละครั้ง (จำลอง)') : 'รวมยอดโอนวันละครั้ง (ทุกวัน 18:00 น.) เข้าบัญชีที่ผูกไว้', done: !!d.completed_at && (paidOut || !d.payout), wait: !!d.completed_at});
  }
  const final = ['completed', 'refunded', 'cancelled', 'partial'].includes(d.status);
  let nowSet = it.some(x => x.now);
  return `<div class="card"><h3>ความคืบหน้า</h3><div class="tl">${it.map((x, i) => {
    let cls = x.done ? 'done' : 'todo';
    if (x.now || (!x.done && !nowSet && (!final || x.wait))) { cls = 'now'; nowSet = true; }
    return `<div class="ti ${cls}"><div class="c">${cls === 'done' ? ic('check', 14) : i + 1}</div><div style="flex:1;min-width:0"><b>${x.t}</b><div class="meta">${x.m || ''}</div>${x.x || ''}</div></div>`;
  }).join('')}</div></div>`;
}
function dealReviews(d) {
  if (!d.reviews.length) return '';
  return `<div class="card"><h3>${ic('star', 18)}รีวิวในดีลนี้</h3>${d.reviews.map(r => `<div class="rev"><div class="h"><div class="who">${r.target_role === 'seller' ? 'ผู้ซื้อรีวิวผู้ขาย' : 'ผู้ขายรีวิวผู้ซื้อ'}</div>${stars(r.stars, 12)}</div>${r.text ? `<p>${esc(r.text)}</p>` : ''}</div>`).join('')}</div>`;
}
async function refreshDeal() { const {p, a} = route(); if (p === 'd') await vDeal(a); }
function dealAct(btn, action, body = {}) {
  busy(btn, async () => {
    await api(`/deals/${S.deal.code}/${action}`, body);
    const msg = {accept: 'รับดีลแล้ว ✓', cancel: 'ยกเลิกดีลแล้ว', 'simulate-delivered': 'จำลอง: พัสดุถึงผู้ซื้อแล้ว', skip: `เร่งเวลาไป ${body.hours >= 24 ? body.hours / 24 + ' วัน' : body.hours + ' ชม.'} แล้ว (ทดสอบ)`}[action];
    if (msg) toast(msg);
    const y = window.scrollY; await refreshDeal(); if (action === 'skip') window.scrollTo(0, y); else window.scrollTo(0, 0);
  });
}
function cancelDeal(btn) { if (confirm('ยกเลิกดีลนี้ใช่ไหม?')) dealAct(btn, 'cancel'); }
function lateRefund(btn) {
  if (!confirm('ขอเงินคืนเต็มจำนวน และยกเลิกดีลนี้ใช่ไหม?')) return;
  busy(btn, async () => { await api(`/deals/${S.deal.code}/late-refund`, {}); toast('คืนเงินแล้ว (จำลอง)'); await refreshDeal(); });
}
function meetSubmit(btn) {
  busy(btn, async () => {
    const c = $('#meetCode').value.trim();
    if (c.length !== 4) throw new Error('กรุณากรอกรหัส 4 หลัก');
    await api(`/deals/${S.deal.code}/meet-code`, {code: c}); toast('ยืนยันรับของแล้ว ปล่อยเงินให้ผู้ขายทันที 🎉'); await refreshDeal();
  });
}

/* ---------------- deal sheets ---------------- */
function paySheet() {
  const d = S.deal;
  openSheet(`<h2 style="text-align:center">สแกนจ่ายด้วยพร้อมเพย์</h2>
    <div class="paytest">โหมดทดลอง – ไม่มีเงินจริง<small>ไม่ต้องสแกน ไม่ต้องโอนเงิน กดปุ่มด้านล่างเพื่อจำลองการจ่าย</small></div>
    <div class="qrwrap">
      <div class="qrhead">THAI QR PAYMENT · PromptPay</div>
      <div style="display:flex;justify-content:center">${fakeQr(200, 29, d.code)}</div>
      <div class="prompt mt8" style="font-size:24px;font-weight:700;color:var(--navy)">${(+d.buyer_pay).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} ฿</div>
      <div class="small muted">บัญชีพักเงิน ดีลชัวร์ (ตัวอย่าง) · ดีล #${esc(d.code)}</div>
      <div class="demo mt8">QR จำลอง – สแกนไม่ได้</div>
    </div>
    ${noteHtml('info', 'เงินจะเข้าบัญชีพักเงินของดีลชัวร์ ไม่ได้โอนตรงไปผู้ขาย')}
    <button class="btn primary" id="payBtn" onclick="paySubmit(this)">${ic('check', 20)}จำลองว่าจ่ายแล้ว</button>`);
}
function paySubmit(btn) {
  busy(btn, async () => { await api(`/deals/${S.deal.code}/pay`, {}); closeSheet(); toast('ชำระเงินสำเร็จ (จำลอง) เงินถูกพักไว้แล้ว'); await refreshDeal(); });
}
function shipSheet() {
  const d = S.deal; S.ship = {carrier: 'Kerry Express', photos: []};
  if (d.delivery === 'parcel') {
    openSheet(`<h2>กรอกเลขพัสดุ</h2><p class="small muted">ผู้ซื้อจะได้รับแจ้งเตือนพร้อมเลขพัสดุทันที</p>
      <label class="lb">บริษัทขนส่ง</label>
      <div class="chips" id="carChips">${['Kerry Express', 'Flash Express', 'ไปรษณีย์ไทย (EMS)', 'J&T Express', 'อื่น ๆ'].map((c, i) => `<button class="chip${i ? '' : ' on'}" style="flex:0 1 auto" data-v="${c}">${c}</button>`).join('')}</div>
      <label class="lb">เลขพัสดุ</label>
      <input class="input" id="trk" maxlength="40" placeholder="เช่น TH0000TEST01" style="text-transform:uppercase;font-family:Prompt;letter-spacing:.5px">
      <button class="btn primary mt12" id="shipBtn" onclick="shipSubmit(this)">${ic('truck', 20)}ยืนยันส่งของแล้ว</button>`);
    $$('#carChips .chip').forEach(c => c.onclick = () => { $$('#carChips .chip').forEach(x => x.classList.remove('on')); c.classList.add('on'); S.ship.carrier = c.dataset.v; });
  } else {
    openSheet(`<h2>แนบหลักฐานการส่งแมสเซนเจอร์</h2><p class="small muted">ระบบจะปล่อยเงินอัตโนมัติ 24 ชม. หลังส่ง ถ้าผู้ซื้อไม่แจ้งปัญหา</p>
      <label class="lb">ลิงก์ติดตามไรเดอร์ / รายละเอียด</label>
      <textarea class="input" id="proofTxt" maxlength="300" placeholder="เช่น ลิงก์ติดตาม Grab, ชื่อไรเดอร์, ทะเบียนรถ"></textarea>
      <label class="lb">รูปตอนส่งของ <span class="opt">(ไม่บังคับ)</span></label>
      <div class="photos" id="proofPh"></div>
      <button class="btn primary mt12" id="shipBtn" onclick="shipSubmit(this)">${ic('bike', 20)}ยืนยันส่งของแล้ว</button>`);
    renderProofPh();
  }
}
function renderProofPh() {
  $('#proofPh').innerHTML = S.ship.photos.map(p => `<div class="ph"><img src="${p}" alt=""></div>`).join('') + (S.ship.photos.length < 4 ? `<div class="ph add" onclick="addProofPh()">＋<br>เพิ่มรูป</div>` : '');
}
function addProofPh() { pickFiles('image/*', true, async fs => { try { for (const f of fs.slice(0, 4 - S.ship.photos.length)) S.ship.photos.push(await resizeImage(f)); } catch (e) { toast(e.message); } renderProofPh(); }); }
function shipSubmit(btn) {
  busy(btn, async () => {
    const d = S.deal;
    const body = d.delivery === 'parcel' ? {tracking: $('#trk').value, carrier: S.ship.carrier} : {proof_text: $('#proofTxt').value, photos: S.ship.photos};
    await api(`/deals/${d.code}/ship`, body); closeSheet(); toast('บันทึกการส่งของแล้ว แจ้งผู้ซื้อแล้ว ✓'); await refreshDeal();
  });
}
function starPicker(id) {
  return `<div class="starpick" id="${id}">${[1, 2, 3, 4, 5].map(n => `<button type="button" aria-label="${n} ดาว" data-n="${n}" onclick="setStars('${id}',${n})">★</button>`).join('')}</div>`;
}
function setStars(id, n) { S.stars = n; $$('#' + id + ' button').forEach(b => b.classList.toggle('on', +b.dataset.n <= n)); }
function confirmSheet() {
  const d = S.deal; S.stars = 0;
  openSheet(`<h2>ยืนยันว่าได้รับของครบแล้ว?</h2>
    <p class="small muted">เมื่อยืนยัน เงิน ${baht(d.seller_get)} จะถูกรวมเข้ารอบโอนถัดไป (วันละครั้ง 18:00 น.) ให้ผู้ขาย และไม่สามารถยกเลิกได้</p>
    <label class="lb mt12">ให้คะแนนร้าน <span class="opt">(ไม่บังคับ)</span></label>${starPicker('cfStars')}
    <textarea class="input mt8" id="cfText" maxlength="300" placeholder="เขียนรีวิวสั้น ๆ (ไม่บังคับ)"></textarea>
    <button class="btn primary mt12" id="cfBtn" onclick="confirmSubmit(this)">${ic('check', 20)}ยืนยันรับของ</button>`);
}
function confirmSubmit(btn) {
  busy(btn, async () => {
    const code = S.deal.code;
    await api(`/deals/${code}/confirm`, {});
    if (S.stars) await api(`/deals/${code}/review`, {stars: S.stars, text: $('#cfText').value});
    closeSheet(); toast('ยืนยันรับของแล้ว ขอบคุณค่ะ 🎉'); await refreshDeal();
  });
}
function reviewSheet() {
  S.stars = 0; const d = S.deal;
  openSheet(`<h2>ให้คะแนน${d.my_role === 'buyer' ? 'ผู้ขาย' : 'ผู้ซื้อ'}</h2><p class="small muted">${esc(d.my_role === 'buyer' ? d.seller.shop_name : d.buyer.name)} · ${esc(d.title)}</p>
    <label class="lb mt12">คะแนน</label>${starPicker('rvStars')}
    <textarea class="input mt8" id="rvText" maxlength="300" placeholder="เขียนรีวิวสั้น ๆ (ไม่บังคับ)"></textarea>
    <button class="btn primary mt12" id="rvBtn" onclick="reviewSubmit(this)">ส่งรีวิว</button>`);
}
function reviewSubmit(btn) {
  busy(btn, async () => {
    if (!S.stars) throw new Error('กรุณาเลือกจำนวนดาว');
    await api(`/deals/${S.deal.code}/review`, {stars: S.stars, text: $('#rvText').value}); closeSheet(); toast('ขอบคุณสำหรับรีวิว ✓'); await refreshDeal();
  });
}
function disputeSheet() {
  S.disp = {reason: 'ของไม่ตรงปก', files: [], names: []};
  openSheet(`<h2>แจ้งปัญหาดีลนี้</h2>
    <div class="note err">${ic('warn', 16, 'color:var(--red)')}<div>แจ้งได้ภายใน <b>3 วันหลังของถึง</b> · ระหว่างตรวจสอบ เงินจะถูกพักไว้ ไม่โอนให้ผู้ขาย</div></div>
    <label class="lb">ปัญหาที่พบ</label>
    <div class="chips" id="dpChips">${['ของไม่ตรงปก', 'ของเสียหาย', 'ไม่ได้รับของ', 'ได้ไม่ครบ', 'อื่น ๆ'].map((c, i) => `<button class="chip${i ? '' : ' on'}" data-v="${c}">${c}</button>`).join('')}</div>
    <label class="lb">แนบคลิปแกะกล่อง หรือรูปหลักฐาน <span style="color:var(--red)">*</span></label>
    <div class="upload" id="dpUp" onclick="pickEvidence()">${ic('video', 26)}<br><b>แตะเพื่ออัปโหลดคลิปแกะกล่อง / รูป</b><br><span class="small">ถ่ายต่อเนื่องตั้งแต่ก่อนเปิดกล่อง เห็นใบปะหน้าชัดเจน (วิดีโอไม่เกิน 20 MB)</span></div>
    <label class="lb">รายละเอียดเพิ่มเติม</label>
    <textarea class="input" id="dpText" maxlength="1000" placeholder="อธิบายปัญหาที่พบ…"></textarea>
    <button class="btn danger mt12" id="dpBtn" style="background:var(--red);color:#fff;border:none" onclick="disputeSubmit(this)">ส่งเรื่องแจ้งปัญหา</button>`);
  $$('#dpChips .chip').forEach(c => c.onclick = () => { $$('#dpChips .chip').forEach(x => x.classList.remove('on')); c.classList.add('on'); S.disp.reason = c.dataset.v; });
}
function pickEvidence() {
  pickFiles('video/*,image/*', true, async files => {
    for (const f of files.slice(0, 4 - S.disp.files.length)) {
      try {
        if (f.type.startsWith('video/')) { if (f.size > 20 * 1024 * 1024) { toast('วิดีโอใหญ่เกิน 20 MB'); continue; } S.disp.files.push(await readDataUrl(f)); }
        else S.disp.files.push(await resizeImage(f));
        S.disp.names.push((f.type.startsWith('video/') ? '🎬 ' : '🖼 ') + f.name);
      } catch (e) { toast(e.message); }
    }
    const up = $('#dpUp'); if (up && S.disp.files.length) { up.classList.add('ok'); up.innerHTML = `${ic('check', 22)}<br><b>แนบแล้ว ${S.disp.files.length} ไฟล์</b><br><span class="small">${S.disp.names.map(esc).join('<br>')}</span><br><span class="small">แตะเพื่อเพิ่ม</span>`; }
  });
}
function disputeSubmit(btn) {
  busy(btn, async () => {
    if (!S.disp.files.length) throw new Error('กรุณาแนบคลิปแกะกล่องหรือรูปหลักฐานอย่างน้อย 1 ไฟล์');
    btn.textContent = 'กำลังอัปโหลด…';
    try { await api(`/deals/${S.deal.code}/dispute`, {reason: S.disp.reason, detail: $('#dpText').value, files: S.disp.files}); }
    finally { btn.textContent = 'ส่งเรื่องแจ้งปัญหา'; }
    closeSheet(); toast('ส่งเรื่องแล้ว ทีมงานจะติดต่อภายใน 24 ชม.'); await refreshDeal();
  });
}

/* ---------------- shop ---------------- */
function trustStats(s, u) {
  return `<div class="grid4">
    <div class="tstat"><div class="i" style="background:var(--tq-l);color:var(--tq-t)">${ic('check', 18)}</div><div><b>${fmt(s.sales)}</b><span>ขายสำเร็จ</span></div></div>
    <div class="tstat"><div class="i" style="background:var(--tq-l);color:var(--tq-t)">${ic('shield', 18)}</div><div><b>${s.dispute_rate}%</b><span>ข้อพิพาท</span></div></div>
    <div class="tstat"><div class="i" style="background:#FFF4DB;color:var(--amber)">${ic('truck', 18)}</div><div><b>${s.on_time_rate === null ? '–' : s.on_time_rate + '%'}</b><span>ส่งตรงเวลา</span></div></div>
    <div class="tstat"><div class="i" style="background:#FFEDE5;color:#C2410C">${ic('cal', 18)}</div><div><b>${since(u.member_since)}</b><span>เปิดร้านมา</span></div></div></div>`;
}
function reviewsCard(u, list, title = 'รีวิวจากผู้ซื้อ') {
  const s = u.stats, tot = s.reviews || 0;
  return `<div class="card"><h3>${title}</h3>${tot ? `<div style="display:flex;gap:14px;align-items:center;margin-bottom:6px">
      <div style="text-align:center"><div class="prompt" style="font-size:34px;font-weight:700;color:var(--navy);line-height:1">${s.rating.toFixed(1)}</div>${stars(s.rating, 12)}<div class="small muted">${fmt(tot)} รีวิว</div></div>
      <div class="bars" style="flex:1">${[5, 4, 3, 2, 1].map(n => `<div class="r">${n}<div class="bar"><i style="width:${(100 * (s.rating_dist[n] || 0) / tot).toFixed(1)}%"></i></div></div>`).join('')}</div></div>` : ''}
    ${list.length ? list.map(r => `<div class="rev"><div class="h"><div class="who"><span class="mini" style="background:${r.from_id % 2 ? '#14B8A6' : '#F59E0B'}">${esc([...r.from_name][0])}</span>${esc(r.from_name)}</div>${stars(r.stars, 12)}</div>${r.text ? `<p>${esc(r.text)}</p>` : ''}<div class="small muted">${r.target_role === 'buyer' ? 'รีวิวในฐานะผู้ซื้อ · ' : ''}${esc(r.title)} · ${ago(r.created_at)}</div></div>`).join('') : '<div class="empty-st">ยังไม่มีรีวิว</div>'}</div>`;
}
async function vShop(id) {
  const u = await api('/shops/' + encodeURIComponent(id)); S.shop = u;
  const s = u.stats, mine = S.me && S.me.id === u.id;
  const lv = l => `<div class="lv${s.level === l ? ' cur' : ''}">${s.level === l && l !== 'new' ? '★ ' : ''}${{new: 'ร้านใหม่', silver: 'ร้านเงิน', gold: 'ร้านทอง'}[l]}</div>`;
  $('#view').innerHTML = `<div class="cover"><div class="tools">
      <button class="icon-btn" aria-label="ย้อนกลับ" onclick="goBack()">${ic('back', 20)}</button>
      <button class="icon-btn" aria-label="แชร์ร้าน" onclick="copyText(location.origin+'/s/${u.id}','คัดลอกลิงก์ร้านแล้ว ✓')">${ic('share', 20)}</button></div></div>
    <div class="shophead card" style="margin:-44px 14px 12px">
      <div style="display:flex;gap:12px;align-items:flex-end;margin-top:-40px">
        <div class="avatar" style="width:76px;height:76px;font-size:30px;border:4px solid #fff">${esc(u.initial)}${u.verified ? `<span class="v" style="width:26px;height:26px;border-radius:13px">${ic('check', 14, 'color:#fff')}</span>` : ''}</div>
        <div style="padding-bottom:2px">${s.level === 'gold' ? '<span class="badge b-gold" style="font-size:12.5px;padding:3px 10px">🏆 ร้านทอง</span>' : levelBadge(s)}</div></div>
      <div style="margin-top:8px;display:flex;align-items:center;gap:6px;flex-wrap:wrap"><h2 style="font-size:19px;font-weight:600">${esc(u.shop_name)}</h2>${u.is_demo ? '<span class="demo">ร้านตัวอย่าง</span>' : ''}</div>
      <div class="small muted">${esc(u.shop_bio || 'เจ้าของร้าน: ' + u.name)}</div>
      <div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">${u.verified ? `<span class="badge b-green">${ic('shield', 12)}ร้านยืนยันตัวตนแล้ว</span>` : '<span class="badge b-silver">ยังไม่ยืนยันตัวตน</span>'}
        <span class="badge b-blue"><span class="stars" style="font-size:11px">★</span>${s.rating ? s.rating.toFixed(1) + ' (' + fmt(s.reviews) + ' รีวิว)' : 'ยังไม่มีรีวิว'}</span></div>
      <div class="levels">${lv('new')}${lv('silver')}${lv('gold')}</div>
      <details class="rules"><summary>ระดับร้านคิดยังไง? · วงเงินตอนนี้ ${fmt(s.seller_limit)} ฿/ดีล</summary>
        <table><tr><th>ระดับ</th><th>ดีลสำเร็จ</th><th>ดาว</th><th>ข้อพิพาท</th><th>วงเงิน/ดีล</th></tr>
        <tr><td>ร้านใหม่</td><td>–</td><td>–</td><td>–</td><td>5,000 ฿</td></tr>
        ${u.levels.slice().reverse().map(l => `<tr><td>${l.name}</td><td>${l.min_deals}+</td><td>${l.min_stars}+</td><td>≤${l.max_dispute}%</td><td>${fmt(l.limit)} ฿</td></tr>`).join('')}</table></details>
    </div>
    <div class="wrap" style="padding-top:0">
      <div class="card"><h3>คะแนนความน่าเชื่อถือ</h3>${trustStats(s, u)}
        <a class="btn ghost sm mt12" href="#/u/${u.id}">${ic('user', 16)}ดูประวัติดีลและโปรไฟล์</a></div>
      <div class="card"><h3>สินค้าในร้าน <span class="muted small" style="font-weight:400;margin-left:auto">${u.products.length} รายการ</span></h3>
        ${mine ? `<button class="btn ghost sm" style="margin-bottom:12px" onclick="productSheet()">${ic('plus', 16)}เพิ่มสินค้าในร้าน</button>` : ''}
        ${u.products.length ? `<div class="pgrid">${u.products.map(p => `<div class="pcard"><div class="img" style="${p.photos[0] ? `background-image:url('${esc(p.photos[0])}')` : ''}">${p.photos[0] ? '' : `<div style="display:grid;place-items:center;height:100%;color:var(--tq-d)">${ic('box', 40)}</div>`}<span class="badge b-green">${p.deliveries.map(x => DLV[x][0]).join(' ')}</span></div>
          <div class="b"><div class="t">${esc(p.title)}</div><div class="p">${baht(p.price)}</div>
          ${mine ? `<button class="btn ghost sm" onclick="delProduct(this,${p.id})">ซ่อนสินค้า</button>` : `<button class="btn primary sm" onclick="buySheet(${p.id})">ซื้อแบบปลอดภัย</button>`}</div></div>`).join('')}</div>`
          : `<div class="empty-st">${mine ? 'ยังไม่มีสินค้า เพิ่มสินค้าเพื่อให้ลูกค้ากดซื้อแบบปลอดภัยได้เลย' : 'ร้านนี้ยังไม่มีสินค้า'}</div>`}</div>
      ${reviewsCard(u, u.reviews)}
      ${mine ? noteHtml('info', 'แชร์ลิงก์หน้าร้านในโพสต์ Facebook / LINE ได้เลย ลูกค้ากด “ซื้อแบบปลอดภัย” แล้วจ่ายผ่านระบบพักเงิน') : ''}
    </div>`;
}
function buySheet(pid) {
  if (!S.me) { S.after = location.hash; location.hash = '#/login'; toast('กรุณาเข้าสู่ระบบก่อนสั่งซื้อ'); return; }
  const p = S.shop.products.find(x => x.id === pid); S.buy = {pid, delivery: p.deliveries[0]};
  const f = calcFee(p.price, p.fee_payer);
  openSheet(`<h2>ซื้อแบบปลอดภัย</h2>
    <div style="display:flex;gap:12px;align-items:center;margin:6px 0 4px">${thumb(p.photos[0])}<div><b>${esc(p.title)}</b><div class="small muted">${esc(p.description || '')}</div></div></div>
    <label class="lb">วิธีส่งมอบ</label>
    <div class="chips" id="buyChips">${p.deliveries.map((x, i) => `<button class="chip${i ? '' : ' on'}" data-v="${x}">${ic(DLV[x][2])}${DLV[x][1]}</button>`).join('')}</div>
    <div class="card fee mt12" style="margin-bottom:0;box-shadow:none">
      <div class="r"><span class="muted">ราคาสินค้า</span><b>${baht(p.price)}</b></div>
      <div class="r"><span class="muted">ค่าธรรมเนียมส่วนของคุณ (${FEEP[p.fee_payer]})</span><b>${baht(f.b)}</b></div>
      <div class="r tot"><span>ยอดที่ต้องจ่าย</span><b>${baht(f.buyer)}</b></div></div>
    <p class="small muted mt8">ร้านจะส่งของภายใน ${p.ship_days} วัน · ถ้าเกินกำหนด ขอเงินคืนได้</p>
    ${p.price > S.me.stats.buyer_limit ? noteHtml('err', `ผู้ใช้ใหม่ซื้อได้สูงสุด ${fmt(S.me.stats.buyer_limit)} บาท/ดีล — ทำดีลสำเร็จครบ 5 ดีลเพื่อปลดล็อกวงเงิน`)
      : p.price > 3000 && !S.me.verified ? noteHtml('warn', 'สินค้านี้เกิน 3,000 บาท ต้องยืนยันตัวตนก่อน <button class="link" onclick="idSheet()">ยืนยันเลย →</button>') : ''}
    <button class="btn primary mt12" id="buyBtn" onclick="buySubmit(this)">${ic('shield', 20)}สั่งซื้อ แล้วไปจ่ายเงิน</button>`);
  $$('#buyChips .chip').forEach(c => c.onclick = () => { $$('#buyChips .chip').forEach(x => x.classList.remove('on')); c.classList.add('on'); S.buy.delivery = c.dataset.v; });
}
function buySubmit(btn) {
  busy(btn, async () => { const r = await api(`/products/${S.buy.pid}/buy`, {delivery: S.buy.delivery}); closeSheet(); toast('สร้างคำสั่งซื้อแล้ว จ่ายเงินเข้าระบบพักเงินได้เลย'); location.hash = '#/d/' + r.code; });
}
function productSheet() {
  S.prod = {photos: [], deliveries: ['parcel'], fee: 'half'};
  openSheet(`<h2>เพิ่มสินค้าในร้าน</h2>
    <label class="lb">ชื่อสินค้า</label><input class="input" id="pTitle" maxlength="120" placeholder="เช่น เสื้อวินเทจ ไซซ์ L">
    <label class="lb">ราคา (บาท)</label><div class="price-wrap"><input class="input" id="pPrice" inputmode="numeric" placeholder="0"><span>บาท</span></div>
    <label class="lb">รายละเอียด <span class="opt">(ไม่บังคับ)</span></label><textarea class="input" id="pDesc" maxlength="500"></textarea>
    <label class="lb">รูปสินค้า</label><div class="photos" id="pPh"></div>
    <label class="lb">วิธีส่งมอบที่รับได้ <span class="opt">(เลือกได้หลายแบบ)</span></label>
    <div class="chips" id="pDl">${Object.keys(DLV).map(k => `<button class="chip${k === 'parcel' ? ' on' : ''}" data-v="${k}">${ic(DLV[k][2])}${DLV[k][1]}</button>`).join('')}</div>
    <label class="lb">ใครจ่ายค่าธรรมเนียม?</label>
    <div class="seg" id="pFee"><button data-v="buyer">ผู้ซื้อ</button><button data-v="seller">ผู้ขาย</button><button class="on" data-v="half">คนละครึ่ง</button></div>
    <label class="lb">ส่งของภายในกี่วัน</label><input class="input" id="pDays" type="number" min="1" max="14" value="3">
    <button class="btn primary mt12" id="pBtn" onclick="productSubmit(this)">บันทึกสินค้า</button>`);
  renderProdPh();
  $$('#pDl .chip').forEach(c => c.onclick = () => { c.classList.toggle('on'); S.prod.deliveries = $$('#pDl .chip.on').map(x => x.dataset.v); });
  $$('#pFee button').forEach(b => b.onclick = () => { $$('#pFee button').forEach(x => x.classList.remove('on')); b.classList.add('on'); S.prod.fee = b.dataset.v; });
  $('#pPrice').oninput = e => { const raw = e.target.value.replace(/[^\d]/g, ''); e.target.value = raw ? Number(raw).toLocaleString('en-US') : ''; };
}
function renderProdPh() {
  $('#pPh').innerHTML = S.prod.photos.map(p => `<div class="ph"><img src="${p}" alt=""></div>`).join('') + (S.prod.photos.length < 6 ? `<div class="ph add" onclick="addProdPh()">＋<br>เพิ่มรูป</div>` : '');
}
function addProdPh() { pickFiles('image/*', true, async fs => { try { for (const f of fs.slice(0, 6 - S.prod.photos.length)) S.prod.photos.push(await resizeImage(f)); } catch (e) { toast(e.message); } renderProdPh(); }); }
function productSubmit(btn) {
  busy(btn, async () => {
    if (!S.prod.deliveries.length) throw new Error('เลือกวิธีส่งมอบอย่างน้อย 1 แบบ');
    await api('/products', {title: $('#pTitle').value, price: $('#pPrice').value.replace(/,/g, ''), description: $('#pDesc').value, photos: S.prod.photos, deliveries: S.prod.deliveries, fee_payer: S.prod.fee, ship_days: $('#pDays').value});
    closeSheet(); toast('เพิ่มสินค้าแล้ว ✓'); await vShop(route().a);
  });
}
function delProduct(btn, id) { if (confirm('ซ่อนสินค้านี้จากหน้าร้าน?')) busy(btn, async () => { await api(`/products/${id}/delete`, {}); toast('ซ่อนสินค้าแล้ว'); await vShop(route().a); }); }

/* ---------------- profile & account ---------------- */
async function vUser(id) {
  const u = await api('/users/' + encodeURIComponent(id)); const s = u.stats;
  $('#view').innerHTML = header({title: 'โปรไฟล์', back: true}) + `<div class="wrap">
    <div class="card"><div class="seller">${avatar(u)}<div style="flex:1;min-width:0">
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap"><b class="prompt" style="font-size:17px">${esc(u.name)}</b>${demoTag(u)}</div>
      ${u.shop_name !== u.name ? `<div class="small muted">ร้าน: ${esc(u.shop_name)}</div>` : ''}
      <div style="display:flex;gap:6px;margin-top:4px;flex-wrap:wrap">${verBadge(u)}${levelBadge(s)}</div></div></div>
      <div class="stats">
        <div class="stat"><b>${fmt(s.sales)}</b><span>ขายสำเร็จ</span></div>
        <div class="stat"><b>${fmt(s.buys)}</b><span>ซื้อสำเร็จ</span></div>
        <div class="stat"><b>${since(u.member_since)}</b><span>ใช้งานมา</span></div>
        <div class="stat"><b>${s.rating ? '★ ' + s.rating.toFixed(1) : '–'}</b><span>ดาวผู้ขาย (${fmt(s.reviews)})</span></div>
        <div class="stat"><b>${s.buyer_rating ? '★ ' + s.buyer_rating.toFixed(1) : '–'}</b><span>ดาวผู้ซื้อ (${fmt(s.buyer_reviews)})</span></div>
        <div class="stat"><b>${s.dispute_rate}%</b><span>ข้อพิพาท</span></div>
      </div>
      <a class="btn ghost sm mt12" href="#/shop/${u.id}">${ic('store', 16)}ดูหน้าร้าน${u.product_count ? ` (${u.product_count} สินค้า)` : ''}</a></div>
    <div class="card"><h3>${ic('list', 18)}ประวัติดีล <span class="muted small" style="font-weight:400;margin-left:auto">ล่าสุด ${u.history.length} ดีล</span></h3>
      ${u.history.length ? u.history.map(h => `<div class="hist"><div class="grow"><div class="ell"><b>${esc(h.title)}</b></div><div class="small muted">${h.role === 'seller' ? 'ขาย' : 'ซื้อ'} · ${h.at ? dShort(h.at) : ''}</div></div>
        <div style="text-align:right">${h.code ? `<a class="small" href="#/d/${h.code}">${baht(h.price)}</a>` : `<span class="small">${baht(h.price)}</span>`}<br>${stLabel(h.status, h.role)}</div></div>`).join('') : '<div class="empty-st">ยังไม่มีดีลที่จบแล้ว</div>'}</div>
    ${reviewsCard(u, u.reviews, 'รีวิวที่ได้รับ')}</div>`;
}
async function vMe() {
  const [pay] = await Promise.all([api('/payouts'), loadMe()]); const u = S.me, s = u.stats;
  $('#view').innerHTML = header({title: 'บัญชีของฉัน', sub: 'โปรไฟล์ · ยืนยันตัวตน · เงินที่รอโอน'}) + `<div class="wrap">
    <div class="card"><div class="seller">${avatar(u)}<div class="grow"><b class="prompt" style="font-size:17px">${esc(u.name)}</b><div class="small muted">${esc(u.phone)}</div>
      <div style="display:flex;gap:6px;margin-top:4px;flex-wrap:wrap">${verBadge(u)}${levelBadge(s)}</div></div></div>
      <div class="stats"><div class="stat"><b>${fmt(s.sales)}</b><span>ขายสำเร็จ</span></div><div class="stat"><b>${fmt(s.buys)}</b><span>ซื้อสำเร็จ</span></div><div class="stat"><b>${s.rating ? '★ ' + s.rating.toFixed(1) : '–'}</b><span>ดาวผู้ขาย</span></div></div>
      <div class="twobtn mt12"><a class="btn ghost sm" href="#/u/${u.id}">โปรไฟล์สาธารณะ</a><a class="btn ghost sm" href="#/shop/${u.id}">หน้าร้านของฉัน</a></div></div>
    <div class="card"><h3>${ic('wallet', 18)}เงินขายของฉัน</h3>
      <div class="row2"><div class="grow"><div class="small muted">รอโอนรอบถัดไป (วันละครั้ง 18:00 น.)</div><b class="prompt" style="font-size:22px;color:var(--tq-t)">${baht(pay.pending)}</b></div><span class="badge b-green">จำลอง</span></div>
      ${pay.items.length ? pay.items.slice(0, 8).map(p => `<div class="hist"><a class="grow ell" href="#/d/${p.code}">${esc(p.title)}</a><div style="text-align:right"><b class="small">${baht(p.amount)}</b><br>${p.status === 'pending' ? '<span class="spill sp-wait">รอโอนรอบถัดไป (วันละครั้ง)</span>' : '<span class="spill sp-done">โอนแล้ว (จำลอง)</span>'}</div></div>`).join('') : '<p class="small muted mt8">ยังไม่มีเงินขาย</p>'}
      <p class="small muted mt8">ในแอปจริง: ผูกบัญชีธนาคาร / พร้อมเพย์ เพื่อรับเงิน (ยังไม่เปิดในโหมดทดลอง)</p></div>
    <div class="card"><h3>${ic('shield', 18)}ยืนยันตัวตน</h3>
      ${u.verified ? noteHtml('ok', '<b>ยืนยันตัวตนแล้ว</b> (ทดสอบ – อนุมัติอัตโนมัติ) สร้างดีลเกิน 3,000 บาทได้') : `<p class="small muted">จำเป็นสำหรับดีลที่เกิน 3,000 บาท</p><button class="btn primary sm mt8" onclick="idSheet()">ยืนยันตัวตน (ทดสอบ)</button>`}
      <p class="small muted mt8">วงเงินต่อดีลตอนนี้: ขาย ${fmt(s.seller_limit)} ฿ (${s.level_name}) · ซื้อ ${fmt(s.buyer_limit)} ฿</p></div>
    <div class="card"><h3>${ic('user', 18)}แก้ไขข้อมูล</h3>
      <label class="lb">ชื่อที่ใช้แสดง</label><input class="input" id="meName" maxlength="60" value="${esc(u.name)}">
      <label class="lb">ชื่อร้าน <span class="opt">(ไม่บังคับ)</span></label><input class="input" id="meShop" maxlength="60" value="${u.shop_name !== u.name ? esc(u.shop_name) : ''}" placeholder="เช่น ร้านของสะสมคุณเอ">
      <label class="lb">คำอธิบายร้าน <span class="opt">(ไม่บังคับ)</span></label><input class="input" id="meBio" maxlength="200" value="${esc(u.shop_bio)}" placeholder="เช่น ของสะสมวินเทจ · กรุงเทพฯ">
      <button class="btn primary sm mt12" onclick="saveMe(this)">บันทึก</button></div>
    <div class="card"><h3>เชื่อมต่อบัญชี <span class="demo" style="margin-left:auto">เร็ว ๆ นี้</span></h3>
      <div class="soon"><button disabled><span class="ic" style="background:#06C755">LINE</span>LINE</button><button disabled><span class="ic" style="background:#1877F2">f</span>Facebook</button></div></div>
    <button class="btn danger" onclick="logout()">ออกจากระบบ</button>
    <p class="footer-note">ดีลชัวร์ (DealSure) ต้นแบบ · โหมดทดลอง – ไม่มีเงินจริง</p></div>`;
}
function saveMe(btn) { busy(btn, async () => { await api('/me/update', {name: $('#meName').value, shop_name: $('#meShop').value, shop_bio: $('#meBio').value}); toast('บันทึกแล้ว ✓'); await vMe(); }); }

/* ---------------- live updates ---------------- */
setInterval(() => {
  const t = Date.now() / 1000 + S.offset;
  $$('[data-until]').forEach(e => e.textContent = dur(+e.dataset.until - t));
  $$('[data-until-short]').forEach(e => e.textContent = durShort(+e.dataset.untilShort - t));
}, 1000);
setInterval(async () => {
  if (!S.me || document.hidden) return;
  try {
    const r = await api('/notifications');
    if (r.unread !== S.unread) { S.unread = r.unread; updateDots(); }
    if ($('#notif').classList.contains('open')) { S.notifs = r.items; renderNotif(); }
    const {p, a} = route(), busyUI = sheetOpen() || $('#notif').classList.contains('open') || ['INPUT', 'TEXTAREA'].includes((document.activeElement || {}).tagName);
    if (p === 'd' && S.deal && !busyUI) {
      const d = await api('/deals/' + encodeURIComponent(a));
      if (JSON.stringify(d) !== S.dealSig) { const y = window.scrollY; await vDeal(a); window.scrollTo(0, y); }
    }
  } catch (e) { /* ignore background errors */ }
}, 6000);

/* ---------------- boot ---------------- */
(async function boot() {
  const m = location.pathname.match(/^\/(d|s)\/([A-Za-z0-9-]+)/);
  if (m) history.replaceState(null, '', '/#/' + (m[1] === 'd' ? 'd/' + m[2].toUpperCase() : 'shop/' + m[2]));
  try { await loadMe(); } catch (e) { /* offline */ }
  window.addEventListener('hashchange', () => { navDepth++; render(); });
  render();
})();
