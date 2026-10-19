'use strict';
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const baht = n => { const v = Math.round((+n || 0) * 100) / 100; return v.toLocaleString('en-US', {minimumFractionDigits: v % 1 ? 2 : 0, maximumFractionDigits: 2}) + ' ฿'; };
const DL = {parcel: 'ส่งพัสดุ', meet: 'นัดรับ', messenger: 'แมสเซนเจอร์'};
const dFull = ts => ts ? new Intl.DateTimeFormat('th-TH', {day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit', timeZone:'Asia/Bangkok'}).format(new Date(ts * 1000)) : '-';
const ST = {open:'รอรับดีล', accepted:'รอจ่าย', held:'พักเงิน', shipped:'กำลังส่ง', delivered:'ของถึงแล้ว', disputed:'ข้อพิพาท', completed:'สำเร็จ', refunded:'คืนเงิน', partial:'คืนบางส่วน', cancelled:'ยกเลิก'};
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
    <div class="card"><h3><svg width="18" height="18" style="color:var(--red)!important"><use href="#warn"/></svg>ข้อพิพาทรอตัดสิน</h3>
      ${r.disputes.length ? r.disputes.map(d => `<div class="card" style="box-shadow:none;border:1.5px solid #F6C6C6" id="dp-${d.code}">
        <div class="row2"><b class="prompt grow">#${esc(d.code)} · ${esc(d.title)}</b><span class="spill sp-red">${esc(d.dispute_reason)}</span></div>
        <div class="small muted">ผู้ขาย: ${esc(d.seller_name)} · ผู้ซื้อ: ${esc(d.buyer_name)} · ${DL[d.delivery] || d.delivery} · แจ้งเมื่อ ${dFull(d.disputed_at)}</div>
        <div class="small">ผู้ซื้อจ่าย <b>${baht(d.buyer_pay)}</b> · ผู้ขายจะได้ (ถ้าปล่อยเงิน) <b>${baht(d.seller_get)}</b> · เลขพัสดุ ${esc(d.tracking || '-')}</div>
        ${d.dispute_detail ? `<div class="proof">${esc(d.dispute_detail)}</div>` : ''}
        <div class="gallery">${files(d.dispute_files)}</div>
        <label class="lb">บันทึกถึงทั้งสองฝ่าย (ไม่บังคับ)</label><input class="input" id="note-${d.code}" maxlength="300" placeholder="เช่น ตรวจคลิปแล้ว ของเสียหายจริง">
        <div class="twobtn mt12"><button class="btn primary sm" onclick="resolve('${d.code}','refund')">คืนเงินผู้ซื้อทั้งหมด</button><button class="btn ghost sm" onclick="resolve('${d.code}','release')">ปล่อยเงินให้ผู้ขาย</button></div>
        <div class="codein mt8"><input class="input" id="amt-${d.code}" inputmode="decimal" placeholder="คืนผู้ซื้อ (บาท)" style="max-width:none;flex:1"><button class="btn ghost sm" style="flex:1" onclick="resolve('${d.code}','partial')">คืนบางส่วน</button></div>
      </div>`).join('') : '<div class="empty-st">ไม่มีข้อพิพาทค้างอยู่ 🎉</div>'}</div>
    <div class="card"><h3><svg width="18" height="18"><use href="#wallet"/></svg>รอโอนรอบถัดไป (วันละครั้ง 18:00 น.)</h3>
      ${r.payouts.length ? `<table class="atable"><tr><th>ผู้ขาย</th><th>ดีล</th><th>ยอด</th></tr>${r.payouts.map(p => `<tr><td>${esc(p.name)}</td><td>#${esc(p.code)}</td><td>${baht(p.amount)}</td></tr>`).join('')}</table>
        <button class="btn primary sm mt12" onclick="runPayout()">จำลองรอบโอนวันนี้ (โอนทั้งหมด)</button>` : '<div class="empty-st">ไม่มียอดรอโอน</div>'}</div>
    <div class="card"><h3><svg width="18" height="18"><use href="#list"/></svg>ดีลล่าสุด (ไม่รวมข้อมูลตัวอย่าง)</h3>
      <div style="overflow-x:auto"><table class="atable"><tr><th>รหัส</th><th>สินค้า</th><th>ผู้ขาย → ผู้ซื้อ</th><th>ยอด</th><th>สถานะ</th><th>สร้างเมื่อ</th></tr>
      ${r.recent.map(d => `<tr><td>${esc(d.code)}</td><td>${esc(d.title)}</td><td>${esc(d.seller_name)} → ${esc(d.buyer_name)}</td><td>${baht(d.buyer_pay)}</td><td>${ST[d.status] || d.status}</td><td>${dFull(d.created_at)}</td></tr>`).join('')}</table></div></div>
    <div class="card"><h3><svg width="18" height="18"><use href="#shield"/></svg>ยืนยันตัวตน (ทดสอบ – อนุมัติอัตโนมัติ)</h3>
      ${r.ids.length ? `<table class="atable"><tr><th>ชื่อ</th><th>เบอร์</th><th>รูปที่ส่ง</th><th>เมื่อ</th></tr>${r.ids.map(u => `<tr><td>${esc(u.name)}</td><td>${esc(u.phone)}</td><td>${u.id_doc ? `<a href="${esc(u.id_doc)}" target="_blank">ดูรูป</a>` : '-'}</td><td>${dFull(u.id_verified_at)}</td></tr>`).join('')}</table>` : '<div class="empty-st">ยังไม่มี</div>'}</div>
    <button class="btn ghost sm" onclick="load()">รีเฟรช</button>`;
}
async function resolve(code, decision) {
  const label = {refund: 'คืนเงินผู้ซื้อทั้งหมด', release: 'ปล่อยเงินให้ผู้ขาย', partial: 'คืนเงินบางส่วน'}[decision];
  if (!confirm(`ยืนยัน: ${label} สำหรับดีล #${code}?`)) return;
  try { await api(`/admin/deals/${code}/resolve`, {decision, note: $('#note-' + code).value, refund_amount: $('#amt-' + code).value}); toast('บันทึกผลการตัดสินแล้ว แจ้งทั้งสองฝ่ายแล้ว'); load(); } catch (e) { toast(e.message); }
}
async function runPayout() { try { const r = await api('/admin/payouts/run', {}); toast(`จำลองโอนเงินให้ผู้ขาย ${r.users} คนแล้ว`); load(); } catch (e) { toast(e.message); } }
load();
