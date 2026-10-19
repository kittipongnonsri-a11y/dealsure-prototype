"""ทดสอบผ่านเบราว์เซอร์ (v5) ที่ 390px: หน้าข้อตกลงการใช้บริการ /terms และนโยบายความเป็นส่วนตัว /privacy
+ ลิงก์จากหน้าเข้าสู่ระบบ หน้าบัญชี และท้ายหน้า · ภาพหน้าจอเก็บที่ screenshots/v5/
วิธีรัน: python3 tests/e2e_v5_legal_browser.py [http://localhost:8787]"""
import os, re, sys, time
from playwright.sync_api import sync_playwright, expect

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'e2e_browser.py'), encoding='utf-8').read().split('\nwith sync_playwright() as p:')[0]
exec(compile(src, 'e2e_helpers', 'exec'))   # BASE, phone(), login(), errors, stamp
OUT = os.path.join(HERE, '..', 'screenshots', 'v5')
os.makedirs(OUT, exist_ok=True)
shots = []


def snap(pg, name, full=False):
    pg.wait_for_timeout(400); pg.evaluate('document.fonts.ready')
    pg.evaluate("document.querySelector('#toast') && document.querySelector('#toast').classList.remove('show')"); pg.wait_for_timeout(350)
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='absolute')")
    path = os.path.join(OUT, name + '.png'); pg.screenshot(path=path, full_page=full)
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='')")
    w = pg.evaluate('[document.documentElement.scrollWidth, window.innerWidth]')
    if w[0] > w[1]: errors.append(f'{name}: เลื่อนแนวนอนได้ ({w[0]} > {w[1]})')
    shots.append(path); print('  📸', name)


def fonts_ok(pg, label):
    if not pg.evaluate("document.fonts.ready.then(() => document.fonts.check('600 16px Prompt', 'ข้อตกลง') && document.fonts.check('16px Sarabun', 'ข้อตกลง'))"):
        errors.append(f'{label}: ฟอนต์ไทย Prompt/Sarabun โหลดไม่ครบ')


with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    U = phone(br, 'ผู้ใช้')

    print('1) หน้าเข้าสู่ระบบมีข้อความยอมรับข้อตกลง + ลิงก์')
    U.goto(BASE + '/#/login'); U.wait_for_selector('#legalConsent'); fonts_ok(U, 'login')
    expect(U.locator('#legalConsent')).to_contain_text('การเข้าใช้งานถือว่าคุณยอมรับ')
    U.evaluate("document.querySelector('#legalConsent').scrollIntoView({block:'center'})"); snap(U, '01-login-consent-links')

    print('2) กดลิงก์ข้อตกลง → /terms')
    U.click('#legalConsent a[href="/terms"]'); U.wait_for_url(re.compile(r'/terms$')); U.wait_for_selector('.legal-sum')
    fonts_ok(U, 'terms')
    expect(U.locator('h1')).to_have_text('ข้อตกลงและเงื่อนไขการใช้บริการ')
    n = U.locator('.legal-sum li').count(); assert 5 <= n <= 7, n
    snap(U, '02-terms-top'); snap(U, '03-terms-full', full=True)
    U.click('.legal-toc summary'); U.wait_for_timeout(200)
    U.evaluate("document.querySelector('.legal-toc').scrollIntoView({block:'start'})"); snap(U, '04-terms-toc-open')
    U.click('.legal-toc a[href="#s10"]'); U.wait_for_timeout(300); snap(U, '05-terms-disputes-section')

    print('3) สลับไปนโยบายความเป็นส่วนตัว')
    U.evaluate('window.scrollTo(0,0)'); U.click('.legal-switch a[href="/privacy"]'); U.wait_for_url(re.compile(r'/privacy$'))
    U.wait_for_selector('.legal-sum'); fonts_ok(U, 'privacy')
    expect(U.locator('h1')).to_have_text('นโยบายความเป็นส่วนตัว')
    n = U.locator('.legal-sum li').count(); assert 5 <= n <= 7, n
    snap(U, '06-privacy-top'); snap(U, '07-privacy-full', full=True)
    U.evaluate("document.querySelector('#s7').scrollIntoView({block:'start'})"); snap(U, '08-privacy-retention-section')

    if '--no-login' not in sys.argv:
        print('4) หน้าบัญชีมีการ์ด “ข้อตกลงและนโยบาย” + ลิงก์ท้ายหน้า')
        U.goto(BASE + '/#/login'); login(U, 'ผู้ทดสอบเอกสาร', '0861' + stamp)
        expect(U.locator('.footer-note .legal-mini').first).to_be_visible()
        U.wait_for_timeout(2500); U.goto(BASE + '/#/me'); U.wait_for_selector('#legalCard')
        U.evaluate("document.querySelector('#legalCard').scrollIntoView({block:'center'})"); snap(U, '09-account-legal-card')
        U.click('#legalCard a[href="/privacy"]'); U.wait_for_url(re.compile(r'/privacy$')); U.wait_for_selector('.legal-sum')
        U.click('.top .icon-btn[aria-label="ย้อนกลับ"]'); U.wait_for_selector('#legalCard')  # ย้อนกลับมาหน้าบัญชีเดิม
    br.close()

print('\nภาพหน้าจอ:', len(shots), 'ไฟล์ →', os.path.abspath(OUT))
if errors:
    print('ไม่ผ่าน:'); [print('  ✗', e) for e in errors]; sys.exit(1)
print('ผ่านทั้งหมด ✓')
