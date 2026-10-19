"""ทดสอบผ่านเบราว์เซอร์ (v3) ดีลที่พัก ที่ 390px: สร้างดีลที่พัก · ผู้เข้าพักรอเช็คอิน · รหัสเช็คอินของเจ้าของ · ยืนยันเช็คอิน
· แจ้งที่พักปลอม · หน้าแอดมิน · จองที่พักจากหน้าร้านตัวอย่าง
ภาพหน้าจอเก็บที่ screenshots/v3/
วิธีรัน: python3 tests/e2e_v3_stay_browser.py [http://localhost:8787]"""
import os, re, sys, time
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright, expect

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'e2e_browser.py'), encoding='utf-8').read().split('\nwith sync_playwright() as p:')[0]
exec(compile(src, 'e2e_helpers', 'exec'))   # admin_password, BASE, phone(), login(), upload(), submit_deal(), wait_text(), errors, stamp
OUT = os.path.join(HERE, '..', 'screenshots', 'v3')
os.makedirs(OUT, exist_ok=True)
TZ = timezone(timedelta(hours=7))
def bkk(days): return (datetime.now(TZ) + timedelta(days=days)).strftime('%Y-%m-%d')
shots = []


def shot(pg, name, full=False):
    pg.wait_for_timeout(500)
    pg.evaluate("document.querySelector('#toast') && document.querySelector('#toast').classList.remove('show')"); pg.wait_for_timeout(300)
    pg.evaluate('document.fonts.ready')
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='absolute')")
    path = os.path.join(OUT, name + '.png')
    pg.screenshot(path=path, full_page=full)
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='')")
    no_hscroll(pg, name); shots.append(path)
    print('  📸', name)


def no_hscroll(pg, label):
    w = pg.evaluate('document.documentElement.scrollWidth'), pg.evaluate('window.innerWidth')
    if w[0] > w[1]: errors.append(f'{label}: เลื่อนแนวนอนได้ ({w[0]} > {w[1]})')


def thai_fonts(pg, label):
    ok = pg.evaluate("document.fonts.ready.then(() => document.fonts.check('600 16px Prompt', 'ดีลที่พัก') && document.fonts.check('16px Sarabun', 'ดีลที่พัก'))")
    if not ok: errors.append(f'{label}: ฟอนต์ไทย Prompt/Sarabun โหลดไม่ครบ')
    return ok


def pay(pg):
    pg.click('text=จ่ายด้วย'); expect(pg.locator('#payBtn')).to_be_visible(); pg.click('#payBtn'); wait_text(pg, 'พักเงินแล้ว (รอเช็คอิน)')


def fill_stay(pg, title, price, cin=3, nights=2, role='seller', photo=None, host='พี่โฮสต์ (ทดสอบ)', addr='88/8 ม.2 ต.ห้วยทราย อ.แม่ริม จ.เชียงใหม่',
              map_url='https://maps.app.goo.gl/TestStay123'):
    pg.goto(BASE + '/#/'); pg.click('#stayCta'); expect(pg.locator('#sAddr')).to_be_visible()
    expect(pg.locator('#kindSeg [data-v=stay]')).to_have_class(re.compile('on'))
    pg.click(f'#roleSeg [data-v={role}]')
    pg.fill('#fTitle', title); pg.fill('#sAddr', addr); pg.fill('#sMap', map_url)
    pg.fill('#sIn', bkk(cin)); pg.fill('#sTime', '14:00'); pg.fill('#sOut', bkk(cin + nights)); pg.fill('#sGuests', '2')
    pg.fill('#price', str(price)); pg.fill('#sHost', host); pg.fill('#sFcd', '3')
    if photo: upload(pg, '.ph.add', photo); pg.wait_for_selector('#fPhotos img')


with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    # รูปที่พักทดสอบ: แปลงจาก SVG ตัวอย่างเป็น JPG
    tmp = br.new_page(viewport={'width': 400, 'height': 400}); tmp.goto(BASE + '/static/demo/house.svg')
    HOUSE = os.path.join(OUT, '_house.jpg'); tmp.screenshot(path=HOUSE, type='jpeg', quality=85); tmp.close()
    H = phone(br, 'เจ้าของที่พัก'); G = phone(br, 'ผู้เข้าพัก')

    print('1) เจ้าของที่พักสร้างดีลที่พัก (ประเภท "ที่พัก")')
    H.goto(BASE + '/'); login(H, 'พี่โฮสต์ (ทดสอบ)', '0891' + stamp)
    wait_text(H, 'ดีลที่พัก'); thai_fonts(H, 'หน้าแรก')
    fill_stay(H, 'บ้านพักริมน้ำ ห้องวิวสวน (ทดสอบ)', 2400, cin=6, photo=HOUSE)
    H.fill('#fDesc', 'ห้องนอน 1 ห้อง · อาหารเช้า 2 ที่ · ที่จอดรถ')
    expect(H.locator('#sDates')).to_contain_text('2 คืน'); expect(H.locator('#sMapHint')).to_contain_text('ลิงก์ Google Maps')
    expect(H.locator('#fBuyer')).to_have_text('2,424 ฿')
    shot(H, '01-create-accommodation-deal', full=True)
    link = submit_deal(H); code = link.rsplit('/', 1)[1]
    assert 'ดีลที่พัก' in H.evaluate('S.shareMsg'), H.evaluate('S.shareMsg')
    H.click('text=ดูหน้าดีล'); wait_text(H, 'รออีกฝ่ายเปิดลิงก์')

    print('2) ผู้เข้าพักเปิดลิงก์ → เห็นความน่าเชื่อถือเจ้าของ + เคล็ดลับกันที่พักปลอม → รับดีล → จ่าย')
    G.goto(link); wait_text(G, 'ดีลที่พักนี้ได้รับการคุ้มครอง')
    expect(G.locator('#hostTrust')).to_contain_text('เข้าพักสำเร็จ'); expect(G.locator('#stayTips')).to_contain_text('ขอวิดีโอคอลดูห้องจริง')
    expect(G.locator('#mapLink')).to_have_attribute('href', 'https://maps.app.goo.gl/TestStay123')
    shot(G, '02-guest-opens-link-host-trust', full=True)
    G.click('text=เข้าสู่ระบบเพื่อรับดีล'); login(G, 'คุณแนน (ทดสอบ)', '0892' + stamp)
    G.click('text=รับดีล แล้วไปจ่ายเงิน'); wait_text(G, 'PromptPay'); pay(G)
    expect(G.locator('.status-hero .timer')).to_be_visible()
    expect(G.locator('#guestCancelBtn')).to_contain_text('ยกเลิกฟรี')
    shot(G, '03-guest-waiting-for-checkin')
    shot(G, '03b-guest-waiting-for-checkin-full', full=True)
    thai_fonts(G, 'หน้าดีลที่พัก')

    print('3) เจ้าของเห็นรหัสเช็คอิน 4 หลัก')
    H.goto(BASE + f'/d/{code}'); expect(H.locator('#checkinShow')).to_be_visible()
    pin = H.locator('#checkinShow').inner_text().replace('\n', '').strip(); assert re.fullmatch(r'\d{4}', pin), pin
    H.locator('#checkinCodeCard').scroll_into_view_if_needed(); H.evaluate('window.scrollBy(0,-90)')
    shot(H, '04-host-checkin-code')

    print('4) เร่งเวลาถึงวันเช็คอิน → ผู้เข้าพักกด "เช็คอินแล้ว ที่พักตรงปก"')
    G.goto(BASE + f'/d/{code}'); G.click('#skipCheckin'); expect(G.locator('#checkinCard')).to_be_visible()
    expect(G.locator('#stayProblemBtn')).to_be_visible()
    G.locator('#checkinCard').scroll_into_view_if_needed(); G.evaluate('window.scrollBy(0,-90)')
    shot(G, '05-guest-checkin-day')
    G.click('#stayOkBtn'); expect(G.locator('#stayCfBtn')).to_be_visible(); G.click('#cfStars [data-n="5"]'); G.fill('#cfText', 'ที่พักตรงปก เจ้าของใจดี (ทดสอบ)')
    shot(G, '06-guest-confirm-checkin')
    G.click('#stayCfBtn'); wait_text(G, 'เช็คอินสำเร็จ · ปล่อยเงินให้เจ้าของที่พักแล้ว')
    shot(G, '07-checkin-completed', full=True)
    H.goto(BASE + f'/d/{code}'); wait_text(H, 'เงินของคุณจากดีลนี้')

    print('5) ดีลที่ผู้เข้าพักสร้างเอง → เจ้าของรับ → กรอกรหัสเช็คอิน')
    fill_stay(G, 'โฮมสเตย์ชายทะเล (ทดสอบ)', 1800, role='buyer', cin=4, nights=1, host='คุณเล็ก')
    link2 = submit_deal(G); code2 = link2.rsplit('/', 1)[1]
    H.goto(link2); H.click('button:has-text("รับดีลนี้")'); wait_text(H, 'รอผู้เข้าพักจ่ายเงิน')
    G.goto(BASE + f'/d/{code2}'); pay(G)
    H.goto(BASE + f'/d/{code2}'); pin2 = H.locator('#checkinShow').inner_text().replace('\n', '').strip()
    G.goto(BASE + f'/d/{code2}'); G.click('#skipCheckin'); G.fill('#checkinCode', pin2)
    G.locator('#checkinCard').scroll_into_view_if_needed()
    shot(G, '08-guest-enters-host-checkin-code')
    G.click('button:has-text("ยืนยันด้วยรหัส")'); wait_text(G, 'เช็คอินสำเร็จ')

    print('6) แจ้งที่พักปลอม: ไม่มีที่พักจริง (รูป + วิดีโอ + ตำแหน่ง) → เงินยังพักไว้')
    fill_stay(H, 'พูลวิลล่าวิวทะเล ราคาพิเศษ (ทดสอบ)', 4500 if False else 2900, cin=2, nights=1)
    link3 = submit_deal(H); code3 = link3.rsplit('/', 1)[1]
    G.goto(link3); G.click('text=รับดีล แล้วไปจ่ายเงิน'); wait_text(G, 'PromptPay'); pay(G)
    G.click('#skipCheckin'); G.click('#stayProblemBtn'); expect(G.locator('#spChips')).to_be_visible()
    G.click('#spChips [data-v="ไม่มีที่พักจริง"]')
    upload(G, '#dpUp', os.path.join(HERE, 'evidence.jpg')); wait_text(G, 'แนบแล้ว 1 ไฟล์')
    upload(G, '#dpUp', os.path.join(HERE, 'unboxing.mp4')); wait_text(G, 'แนบแล้ว 2 ไฟล์')
    G.fill('#spLoc', 'ยืนอยู่ตรงหมุดใน Google Maps เป็นที่ดินเปล่า ไม่มีบ้าน (ทดสอบ)')
    G.fill('#dpText', 'โทรหาเจ้าของ 3 ครั้งไม่รับสาย (ทดสอบ)')
    shot(G, '09-fake-listing-report')
    G.click('#spBtn'); wait_text(G, 'ทีมงานกำลังตรวจสอบ')
    expect(G.locator('#teamCard')).to_be_visible(); expect(G.locator('.proof').first).to_contain_text('ตำแหน่งตอนแจ้ง')
    shot(G, '10-fake-listing-disputed', full=True)

    print('7) แอดมินเห็นข้อพิพาทที่พัก → ส่งข้อความ → คืนเงินเต็ม')
    A = phone(br, 'แอดมิน')
    A.goto(BASE + '/admin'); A.fill('#pw', admin_password()); A.click('button:has-text("เข้าสู่ระบบ")'); wait_text(A, 'ข้อพิพาทรอตัดสิน')
    dp = A.locator(f'#dp-{code3}'); expect(dp).to_contain_text('ไม่มีที่พักจริง'); expect(dp).to_contain_text('ผู้เข้าพักอยู่ที่'); expect(dp).to_contain_text('เปิด Google Maps')
    atid = A.evaluate(f"+document.querySelector('#dp-{code3} .admin-thread').id.split('-')[1]")
    A.fill(f'#amsg-{atid}', 'ทีมงานรับเรื่องแล้วค่ะ ตรวจพิกัดแล้วไม่พบที่พัก กำลังติดต่อเจ้าของ เงินยังพักไว้ปลอดภัย')
    A.click(f'#asend-{atid}'); A.wait_for_selector(f'#amsgs-{atid} .msg.team')
    dp.scroll_into_view_if_needed()
    shot(A, '11-admin-accommodation-dispute')
    shot(A, '11b-admin-accommodation-dispute-full', full=True)
    A.fill(f'#note-{code3}', 'ตรวจสอบแล้ว ไม่มีที่พักตามประกาศ'); A.click(f'#dp-{code3} button:has-text("คืนเงินผู้เข้าพักทั้งหมด")'); wait_text(A, 'บันทึกผลการตัดสินแล้ว')
    G.goto(BASE + f'/d/{code3}'); wait_text(G, 'คืนเงินผู้เข้าพักเต็มจำนวน')
    shot(G, '12-guest-refunded')

    print('8) จองที่พักจากหน้าร้านตัวอย่าง (บ้านพักริมดอย) → ยกเลิกฟรีได้')
    G.goto(BASE + '/#/'); wait_text(G, 'ร้านแนะนำ')
    sid = G.evaluate("fetch('/api/shops').then(r=>r.json()).then(j=>j.shops.find(s=>s.name==='พี่ปุ้ย (ตัวอย่าง)').id)")
    G.goto(BASE + f'/#/shop/{sid}'); wait_text(G, 'จองแบบปลอดภัย'); expect(G.locator('.shophead')).to_contain_text('เข้าพักสำเร็จ')
    shot(G, '13-demo-host-storefront', full=True)
    G.locator('.pcard', has_text='บ้านไม้ริมดอย').locator('button:has-text("จองแบบปลอดภัย")').click()
    G.fill('#bkIn', bkk(10)); G.fill('#bkN', '2'); G.fill('#bkG', '2'); expect(G.locator('#bkPrice')).to_have_text('2,580 ฿')
    shot(G, '14-storefront-booking-sheet')
    G.click('#buyBtn'); wait_text(G, 'PromptPay'); pay(G)
    expect(G.locator('#hostTrust')).to_contain_text('พี่ปุ้ย'); expect(G.locator('#hostTrust')).to_contain_text('ตัวอย่าง')
    G.click('#guestCancelBtn'); expect(G.locator('#scBtn')).to_contain_text('ยกเลิกฟรี')
    shot(G, '15-guest-free-cancel-sheet')
    G.click('#scBtn'); wait_text(G, 'ยกเลิกในช่วงยกเลิกฟรี · คืนเงินหักค่าดำเนินการ')  # v6: หักค่าดำเนินการ 2% ขั้นต่ำ 10 บาท

    print('9) ปล่อยเงินอัตโนมัติ 24 ชม. หลังเช็คอิน (ปุ่มเร่งเวลา)')
    fill_stay(H, 'ห้องพักใกล้ตลาด (ทดสอบ)', 900, cin=1, nights=1)
    link4 = submit_deal(H); code4 = link4.rsplit('/', 1)[1]
    G.goto(link4); G.click('text=รับดีล แล้วไปจ่ายเงิน'); wait_text(G, 'PromptPay'); pay(G)
    G.click('#skipRelease'); wait_text(G, 'เช็คอินสำเร็จ · ปล่อยเงินให้เจ้าของที่พักแล้ว'); wait_text(G, 'ระบบปล่อยเงินอัตโนมัติ (24 ชม. หลังเวลาเช็คอิน)')
    H.goto(BASE + '/#/'); wait_text(H, 'ดีลที่จบแล้ว')
    shot(H, '16-host-home-deal-cards')
    print('   Thai fonts OK:', thai_fonts(H, 'หน้าแรกเจ้าของ'))
    br.close()

missing = [s for s in shots if not os.path.isfile(s) or os.path.getsize(s) < 5000]
if missing: errors.append('ไฟล์ภาพหน้าจอหาย/เล็กผิดปกติ: ' + ', '.join(missing))
print(f'\nภาพหน้าจอ {len(shots)} ไฟล์ที่ {os.path.abspath(OUT)}')
if errors:
    print('ข้อผิดพลาด:'); [print('  ✗', e) for e in errors]; sys.exit(1)
print('ผ่านทั้งหมด ✓ (ไม่มี JS error, ไม่มีเลื่อนแนวนอน, ฟอนต์ไทยโหลดครบ)')
