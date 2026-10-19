"""ทดสอบผ่านเบราว์เซอร์ (v4) ที่ 390px: ช่องทางโซเชียล (แก้ไขในบัญชี · ปุ่มบนโปรไฟล์/หน้าร้าน) และรีวิว
(สรุป + 3 รีวิวสำคัญ · ตัวกรอง · เรียง · ดูทั้งหมด · แนบรูปในรีวิว)
ภาพหน้าจอเก็บที่ screenshots/v4/
วิธีรัน: python3 tests/e2e_v4_browser.py [http://localhost:8787]"""
import os, re, sys, time
from playwright.sync_api import sync_playwright, expect

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'e2e_browser.py'), encoding='utf-8').read().split('\nwith sync_playwright() as p:')[0]
exec(compile(src, 'e2e_helpers', 'exec'))   # BASE, phone(), login(), upload(), wait_text(), errors, stamp
OUT = os.path.join(HERE, '..', 'screenshots', 'v4')
os.makedirs(OUT, exist_ok=True)
shots = []


def shot(pg, name, full=False, el=None):
    pg.wait_for_timeout(450)
    pg.evaluate("document.querySelector('#toast') && document.querySelector('#toast').classList.remove('show')"); pg.wait_for_timeout(300)
    pg.evaluate('document.fonts.ready')
    path = os.path.join(OUT, name + '.png')
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='absolute')")
    if el: pg.locator(el).screenshot(path=path)
    else: pg.screenshot(path=path, full_page=full)
    if full: pg.evaluate("document.querySelector('#tabbar') && (document.querySelector('#tabbar').style.position='')")
    w = pg.evaluate('[document.documentElement.scrollWidth, window.innerWidth]')
    if w[0] > w[1]: errors.append(f'{name}: เลื่อนแนวนอนได้ ({w[0]} > {w[1]})')
    shots.append(path); print('  📸', name)


def thai_fonts(pg, label):
    ok = pg.evaluate("document.fonts.ready.then(() => document.fonts.check('600 16px Prompt', 'รีวิวทั้งหมด') && document.fonts.check('16px Sarabun', 'รีวิวทั้งหมด'))")
    if not ok: errors.append(f'{label}: ฟอนต์ไทย Prompt/Sarabun โหลดไม่ครบ')
    return ok


def to_top(pg, sel):
    pg.evaluate(f"window.scrollTo(0, document.querySelector('{sel}').getBoundingClientRect().top + window.scrollY - 70)"); pg.wait_for_timeout(250)


def rev_stars(pg): return [int(x) for x in pg.locator('#rvList .rev').evaluate_all('els => els.map(e => e.dataset.stars)')]


with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    S = phone(br, 'ผู้ขาย'); B = phone(br, 'ผู้ซื้อ')

    print('1) ผู้ขายใส่ช่องทางโซเชียลในหน้าบัญชี (ตรวจรูปแบบ + บอกช่องที่ผิด)')
    S.goto(BASE + '/'); login(S, 'ร้านน้องโซ (ทดสอบ)', '0871' + stamp)
    S.goto(BASE + '/#/me'); S.wait_for_selector('#socCard'); thai_fonts(S, 'หน้าบัญชี')
    S.fill('#so-facebook', 'https://m.facebook.com/nongso.shop?ref=bookmarks')
    S.fill('#so-line', '@NongSoShop'); S.fill('#so-instagram', 'bad handle!'); S.fill('#so-tiktok', 'https://www.tiktok.com/@nongso.shop?lang=th')
    S.fill('#so-youtube', '@NongSoChannel'); S.fill('#so-website', 'nongso.example.com'); S.fill('#so-phone', '+66 81 234 5678')
    S.click('#soBtn'); expect(S.locator('#soe-instagram')).to_contain_text('Instagram: รูปแบบไม่ถูกต้อง')
    expect(S.locator('#so-instagram')).to_have_class(re.compile('bad'))
    to_top(S, '#so-instagram'); shot(S, '01-social-links-validation-error')
    S.fill('#so-instagram', 'https://www.instagram.com/NongSo.Shop/?igsh=abc'); S.click('#soBtn'); wait_text(S, 'บันทึกช่องทางโซเชียลแล้ว')
    S.wait_for_selector('#socCard #socChips')
    expect(S.locator('#so-instagram')).to_have_value('@nongso.shop'); expect(S.locator('#so-facebook')).to_have_value('nongso.shop')
    expect(S.locator('#so-phone')).to_have_value('081-234-5678'); expect(S.locator('#so-line')).to_have_value('@nongsoshop')
    to_top(S, '#socCard'); shot(S, '02-social-links-edit-saved', full=False)
    shot(S, '02b-social-links-edit-card', el='#socCard')

    print('2) ปุ่มโซเชียลบนโปรไฟล์สาธารณะ (เปิดแอป/ลิงก์ที่ถูกต้อง)')
    uid = S.evaluate('S.me.id')
    B.goto(BASE + f'/#/u/{uid}'); B.wait_for_selector('#socChips')
    hrefs = B.locator('#socChips a').evaluate_all('els => els.map(a => [a.dataset.k, a.getAttribute("href"), a.getAttribute("target")])')
    want = {'facebook': 'https://www.facebook.com/nongso.shop', 'line': 'https://line.me/R/ti/p/@nongsoshop', 'instagram': 'https://www.instagram.com/nongso.shop/',
            'tiktok': 'https://www.tiktok.com/@nongso.shop', 'youtube': 'https://www.youtube.com/@NongSoChannel', 'website': 'https://nongso.example.com',
            'phone': 'tel:+66812345678'}
    assert [h[0] for h in hrefs] == list(want), hrefs
    for k, h, t in hrefs:
        assert h == want[k], (k, h)
        assert (t is None) if k == 'phone' else (t == '_blank'), (k, t)
    expect(B.locator('#socNote')).to_contain_text('ยังไม่ได้ตรวจสอบ')
    shot(B, '03-social-chips-profile')

    print('3) ร้านตัวอย่าง: ปุ่มโซเชียล + ป้าย "ตรวจแล้ว" บนหน้าร้าน')
    gold = B.evaluate("api('/shops').then(r => r.shops.find(s => s.stats.level === 'gold').id)")
    B.goto(BASE + f'/#/shop/{gold}'); B.wait_for_selector('#socChips')
    expect(B.locator('#socChips a[data-k=facebook] .vf')).to_contain_text('ตรวจแล้ว')
    expect(B.locator('#socNote')).to_contain_text('ทีมงานตรวจสอบแล้ว')
    shot(B, '04-social-chips-shop')

    print('4) รีวิว: สรุป + แสดง 3 รีวิวสำคัญ + รีวิวติชมล่าสุด')
    B.wait_for_selector('#reviews .rv-sum'); thai_fonts(B, 'หน้าร้าน')
    expect(B.locator('#rvList .rev')).to_have_count(3)
    expect(B.locator('#rvList .rev.pinned .pin')).to_contain_text('รีวิวติชมล่าสุด')
    total = B.evaluate('RV.st.page.summary.count')
    expect(B.locator('#rvMore')).to_have_text(f'ดูรีวิวทั้งหมด ({total:,})')
    expect(B.locator('#rvChips .chip')).to_have_count(7)
    expect(B.locator('#rvChips .chip[data-f=stay]')).to_be_disabled()
    expect(B.locator('#rvSort button.on')).to_have_text('สำคัญที่สุด')
    to_top(B, '#reviews'); shot(B, '05-reviews-summary-top3')
    shot(B, '05b-reviews-card', el='#reviews')

    print('5) ตัวกรอง 1–3 ดาว (ติชม) / มีรูป / เรียงล่าสุด / ดูทั้งหมด')
    B.click('#rvChips .chip[data-f=low]'); expect(B.locator('#rvChips .chip.on')).to_have_attribute('data-f', 'low')
    B.wait_for_selector('#rvChips .chip.on[data-f="low"]')
    assert all(s <= 3 for s in rev_stars(B)), rev_stars(B)
    to_top(B, '#reviews'); shot(B, '06-reviews-filter-low-stars')
    B.click('#rvChips .chip[data-f=photos]'); B.wait_for_selector('#rvChips .chip.on[data-f="photos"]')
    assert B.locator('#rvList .rev').count() == B.locator('#rvList .rev .rph').count() > 0
    B.click('#rvSort [data-v=recent]'); B.wait_for_selector('#rvSort button.on[data-v="recent"]')
    expect(B.locator('#reviews .rv-how')).to_have_count(0)
    B.click('#rvChips .chip[data-f=all]'); B.wait_for_selector('#rvChips .chip.on[data-f="all"]')
    B.click('#rvMore'); B.wait_for_function('document.querySelectorAll("#rvList .rev").length === 13')
    expect(B.locator('#rvMore')).to_contain_text(f'ดูเพิ่ม (อีก {total - 13:,} รีวิว)')
    B.locator('.rv-bars button').nth(0).click(); B.wait_for_selector('#rvChips .chip.on[data-f="5"]')
    assert set(rev_stars(B)) == {5}

    print('6) เจ้าของที่พักตัวอย่าง: ตัวกรอง "ที่พัก" / "สินค้า"')
    host = B.evaluate("api('/shops').then(r => r.shops.find(s => s.name === 'พี่ปุ้ย (ตัวอย่าง)').id)")
    B.goto(BASE + f'/#/shop/{host}'); B.wait_for_selector('#reviews .rv-sum')
    B.click('#rvChips .chip[data-f=stay]'); B.wait_for_selector('#rvChips .chip.on[data-f="stay"]')
    assert B.locator('#rvList .rev .kt', has_text='ที่พัก').count() == B.locator('#rvList .rev').count() == 3
    to_top(B, '#reviews'); shot(B, '07-reviews-filter-stay')
    B.click('#rvChips .chip[data-f=goods]'); B.wait_for_selector('#rvChips .chip.on[data-f="goods"]')
    assert B.locator('#rvList .rev .kt', has_text='สินค้า').count() == B.locator('#rvList .rev').count() > 0

    print('7) ผู้ซื้อรีวิวพร้อมแนบรูป (สูงสุด 3 รูป)')
    B.goto(BASE + '/#/login'); login(B, 'คุณรีวิว (ทดสอบ)', '0872' + stamp)
    due = time.strftime('%Y-%m-%d', time.localtime(time.time() + 3 * 86400))
    code = S.evaluate(f"api('/deals', {{role:'seller', title:'กล้องฟิล์มทดสอบรีวิว (ทดสอบ)', price:1500, delivery:'parcel', due_date:'{due}', fee_payer:'half', photos:[]}}).then(r => r.code)")
    B.evaluate(f"(async () => {{ await api('/deals/{code}/accept', {{}}); await api('/deals/{code}/pay', {{}}); }})()")
    S.evaluate(f"api('/deals/{code}/ship', {{tracking:'TH0000TEST01', carrier:'Kerry Express'}})")
    B.evaluate(f"api('/deals/{code}/confirm', {{}})")
    B.goto(BASE + f'/#/d/{code}'); B.click('text=ให้คะแนนผู้ขาย')
    B.click('#rvStars [data-n="4"]'); B.fill('#rvText', 'กล้องสภาพดีตามรูป แพ็คมาแน่นหนา ส่งไว แต่สายคล้องเก่ากว่าที่คิดนิดหน่อยค่ะ')
    for f in ('camera.jpg', 'evidence.jpg', 'camera.jpg'):
        upload(B, '#rvPhAdd', os.path.join(HERE, f)); B.wait_for_timeout(300)
    B.wait_for_function('S.rvPhotos.length === 3'); expect(B.locator('#rvPhAdd')).to_have_count(0)
    shot(B, '08-review-sheet-with-photos')
    B.click('#rvBtn'); wait_text(B, 'ขอบคุณสำหรับรีวิว')
    B.wait_for_selector('.rev .rph a'); assert B.locator('.rev .rph a').count() == 3
    B.goto(BASE + f'/#/shop/{uid}'); B.wait_for_selector('#reviews #rvList .rev .rph')
    expect(B.locator('#rvList .rev').first).to_contain_text('กล้องสภาพดีตามรูป')
    to_top(B, '#reviews'); shot(B, '09-shop-review-with-photos')
    br.close()

missing = [s for s in shots if not os.path.isfile(s) or os.path.getsize(s) < 5000]
if missing: errors.append('ไฟล์ภาพหน้าจอหาย/เล็กผิดปกติ: ' + ', '.join(missing))
print(f'\nภาพหน้าจอ {len(shots)} ไฟล์ที่ {os.path.abspath(OUT)}')
if errors:
    print('ข้อผิดพลาด:'); [print('  ✗', e) for e in errors]; sys.exit(1)
print('ผ่านทั้งหมด ✓ (ไม่มี JS error, ไม่มีเลื่อนแนวนอน, ฟอนต์ไทยโหลดครบ)')
