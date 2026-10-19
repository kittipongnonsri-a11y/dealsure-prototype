'use strict';
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const baht = n => { const v = Math.round((+n || 0) * 100) / 100; return v.toLocaleString('en-US', {minimumFractionDigits: v % 1 ? 2 : 0, maximumFractionDigits: 2}) + ' ฿'; };
const DL = {parcel: 'ส่งพัสดุ', meet: 'นัดรับ', messenger: 'แมสเซนเจอร์', stay: '🏠 ดีลที่พัก'};
const dFull = ts => ts ? new Intl.DateTimeFormat('th-TH', {day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit', timeZone:'Asia/Bangkok'}).format(new Date(ts * 1000)) : '-';
const ST = {open:'รอรับดีล', accepted:'รอจ่าย', held:'พักเงิน', shipped:'กำลังส่ง', delivered:'ของถึงแล้ว', disputed:'ข้อพิพาท', completed:'สำเร็จ', refunded:'คืนเงิน', partial:'คืนบางส่วน', cancelled:'ยกเลิก'};
const ic = (id, n = 16) => `<svg width="${n}" height="${n}"><use href="#${id}"/></svg>`;
const ROLE = {seller: 'ผู้ขาย', buyer: 'ผู้ซื้อ', admin: 'ทีมงาน'};
const ROLE_STAY = {seller: 'เจ้าของที่พัก', buyer: 'ผู้เข้าพัก', admin: 'ทีมงาน'};
const TH = {}, PEND = {}, DRAFT = {};
const tm = ts => new Intl.DateTimeFormat('th-TH', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Bangkok'}).format(new Date(ts * 1000));
function av(u) {
  if (!u) return '<div class="avatar xs team"><svg viewBox="0 0 1024 1024"><use href="#logoA"/></svg></div>';
  return u.avatar ? `<div class="avatar xs has-img" style="--img:url('${esc(u.avatar)}')"></div>` : `<div class="avatar xs">${esc(u.initial)}</div>`;
}
function msgHtml(m, t, adminView) {
  const u = m.is_admin ? null : t.users[m.sender_id];
  const name = m.is_admin ? 'ทีมงานดีลชัวร์' : (m.role === 'seller' ? u.shop_name : u.name);
  const mine = adminView && m.is_admin;
  return `<div class="msg${mine ? ' me' : ''}${m.is_admin ? ' team' : ''}">${mine ? '' : `<div class="mav">${av(u)}</div>`}<div class="bw">
    <div class="who">${esc(name)} ${m.is_admin ? `<span class="badge b-team">${ic('shield', 11)}ทีมงาน</span>` : `<span class="rtag">${((t.deal && t.deal.kind === 'stay') ? ROLE_STAY : ROLE)[m.role] || ''}</span>`}</div>
    <div class="bub">${m.photos.length ? `<div class="mph n${Math.min(m.photos.length, 2)}">${m.photos.map(p => `<a href="${esc(p)}" target="_blank"><img src="${esc(p)}" alt="รูป"></a>`).join('')}</div>` : ''}${m.text ? `<div class="tx">${esc(m.text)}</div>` : ''}</div>
    ${m.warn ? `<div class="mwarn">${ic('warn', 13)}มีการพูดถึงการโอนเงิน/เลขบัญชี</div>` : ''}<div class="mt">${tm(m.created_at)}</div></div></div>`;
}
function threadMsgs(t, msgs, adminView = true) {
  return msgs.length ? msgs.map(m => msgHtml(m, t, adminView)).join('') : '<div class="chat-empty">ยังไม่มีข้อความ · เริ่มคุยกับผู้ซื้อและผู้ขายได้เลย</div>';
}
function pendHtml(id) { return (PEND[id] || []).map((p, i) => `<div class="ph"><img src="${p}" alt=""><button class="x" onclick="PEND[${id}].splice(${i},1);renderPend(${id})">✕</button></div>`).join(''); }
function renderPend(id) { const e = $('#apend-' + id); if (e) { e.innerHTML = pendHtml(id); e.classList.toggle('hidden', !(PEND[id] || []).length); } }
function resizeImage(file, max = 1280) {
  return new Promise((res, rej) => {
    const url = URL.createObjectURL(file), img = new Image();
    img.onload = () => { const k = Math.min(1, max / Math.max(img.width, img.height)); const c = document.createElement('canvas'); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k); c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url); res(c.toDataURL('image/jpeg', 0.82)); };
    img.onerror = () => rej(new Error('เปิดรูปนี้ไม่ได้')); img.src = url;
  });
}
function addPhoto(id) {
  const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*'; inp.multiple = true;
  inp.onchange = async () => { PEND[id] = PEND[id] || []; for (const f of [...inp.files].slice(0, 4 - PEND[id].length)) { try { PEND[id].push(await resizeImage(f)); } catch (e) { toast(e.message); } } renderPend(id); };
  inp.click();
}
async function sendMsg(id) {
  const ta = $('#amsg-' + id), btn = $('#asend-' + id), text = ta.value.trim();
  if (!text && !(PEND[id] || []).length) return toast('พิมพ์ข้อความหรือแนบรูปก่อนส่ง');
  btn.disabled = true;
  try {
    await api(`/admin/threads/${id}/messages`, {text, photos: PEND[id] || []});
    ta.value = ''; DRAFT[id] = ''; PEND[id] = []; renderPend(id); toast('ส่งข้อความถึงผู้ซื้อและผู้ขายแล้ว'); await pollThread(id, true);
  } catch (e) { toast(e.message); } finally { btn.disabled = false; }
}
async function pollThread(id, force) {
  const t = TH[id]; if (!t) return;
  const r = await api(`/admin/threads/${id}?after=${t.last_id}`);
  if (!r.messages.length && !force) return;
  t.messages.push(...r.messages.filter(m => m.id > t.last_id)); t.last_id = r.last_id || t.last_id; t.users = r.users;
  const box = $('#amsgs-' + id); if (box) { box.innerHTML = threadMsgs(t, t.messages); box.scrollTop = box.scrollHeight; }
  const u = $('#aunread-' + id); if (u) u.remove();
}
setInterval(() => { if (!document.hidden) Object.keys(TH).forEach(id => $('#amsgs-' + id) && pollThread(+id).catch(() => {})); }, 5000);
function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('show'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('show'), 2600); }
async function api(path, body) {
  const r = await fetch('/api' + path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const j = await r.json().catch(() => ({error: 'ผิดพลาด'}));
  if (!r.ok) { const e = new Error(j.error || 'ผิดพลาด'); e.status = r.status; throw e; }
  return j;
}
function loginView(msg) {
  $('#view').innerHTML = `<div class="card" style="max-width:420px;margin:0 auto"><h3>เข้าสู่ระบบแอดมิน</h3>
    ${msg ? `<div class="note err"><div>${esc(msg)}</div></div>` : ''}
    <label class="lb">รหัสผ่านแอดมิน (ดูใน README)</label><input class="input" id="pw" type="password">
    <button class="btn primary mt12" onclick="login()">เข้าสู่ระบบ</button></div>`;
  $('#pw').addEventListener('keydown', e => e.key === 'Enter' && login());
}
async function login() { try { await api('/admin/login', {password: $('#pw').value}); load(); } catch (e) { loginView(e.message); } }
async function load() {
  let r; try { r = await api('/admin/overview'); } catch (e) { if (e.status === 401) return loginView(); return toast(e.message); }
  const files = fs => fs.map(f => /\.(mp4|webm|mov)$/.test(f) ? `<video src="${esc(f)}" controls playsinline preload="metadata"></video>` : `<a href="${esc(f)}" target="_blank"><img src="${esc(f)}" alt="หลักฐาน"></a>`).join('');
  $('#view').innerHTML = `
    <div class="stats" style="margin:0 0 12px"><div class="stat" style="background:#fff"><b>${baht(r.held_total)}</b><span>เงินที่พักไว้ตอนนี้ (จำลอง)</span></div>
      <div class="stat" style="background:#fff"><b>${r.disputes.length}</b><span>ข้อพิพาทรอตัดสิน</span></div><div class="stat" style="background:#fff"><b>${r.users}</b><span>ผู้ใช้ (ไม่รวมตัวอย่าง)</span></div></div>
    ${flagsCard(r.flags || [])}
    <div class="card"><h3><svg width="18" height="18" style="color:var(--red)!important"><use href="#warn"/></svg>ข้อพิพาทรอตัดสิน</h3>
      ${r.disputes.length ? r.disputes.map(d => `<div class="card" style="box-shadow:none;border:1.5px solid #F6C6C6" id="dp-${d.code}">
        <div class="row2"><b class="prompt grow">#${esc(d.code)} · ${esc(d.title)}</b><span class="spill sp-red">${esc(d.dispute_reason)}</span></div>
        ${d.kind === 'stay' ? `<div class="small muted">เจ้าของที่พัก: ${esc(d.seller_name)} · ผู้เข้าพัก: ${esc(d.buyer_name)} · 🏠 ดีลที่พัก · แจ้งเมื่อ ${dFull(d.disputed_at)}</div>
        <div class="small">ผู้เข้าพักจ่าย <b>${baht(d.buyer_pay)}</b> · เจ้าของจะได้ (ถ้าปล่อยเงิน) <b>${baht(d.seller_get)}</b> · เช็คอิน <b>${dFull(d.checkin_at)}</b> · ${d.nights} คืน ${d.guests} คน</div>
        <div class="addr"><div><b>ที่อยู่ตามประกาศ:</b> ${esc(d.address || '-')} · ผู้ติดต่อ ${esc(d.host_contact || '-')}<br>${d.map_url ? `<a class="link" href="${esc(d.map_url)}" target="_blank" rel="noopener">📍 เปิด Google Maps ↗</a>` : ''}</div></div>
        ${d.dispute_location ? `<div class="proof">📍 ผู้เข้าพักอยู่ที่: ${esc(d.dispute_location)}</div>` : ''}`
        : `<div class="small muted">ผู้ขาย: ${esc(d.seller_name)} · ผู้ซื้อ: ${esc(d.buyer_name)} · ${DL[d.delivery] || d.delivery} · แจ้งเมื่อ ${dFull(d.disputed_at)}</div>
        <div class="small">ผู้ซื้อจ่าย <b>${baht(d.buyer_pay)}</b> · ผู้ขายจะได้ (ถ้าปล่อยเงิน) <b>${baht(d.seller_get)}</b> · เลขพัสดุ ${esc(d.tracking || '-')}</div>`}
        ${d.dispute_detail ? `<div class="proof">${esc(d.dispute_detail)}</div>` : ''}
        <div class="gallery">${files(d.dispute_files)}</div>
        <div class="admin-thread" id="athread-${d.thread.id}">
          <h4>${ic('chat', 18)}ข้อความถึง${d.kind === 'stay' ? 'ผู้เข้าพักและเจ้าของที่พัก' : 'ผู้ซื้อและผู้ขาย'} ${d.thread.unread ? `<span class="unread-pill" id="aunread-${d.thread.id}">ใหม่ ${d.thread.unread}</span>` : ''}<span class="small muted" style="font-weight:400;margin-left:auto">ทั้งสองฝ่ายเห็นข้อความนี้ในหน้าดีล + ได้แจ้งเตือน</span></h4>
          <div class="msgs" id="amsgs-${d.thread.id}">${threadMsgs(d.thread, d.thread.messages)}</div>
          <div class="composer">
            <div class="photos cpend hidden" id="apend-${d.thread.id}"></div>
            <div class="crow"><button class="cbtn" aria-label="แนบรูป" onclick="addPhoto(${d.thread.id})">${ic('camera', 22)}</button>
              <textarea class="input cin" id="amsg-${d.thread.id}" rows="1" maxlength="1000" placeholder="พิมพ์ในนามทีมงาน…" oninput="DRAFT[${d.thread.id}]=this.value">${esc(DRAFT[d.thread.id] || '')}</textarea>
              <button class="csend" id="asend-${d.thread.id}" aria-label="ส่ง" onclick="sendMsg(${d.thread.id})">${ic('send', 20)}</button></div></div>
          ${d.deal_chat.length ? `<details class="dchat"><summary>ดูแชทระหว่าง${d.kind === 'stay' ? 'ผู้เข้าพัก–เจ้าของที่พัก' : 'ผู้ซื้อ–ผู้ขาย'} (${d.deal_chat.length} ข้อความ · ใช้เป็นหลักฐาน)</summary><div class="msgs">${threadMsgs(d.thread, d.deal_chat, false)}</div></details>` : `<div class="small muted mt8">${d.kind === 'stay' ? 'ผู้เข้าพัก–เจ้าของที่พัก' : 'ผู้ซื้อ–ผู้ขาย'}ยังไม่เคยแชทกันในดีลนี้</div>`}
        </div>
        <div class="note mt8"><div class="small">ตัดสินจาก<b>หลักฐานการส่ง (เลขพัสดุ/รูปส่งมอบ) วิดีโอแพ็กของ วิดีโอแกะกล่อง และแชท</b> ·
          ${d.dispute_reason === 'ขอยกเลิกหลังหมดเวลายกเลิกฟรี' ? `ตัดสินให้ผู้เข้าพัก: ถือว่ายกเลิกเอง หักค่าดำเนินการ ${baht(Math.max(10, d.buyer_pay * 0.02))}` : `ตัดสินให้${d.kind === 'stay' ? 'ผู้เข้าพัก' : 'ผู้ซื้อ'}: ${d.kind === 'stay' ? 'เจ้าของ' : 'ผู้ขาย'}ผิด → ได้คืนเต็ม ${baht(d.buyer_pay)} + ค่าปรับ ${baht(d.fee)} · ตัดสินให้${d.kind === 'stay' ? 'เจ้าของ' : 'ผู้ขาย'}: ${d.kind === 'stay' ? 'ผู้เข้าพัก' : 'ผู้ซื้อ'}แพ้ข้อพิพาท (บันทึกประวัติ)`} ·
          แบ่งเงิน: ค่าธรรมเนียมคิดจากยอดที่${d.kind === 'stay' ? 'เจ้าของ' : 'ผู้ขาย'}ได้จริง (2% ขั้นต่ำ 20 ฿)</div></div>
        <label class="lb">บันทึกถึงทั้งสองฝ่าย (ไม่บังคับ)</label><input class="input" id="note-${d.code}" maxlength="300" placeholder="เช่น ตรวจคลิปแล้ว ของเสียหายจริง">
        <div class="twobtn mt12"><button class="btn primary sm" onclick="resolve('${d.code}','refund')">คืนเงิน${d.kind === 'stay' ? 'ผู้เข้าพัก' : 'ผู้ซื้อ'}ทั้งหมด</button><button class="btn ghost sm" onclick="resolve('${d.code}','release')">ปล่อยเงินให้${d.kind === 'stay' ? 'เจ้าของที่พัก' : 'ผู้ขาย'}</button></div>
        <div class="codein mt8"><input class="input" id="amt-${d.code}" inputmode="decimal" placeholder="คืน${d.kind === 'stay' ? 'ผู้เข้าพัก' : 'ผู้ซื้อ'} (บาท)" style="max-width:none;flex:1"><button class="btn ghost sm" style="flex:1" onclick="resolve('${d.code}','partial')">คืนบางส่วน</button></div>
      </div>`).join('') : '<div class="empty-st">ไม่มีข้อพิพาทค้างอยู่ 🎉</div>'}</div>
    <div class="card"><h3><svg width="18" height="18"><use href="#wallet"/></svg>รอโอนรอบถัดไป (วันละครั้ง 18:00 น.)</h3>
      ${r.payouts.length ? `<table class="atable"><tr><th>ผู้ขาย</th><th>ดีล</th><th>ยอด</th></tr>${r.payouts.map(p => `<tr><td>${esc(p.name)}</td><td>#${esc(p.code)}</td><td>${baht(p.amount)}</td></tr>`).join('')}</table>
        <p class="small muted mt8">โอนวันละ 1 ครั้ง/ผู้ขาย รวมทุกดีล · หักค่าโอนออก 30 ฿ (ฟรีเมื่อยอดรวม ≥ 1,000 ฿) และค่าปรับค้าง</p>
        <button class="btn primary sm mt12" onclick="runPayout()">จำลองรอบโอนวันนี้ (โอนทั้งหมด)</button>` : '<div class="empty-st">ไม่มียอดรอโอน</div>'}</div>
    <div class="card"><h3><svg width="18" height="18"><use href="#list"/></svg>ดีลล่าสุด (ไม่รวมข้อมูลตัวอย่าง)</h3>
      <div style="overflow-x:auto"><table class="atable"><tr><th>รหัส</th><th>สินค้า</th><th>ผู้ขาย → ผู้ซื้อ</th><th>ยอด</th><th>สถานะ</th><th>สร้างเมื่อ</th></tr>
      ${r.recent.map(d => `<tr><td>${esc(d.code)}</td><td>${d.kind === 'stay' ? '🏠 ' : ''}${esc(d.title)}</td><td>${esc(d.seller_name)} → ${esc(d.buyer_name)}</td><td>${baht(d.buyer_pay)}</td><td>${ST[d.status] || d.status}</td><td>${dFull(d.created_at)}</td></tr>`).join('')}</table></div></div>
    <div class="card"><h3><svg width="18" height="18"><use href="#shield"/></svg>ยืนยันตัวตน (ทดสอบ – อนุมัติอัตโนมัติ)</h3>
      ${r.ids.length ? `<table class="atable"><tr><th>ชื่อ</th><th>เบอร์</th><th>รูปที่ส่ง</th><th>เมื่อ</th></tr>${r.ids.map(u => `<tr><td>${esc(u.name)}</td><td>${esc(u.phone)}</td><td>${u.id_doc ? `<a href="${esc(u.id_doc)}" target="_blank">ดูรูป</a>` : '-'}</td><td>${dFull(u.id_verified_at)}</td></tr>`).join('')}</table>` : '<div class="empty-st">ยังไม่มี</div>'}</div>
    <button class="btn ghost sm" onclick="load()">รีเฟรช</button>`;
  for (const k of Object.keys(TH)) delete TH[k];
  r.disputes.forEach(d => { TH[d.thread.id] = d.thread; const b = $('#amsgs-' + d.thread.id); if (b) b.scrollTop = b.scrollHeight; });
}
function flagsCard(flags) {
  const pen = flags.filter(f => f.kind === 'penalty'), lost = flags.filter(f => f.kind === 'lost_dispute');
  const hot = flags.filter(f => f.flagged).length;
  const row = f => `<tr class="${f.flagged ? 'flag-hot' : ''}"><td>${esc(f.name)}<br><span class="small muted">${esc(f.phone)}</span></td><td><b>${f.count}</b> ครั้ง / ${f.days} วัน${f.kind === 'penalty' ? `<br><span class="small muted">รวม ${baht(f.total)}</span>` : ''}</td>
    <td>${f.flagged ? `<span class="spill sp-red">${f.kind === 'penalty' ? '⚠ ผิดซ้ำ ตรวจสอบร้าน' : '⚠ เสนอระงับบัญชี'}</span>` : '<span class="spill sp-gray">เฝ้าดู</span>'}</td></tr>`;
  return `<div class="card" id="flagsCard"><h3><svg width="18" height="18" style="color:var(--red)!important"><use href="#warn"/></svg>ผู้ใช้ที่ต้องจับตา ${hot ? `<span class="spill sp-red" style="margin-left:auto">${hot} รายเกินเกณฑ์</span>` : ''}</h3>
    ${hot ? `<div class="note err"><div><b>มีผู้ใช้เกินเกณฑ์ ${hot} ราย</b> — ผู้ขายโดนค่าปรับ ≥3 ครั้งใน 30 วัน หรือผู้ซื้อแพ้ข้อพิพาท ≥3 ครั้งใน 90 วัน</div></div>` : ''}
    <h4 class="mt8">ผู้ขาย/เจ้าของที่พักโดนค่าปรับ (30 วัน)</h4>
    ${pen.length ? `<table class="atable"><tr><th>ผู้ใช้</th><th>ค่าปรับ</th><th>สถานะ</th></tr>${pen.map(row).join('')}</table>` : '<div class="small muted">ไม่มี</div>'}
    <h4 class="mt12">ผู้ซื้อแพ้ข้อพิพาท (90 วัน)</h4>
    ${lost.length ? `<table class="atable"><tr><th>ผู้ใช้</th><th>แพ้ข้อพิพาท</th><th>สถานะ</th></tr>${lost.map(row).join('')}</table>` : '<div class="small muted">ไม่มี</div>'}</div>`;
}
async function resolve(code, decision) {
  const label = {refund: 'คืนเงินผู้ซื้อทั้งหมด', release: 'ปล่อยเงินให้ผู้ขาย', partial: 'คืนเงินบางส่วน'}[decision];
  if (!confirm(`ยืนยัน: ${label} สำหรับดีล #${code}?`)) return;
  try { await api(`/admin/deals/${code}/resolve`, {decision, note: $('#note-' + code).value, refund_amount: $('#amt-' + code).value}); toast('บันทึกผลการตัดสินแล้ว แจ้งทั้งสองฝ่ายแล้ว'); load(); } catch (e) { toast(e.message); }
}
async function runPayout() { try { const r = await api('/admin/payouts/run', {}); toast(`จำลองโอนเงินรอบวันนี้แล้ว (${r.users} คน · หักค่าโอน/ค่าปรับแล้ว)`); load(); } catch (e) { toast(e.message); } }
load();
