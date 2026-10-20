"""v14 browser: จ่ายบัตรผ่าน Stripe Checkout (TEST MODE) ด้วยบัตรทดสอบ 4242 → กลับมาดีล held → ยกเลิก → คืนเงินผ่าน Stripe
ต้องเปิดเซิร์ฟเวอร์ด้วย STRIPE_TEST_SECRET_KEY=sk_test_... (ถ้าไม่เปิด จะถ่ายแค่หน้าจ่ายโหมดจำลอง)
วิธีรัน: python3 tests/e2e_v14_stripe_browser.py [http://localhost:8787]"""
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
OUT = os.path.join(HERE, '..', 'screenshots', 'v14')
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
    S.goto(BASE + '/'); login(S, 'ร้าน v14', '092' + stamp + '1')
    B.goto(BASE + '/'); login(B, 'ผู้ซื้อ v14', '093' + stamp + '2')
    code = post(S, '/deals', {'role': 'seller', 'title': 'หูฟังไร้สาย (ทดสอบ Stripe v14)', 'price': 1000, 'delivery': 'parcel', 'due_date': DUE, 'fee_payer': 'half'})['code']
    post(B, f'/deals/{code}/accept', {})
    on = B.request.get(BASE + f'/api/deals/{code}').json()['stripe']['enabled']
    print('Stripe เปิดอยู่:', on)
    B.goto(BASE + f'/#/d/{code}'); B.click('text=จ่ายด้วย')
    shot(B, '01-pay-sheet' + ('-stripe-test' if on else '-fake-mode'))
    B.click('#payMethod [data-m=card]'); expect(B.locator('#payTotal')).to_contain_text('1,066.60')
    shot(B, '02-pay-card' + ('-stripe-checkout-button' if on else '-fake-mode'))
    if on:
        expect(B.locator('#stripeBox')).to_contain_text('TEST MODE')
        B.click('#payBtn'); B.wait_for_url('https://checkout.stripe.com/**', timeout=30000)
        B.wait_for_timeout(3000); shot(B, '03-stripe-checkout-page')
        acc = B.locator('[data-testid="card-accordion-item-button"], #payment-method-accordion-item-title-card')
        if acc.count() and acc.first.is_visible(): acc.first.click()
        B.wait_for_selector('#cardNumber', timeout=15000)
        em = B.locator('#email')
        assert B.locator('text=PromptPay').count() == 0, 'Checkout ต้องมีแต่บัตร'
        if em.count() and em.is_visible(): em.fill('buyer-test@example.com')
        B.fill('#cardNumber', '4242424242424242'); B.fill('#cardExpiry', '12 / 34'); B.fill('#cardCvc', '123')
        nm = B.locator('#billingName')
        if nm.count() and nm.is_visible(): nm.fill('Test Buyer')
        ctry = B.locator('#billingCountry')
        if ctry.count() and ctry.is_visible(): ctry.select_option('TH')
        shot(B, '04-stripe-checkout-test-card-4242')
        B.click('.SubmitButton')
        B.wait_for_url(BASE + '/**', timeout=60000)
        B.wait_for_selector('#buyerCancelBtn', timeout=20000)
        B.wait_for_timeout(500); B.evaluate('document.fonts.ready')
        B.screenshot(path=os.path.join(OUT, '05-back-paid-held.png')); print('  📸 05-back-paid-held')
        assert '?stripe_session' not in B.url, B.url
        d = B.request.get(BASE + f'/api/deals/{code}').json()
        assert d['status'] == 'held' and d['stripe']['paid'], d['status']
        B.click('#buyerCancelBtn'); expect(B.locator('#cancelBreak')).to_contain_text('994.70')
        shot(B, '06-cancel-preview-stripe')
        B.click('#cxBtn'); B.wait_for_timeout(2500)
        d = B.request.get(BASE + f'/api/deals/{code}').json()
        assert d['status'] == 'refunded' and d['stripe']['refunded'], d['status']
        shot(B, '07-refunded-via-stripe', full=True)
        print('  ✓ Checkout 4242 → held → ยกเลิก → คืนผ่าน Stripe')
    br.close()
print('ข้อผิดพลาด JS:', errors or 'ไม่มี')
sys.exit(1 if errors else 0)
