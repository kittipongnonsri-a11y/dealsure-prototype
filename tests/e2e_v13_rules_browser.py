"""v13 browser: วิธีจ่าย/ค่าธรรมเนียมบัตร · ค่าดำเนินการยกเลิก · วงเงินร้านใหม่ 3,000 · ระงับเมื่อค้างค่าปรับ
วิธีรัน: python3 tests/e2e_v13_rules_browser.py [http://localhost:8787]"""
import os, re, sys, time
from playwright.sync_api import sync_playwright, expect

def admin_password():
    import os
    pw = os.environ.get('ADMIN_PASSWORD')
    if pw: return pw
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'admin_password.txt')
    if os.path.exists(fp): return open(fp).read().strip()
    sys.exit('ตั้ง ADMIN_PASSWORD')

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8787'
if not BASE.startswith(('http://localhost', 'http://127.0.0.1')): sys.exit('รันกับเซิร์ฟเวอร์ในเครื่องเท่านั้น')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'screenshots', 'v13')
os.makedirs(OUT, exist_ok=True)
errors = []
stamp = str(int(time.time()))[-6:]

def phone(browser, label):
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                              locale='th-TH', timezone_id='Asia/Bangkok')
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errors.append(f'[{label}] {e}'))
    return pg

def shot(pg, name, full=False):
    pg.wait_for_timeout(400)
    pg.evaluate("document.querySelector('#toast') && document.querySelector('#toast').classList.remove('show')")
    pg.wait_for_timeout(200)
    pg.evaluate('document.fonts.ready')
    pg.screenshot(path=os.path.join(OUT, name + '.png'), full_page=full)
    print('  📸', name)

def login(pg, name, tel):
    expect(pg.locator('#lgName')).to_be_visible()
    pg.fill('#lgName', name); pg.fill('#lgPhone', tel); pg.click('#lgBtn')
    expect(pg.locator('#otpShow')).to_be_visible()
    code = pg.locator('#otpShow').inner_text().replace('\n', '').strip()
    pg.fill('#lgCode', code); pg.click('#lgVerify')
    pg.wait_for_selector('#tabbar:not(.hidden)')

def wait_text(pg, t, timeout=10000):
    expect(pg.locator(f'text={t}').first).to_be_visible(timeout=timeout)



import json
from datetime import datetime, timedelta, timezone
DUE = (datetime.now(timezone(timedelta(hours=7))) + timedelta(days=2)).strftime('%Y-%m-%d')
def post(pg, path, body):
    r = pg.request.post(BASE + '/api' + path, data=json.dumps(body), headers={'Content-Type': 'application/json'})
    assert r.ok, (path, r.status, r.text()[:200]); return r.json()
def scroll(pg, sel): pg.evaluate(f"document.querySelector('{sel}').scrollIntoView({{block:'center'}})")

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    S = phone(br, 'seller'); B = phone(br, 'buyer')
    S.goto(BASE + '/'); login(S, 'ร้านใหม่ v13', '090' + stamp + '1')
    B.goto(BASE + '/'); login(B, 'ผู้ซื้อ v13', '091' + stamp + '2')

    print('1) หน้าจ่าย: เลือกพร้อมเพย์ / บัตร (+ค่าธรรมเนียมบัตร)')
    code = post(S, '/deals', {'role': 'seller', 'title': 'หูฟังไร้สาย (ทดสอบ v13)', 'price': 1000, 'delivery': 'parcel', 'due_date': DUE, 'fee_payer': 'half'})['code']
    post(B, f'/deals/{code}/accept', {})
    B.goto(BASE + f'/#/d/{code}'); B.click('text=จ่ายด้วย')
    expect(B.locator('#payMethod button.on')).to_contain_text('พร้อมเพย์')
    expect(B.locator('#payTotal')).to_have_text('1,015 ฿')
    shot(B, '01-pay-promptpay-default')
    B.click('#payMethod [data-m=card]')
    expect(B.locator('#cardFeeRow')).to_contain_text('51.60')
    expect(B.locator('#payTotal')).to_contain_text('1,066.60')
    scroll(B, '#payCharges'); shot(B, '02-pay-card-surcharge')
    B.click('#payBtn'); B.wait_for_selector('#buyerCancelBtn')

    print('2) ยกเลิกก่อนส่งของ: แสดงค่าดำเนินการ + ค่าธรรมเนียมบัตรไม่คืน')
    B.click('#buyerCancelBtn'); expect(B.locator('#cancelBreak')).to_contain_text('ไม่คืน')
    expect(B.locator('#cancelBreak')).to_contain_text('994.70')
    shot(B, '03-cancel-preview-processing-charge')
    B.click('text=ไม่ยกเลิก')
    c2 = post(S, '/deals', {'role': 'seller', 'title': 'กระเป๋าผ้า (ทดสอบ v13)', 'price': 1500, 'delivery': 'parcel', 'due_date': DUE, 'fee_payer': 'half'})['code']
    post(B, f'/deals/{c2}/accept', {}); post(B, f'/deals/{c2}/pay', {'method': 'promptpay'})
    B.goto(BASE + f'/#/d/{c2}'); B.click('#buyerCancelBtn'); expect(B.locator('#cancelBreak')).to_contain_text('31.95')
    shot(B, '04-cancel-preview-promptpay-cost-plus-5')
    B.click('text=ไม่ยกเลิก')

    print('3) ร้านใหม่ (ขายสำเร็จ < 5 ดีล) สร้างดีลเกิน 3,000 ไม่ได้')
    S.goto(BASE + '/#/create'); expect(S.locator('#fTitle')).to_be_visible()
    S.fill('#fTitle', 'กล้องมือสอง (ทดสอบ v13)'); S.fill('#price', '3500')
    expect(S.locator('#newSellerLimit')).to_contain_text('ร้านใหม่ (ขายสำเร็จยังไม่ครบ 5 ดีล) สร้างดีลได้สูงสุด 3,000 บาท/ดีล')
    scroll(S, '#limitNotes'); shot(S, '05-new-seller-3000-limit')

    print('4) ค้างค่าปรับ → ระงับสร้างดีล/โอนออก')
    S.goto(BASE + f'/#/d/{code}'); S.click('#sellerCancelBtn'); S.click('#cxBtn'); S.wait_for_timeout(800)
    S.goto(BASE + '/#/create'); expect(S.locator('#fTitle')).to_be_visible(); S.fill('#price', '500')
    expect(S.locator('#penaltyBlock')).to_contain_text('ค่าปรับค้างชำระ')
    scroll(S, '#limitNotes'); shot(S, '06-blocked-by-penalty-create')
    S.fill('#fTitle', 'ของทดสอบ'); S.click('#createBtn'); wait_text(S, 'ต้องชำระให้ครบก่อน')
    shot(S, '06b-blocked-by-penalty-error')
    S.goto(BASE + '/#/me'); S.wait_for_selector('#payPenaltyBtn')
    scroll(S, '#penaltyBox'); shot(S, '07-blocked-by-penalty-payouts')
    S.click('#payPenaltyBtn'); S.wait_for_timeout(800)
    assert S.locator('#payPenaltyBtn').count() == 0
    br.close()
print('ข้อผิดพลาด JS:', errors or 'ไม่มี'); sys.exit(1 if errors else 0)
