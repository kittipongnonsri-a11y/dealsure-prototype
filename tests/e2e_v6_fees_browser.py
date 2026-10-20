"""ทดสอบผ่านเบราว์เซอร์ (v6) ที่ 390px: ค่าธรรมเนียม/ค่าดำเนินการ/ค่าปรับ/ค่าโอนออก แสดงก่อนจ่ายและก่อนยืนยันยกเลิก
ภาพหน้าจอเก็บที่ screenshots/v6/
วิธีรัน: python3 tests/e2e_v6_fees_browser.py [http://localhost:8787]   (ห้ามรันกับเว็บจริง)"""
import os, re, sys, time
from playwright.sync_api import sync_playwright, expect

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'e2e_browser.py'), encoding='utf-8').read().split('\nwith sync_playwright() as p:')[0]
exec(compile(src, 'e2e_helpers', 'exec'))   # admin_password, BASE, phone(), login(), create_deal(), submit_deal(), wait_text(), errors, stamp
if not BASE.startswith(('http://localhost', 'http://127.0.0.1')): sys.exit('รันกับเซิร์ฟเวอร์ในเครื่องเท่านั้น')
OUT = os.path.join(HERE, '..', 'screenshots', 'v6')
os.makedirs(OUT, exist_ok=True)
shots = []
RULE = 'ค่าโอนออก 30 บาท/วัน ฟรีเมื่อยอดรวม 3,000 บาทขึ้นไป'


def snap(pg, name, full=False, el=None):
    pg.wait_for_timeout(450); pg.evaluate('document.fonts.ready')
    pg.evaluate("document.querySelector('#toast') && document.querySelector('#toast').classList.remove('show')"); pg.wait_for_timeout(300)
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='absolute')")
    path = os.path.join(OUT, name + '.png')
    (pg.locator(el).screenshot(path=path) if el else pg.screenshot(path=path, full_page=full))
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='')")
    w = pg.evaluate('[document.documentElement.scrollWidth, window.innerWidth]')
    if w[0] > w[1]: errors.append(f'{name}: เลื่อนแนวนอนได้ ({w[0]} > {w[1]})')
    shots.append(path); print('  📸', name)


def js_api(pg, path, body='{}'):
    return pg.evaluate(f"api({path!r}, {body})")


def api_deal(S, B, price, ship=False, confirm=False):
    code = S.evaluate(f"api('/deals', {{role:'seller', title:'ของทดสอบ v6 {price}', price:{price}, delivery:'parcel', due_date:todayStr(3), fee_payer:'half'}}).then(r => r.code)")
    B.evaluate(f"api('/deals/{code}/accept', {{}}).then(() => api('/deals/{code}/pay', {{}}))")
    if ship: S.evaluate(f"api('/deals/{code}/ship', {{tracking:'TH6V6{code[-4:]}', carrier:'Kerry Express'}})")
    if confirm: B.evaluate(f"api('/deals/{code}/confirm', {{}})")
    return code


with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    S = phone(br, 'ผู้ขาย'); B = phone(br, 'ผู้ซื้อ'); A = phone(br, 'แอดมิน')

    print('1) ผู้ขายสร้างดีล: ยอดขั้นต่ำ 100 + ตารางค่าธรรมเนียม/ค่าโอนออก/ถ้ายกเลิก')
    S.goto(BASE + '/'); login(S, 'ผู้ขาย v6 (ทดสอบ)', '0871' + stamp)
    create_deal(S, 'ลำโพงบลูทูธ มือสอง (ทดสอบ v6)', 80)
    expect(S.locator('#limitNotes')).to_contain_text('ยอดดีลขั้นต่ำ 100 บาท')
    S.click('#createBtn'); wait_text(S, 'ยอดดีลขั้นต่ำ 100 บาท')
    S.fill('#price', '1500')
    expect(S.locator('#fPayout')).to_contain_text(RULE)
    expect(S.locator('#fCancel')).to_contain_text('ค่าดำเนินการ 31.95 ฿')
    expect(S.locator('#fCancel')).to_contain_text('ได้คืนเต็ม 1,522.50 ฿')
    S.locator('#feeSeg').scroll_into_view_if_needed(); S.evaluate("document.querySelector('#feeSeg').closest('.card').scrollIntoView({block:'start'})")
    snap(S, '01-create-fee-breakdown')
    snap(S, '01b-create-fee-breakdown-card', el="xpath=//div[@id='feeSeg']/ancestor::div[contains(@class,'card')][1]")
    link = submit_deal(S); code1 = link.rsplit('/', 1)[1]

    print('2) ผู้ซื้อรับดีล → หน้าจ่ายเงินแสดงค่าใช้จ่ายทั้งหมดก่อนจ่าย')
    B.goto(link); B.click('text=เข้าสู่ระบบเพื่อรับดีล'); login(B, 'ผู้ซื้อ v6 (ทดสอบ)', '0872' + stamp)
    B.goto(link); B.click('text=รับดีล แล้วไปจ่ายเงิน'); B.wait_for_selector('text=จ่ายด้วย')
    B.click('text=จ่ายด้วย'); expect(B.locator('#payCharges')).to_contain_text('ค่าดำเนินการ 31.95 ฿')
    expect(B.locator('#payCharges')).to_contain_text('ค่าธรรมเนียมบัตร')
    B.evaluate("document.querySelector('#payCharges').scrollIntoView({block:'center'})"); snap(B, '02-pay-sheet-all-charges')
    B.click('#payBtn'); B.wait_for_selector('#buyerCancelBtn')

    print('3) ผู้ซื้อยกเลิกก่อนผู้ขายส่งของ → หน้ายืนยันแสดงค่าดำเนินการ')
    expect(B.locator('#buyerCancelBtn')).to_contain_text('ค่าดำเนินการ 31.95 ฿')
    B.click('#buyerCancelBtn'); expect(B.locator('#cancelBreak')).to_contain_text('−31.95 ฿')
    expect(B.locator('#cancelBreak')).to_contain_text('1,490.55 ฿'); expect(B.locator('#cxBtn')).to_contain_text('รับคืน 1,490.55 ฿')
    snap(B, '03-buyer-cancel-sheet-with-charge')
    B.click('#cxBtn'); wait_text(B, 'หักค่าดำเนินการ 31.95 ฿')
    snap(B, '04-buyer-cancelled-refund-minus-charge')

    print('5) หลังผู้ขายส่งของ ผู้ซื้อไม่มีปุ่มยกเลิก')
    code3 = api_deal(S, B, 900, ship=True)
    B.goto(BASE + '/#/d/' + code3); wait_text(B, 'ยกเลิกดีลไม่ได้')
    assert B.locator('#buyerCancelBtn').count() == 0 and B.locator('text=ยกเลิกดีล (').count() == 0
    snap(B, '07-buyer-after-ship-no-cancel')
    B.evaluate(f"api('/deals/{code3}/confirm', {{}})")

    print('4) ผู้ขายยกเลิกหลังผู้ซื้อจ่าย → หน้ายืนยันแสดงค่าปรับ')
    code2 = api_deal(S, B, 2000)
    S.goto(BASE + '/#/d/' + code2); S.wait_for_selector('#sellerCancelBtn')
    expect(S.locator('#sellerCancelBtn')).to_contain_text('ค่าปรับ 60 ฿')
    S.click('#sellerCancelBtn'); expect(S.locator('#cancelBreak')).to_contain_text('2,030 ฿'); expect(S.locator('#cancelBreak')).to_contain_text('60 ฿')
    snap(S, '05-seller-cancel-sheet-penalty')
    S.click('#cxBtn'); wait_text(S, 'หักจากยอดรอโอนทันที')
    snap(S, '06-seller-deal-penalty-note')

    print('6) หน้าเงินขายของฉัน: ยอดรวม − ค่าโอนออก − ค่าปรับ')
    S.goto(BASE + '/#/me'); S.wait_for_selector('#payoutCard')
    expect(S.locator('#payBreak')).to_contain_text('−30 ฿')        # 826.50 < 3,000 → ค่าโอนออก 30
    expect(S.locator('#payBreak')).to_contain_text('826.50 ฿')     # v13: ค่าปรับ 60 หักจากยอดรอโอนทันที 886.50 → 826.50
    expect(S.locator('#payBreak')).to_contain_text(RULE)
    expect(S.locator('#penaltyBox')).to_contain_text('หักแล้ว')
    expect(S.locator('#payNet')).to_have_text('796.50 ฿')          # 826.50 − ค่าโอน 30
    S.evaluate("document.querySelector('#payoutCard').scrollIntoView({block:'start'})")
    snap(S, '08-seller-payout-fee-penalty')
    snap(S, '08b-seller-payout-card', el='#payoutCard')

    print('7) ข้อตกลง /terms: หัวข้อค่าธรรมเนียม + สรุปสั้นๆ (ไม่มีหมายเหตุร่างข้อ 6.5)')
    B.goto(BASE + '/terms'); B.wait_for_selector('#s6')
    html = B.content()
    assert '[ร่าง:' not in html and 'อาจปรับก่อนเปิดใช้งานจริง' not in html, 'ยังมีหมายเหตุร่าง'
    expect(B.locator('#s6')).to_contain_text('ค่าที่สูงสุดระหว่าง 10 บาท, 2% ของยอดที่ผู้ซื้อจ่าย')
    expect(B.locator('#s6')).to_contain_text('ไม่มีค่าโอนออกเมื่อยอดรวมของวันนั้นตั้งแต่ 3,000 บาทขึ้นไป')
    expect(B.locator('.legal-sum')).to_contain_text('ผู้ซื้อยกเลิกไม่ได้')
    B.evaluate("document.querySelector('#s6').scrollIntoView({block:'start'})"); snap(B, '09-terms-fee-section')
    snap(B, '09b-terms-fee-section-full', el='#s6')
    snap(B, '10-terms-summary-box', el='.legal-sum')

    print('8) แอดมิน: ผู้ขายผิดซ้ำ 3 ครั้งใน 30 วัน → คำเตือน')
    B.goto(BASE + '/#/'); B.wait_for_selector('#tabbar:not(.hidden)')
    for pr in (500, 600):
        c = api_deal(S, B, pr); S.evaluate(f"api('/deals/{c}/cancel', {{}})")
    A.set_viewport_size({'width': 390, 'height': 844})
    A.goto(BASE + '/admin'); A.fill('#pw', admin_password()); A.click('button:has-text("เข้าสู่ระบบ")'); A.wait_for_selector('#flagsCard')
    expect(A.locator('#flagsCard')).to_contain_text('ผู้ขาย v6 (ทดสอบ)'); expect(A.locator('#flagsCard')).to_contain_text('ผิดซ้ำ')
    snap(A, '11-admin-repeat-offender-flag', el='#flagsCard')

    br.close()

print('\nภาพหน้าจอ:', len(shots))
missing = [s for s in shots if not os.path.exists(s) or os.path.getsize(s) < 2000]
if missing: errors.append(f'ไฟล์ภาพไม่ครบ: {missing}')
if errors:
    print('\n'.join('  ✗ ' + e for e in errors)); sys.exit(1)
print('  ✓ ผ่านทั้งหมด ไม่มี error ใน console และไม่เลื่อนแนวนอน')
