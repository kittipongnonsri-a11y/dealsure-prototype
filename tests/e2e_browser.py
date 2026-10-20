"""ทดสอบผ่านเบราว์เซอร์จริง (headless Chrome) จำลองมือถือ 2 เครื่อง: ผู้ขาย + ผู้ซื้อ
และถ่ายภาพหน้าจอไว้ที่ screenshots/
วิธีรัน: python3 tests/e2e_browser.py [http://localhost:8787]"""
import os, re, sys, time
from playwright.sync_api import sync_playwright, expect


def admin_password():
    """อ่านรหัสผู้ดูแลจาก env ADMIN_PASSWORD หรือไฟล์ data/admin_password.txt (กรณีเซิร์ฟเวอร์สุ่มให้)"""
    import os
    pw = os.environ.get('ADMIN_PASSWORD')
    if pw: return pw
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'admin_password.txt')
    if os.path.exists(fp): return open(fp).read().strip()
    sys.exit('ตั้งตัวแปร ADMIN_PASSWORD ให้ตรงกับเซิร์ฟเวอร์ก่อนรันทดสอบ')

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8787'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'screenshots')
os.makedirs(OUT, exist_ok=True)
errors = []
stamp = str(int(time.time()))[-6:]


def phone(browser, label):
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                              locale='th-TH', timezone_id='Asia/Bangkok', user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148')
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errors.append(f'[{label}] pageerror: {e}'))
    pg.on('console', lambda m: m.type == 'error' and 'Failed to load resource' not in m.text and errors.append(f'[{label}] console: {m.text}'))
    pg.on('dialog', lambda d: d.accept())
    return pg


def shot(pg, name, full=False, toast=False):
    pg.wait_for_timeout(450)
    if not toast: pg.evaluate("document.querySelector('#toast') && document.querySelector('#toast').classList.remove('show')"); pg.wait_for_timeout(300)
    pg.evaluate('document.fonts.ready')
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='absolute')")
    pg.screenshot(path=os.path.join(OUT, name + '.png'), full_page=full)
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='')")
    print('  📸', name)


def login(pg, name, tel, first_shots=False):
    expect(pg.locator('#lgName')).to_be_visible()
    pg.fill('#lgName', name); pg.fill('#lgPhone', tel)
    if first_shots: shot(pg, '01-login')
    pg.click('#lgBtn')
    expect(pg.locator('#otpShow')).to_be_visible()
    code = pg.locator('#otpShow').inner_text().replace('\n', '').strip()
    assert re.fullmatch(r'\d{6}', code), code
    if first_shots: shot(pg, '02-otp-demo-code')
    pg.fill('#lgCode', code); pg.click('#lgVerify')
    pg.wait_for_selector('#tabbar:not(.hidden)')


def upload(pg, click_sel, path):
    with pg.expect_file_chooser() as fc:
        pg.click(click_sel)
    fc.value.set_files(path)


def create_deal(pg, title, price, delivery='parcel', fee='half', photo=None, role='seller'):
    pg.goto(BASE + '/#/create'); expect(pg.locator('#fTitle')).to_be_visible()
    pg.click(f'#roleSeg [data-v={role}]')
    pg.fill('#fTitle', title); pg.fill('#price', str(price))
    pg.click(f'#delivChips [data-v={delivery}]'); pg.click(f'#feeSeg [data-v={fee}]')
    if photo:
        upload(pg, '.ph.add', photo); pg.wait_for_selector('#fPhotos img')


def submit_deal(pg):
    pg.click('#createBtn')
    expect(pg.locator('#shareUrl')).to_be_visible()
    return pg.locator('#shareUrl').inner_text().strip()


def wait_text(pg, text, timeout=8000):
    pg.wait_for_selector(f'text={text}', timeout=timeout)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    S = phone(br, 'ผู้ขาย'); B = phone(br, 'ผู้ซื้อ')

    print('1) ผู้ขายล็อกอิน (OTP แสดงบนจอ)')
    S.goto(BASE + '/'); login(S, 'น้องฝ้าย (ทดสอบ)', '0861' + stamp, first_shots=True)
    wait_text(S, 'ดีลล่าสุด'); shot(S, '03-home')

    print('2) ผู้ขายสร้างดีลส่งพัสดุ + รูป → ได้ลิงก์')
    create_deal(S, 'กล้องฟิล์ม Olympus มือสอง (ทดสอบ)', 2500, photo=os.path.join(HERE, 'camera.jpg'))
    S.fill('#fDesc', 'สภาพ 90% พร้อมสายคล้อง')
    shot(S, '04-create-deal', full=True)
    link = submit_deal(S)
    assert '/d/DS-' in link, link
    expect(S.locator('#lineShare')).to_have_attribute('href', re.compile(r'^https://line\.me/R/msg/text/\?'))
    shot(S, '05-share-link-sheet')
    S.click('text=ดูหน้าดีล'); wait_text(S, 'รออีกฝ่ายเปิดลิงก์')

    print('3) ผู้ซื้อ (มือถืออีกเครื่อง) เปิดลิงก์ → ล็อกอิน → รับดีล → จ่าย (จำลอง)')
    B.goto(link); wait_text(B, 'ดีลนี้ได้รับการคุ้มครอง'); shot(B, '06-buyer-opens-link', full=True)
    B.click('text=เข้าสู่ระบบเพื่อรับดีล'); login(B, 'คุณบีม (ทดสอบ)', '0862' + stamp)
    wait_text(B, 'รับดีล แล้วไปจ่ายเงิน'); shot(B, '07-buyer-sees-seller-profile')
    B.click('text=รับดีล แล้วไปจ่ายเงิน'); wait_text(B, 'PromptPay')
    B.click('text=จ่ายด้วย'); expect(B.locator('#payBtn')).to_be_visible()
    expect(B.locator('.paytest')).to_contain_text('โหมดทดลอง – ไม่มีเงินจริง')
    shot(B, '08-fake-promptpay')
    B.click('#payBtn'); wait_text(B, 'เงินพักไว้แล้ว'); shot(B, '09-buyer-money-held')

    print('4) ผู้ขายเห็นแจ้งเตือน → กรอกเลขพัสดุ')
    S.reload(); wait_text(S, 'กรอกเลขพัสดุ')
    S.click('.top .icon-btn[aria-label="การแจ้งเตือน"]'); wait_text(S, 'ผู้ซื้อจ่ายแล้ว'); shot(S, '10-seller-notification-bell')
    S.click('#notif .link'); S.click('button:has-text("กรอกเลขพัสดุ")')
    S.click('#carChips [data-v="Flash Express"]'); S.fill('#trk', 'TH0000TEST01'); shot(S, '11-seller-tracking-sheet')
    S.click('#shipBtn'); wait_text(S, 'กำลังจัดส่ง'); shot(S, '12-seller-shipped', full=True)

    print('5) ผู้ซื้อ: จำลองของถึง → นับถอยหลัง 3 วัน → ยืนยันรับของ + ให้ดาว')
    B.reload(); wait_text(B, 'จำลอง: ขนส่งแจ้งว่าของถึงแล้ว')
    B.click('text=จำลอง: ขนส่งแจ้งว่าของถึงแล้ว'); wait_text(B, 'ระบบจะโอนเงินให้ผู้ขายอัตโนมัติใน')
    shot(B, '13-buyer-delivered-countdown')
    B.click('text=เร่งเวลา (ทดสอบ) +1 วัน'); wait_text(B, 'ดีลนี้เร่งเวลาไปแล้ว')
    B.locator('.testbox').scroll_into_view_if_needed(); shot(B, '14-test-tools-skip-time')
    B.evaluate('window.scrollTo(0,0)')
    B.click('.twobtn >> text=ยืนยันรับของ'); B.click('#cfStars [data-n="5"]'); B.fill('#cfText', 'ของตรงปก ส่งไวมาก (ทดสอบ)')
    shot(B, '15-buyer-confirm-review')
    B.click('#cfBtn'); wait_text(B, 'ดีลสำเร็จ'); shot(B, '16-buyer-completed', full=True)

    print('6) ผู้ขาย: เงินรอโอนรอบถัดไป + รีวิวผู้ซื้อ')
    S.reload(); wait_text(S, 'รอโอนรอบถัดไป (วันละครั้ง)'); shot(S, '17-seller-payout-pending')
    S.click('text=ให้คะแนนผู้ซื้อ'); S.click('#rvStars [data-n="5"]'); S.fill('#rvText', 'จ่ายไว คุยง่าย'); S.click('#rvBtn'); wait_text(S, 'ผู้ขายรีวิวผู้ซื้อ')

    print('7) นัดรับ: ผู้ซื้อกรอกรหัส 4 หลักของผู้ขาย → ปล่อยเงินทันที')
    create_deal(S, 'แผ่นเสียงลูกกรุง (ทดสอบ)', 750, delivery='meet', fee='seller')
    link = submit_deal(S)
    B.goto(link); B.reload(); wait_text(B, 'รับดีล แล้วไปจ่ายเงิน'); B.click('text=รับดีล แล้วไปจ่ายเงิน')
    wait_text(B, 'PromptPay'); B.click('text=จ่ายด้วย'); B.click('#payBtn'); wait_text(B, 'เจอผู้ขายแล้ว?')
    S.goto(link); S.reload(); wait_text(S, 'รหัสนัดรับของคุณ')
    code = S.locator('#meetShow').inner_text().replace('\n', '').strip(); assert re.fullmatch(r'\d{4}', code), code
    shot(S, '18-meetup-seller-code')
    B.fill('#meetCode', '0000' if code != '0000' else '1111'); B.click('.codein .btn'); B.wait_for_timeout(600)
    B.fill('#meetCode', code); shot(B, '19-meetup-buyer-enters-code')
    B.click('.codein .btn'); wait_text(B, 'ดีลสำเร็จ')

    print('8) ข้อพิพาท: ผู้ซื้อแจ้งปัญหา + แนบคลิป → แอดมินตัดสินคืนบางส่วน')
    create_deal(S, 'วิทยุวินเทจ (ทดสอบ)', 1890, delivery='parcel', fee='buyer')
    link = submit_deal(S)
    B.goto(link); B.reload(); B.click('text=รับดีล แล้วไปจ่ายเงิน'); wait_text(B, 'PromptPay'); B.click('text=จ่ายด้วย'); B.click('#payBtn'); wait_text(B, 'เงินพักไว้แล้ว')
    S.goto(link); S.reload(); S.click('button:has-text("กรอกเลขพัสดุ")'); S.fill('#trk', 'TH0000TEST02'); S.click('#shipBtn'); wait_text(S, 'กำลังจัดส่ง')
    B.reload(); B.click('text=จำลอง: ขนส่งแจ้งว่าของถึงแล้ว'); wait_text(B, 'ระบบจะโอนเงินให้ผู้ขายอัตโนมัติใน')
    B.click('.twobtn >> text=แจ้งปัญหา'); B.click('#dpChips [data-v="ของเสียหาย"]')
    with B.expect_file_chooser() as fc: B.click('#dpUp')
    fc.value.set_files([os.path.join(HERE, 'unboxing.mp4'), os.path.join(HERE, 'evidence.jpg')])
    wait_text(B, 'แนบแล้ว 2 ไฟล์'); B.fill('#dpText', 'ลำโพงแตก กล่องบุบ (ทดสอบ)'); shot(B, '20-dispute-sheet')
    B.click('#dpBtn'); wait_text(B, 'เงินยังพักไว้'); shot(B, '21-disputed-money-held', full=True)
    dcode = link.rsplit('/', 1)[1]
    A = phone(br, 'แอดมิน'); A.set_viewport_size({'width': 900, 'height': 1000})
    A.goto(BASE + '/admin'); A.fill('#pw', admin_password()); A.click('button:has-text("เข้าสู่ระบบ")'); wait_text(A, 'ข้อพิพาทรอตัดสิน')
    expect(A.locator(f'#dp-{dcode}')).to_be_visible(); expect(A.locator(f'#dp-{dcode} video')).to_have_count(1)
    shot(A, '22-admin-dispute', full=True)
    A.fill(f'#note-{dcode}', 'ตรวจคลิปแล้ว ของเสียหายบางส่วน คืนเงินผู้ซื้อ 900 บาท'); A.fill(f'#amt-{dcode}', '900')
    A.click(f'#dp-{dcode} >> text=คืนบางส่วน'); A.wait_for_selector(f'#dp-{dcode}', state='detached')
    B.reload(); wait_text(B, 'ผลการตัดสิน'); shot(B, '23-dispute-resolved-partial', full=True)

    print('9) ส่งช้าเกินกำหนด → ผู้ซื้อขอเงินคืน')
    create_deal(S, 'นาฬิกาไขลาน (ทดสอบ)', 1200)
    link = submit_deal(S)
    B.goto(link); B.reload(); B.click('text=รับดีล แล้วไปจ่ายเงิน'); wait_text(B, 'PromptPay'); B.click('text=จ่ายด้วย'); B.click('#payBtn'); wait_text(B, 'เงินพักไว้แล้ว')
    B.click('text=เร่งเวลา (ทดสอบ) +3 วัน'); B.click('text=เร่งเวลา (ทดสอบ) +1 วัน'); wait_text(B, 'ขอเงินคืน (ส่งช้าเกินกำหนด)')
    B.evaluate('window.scrollTo(0,0)'); shot(B, '24-late-delivery-refund-button')
    B.click('text=ขอเงินคืน (ส่งช้าเกินกำหนด)'); wait_text(B, 'คืนเงินให้ผู้ซื้อแล้ว')

    print('10) หน้าร้านตัวอย่าง (Gold) → ซื้อแบบปลอดภัย')
    B.goto(BASE + '/#/'); wait_text(B, 'ร้านแนะนำ'); shot(B, '25-buyer-home-deals', full=True)
    B.click('.shoprow >> nth=0'); wait_text(B, 'คะแนนความน่าเชื่อถือ'); shot(B, '26-shop-gold', full=True)
    B.click('#seeAllGoods'); wait_text(B, 'สินค้าขายประจำทั้งหมด'); wait_text(B, 'แผ่นเสียง'); shot(B, '26b-shop-products-all', full=True)
    B.click('.pcard:has-text("แผ่นเสียง") >> text=ซื้อแบบปลอดภัย'); B.click('#buyChips [data-v=messenger]'); shot(B, '27-shop-buy-sheet')
    B.click('#buyBtn'); wait_text(B, 'สั่งซื้อจากหน้าร้าน'); wait_text(B, 'PromptPay'); shot(B, '28-shop-order-pay')
    B.click('text=จ่ายด้วย'); B.click('#payBtn'); wait_text(B, 'เงินพักไว้แล้ว')

    print('11) ยืนยันตัวตน (ทดสอบ) สำหรับดีลเกิน 3,000')
    create_deal(S, 'เลนส์กล้อง (ทดสอบ)', 4200)
    expect(S.locator('#newSellerLimit')).to_contain_text('3,000')  # v13: ร้านใหม่ < 5 ดีลสำเร็จ สูงสุด 3,000
    S.click('#roleSeg [data-v=buyer]'); S.fill('#price', '4200')  # ฝั่งผู้ซื้อ (วงเงิน 5,000) ยังต้องยืนยันตัวตนเมื่อเกิน 3,000
    wait_text(S, 'ต้องยืนยันตัวตน'); S.locator('#limitNotes').scroll_into_view_if_needed(); shot(S, '29-over-3000-needs-id')
    S.click('#limitNotes >> text=ยืนยันเลย'); upload(S, '#idBox', os.path.join(HERE, 'fake-id.jpg')); S.wait_for_selector('#idBox img')
    shot(S, '30-id-verify-test')
    S.click('text=ส่งยืนยันตัวตน (ทดสอบ)'); wait_text(S, 'คุณยืนยันตัวตนแล้ว')
    S.click('#roleSeg [data-v=seller]'); S.fill('#price', '6000'); wait_text(S, 'วงเงินของร้านระดับ Bronze คือ 5,000'); S.locator('#limitNotes').scroll_into_view_if_needed(); shot(S, '31-new-user-limit-5000')

    print('12) โปรไฟล์ / บัญชี / ร้านของฉัน')
    B.goto(BASE + '/#/me'); wait_text(B, 'บัญชีของฉัน')
    S.goto(BASE + '/#/me'); wait_text(S, 'เงินขายของฉัน'); shot(S, '32-seller-account-payouts', full=True)
    uid = S.evaluate('S.me.id'); B.goto(BASE + f'/#/u/{uid}'); wait_text(B, 'ประวัติดีล'); shot(B, '33-seller-public-profile', full=True)
    S.goto(BASE + '/#/myshop'); wait_text(S, 'เพิ่มสินค้าขายประจำ'); S.click('text=เพิ่มสินค้าขายประจำ')
    S.fill('#pTitle', 'กระเป๋ากล้องหนัง (ทดสอบ)'); S.fill('#pPrice', '890'); upload(S, '#pPh .ph.add', os.path.join(HERE, 'camera.jpg')); S.wait_for_selector('#pPh img')
    S.click('#pDl [data-v=meet]'); S.click('#pBtn'); wait_text(S, 'กระเป๋ากล้องหนัง (ทดสอบ)'); shot(S, '34-my-shop-new', full=True)
    B.click('.top .icon-btn[aria-label="การแจ้งเตือน"]'); wait_text(B, 'การแจ้งเตือน'); B.wait_for_timeout(500); shot(B, '35-buyer-notifications')
    br.close()

print('\nJS errors:', errors or 'ไม่มี')
sys.exit(1 if errors else 0)
