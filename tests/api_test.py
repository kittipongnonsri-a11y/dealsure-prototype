"""ทดสอบ API แบบ end-to-end ด้วยผู้ใช้ทดสอบ 2 คน (เหมือนใช้ curl)
วิธีรัน: python3 tests/api_test.py [http://localhost:8787]"""
import json, sys, http.cookiejar, urllib.request, urllib.error, base64, time


def admin_password():
    """อ่านรหัสผู้ดูแลจาก env ADMIN_PASSWORD หรือไฟล์ data/admin_password.txt (กรณีเซิร์ฟเวอร์สุ่มให้)"""
    import os
    pw = os.environ.get('ADMIN_PASSWORD')
    if pw: return pw
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'admin_password.txt')
    if os.path.exists(fp): return open(fp).read().strip()
    sys.exit('ตั้งตัวแปร ADMIN_PASSWORD ให้ตรงกับเซิร์ฟเวอร์ก่อนรันทดสอบ')

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8787'
PNG = 'data:image/png;base64,' + base64.b64encode(bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0f01f0005000201e5f9c4e90000000049454e44ae426082')).decode()
ok = fail = 0


class C:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def req(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(BASE + '/api' + path, data=data, headers={'Content-Type': 'application/json'})
        try:
            with self.op.open(r) as resp: return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def ok(self, path, body=None):
        s, j = self.req(path, body)
        assert s == 200, f'{path} -> {s} {j}'
        return j

    def login(self, name, phone):
        j = self.ok('/login/start', {'name': name, 'phone': phone})
        s, e = self.req('/login/verify', {'phone': j['phone'], 'code': '000000' if j['demo_code'] != '000000' else '111111'})
        assert s == 400, 'wrong OTP must fail'
        self.ok('/login/verify', {'phone': j['phone'], 'code': j['demo_code']})
        return self.ok('/me')['user']


def check(name, cond, extra=''):
    global ok, fail
    if cond: ok += 1; print('  ✓', name)
    else: fail += 1; print('  ✗', name, extra)


def deal(c, code): return c.ok('/deals/' + code)


def new_deal(c, **kw):
    b = dict(role='seller', title='ทดสอบ', price=1000, delivery='parcel', due_date=time.strftime('%Y-%m-%d', time.localtime(time.time() + 2 * 86400)), fee_payer='half', photos=[PNG])
    b.update(kw)
    return c.ok('/deals', b)['code']


A, B, X = C(), C(), C()
stamp = str(int(time.time()))[-6:]
ua = A.login('ผู้ขายทดสอบ A', '081' + stamp + '1')
ub = B.login('ผู้ซื้อทดสอบ B', '082' + stamp + '2')
X.login('คนนอก X', '083' + stamp + '3')
print('1) ล็อกอิน + OTP'); check('A และ B ล็อกอินได้', ua['id'] != ub['id'])

print('2) ดีลส่งพัสดุ: สร้าง → รับ → จ่าย → ส่ง → ของถึง → เร่งเวลา → ปล่อยเงินอัตโนมัติ')
code = new_deal(A, title='กล้องฟิล์มทดสอบ', price=2500)
d = deal(B, code)
check('ค่าธรรมเนียม 3% คนละครึ่ง', d['fee'] == 75 and d['buyer_pay'] == 2537.5 and d['seller_get'] == 2462.5, d)
check('ผู้ซื้อเห็นปุ่มรับดีล + โปรไฟล์ผู้ขาย', 'accept' in d['actions'] and d['seller']['name'] == 'ผู้ขายทดสอบ A')
B.ok(f'/deals/{code}/accept', {})
s, e = X.req(f'/deals/{code}')
check('คนนอกดูดีลที่มีคู่แล้วไม่ได้', s == 403)
s, e = A.req(f'/deals/{code}/pay', {})
check('ผู้ขายกดจ่ายแทนไม่ได้', s == 403)
B.ok(f'/deals/{code}/pay', {})
check('เงินพักไว้ (held)', deal(A, code)['status'] == 'held')
s, e = A.req(f'/deals/{code}/ship', {'tracking': 'x', 'carrier': 'Kerry Express'})
check('เลขพัสดุสั้นเกินถูกปฏิเสธ', s == 400)
A.ok(f'/deals/{code}/ship', {'tracking': 'TH0000TEST01', 'carrier': 'Kerry Express'})
d = deal(B, code)
check('สถานะ shipped + ผู้ซื้อยืนยัน/แจ้งปัญหาได้', d['status'] == 'shipped' and 'confirm' in d['actions'] and 'dispute' in d['actions'])
B.ok(f'/deals/{code}/skip', {'hours': 48})
d = deal(B, code)
check('เร่งเวลา 2 วัน → ขนส่งแจ้งของถึง (delivered) + นับถอยหลัง 3 วัน', d['status'] == 'delivered' and abs(d['auto_release_at'] - d['delivered_at'] - 3 * 86400) < 1)
B.ok(f'/deals/{code}/skip', {'hours': 72})
d = deal(A, code)
check('ครบ 3 วัน → ปล่อยเงินอัตโนมัติ', d['status'] == 'completed' and d['release_reason'] == 'auto')
check('ผู้ขายเห็นยอด รอโอนรอบถัดไป', d['payout'] and d['payout']['status'] == 'pending')
B.ok(f'/deals/{code}/review', {'stars': 5, 'text': 'ดีมาก'})
A.ok(f'/deals/{code}/review', {'stars': 4, 'text': 'จ่ายไว'})
s, e = B.req(f'/deals/{code}/review', {'stars': 5})
check('รีวิวซ้ำไม่ได้', s == 400)
p = A.ok(f'/users/{ua["id"]}')
check('โปรไฟล์มีสถิติ + ประวัติ', p['stats']['sales'] == 1 and p['stats']['rating'] == 5 and len(p['history']) == 1)

print('3) ดีลแมสเซนเจอร์: หลักฐาน → ปล่อยเงิน 24 ชม.')
code = new_deal(A, title='แมสทดสอบ', delivery='messenger', fee_payer='buyer', price=500)
B.ok(f'/deals/{code}/accept', {}); B.ok(f'/deals/{code}/pay', {})
s, e = A.req(f'/deals/{code}/ship', {})
check('ต้องมีหลักฐาน', s == 400)
A.ok(f'/deals/{code}/ship', {'proof_text': 'Grab ทดสอบ ทะเบียน 1กข1234', 'photos': [PNG]})
d = deal(B, code)
check('ส่งแล้วถือว่าถึง + ปล่อยใน 24 ชม.', d['status'] == 'delivered' and abs(d['auto_release_at'] - d['shipped_at'] - 86400) < 1)
B.ok(f'/deals/{code}/skip', {'hours': 24})
check('ครบ 24 ชม. ปล่อยเงิน', deal(A, code)['status'] == 'completed')

print('4) ดีลนัดรับ (ผู้ซื้อสร้าง): รหัส 4 หลัก → ปล่อยเงินทันที')
code = new_deal(B, role='buyer', title='นัดรับทดสอบ', delivery='meet', fee_payer='seller', price=800)
d = deal(A, code)
check('ผู้ขายเปิดลิงก์แล้วเห็นปุ่มรับดีล', 'accept' in d['actions'] and d['buyer']['name'] == 'ผู้ซื้อทดสอบ B')
A.ok(f'/deals/{code}/accept', {}); B.ok(f'/deals/{code}/pay', {})
da, db_ = deal(A, code), deal(B, code)
check('ผู้ขายเห็นรหัส ผู้ซื้อไม่เห็น', da.get('meet_code') and len(da['meet_code']) == 4 and 'meet_code' not in db_)
wrong = '0000' if da['meet_code'] != '0000' else '1111'
s, e = B.req(f'/deals/{code}/meet-code', {'code': wrong})
check('รหัสผิดถูกปฏิเสธ', s == 400)
B.ok(f'/deals/{code}/meet-code', {'code': da['meet_code']})
d = deal(A, code)
check('รหัสถูก → ปล่อยเงินทันที', d['status'] == 'completed' and d['release_reason'] == 'meet_code' and d['seller_get'] == 776)

print('5) ข้อพิพาท + แอดมินตัดสิน (คืนบางส่วน / คืนเต็ม / ปล่อยเงิน)')
codes = []
for i in range(3):
    c = new_deal(A, title=f'ข้อพิพาท {i}', price=1500)
    B.ok(f'/deals/{c}/accept', {}); B.ok(f'/deals/{c}/pay', {})
    A.ok(f'/deals/{c}/ship', {'tracking': f'TH0000TEST0{i}', 'carrier': 'Flash Express'})
    B.ok(f'/deals/{c}/simulate-delivered', {})
    codes.append(c)
s, e = B.req(f'/deals/{codes[0]}/dispute', {'reason': 'ของเสียหาย', 'files': []})
check('ต้องแนบหลักฐาน', s == 400)
for c in codes: B.ok(f'/deals/{c}/dispute', {'reason': 'ของเสียหาย', 'detail': 'กล่องบุบ', 'files': [PNG]})
B.ok(f'/deals/{codes[0]}/skip', {'hours': 24 * 7})
check('ระหว่างข้อพิพาท เร่งเวลาแล้วเงินยังพักไว้', deal(A, codes[0])['status'] == 'disputed')
ADM = C()
s, e = ADM.req('/admin/overview')
check('แอดมินต้องล็อกอิน', s == 401)
s, e = ADM.req('/admin/login', {'password': 'ผิด'})
check('รหัสแอดมินผิดถูกปฏิเสธ', s == 403)
ADM.ok('/admin/login', {'password': admin_password()})
ov = ADM.ok('/admin/overview')
check('แอดมินเห็นข้อพิพาท 3 รายการ', sum(1 for x in ov['disputes'] if x['code'] in codes) == 3)
ADM.ok(f'/admin/deals/{codes[0]}/resolve', {'decision': 'partial', 'refund_amount': 500, 'note': 'แบ่งกันคนละส่วน'})
ADM.ok(f'/admin/deals/{codes[1]}/resolve', {'decision': 'refund'})
ADM.ok(f'/admin/deals/{codes[2]}/resolve', {'decision': 'release'})
d0, d1, d2 = deal(A, codes[0]), deal(A, codes[1]), deal(A, codes[2])
# v13: คืนบางส่วน → ค่าธรรมเนียมเต็มของดีล 45 (3% ของ 1,500) · ส่วนผู้ซื้อ 22.50 ไม่คืน · ผู้ขายได้ 1,500 − 500 − 22.50 = 977.50
check('คืนบางส่วน: ผู้ซื้อได้ 500 ผู้ขายได้ 977.50 (ค่าธรรมเนียมเต็ม 45)', d0['status'] == 'partial' and d0['refund_amount'] == 500 and d0['payout_amount'] == 977.5 and d0['fee_charged'] == 45, d0)
check('คืนเต็ม', d1['status'] == 'refunded' and d1['refund_amount'] == 1522.5)
check('ปล่อยเงิน', d2['status'] == 'completed' and d2['release_reason'] == 'admin')

print('6) ส่งช้า: ผู้ซื้อขอเงินคืนหลังวันที่ตกลง')
code = new_deal(A, title='ส่งช้าทดสอบ', price=600)
B.ok(f'/deals/{code}/accept', {}); B.ok(f'/deals/{code}/pay', {})
s, e = B.req(f'/deals/{code}/late-refund', {})
check('ยังไม่เลยกำหนด ขอคืนไม่ได้', s == 400)
B.ok(f'/deals/{code}/skip', {'hours': 72})
check('เลยกำหนดแล้วมีปุ่มขอคืน', 'late_refund' in deal(B, code)['actions'])
B.ok(f'/deals/{code}/late-refund', {})
check('คืนเงินแล้ว', deal(B, code)['status'] == 'refunded')

print('7) วงเงิน + ยืนยันตัวตน')
s, e = A.req('/deals', dict(role='seller', title='แพง', price=4000, delivery='parcel', due_date=time.strftime('%Y-%m-%d'), fee_payer='half'))
check('เกิน 3,000 ต้องยืนยันตัวตน', s == 403 and 'ยืนยันตัวตน' in e['error'])
A.ok('/me/verify-id', {'image': PNG})
check('ยืนยันตัวตนอัตโนมัติ (ทดสอบ)', A.ok('/me')['user']['verified'])
code4k = new_deal(A, title='แพง 4,000', price=4000)
check('สร้างดีล 4,000 ได้หลังยืนยัน', bool(code4k))
s, e = A.req('/deals', dict(role='seller', title='แพงมาก', price=6000, delivery='parcel', due_date=time.strftime('%Y-%m-%d'), fee_payer='half'))
check('Bronze เกิน 5,000 ไม่ได้', s == 400 and '5,000' in e['error'])
s, e = B.req(f'/deals/{code4k}/accept', {})
check('ผู้ซื้อที่ยังไม่ยืนยันตัวตน รับดีล 4,000 ไม่ได้', s == 403)
check('ขั้นต่ำ 20 บาท: ราคา 100 ค่าธรรมเนียม 20', deal(B, new_deal(A, title='ถูก', price=100))['fee'] == 20)

print('8) ซื้อจากหน้าร้านตัวอย่าง (Gold)')
shops = B.ok('/shops')['shops']
gold = [s for s in shops if s['stats']['level'] == 'gold'][0]
shop = B.ok(f'/shops/{gold["id"]}')
check('หน้าร้านตัวอย่างเป็น Gold + มีสินค้าขายประจำ ≥ 6', shop['stats']['level'] == 'gold' and shop['verified'] and len([p for p in shop['products'] if p.get('kind') != 'stay']) >= 6)
watch = [p for p in shop['products'] if p['price'] == 3200][0]
lens = [p for p in shop['products'] if p['price'] == 6500][0]
s, e = B.req(f'/products/{watch["id"]}/buy', {'delivery': 'parcel'})
check('สินค้า 3,200 ต้องยืนยันตัวตน', s == 403)
B.ok('/me/verify-id', {'image': PNG})
X.ok('/me/verify-id', {'image': PNG})
s, e = X.req(f'/products/{lens["id"]}/buy', {'delivery': 'parcel'})
check('ผู้ใช้ใหม่ (X) ซื้อเกิน 5,000 ไม่ได้', s == 400 and '5,000' in e['error'])
check('B ทำดีลสำเร็จครบ 5 ดีลแล้ว วงเงินซื้อปลดล็อก', B.ok('/me')['user']['stats']['buyer_limit'] == 50000)
code = B.ok(f'/products/{watch["id"]}/buy', {'delivery': 'meet'})['code']
d = deal(B, code)
check('สั่งซื้อจากร้าน → รอจ่าย', d['status'] == 'accepted' and 'pay' in d['actions'] and d['source'] == 'shop')
B.ok(f'/deals/{code}/pay', {})
check('จ่ายแล้ว เงินพักไว้', deal(B, code)['status'] == 'held')

print('9) แจ้งเตือน + รอบโอนเงิน')
n = A.ok('/notifications')
check('ผู้ขายมีแจ้งเตือน', n['unread'] > 5)
A.ok('/notifications/read', {})
check('อ่านแล้ว', A.ok('/notifications')['unread'] == 0)
pay = A.ok('/payouts')
check('มียอดรอโอนรอบถัดไป', pay['pending'] > 0)
ADM.ok('/admin/payouts/run', {})
check('จำลองรอบโอนแล้ว', A.ok('/payouts')['pending'] == 0)

print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {fail}')
sys.exit(1 if fail else 0)
