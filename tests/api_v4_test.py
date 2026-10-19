"""ทดสอบ API v4: ช่องทางโซเชียล (ตรวจ/แปลงรูปแบบ · แสดงบนโปรไฟล์/หน้าร้าน · ป้ายตรวจแล้วโดยทีมงาน)
และรีวิว (สรุป · 3 รีวิวสำคัญ · ดันรีวิวติชมล่าสุด · ตัวกรอง · เรียง · ดูเพิ่ม · รูปในรีวิว ≤ 3)
วิธีรัน: python3 tests/api_v4_test.py [http://localhost:8787]"""
import base64, os, sys, time
sys.argv = sys.argv[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'api_test.py'), encoding='utf-8').read().split('\nA, B, X = C(), C(), C()')[0]
exec(compile(src, 'api_test_helpers', 'exec'))
JPG = 'data:image/jpeg;base64,' + base64.b64encode(open(os.path.join(HERE, 'camera.jpg'), 'rb').read()).decode()
VID = 'data:video/mp4;base64,' + base64.b64encode(open(os.path.join(HERE, 'unboxing.mp4'), 'rb').read()).decode()

A, B, X, ADM, ANON = C(), C(), C(), C(), C()
stamp = str(int(time.time()))[-6:]
ua = A.login('ร้านโซเชียลทดสอบ', '081' + stamp + '4'); ub = B.login('ผู้ซื้อรีวิวทดสอบ', '082' + stamp + '5'); X.login('คนนอก', '083' + stamp + '6')
ADM.ok('/admin/login', {'password': admin_password()})

print('1) ช่องทางโซเชียล: แปลงชื่อผู้ใช้/ลิงก์เป็นรูปแบบมาตรฐาน')
cases = [
    ('facebook', 'padaeng.shop', 'padaeng.shop', 'https://www.facebook.com/padaeng.shop'),
    ('facebook', 'https://m.facebook.com/padaeng.shop/?ref=bookmarks', 'padaeng.shop', 'https://www.facebook.com/padaeng.shop'),
    ('facebook', 'fb.com/padaeng.shop', 'padaeng.shop', 'https://www.facebook.com/padaeng.shop'),
    ('facebook', 'https://www.facebook.com/profile.php?id=100012345678', 'โปรไฟล์ Facebook', 'https://www.facebook.com/profile.php?id=100012345678'),
    ('facebook', 'https://www.facebook.com/groups/vintage.th', 'กลุ่ม Facebook', 'https://www.facebook.com/groups/vintage.th'),
    ('line', '@PadaengShop', '@padaengshop', 'https://line.me/R/ti/p/@padaengshop'),
    ('line', 'padaeng99', 'padaeng99', 'https://line.me/ti/p/~padaeng99'),
    ('line', 'https://line.me/ti/p/~padaeng99', 'padaeng99', 'https://line.me/ti/p/~padaeng99'),
    ('line', 'https://line.me/R/ti/p/%40padaengshop', '@padaengshop', 'https://line.me/R/ti/p/@padaengshop'),
    ('line', 'https://lin.ee/AbC123x', 'LINE OA', 'https://lin.ee/AbC123x'),
    ('instagram', '@Padaeng.Shop', '@padaeng.shop', 'https://www.instagram.com/padaeng.shop/'),
    ('instagram', 'https://www.instagram.com/padaeng.shop/?igsh=xyz', '@padaeng.shop', 'https://www.instagram.com/padaeng.shop/'),
    ('tiktok', '@padaeng.shop', '@padaeng.shop', 'https://www.tiktok.com/@padaeng.shop'),
    ('tiktok', 'https://www.tiktok.com/@padaeng.shop?lang=th', '@padaeng.shop', 'https://www.tiktok.com/@padaeng.shop'),
    ('tiktok', 'https://vt.tiktok.com/ZSabc123/', 'TikTok', 'https://vt.tiktok.com/ZSabc123/'),
    ('youtube', '@PadaengChannel', '@PadaengChannel', 'https://www.youtube.com/@PadaengChannel'),
    ('youtube', 'https://www.youtube.com/channel/UC1234567890abcdef', 'ช่อง YouTube', 'https://www.youtube.com/channel/UC1234567890abcdef'),
    ('website', 'padaeng.example.com', 'padaeng.example.com', 'https://padaeng.example.com'),
    ('website', 'https://shop.example.co.th/about', 'shop.example.co.th/about', 'https://shop.example.co.th/about'),
    ('phone', '081 234 5678', '081-234-5678', 'tel:+66812345678'),
    ('phone', '+66 81-234-5678', '081-234-5678', 'tel:+66812345678'),
    ('phone', '02-123-4567', '02-123-4567', 'tel:+6621234567'),
]
for k, v, h, url in cases:
    r = A.ok('/me/socials', {k: v})
    got = [x for x in r['socials'] if x['key'] == k]
    check(f'{k}: "{v}" → {h}', got and got[0]['h'] == h and got[0]['url'] == url and not got[0]['verified'], got)

print('2) ช่องทางโซเชียล: ปฏิเสธรูปแบบผิด (บอกช่องที่ผิด)')
bad = [('facebook', 'ร้านป้าแดง'), ('facebook', 'https://evil.example.com/padaeng'), ('line', 'ab'), ('line', 'https://line.me/'),
       ('instagram', 'bad handle!'), ('instagram', 'https://www.instagram.com/p/Cxyz/'), ('tiktok', 'https://www.tiktok.com/padaeng'),
       ('youtube', 'https://youtu.be/dQw4w9WgXcQ'), ('website', 'javascript:alert(1)'), ('website', 'not a url'),
       ('website', 'https://facebook.com/padaeng.shop'), ('phone', '12345'), ('phone', '0812345678901'), ('facebook', 'javascript:alert(1)')]
for k, v in bad:
    s, e = A.req('/me/socials', {k: v})
    check(f'ปฏิเสธ {k}: "{v}"', s == 400 and e.get('field') == k and e['error'], e)
s, e = A.req('/me/socials', {'instagram': '@ok.handle', 'phone': 'abc'})
check('ผิดช่องเดียว → ไม่บันทึกทั้งชุด', s == 400 and e['field'] == 'phone' and [x['h'] for x in A.ok('/me')['user']['socials'] if x['key'] == 'instagram'] == ['@padaeng.shop'])
s, e = ANON.req('/me/socials', {'line': 'padaeng99'})
check('ยังไม่ล็อกอินบันทึกไม่ได้', s == 401)

print('3) แสดงบนโปรไฟล์ + หน้าร้าน (เรียงตามลำดับ · ลบได้ด้วยค่าว่าง)')
A.ok('/me/socials', {'facebook': 'padaeng.shop', 'line': '@padaengshop', 'instagram': '@padaeng.shop', 'tiktok': '', 'youtube': '', 'website': '', 'phone': '0812345678'})
pu = ANON.ok(f'/users/{ua["id"]}'); sh = ANON.ok(f'/shops/{ua["id"]}')
check('โปรไฟล์สาธารณะเห็น 4 ช่อง ตามลำดับ', [x['key'] for x in pu['socials']] == ['facebook', 'line', 'instagram', 'phone'], pu['socials'])
check('หน้าร้านเห็นเหมือนกัน', sh['socials'] == pu['socials'])
check('มีค่าสำหรับช่องแก้ไข (edit)', [x['edit'] for x in pu['socials']] == ['padaeng.shop', '@padaengshop', '@padaeng.shop', '081-234-5678'])
A.ok('/me/socials', {'phone': ''})
check('ส่งค่าว่าง = ลบช่องนั้น · ช่องที่ไม่ได้ส่งไม่ถูกแตะ', [x['key'] for x in A.ok('/me')['user']['socials']] == ['facebook', 'line', 'instagram'])

print('4) ป้าย "ตรวจแล้ว" (ทีมงานเท่านั้น) · แก้ค่า = ต้องตรวจใหม่')
s, e = A.req(f'/admin/users/{ua["id"]}/socials/verify', {'key': 'facebook'})
check('ผู้ใช้ทั่วไปกดยืนยันเองไม่ได้', s == 401)
r = ADM.ok(f'/admin/users/{ua["id"]}/socials/verify', {'key': 'facebook', 'verified': True})
check('ทีมงานยืนยัน Facebook', [x['verified'] for x in r['socials'] if x['key'] == 'facebook'] == [True])
s, e = ADM.req(f'/admin/users/{ua["id"]}/socials/verify', {'key': 'youtube'})
check('ยืนยันช่องที่ไม่ได้ใส่ไม่ได้', s == 400)
A.ok('/me/socials', {'facebook': 'https://facebook.com/padaeng.shop', 'line': 'padaeng99'})
check('บันทึกค่าเดิม (คนละรูปแบบ) ป้ายยังอยู่', [x['verified'] for x in A.ok('/me')['user']['socials'] if x['key'] == 'facebook'] == [True])
A.ok('/me/socials', {'facebook': 'padaeng.newpage'})
check('เปลี่ยนเพจ → ป้ายตรวจแล้วหายไป', [x['verified'] for x in A.ok('/me')['user']['socials'] if x['key'] == 'facebook'] == [False])

print('5) ร้านตัวอย่างมีช่องทางโซเชียลตัวอย่าง')
gold = [x for x in ANON.ok('/shops')['shops'] if x['stats']['level'] == 'gold'][0]
check('Gold ตัวอย่าง: 6 ช่อง · Facebook ตรวจแล้ว · ลิงก์ .example', len(gold['socials']) >= 6 and any(x['key'] == 'facebook' and x['verified'] for x in gold['socials'])
      and any(x['key'] == 'website' and '.example' in x['url'] for x in gold['socials']), gold['socials'])


def done_deal(price, title):
    code = new_deal(A, title=title, price=price)
    B.ok(f'/deals/{code}/accept', {}); B.ok(f'/deals/{code}/pay', {})
    A.ok(f'/deals/{code}/ship', {'tracking': 'TH0000TEST01', 'carrier': 'Kerry Express'}); B.ok(f'/deals/{code}/confirm', {})
    return code


print('6) รูปในรีวิว (ไม่บังคับ · สูงสุด 3 รูป · รูปเท่านั้น)')
c1 = done_deal(2500, 'กล้องทดสอบรีวิว')
s, e = B.req(f'/deals/{c1}/review', {'stars': 5, 'text': 'x', 'photos': [PNG] * 4})
check('4 รูป → ปฏิเสธ', s == 400 and '3 รูป' in e['error'], e)
s, e = B.req(f'/deals/{c1}/review', {'stars': 5, 'text': 'x', 'photos': [VID]})
check('วิดีโอ → ปฏิเสธ (รูปเท่านั้น)', s == 400)
B.ok(f'/deals/{c1}/review', {'stars': 5, 'text': 'ของตรงปก แพ็คดีมาก ' * 6, 'photos': [JPG, PNG, PNG]})
dr = deal(B, c1)['reviews'][0]
check('รีวิวในหน้าดีลมี 3 รูป (/uploads/…)', len(dr['photos']) == 3 and all(p.startswith('/uploads/') for p in dr['photos']), dr)
c2 = done_deal(1800, 'วิทยุทดสอบรีวิว'); B.ok(f'/deals/{c2}/review', {'stars': 4, 'text': 'ดีครับ ส่งไวมาก ห่อของมาอย่างดี ' * 4, 'photos': [JPG]})
c3 = done_deal(1500, 'แผ่นเสียงทดสอบ'); B.ok(f'/deals/{c3}/review', {'stars': 5, 'text': 'ประทับใจมาก แนะนำร้านนี้เลย ' * 5, 'photos': [PNG, PNG]})
c4 = done_deal(3000, 'นาฬิกาทดสอบ'); B.ok(f'/deals/{c4}/review', {'stars': 5, 'text': 'คุ้มค่า ' * 20, 'photos': [JPG]})
c5 = done_deal(100, 'ของถูกทดสอบ'); B.ok(f'/deals/{c5}/review', {'stars': 1})        # ติชม: ไม่มีข้อความ ราคาต่ำ → คะแนนต่ำสุด
c6 = done_deal(200, 'ของทดสอบ 6'); B.ok(f'/deals/{c6}/review', {'stars': 3, 'text': 'พอใช้'})

print('7) สรุปรีวิว + 3 รีวิวสำคัญ + ดันรีวิวติชมล่าสุด')
sh = ANON.ok(f'/shops/{ua["id"]}'); top = sh['reviews_top']; sm = top['summary']
check('สรุป: 6 รีวิว · เฉลี่ย 3.83 · แท่งดาว', sm['count'] == 6 and sm['avg'] == 3.83 and sm['dist'] == {'1': 1, '2': 0, '3': 1, '4': 1, '5': 3}, sm)
check('จำนวนต่อตัวกรอง', sm['counts'] == {'all': 6, '5': 3, '4': 1, 'low': 2, 'photos': 4, 'goods': 6, 'stay': 0}, sm['counts'])
check('ค่าเริ่มต้นแสดง 3 รีวิว + มีต่อ', len(top['items']) == 3 and top['total'] == 6 and top['has_more'] and top['sort'] == 'important')
ranks = [r['stars'] for r in top['items']]
check('รีวิวติชม 1 ดาว (คะแนนต่ำสุด) ถูกดันขึ้นอันดับ 3 + ติดป้าย pinned', ranks[2] == 1 and top['items'][2]['pinned'] and not any(r['pinned'] for r in top['items'][:2]), ranks)
check('อันดับ 1–2 มีรูป + ข้อความยาว', all(r['photos'] and len(r['text']) > 60 for r in top['items'][:2]))
full = ANON.ok(f'/users/{ua["id"]}/reviews?role=seller&limit=50')
check('สำคัญที่สุด: คะแนนเรียงลดลง (ยกเว้นรีวิวที่ถูกดัน)', [r['score'] for r in full['items'] if not r['pinned']] == sorted([r['score'] for r in full['items'] if not r['pinned']], reverse=True))
p1 = ANON.ok(f'/users/{ua["id"]}/reviews?role=seller&offset=0&limit=4'); p2 = ANON.ok(f'/users/{ua["id"]}/reviews?role=seller&offset=4&limit=4')
ids = [r['id'] for r in p1['items'] + p2['items']]
check('ดูเพิ่มทีละหน้า: ครบ 6 ไม่ซ้ำ', len(ids) == 6 and len(set(ids)) == 6 and p1['has_more'] and not p2['has_more'])
rec = ANON.ok(f'/users/{ua["id"]}/reviews?role=seller&sort=recent&limit=50')['items']
check('ล่าสุด: เรียงตามเวลา', [r['created_at'] for r in rec] == sorted([r['created_at'] for r in rec], reverse=True) and rec[0]['stars'] == 3)

print('8) ตัวกรอง')
for f, cond, n in [('5', lambda r: r['stars'] == 5, 3), ('4', lambda r: r['stars'] == 4, 1), ('low', lambda r: r['stars'] <= 3, 2),
                   ('photos', lambda r: len(r['photos']) > 0, 4), ('goods', lambda r: r['kind'] == 'goods', 6), ('stay', lambda r: True, 0)]:
    pg = ANON.ok(f'/users/{ua["id"]}/reviews?role=seller&filter={f}&limit=50')
    check(f'ตัวกรอง {f}: {n} รีวิว ตรงเงื่อนไข', pg['total'] == n and len(pg['items']) == n and all(cond(r) for r in pg['items']) and pg['filter'] == f)
pg = ANON.ok(f'/users/{ua["id"]}/reviews?role=seller&filter=evil&sort=evil&limit=abc')
check('ค่าแปลก ๆ → ค่าเริ่มต้น', pg['filter'] == 'all' and pg['sort'] == 'important' and len(pg['items']) == 3)
s, e = ANON.req('/users/99999999/reviews')
check('ผู้ใช้ไม่มีอยู่ → 404', s == 404)

print('9) รีวิวตัวอย่าง (ข้อมูลปลอม ติดป้าย) ใช้ทดลองตัวกรองได้')
host = [x for x in ANON.ok('/shops')['shops'] if x['name'] == 'พี่ปุ้ย (ตัวอย่าง)'][0]
hp = ANON.ok(f'/shops/{host["id"]}')['reviews_top']; hc = hp['summary']['counts']
check('เจ้าของที่พักตัวอย่าง: มีทั้งรีวิวสินค้าและที่พัก + มีรูป + มีติชม', hc['goods'] > 0 and hc['stay'] > 0 and hc['photos'] > 0 and hc['low'] > 0, hc)
check('รีวิวตัวอย่างติดป้าย is_demo + ข้อความ "(รีวิวตัวอย่าง)" สำหรับรีวิวใหม่', all(r['is_demo'] for r in hp['items']))
gp = ANON.ok(f'/shops/{gold["id"]}')['reviews_top']
check('Gold ตัวอย่าง: 3 อันดับแรกมีรีวิวติชม (≤2 ดาว) ล่าสุด', any(r['stars'] <= 2 and r['pinned'] for r in gp['items']), [r['stars'] for r in gp['items']])
check('ร้านยังเป็น Gold', ANON.ok(f'/shops/{gold["id"]}')['stats']['level'] == 'gold')

print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {fail}')
sys.exit(1 if fail else 0)
