"""v9 browser: เลือกจากสินค้าขายประจำ · สร้างดีลจากหน้าร้าน · ที่พักให้จอง
วิธีรัน: python3 tests/e2e_v9_product_deal_browser.py [http://localhost:8787]"""
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
OUT = os.path.join(HERE, '..', 'screenshots', 'v9')
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

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    S = phone(br, 'seller'); B = phone(br, 'buyer')

    print('1) เข้าสู่ระบบร้านทองตัวอย่าง → สร้างดีล เห็นตัวเลือกสินค้าขายประจำ')
    S.goto(BASE + '/app')
    login(S, 'ป้าแดง (ทดสอบ v9)', '0800000001')
    wait_text(S, 'ดีลล่าสุด')
    S.goto(BASE + '/app#/create')
    wait_text(S, 'เลือกจากสินค้าขายประจำ')
    expect(S.locator('#tplPick')).to_be_visible()
    expect(S.locator('#tplRow .tpl-card').first).to_be_visible()
    shot(S, '01-create-picker')
    shot(S, '01b-create-picker-full', full=True)

    print('2) เลือกสินค้า → ฟอร์มถูกกรอก · แก้ราคา')
    # click first real product card (not blank)
    S.locator('#tplRow .tpl-card:not(.blank)').first.click()
    wait_text(S, 'ดึงข้อมูลจาก:')
    expect(S.locator('#fTitle')).not_to_have_value('')
    expect(S.locator('#tplNote')).to_be_visible()
    # edit price
    S.fill('#price', '2100')
    expect(S.locator('#fPrice')).to_contain_text('2,100')
    shot(S, '02-prefilled-edited-price')
    shot(S, '02b-prefilled-full', full=True)

    print('3) สร้างดีลจากหน้าร้าน (ปุ่ม สร้างดีลจากสินค้านี้)')
    S.goto(BASE + '/app#/myshop')
    wait_text(S, 'สินค้าขายประจำ')
    expect(S.locator('button:has-text("สร้างดีลจากสินค้านี้")').first).to_be_visible()
    shot(S, '03-shop-create-from-product')
    S.locator('button:has-text("สร้างดีลจากสินค้านี้")').first.click()
    wait_text(S, 'ดึงข้อมูลจาก:')
    expect(S.locator('#fTitle')).not_to_have_value('')
    shot(S, '03b-from-shop-prefilled')

    print('4) ที่พักให้จอง — หน้าร้านพี่ปุ้ย')
    B.goto(BASE + '/app')
    login(B, 'ผู้เข้าพัก v9', '0899' + stamp)
    sid = B.evaluate("fetch('/api/shops').then(r=>r.json()).then(j=>j.shops.find(s=>s.name==='พี่ปุ้ย (ตัวอย่าง)'|| (s.shop_name||'').includes('บ้านพักริมดอย')).id)")
    # find host by phone via shops list
    host = B.evaluate("""async () => {
      const j = await (await fetch('/api/shops')).json();
      const s = j.shops.find(x => (x.shop_name||x.name||'').includes('บ้านพักริมดอย') || (x.name||'').includes('ปุ้ย'));
      return s && s.id;
    }""")
    assert host, 'host shop not found'
    B.goto(BASE + f'/#/shop/{host}')
    wait_text(B, 'ที่พักให้จอง')
    expect(B.locator('#shopStays')).to_contain_text('ที่พักให้จอง')
    expect(B.locator('#shopStays')).not_to_contain_text('ที่พักในร้าน')
    B.locator('#shopStays').scroll_into_view_if_needed()
    shot(B, '04-stays-section-renamed')
    shot(B, '04b-stays-section-full', full=True)

    print('5) เจ้าของที่พักเห็นปุ่มเพิ่มที่พักให้จอง')
    H = phone(br, 'host')
    H.goto(BASE + '/app')
    login(H, 'พี่ปุ้ย (ทดสอบ)', '0800000003')
    H.goto(BASE + '/app#/myshop')
    wait_text(H, 'เพิ่มที่พักให้จอง')
    expect(H.locator('#addStayBtn')).to_contain_text('เพิ่มที่พักให้จอง')
    shot(H, '05-owner-add-stay-renamed')

    br.close()

print('\nJS errors:', errors or 'ไม่มี')
print('ภาพหน้าจอ:', len(os.listdir(OUT)), 'ไฟล์ →', OUT)
sys.exit(1 if errors else 0)
