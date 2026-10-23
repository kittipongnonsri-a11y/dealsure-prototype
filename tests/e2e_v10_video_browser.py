"""v10 browser: คลิปวิดีโอ (ไม่บังคับ) · คลิปแพ็คของ · ขอคลิปแกะกล่อง · แบนเนอร์เตือนผู้ซื้อ
วิธีรัน: python3 tests/e2e_v10_video_browser.py [http://localhost:8787]"""
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
OUT = os.path.join(HERE, '..', 'screenshots', 'v10')
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


import base64, json
VIDF = os.path.join(HERE, 'unboxing.mp4')
VID = 'data:video/mp4;base64,' + base64.b64encode(open(VIDF, 'rb').read()).decode()
from datetime import datetime, timedelta, timezone
DUE = (datetime.now(timezone(timedelta(hours=7))) + timedelta(days=2)).strftime('%Y-%m-%d')
def post(pg, path, body):
    r = pg.request.post(BASE + '/api' + path, data=json.dumps(body), headers={'Content-Type': 'application/json'})
    assert r.ok, (path, r.status, r.text()[:200]); return r.json()
def get(pg, path): return pg.request.get(BASE + '/api' + path).json()

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    S = phone(br, 'seller'); B = phone(br, 'buyer')
    S.goto(BASE + '/app'); login(S, 'ร้านคลิป v10', '086' + stamp + '1')
    B.goto(BASE + '/app'); login(B, 'ผู้ซื้อคลิป v10', '087' + stamp + '2')
    uid = get(S, '/me')['user']['id']

    print('1) สินค้าขายประจำมีคลิป → การ์ดมีไอคอนเล่น')
    post(S, '/products', {'title': 'กระเป๋าผ้า (มีคลิป)', 'price': 350, 'photos': [VID], 'deliveries': ['parcel']})
    post(S, '/products', {'title': 'พวงกุญแจ (ไม่มีคลิป)', 'price': 120, 'deliveries': ['parcel']})
    B.goto(BASE + f'/#/shop/{uid}'); wait_text(B, 'กระเป๋าผ้า (มีคลิป)')
    expect(B.locator('.pcard .play').first).to_be_visible()
    B.locator('.pcard .play').first.scroll_into_view_if_needed(); B.evaluate('window.scrollBy(0,150)'); shot(B, '01-product-card-video')

    print('2) แจ้งส่งของ — ช่องคลิปตอนแพ็คของ (ไม่บังคับ)')
    code = post(S, '/deals', {'role': 'seller', 'title': 'กระเป๋าผ้า (มีคลิป)', 'price': 350, 'delivery': 'parcel', 'due_date': DUE, 'fee_payer': 'half'})['code']
    post(B, f'/deals/{code}/accept', {}); post(B, f'/deals/{code}/pay', {})
    S.goto(BASE + f'/#/d/{code}'); S.locator('button:has-text("กรอกเลขพัสดุ")').click()
    wait_text(S, 'คลิปตอนแพ็คของ'); wait_text(S, 'แนบไว้เป็นหลักฐาน ช่วยให้ผู้ซื้อมั่นใจและใช้ตอนมีข้อพิพาทได้')
    S.fill('#trk', 'TH0000CLIP10')
    shot(S, '02-ship-step-clip-field')
    with S.expect_file_chooser() as fc: S.click('#packUp')
    fc.value.set_files(VIDF); wait_text(S, 'แนบคลิปแล้ว')
    shot(S, '02b-ship-step-clip-attached')
    S.click('#shipBtn'); expect(S.locator('#packVideo')).to_be_visible(timeout=15000)

    print('3) ผู้ขายกด "ขอคลิปตอนแกะกล่อง"')
    expect(S.locator('#reqUnboxBtn')).to_be_visible()
    S.locator('#clipsCard').scroll_into_view_if_needed(); shot(S, '03-seller-request-unbox-button')
    S.click('#reqUnboxBtn'); expect(S.locator('#unboxRequested')).to_be_visible()

    print('4) ผู้ซื้อ: เห็นแบนเนอร์เตือน + คลิปแพ็ค + ช่องแนบคลิปแกะกล่อง')
    B.goto(BASE + f'/#/d/{code}')
    expect(B.locator('#unboxTip')).to_contain_text('แนะนำให้ถ่ายคลิปตอนแกะกล่องไว้')
    expect(B.locator('#packVideo')).to_be_visible(); expect(B.locator('#unboxAsk')).to_contain_text('ผู้ขายขอคลิปตอนแกะกล่อง')
    B.locator('#unboxTip').scroll_into_view_if_needed(); shot(B, '04-buyer-reminder-banner')
    B.locator('#clipsCard').scroll_into_view_if_needed(); shot(B, '05-deal-page-pack-clip-and-upload-prompt')
    shot(B, '05b-deal-page-full', full=True)
    n = get(B, '/notifications')['items']
    assert any('ถ่ายคลิปตอนแกะกล่อง' in x['text'] for x in n), 'แจ้งเตือนส่งของไม่มีคำแนะนำ'

    print('5) หน้ายืนยันรับของ มีแบนเนอร์ และยืนยันได้โดยไม่ต้องแนบคลิป')
    B.locator('button:has-text("ยืนยันรับของ")').first.click()
    expect(B.locator('.sheet #unboxTip, #sheet #unboxTip').first).to_be_visible()
    shot(B, '06-confirm-receipt-reminder')
    B.click('#cfBtn'); wait_text(B, 'สำเร็จ', 15000)

    print('6) ดีลนัดรับ (meet) ไม่มีแบนเนอร์')
    c2 = post(S, '/deals', {'role': 'seller', 'title': 'ของนัดรับ', 'price': 200, 'delivery': 'meet', 'due_date': DUE, 'fee_payer': 'half'})['code']
    post(B, f'/deals/{c2}/accept', {}); post(B, f'/deals/{c2}/pay', {})
    B.goto(BASE + f'/#/d/{c2}'); wait_text(B, 'ของนัดรับ'); B.wait_for_timeout(500)
    assert B.locator('#unboxTip:visible').count() == 0, 'meet deal ไม่ควรมีแบนเนอร์'

    print('7) แจ้งปัญหา — ช่องคลิปตอนแกะกล่อง (ไม่บังคับ)')
    c3 = post(S, '/deals', {'role': 'seller', 'title': 'ของมีปัญหา', 'price': 250, 'delivery': 'parcel', 'due_date': DUE, 'fee_payer': 'half'})['code']
    post(B, f'/deals/{c3}/accept', {}); post(B, f'/deals/{c3}/pay', {})
    post(S, f'/deals/{c3}/ship', {'tracking': 'TH0000CLIP11', 'carrier': 'Kerry Express'})
    B.goto(BASE + f'/#/d/{c3}'); B.locator('button:has-text("แจ้งปัญหา")').first.click()
    wait_text(B, 'มีคลิปตอนแกะกล่องจะช่วยให้ทีมงานตัดสินเรื่องได้เร็วและชัดเจนขึ้น')
    shot(B, '07-dispute-unbox-clip-field')
    print('8) v11: ผู้ซื้อขอคลิปตอนแพ็คของ → ผู้ขายเห็นคำขอ')
    OUT11 = os.path.join(HERE, '..', 'screenshots', 'v11'); os.makedirs(OUT11, exist_ok=True)
    def shot11(pg, name, full=False):
        pg.wait_for_timeout(500); pg.evaluate("document.querySelector('#toast') && document.querySelector('#toast').classList.remove('show')")
        pg.screenshot(path=os.path.join(OUT11, name + '.png'), full_page=full); print('  📸 v11', name)
    c7 = post(S, '/deals', {'role': 'seller', 'title': 'เสื้อยืดลายแมว', 'price': 290, 'delivery': 'parcel', 'due_date': DUE, 'fee_payer': 'half'})['code']
    post(B, f'/deals/{c7}/accept', {}); post(B, f'/deals/{c7}/pay', {})
    B.goto(BASE + f'/#/d/{c7}'); expect(B.locator('#reqPackBtn')).to_be_visible()
    B.locator('#clipsCard').scroll_into_view_if_needed(); shot11(B, '01-buyer-request-pack-button')
    B.click('#reqPackBtn'); expect(B.locator('#packRequested')).to_contain_text('ส่งคำขอแล้ว · ผู้ขายต้องแนบคลิปก่อนส่งของ')
    shot11(B, '02-buyer-request-sent')
    S.goto(BASE + f'/#/d/{c7}'); expect(S.locator('#packAsk')).to_contain_text('ผู้ซื้อขอคลิปตอนแพ็คของ')
    S.locator('#packAsk').scroll_into_view_if_needed(); shot11(S, '03-seller-request-prompt-deal-page')
    S.locator('button:has-text("กรอกเลขพัสดุ")').click(); expect(S.locator('#packReqTip')).to_be_visible()
    wait_text(S, '(ผู้ซื้อขอ · ต้องแนบ)'); S.fill('#trk', 'TH0000CLIP12')
    expect(S.locator('#shipBtn')).to_be_disabled(); expect(S.locator('#packNeedMsg')).to_be_visible()
    shot11(S, '04-seller-ship-blocked-until-clip')
    with S.expect_file_chooser() as fc: S.click('#packUp')
    fc.value.set_files(VIDF); expect(S.locator('#shipBtn')).to_be_enabled()
    shot11(S, '05-seller-ship-clip-attached')
    S.click('#shipBtn'); expect(S.locator('#packVideo')).to_be_visible(timeout=15000)
    B.reload(); expect(B.locator('#packVideo')).to_be_visible(); B.wait_for_timeout(300)
    assert B.locator('#reqPackBtn').count() == 0
    br.close()

print('\nข้อผิดพลาด JS:', errors or 'ไม่มี')
sys.exit(1 if errors else 0)
