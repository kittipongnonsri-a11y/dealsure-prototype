"""ทดสอบผ่านเบราว์เซอร์ (v2): รูปโปรไฟล์ · แชทในดีล · รายการแชท · ทักร้าน · ทีมงานคุยในข้อพิพาท · การ์ดดีลใหม่
ภาพหน้าจอเก็บที่ screenshots/v2/
วิธีรัน: python3 tests/e2e_v2_browser.py [http://localhost:8787]"""
import os, re, sys, time
from playwright.sync_api import sync_playwright, expect

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'e2e_browser.py'), encoding='utf-8').read().split('\nwith sync_playwright() as p:')[0]
exec(compile(src, 'e2e_helpers', 'exec'))   # admin_password, BASE, phone(), login(), upload(), create_deal(), submit_deal(), wait_text()
OUT = os.path.join(HERE, '..', 'screenshots', 'v2')
os.makedirs(OUT, exist_ok=True)


def shot(pg, name, full=False):
    pg.wait_for_timeout(500)
    pg.evaluate("document.querySelector('#toast') && document.querySelector('#toast').classList.remove('show')"); pg.wait_for_timeout(300)
    pg.evaluate('document.fonts.ready')
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='absolute')")
    pg.screenshot(path=os.path.join(OUT, name + '.png'), full_page=full)
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='')")
    print('  📸', name)


def no_hscroll(pg, label):
    w = pg.evaluate('document.documentElement.scrollWidth'), pg.evaluate('window.innerWidth')
    if w[0] > w[1]: errors.append(f'{label}: เลื่อนแนวนอนได้ ({w[0]} > {w[1]})')


def thai_fonts(pg, label):
    ok = pg.evaluate("document.fonts.ready.then(() => document.fonts.check('600 16px Prompt', 'ดีลชัวร์') && document.fonts.check('16px Sarabun', 'ดีลชัวร์'))")
    if not ok: errors.append(f'{label}: ฟอนต์ไทย Prompt/Sarabun โหลดไม่ครบ')
    return ok


with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    S = phone(br, 'ผู้ขาย'); B = phone(br, 'ผู้ซื้อ')

    print('1) ผู้ขายเปลี่ยนรูปโปรไฟล์ (ครอปเป็นสี่เหลี่ยมจัตุรัส)')
    S.goto(BASE + '/'); login(S, 'น้องฝ้าย (ทดสอบ)', '0871' + stamp)
    S.goto(BASE + '/#/me'); wait_text(S, 'บัญชีของฉัน')
    upload(S, '#avEdit', os.path.join(HERE, 'camera.jpg'))
    expect(S.locator('#cropCv')).to_be_visible()
    S.fill('#cropZoom', '1.6'); S.dispatch_event('#cropZoom', 'input')
    box = S.locator('#cropCv').bounding_box()
    S.mouse.move(box['x'] + 130, box['y'] + 130); S.mouse.down(); S.mouse.move(box['x'] + 100, box['y'] + 115, steps=5); S.mouse.up()
    shot(S, '01-profile-picture-crop')
    S.click('#cropSave'); S.wait_for_selector('#avEdit .avatar.has-img')
    av = S.evaluate('S.me.avatar'); assert av and av.startswith('/uploads/'), av
    shot(S, '02-profile-picture-changed')
    print('   Thai fonts OK:', thai_fonts(S, 'บัญชี'))

    print('2) สร้างดีล 2 รายการ (ชื่อยาว) → ผู้ซื้อรับ+จ่าย 1 รายการ')
    create_deal(S, 'กล้องฟิล์ม Olympus OM-1 มือสอง พร้อมเลนส์ 50mm f1.8 และกระเป๋าหนังแท้ (ทดสอบ)', 2500, photo=os.path.join(HERE, 'camera.jpg'))
    link = submit_deal(S); code = link.rsplit('/', 1)[1]
    create_deal(S, 'แผ่นเสียงลูกกรุง สุนทราภรณ์ ชุดสะสมหายาก 5 แผ่น ปกเดิม (ทดสอบ)', 750, delivery='meet', fee='seller')
    submit_deal(S)
    B.goto(link); B.click('text=เข้าสู่ระบบเพื่อรับดีล'); login(B, 'คุณบีม (ทดสอบ)', '0872' + stamp)
    B.click('text=รับดีล แล้วไปจ่ายเงิน'); wait_text(B, 'PromptPay'); B.click('text=จ่ายด้วย'); B.click('#payBtn'); wait_text(B, 'เงินพักไว้แล้ว')

    print('3) แชทในหน้าดีล: ผู้ซื้อส่งข้อความ + รูป')
    expect(B.locator('#chatCard .chat-safe')).to_contain_text('อย่าโอนเงินนอกแอป')
    expect(B.locator('#chatCard')).to_contain_text('ยังไม่มีข้อความ')
    expect(B.locator('.seller .avatar.has-img')).to_have_count(1)   # รูปโปรไฟล์ผู้ขายในหน้าดีล
    tid = B.evaluate("+document.querySelector('#chatCard [data-thread]').dataset.thread")
    B.fill(f'#cin-{tid}', 'สวัสดีครับ จ่ายแล้วนะครับ ส่งวันไหนครับ'); B.click(f'#csend-{tid}')
    B.wait_for_selector(f'#msgs-{tid} .msg.me')
    upload(B, '#chatCard .cbtn', os.path.join(HERE, 'evidence.jpg')); B.wait_for_selector(f'#cpend-{tid} img')
    B.fill(f'#cin-{tid}', 'ขอดูรูปเลนส์ชัด ๆ อีกมุมได้ไหมครับ'); B.click(f'#csend-{tid}')
    B.wait_for_selector(f'#msgs-{tid} .msg.me .mph img')
    B.locator('#chatCard').scroll_into_view_if_needed(); shot(B, '03-deal-chat-buyer')

    print('4) ผู้ขาย: การ์ด "ดีลล่าสุด" แบบใหม่ (360 / 390 px) + แชทยังไม่อ่าน')
    S.goto(BASE + '/#/'); wait_text(S, 'ดีลล่าสุด')
    S.wait_for_selector('.dcard .dc-chat')
    expect(S.locator('#chatBadge')).to_be_visible()
    hs = S.evaluate("[...document.querySelectorAll('.dc-title')].map(e => Math.round(e.getBoundingClientRect().height))")
    lh = S.evaluate("parseFloat(getComputedStyle(document.querySelector('.dc-title')).lineHeight)")
    if not any(h >= 1.8 * lh for h in hs): errors.append(f'ชื่อสินค้าไม่ขึ้น 2 บรรทัด {hs} lh={lh}')
    S.locator('.sec-h').first.scroll_into_view_if_needed(); S.evaluate('window.scrollBy(0,-12)')
    no_hscroll(S, 'หน้าแรก 390'); shot(S, '04-home-deal-cards-390')
    shot(S, '04b-home-deal-cards-390-full', full=True)
    S.set_viewport_size({'width': 360, 'height': 780}); S.reload(); wait_text(S, 'ดีลล่าสุด')
    S.locator('.sec-h').first.scroll_into_view_if_needed(); S.evaluate('window.scrollBy(0,-12)')
    no_hscroll(S, 'หน้าแรก 360'); shot(S, '05-home-deal-cards-360')
    shot(S, '05b-home-deal-cards-360-full', full=True)
    S.set_viewport_size({'width': 390, 'height': 844})

    print('5) ผู้ขาย: กระดิ่งแจ้งเตือนแชท → แชทเต็มจอ → ตอบ (มีคำเตือนห้ามโอนนอกแอป)')
    S.evaluate('window.scrollTo(0,0)')
    S.click('.top .icon-btn[aria-label="การแจ้งเตือน"]'); S.wait_for_selector('#notif .it:has-text("ขอดูรูปเลนส์")')
    expect(S.locator('#notif .it').first).to_contain_text('💬')
    shot(S, '06-bell-chat-notification')
    S.click('#notif .it >> nth=0'); S.wait_for_selector('.chat.full .msg')
    S.fill(f'#cin-{tid}', 'ส่งพรุ่งนี้เช้าครับ เดี๋ยวถ่ายรูปเลนส์ให้ดูนะครับ'); S.click(f'#csend-{tid}')
    S.wait_for_selector(f'#msgs-{tid} .msg.me')
    S.fill(f'#cin-{tid}', 'ถ้าสะดวกโอนตรงเข้าบัญชี 123-4-56789-0 ก็ได้นะ'); S.click(f'#csend-{tid}')
    S.wait_for_selector(f'#msgs-{tid} .mwarn')
    shot(S, '07-chat-fullscreen-seller')
    no_hscroll(S, 'แชทเต็มจอ')

    print('6) ผู้ซื้อ: ข้อความใหม่เด้งเข้าแชทในหน้าดีล (polling) + รายการแชท')
    B.wait_for_selector(f'#msgs-{tid} .msg:not(.me)', timeout=12000)
    B.wait_for_selector(f'#msgs-{tid} .mwarn', timeout=12000)
    B.goto(BASE + '/#/chats'); B.wait_for_selector('.chatlist .ci')

    print('7) ทักร้านก่อนซื้อ (ร้านตัวอย่าง)')
    B.goto(BASE + '/#/'); wait_text(B, 'ร้านแนะนำ'); B.click('.shoprow >> nth=0'); wait_text(B, 'คะแนนความน่าเชื่อถือ')
    expect(B.locator('#chatShopBtn')).to_be_visible(); shot(B, '09-shop-chat-button')
    B.click('#chatShopBtn'); B.wait_for_selector('.chat.full')
    expect(B.locator('.chat-safe')).to_be_visible()
    stid = B.evaluate("+document.querySelector('[data-thread]').dataset.thread")
    B.fill(f'#cin-{stid}', 'สวัสดีค่ะ กล้องตัวนี้ยังมีไหมคะ ขอดูรูปเพิ่มได้ไหม'); B.click(f'#csend-{stid}'); B.wait_for_selector(f'#msgs-{stid} .msg.me')
    shot(B, '10-shop-chat-before-buying')
    B.goto(BASE + '/#/chats'); B.wait_for_selector('.chatlist .ci >> nth=1'); shot(B, '08-chat-list')

    print('8) ข้อพิพาท → แอดมินส่งข้อความถึงทั้งสองฝ่าย')
    S.goto(BASE + f'/#/d/{code}'); S.click('button:has-text("กรอกเลขพัสดุ")'); S.fill('#trk', 'TH0000CHAT01'); S.click('#shipBtn'); wait_text(S, 'กำลังจัดส่ง')
    B.goto(BASE + f'/#/d/{code}'); B.click('text=จำลอง: ขนส่งแจ้งว่าของถึงแล้ว'); wait_text(B, 'ระบบจะโอนเงินให้ผู้ขายอัตโนมัติใน')
    B.click('.twobtn >> text=แจ้งปัญหา'); B.click('#dpChips [data-v="ของไม่ตรงปก"]')
    upload(B, '#dpUp', os.path.join(HERE, 'evidence.jpg')); wait_text(B, 'แนบแล้ว 1 ไฟล์')
    B.fill('#dpText', 'เลนส์มีฝ้า ไม่ตรงกับรูปที่ลง (ทดสอบ)'); B.click('#dpBtn'); wait_text(B, 'เงินยังพักไว้')
    expect(B.locator('#teamCard')).to_contain_text('ทีมงานยังไม่ได้ส่งข้อความ')
    A = phone(br, 'แอดมิน')
    A.goto(BASE + '/admin'); A.fill('#pw', admin_password()); A.click('button:has-text("เข้าสู่ระบบ")'); wait_text(A, 'ข้อพิพาทรอตัดสิน')
    dp = A.locator(f'#dp-{code}'); expect(dp).to_be_visible()
    expect(dp.locator('details.dchat')).to_contain_text('ดูแชทระหว่างผู้ซื้อ–ผู้ขาย')
    atid = A.evaluate(f"+document.querySelector('#dp-{code} .admin-thread').id.split('-')[1]")
    A.fill(f'#amsg-{atid}', 'สวัสดีค่ะ ทีมงานดีลชัวร์รับเรื่องแล้ว รบกวนผู้ซื้อส่งรูปฝ้าในเลนส์แบบชัด ๆ และผู้ขายส่งรูปก่อนแพ็คของด้วยนะคะ')
    A.click(f'#asend-{atid}'); A.wait_for_selector(f'#amsgs-{atid} .msg.team')
    dp.locator('details.dchat summary').click()
    dp.scroll_into_view_if_needed(); A.locator(f'#athread-{atid}').scroll_into_view_if_needed()
    shot(A, '11-admin-dispute-messaging')

    print('9) ผู้ซื้อ/ผู้ขายเห็นข้อความทีมงานในหน้าดีล + กระดิ่ง แล้วตอบพร้อมรูป')
    B.reload(); B.click('.top .icon-btn[aria-label="การแจ้งเตือน"]'); wait_text(B, 'ทีมงานดีลชัวร์: สวัสดีค่ะ')
    shot(B, '12-buyer-bell-team-message')
    B.click('#notif .it >> nth=0'); B.wait_for_selector('#teamCard .msg.team .b-team')
    B.fill(f'#cin-{B.evaluate("+document.querySelector(\'#teamCard [data-thread]\').dataset.thread")}', 'ส่งรูปเลนส์ให้แล้วค่ะ เห็นฝ้าชัดเลย')
    upload(B, '#teamCard .cbtn', os.path.join(HERE, 'evidence.jpg')); B.wait_for_selector('#teamCard .cpend img')
    B.click('#teamCard .csend'); B.wait_for_selector('#teamCard .msg.me .mph img')
    B.locator('#teamCard').scroll_into_view_if_needed(); shot(B, '13-buyer-replies-to-team')
    S.goto(BASE + f'/#/d/{code}/team'); S.wait_for_selector('#teamCard .msg.team')
    S.wait_for_selector('#teamCard .msg:not(.me):not(.team)')
    S.fill('#teamCard .cin', 'ผู้ขายถ่ายรูปก่อนแพ็คไว้ครับ เลนส์ใสปกติ แนบรูปให้ครับ')
    upload(S, '#teamCard .cbtn', os.path.join(HERE, 'camera.jpg')); S.wait_for_selector('#teamCard .cpend img')
    S.click('#teamCard .csend'); S.wait_for_selector('#teamCard .msg.me')
    S.locator('#teamCard').scroll_into_view_if_needed(); shot(S, '14-seller-sees-team-thread')
    A.wait_for_selector(f'#amsgs-{atid} .msg:not(.team) >> nth=1', timeout=12000)
    A.locator(f'#athread-{atid}').scroll_into_view_if_needed(); shot(A, '15-admin-sees-both-replies')

    print('10) รูปโปรไฟล์แสดงในหน้าร้าน + แชท + การ์ดดีลของผู้ซื้อ')
    B.goto(BASE + f'/#/shop/{S.evaluate("S.me.id")}'); B.wait_for_selector('.shophead .avatar.has-img'); shot(B, '16-shop-page-avatar')
    B.goto(BASE + '/#/'); B.wait_for_selector('.dcard .avatar.has-img'); B.locator('.sec-h').first.scroll_into_view_if_needed(); B.evaluate('window.scrollBy(0,-12)'); shot(B, '17-buyer-home-cards-avatar')
    no_hscroll(B, 'หน้าแรกผู้ซื้อ')
    br.close()

print('\nJS errors / ปัญหา:', errors or 'ไม่มี')
sys.exit(1 if errors else 0)
