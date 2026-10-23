"""v12 browser: ค่าธรรมเนียม 3% (ขั้นต่ำ 20 บาท) ในหน้าสร้างดีล
วิธีรัน: python3 tests/e2e_v12_fee_browser.py [http://localhost:8787]"""
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
OUT = os.path.join(HERE, '..', 'screenshots', 'v12')
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
    S = phone(br, 'seller')
    S.goto(BASE + '/app'); login(S, 'ร้านค่าธรรมเนียม v12', '088' + stamp + '1')
    S.goto(BASE + '/app#/create'); S.wait_for_selector('#price')
    if S.locator('#fTitle').count(): S.fill('#fTitle', 'กล้องฟิล์ม (ทดสอบ v12)')
    S.fill('#price', '2500')
    expect(S.locator('#fFee')).to_contain_text('75')
    expect(S.locator('#fBuyer')).to_contain_text('2,537.50')
    expect(S.locator('text=ค่าธรรมเนียม 3%').first).to_be_visible()
    S.evaluate("document.querySelector('#fFee').closest('.card').scrollIntoView({block:'start'})")
    shot(S, '01-fee-preview-3pct')
    S.fill('#price', '500'); expect(S.locator('#fFee')).to_contain_text('20')
    S.evaluate("document.querySelector('#fFee').closest('.card').scrollIntoView({block:'start'})")
    shot(S, '02-fee-preview-min-20')
    br.close()
print('ข้อผิดพลาด JS:', errors or 'ไม่มี'); sys.exit(1 if errors else 0)
