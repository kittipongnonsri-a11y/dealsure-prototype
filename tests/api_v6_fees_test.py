"""ทดสอบ API v6: กฎค่าธรรมเนียม/คืนเงิน/โอนเงินที่เจ้าของยืนยันแล้ว
1) ค่าธรรมเนียม 3% ขั้นต่ำ 20 บาท เลือกผู้จ่ายได้   2) ยอดดีลขั้นต่ำ 100 บาท (สร้างดีล + หน้าร้าน)
3) ค่าโอนออก 30 บาท/วัน หักจากยอดรวมโอนรายวัน ฟรีเมื่อยอดรวม ≥ 1,000   4) ผู้ซื้อยกเลิกเอง = ค่าดำเนินการ 2% ขั้นต่ำ 10 บาท
5) ผู้ขาย/เจ้าของผิด = คืนเต็ม + ค่าปรับเท่าค่าธรรมเนียม หักจากยอดโอนถัดไป + แจ้งเตือนแอดมินเมื่อผิดซ้ำ ≥3 ใน 30 วัน
6) คืนบางส่วน = ค่าธรรมเนียมคิดจากยอดที่ผู้ขายได้จริง (ขั้นต่ำ 20)   7) แสดงยอดจริงก่อนจ่าย/ก่อนยกเลิก
8) ผู้ขายส่งของ/ส่งมอบแล้ว ผู้ซื้อยกเลิกไม่ได้ · ผู้ซื้อแพ้ข้อพิพาทถูกบันทึก ≥3 ใน 90 วัน → เสนอระงับบัญชี
วิธีรัน: python3 tests/api_v6_fees_test.py [http://localhost:8787]   (ห้ามรันกับเว็บจริง)"""
import os, sqlite3, sys, time
from datetime import datetime, timedelta, timezone
sys.argv = sys.argv[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'api_test.py'), encoding='utf-8').read().split('\nA, B, X = C(), C(), C()')[0]
exec(compile(src, 'api_test_helpers', 'exec'))
if not BASE.startswith(('http://localhost', 'http://127.0.0.1')): sys.exit('รันกับเซิร์ฟเวอร์ในเครื่องเท่านั้น')

TZ = timezone(timedelta(hours=7))
def bkk_date(days): return (datetime.now(TZ) + timedelta(days=days)).strftime('%Y-%m-%d')
def r2(x): return round(x + 1e-9, 2)
def charge(paid): return r2(min(paid, max(10, paid * 0.02)))
MAP = 'https://maps.app.goo.gl/AbCdEf123'
def stay_body(**kw):
    b = dict(kind='stay', role='seller', title='บ้านพักทดสอบ v6', address='1 ม.1 ต.ทดสอบ', map_url=MAP, checkin_date=bkk_date(10),
             checkin_time='14:00', checkout_date=bkk_date(11), guests=2, price=1000, fee_payer='half', host_contact='โฮสต์', free_cancel_days=3, photos=[PNG])
    b.update(kw); return b

stamp = str(int(time.time()))[-6:]
S, B, S2, ADM = C(), C(), C(), C()
us = S.login('ผู้ขาย v6', '084' + stamp + '1'); ub = B.login('ผู้ซื้อ v6', '085' + stamp + '2'); S2.login('ผู้ขาย v6 ฝั่งสอง', '086' + stamp + '3')
ADM.ok('/admin/login', {'password': admin_password()})
ADM.ok('/admin/payouts/run', {})  # เคลียร์ยอดค้างของผู้ใช้อื่นก่อน (เครื่องทดสอบเท่านั้น)

def paid_deal(seller=S, buyer=B, **kw):
    code = new_deal(seller, **kw); buyer.ok(f'/deals/{code}/accept', {}); buyer.ok(f'/deals/{code}/pay', {}); return code

print('1) ค่าธรรมเนียม 3% ขั้นต่ำ 20 บาท · เลือกผู้จ่าย')
for payer, bp, sg in (('buyer', 2575, 2500), ('seller', 2500, 2425), ('half', 2537.5, 2462.5)):
    d = deal(B, new_deal(S, price=2500, fee_payer=payer))
    check(f'2,500 บาท {payer}: ค่าธรรมเนียม 75 · ผู้ซื้อจ่าย {bp} · ผู้ขายได้ {sg}', d['fee'] == 75 and d['buyer_pay'] == bp and d['seller_get'] == sg, d['fee'])
check('ดีล 100 บาท ค่าธรรมเนียมขั้นต่ำ 20', deal(B, new_deal(S, price=100))['fee'] == 20)

print('2) ยอดดีลขั้นต่ำ 100 บาท')
s, e = S.req('/deals', dict(role='seller', title='ถูกไป', price=99, delivery='parcel', due_date=bkk_date(2), fee_payer='half'))
check('สร้างดีล 99 บาทไม่ได้ + ข้อความไทยชัดเจน', s == 400 and 'ขั้นต่ำ 100 บาท' in e['error'], e)
s, e = S.req('/deals', dict(role='buyer', title='ถูกไป', price='50', delivery='meet', due_date=bkk_date(2), fee_payer='buyer'))
check('ผู้ซื้อสร้างดีล 50 บาทก็ไม่ได้', s == 400 and 'ขั้นต่ำ 100 บาท' in e['error'])
s, e = S.req('/deals', stay_body(price=99))
check('ดีลที่พัก 99 บาทไม่ได้', s == 400 and 'ขั้นต่ำ 100 บาท' in e['error'])
check('ดีล 100 บาทพอดีได้', bool(new_deal(S, price=100)))
s, e = S.req('/products', {'title': 'ของถูก', 'price': '99', 'deliveries': ['parcel']})
check('ลงสินค้าหน้าร้านราคา 99 ไม่ได้', s == 400 and 'ขั้นต่ำ 100 บาท' in e['error'])
s, e = S.req('/products', dict(stay_body(price='80'), kind='stay'))
check('ลงที่พักราคาต่อคืน 80 ไม่ได้', s == 400 and 'ขั้นต่ำ 100 บาท' in e['error'])
pid = S.ok('/products', {'title': 'ของ 100 บาท', 'price': '100', 'deliveries': ['parcel']})['id']
# สินค้าเก่าที่ลงไว้ก่อนกฎใหม่ (ราคา 80) → สั่งซื้อไม่ได้
db = sqlite3.connect(os.path.join(os.environ.get('DEALSURE_DATA', os.path.join(HERE, '..', 'data')), 'dealsure.db'))
db.execute('UPDATE products SET price=80 WHERE id=?', (pid,)); db.commit(); db.close()
s, e = B.req(f'/products/{pid}/buy', {'delivery': 'parcel'})
check('สั่งซื้อสินค้าหน้าร้านที่ต่ำกว่า 100 ไม่ได้ + ข้อความชัดเจน', s == 400 and 'ขั้นต่ำ 100 บาท' in e['error'], e)

print('3) ค่าโอนออก 30 บาท/วัน · รวมโอนวันละครั้ง · v13: ฟรีเมื่อยอดรวม ≥ 3,000 (ดีลชัวร์จ่ายค่าโอนให้)')
c1 = paid_deal(price=300); c2 = paid_deal(price=400, delivery='meet')
for c in (c1,):
    S.ok(f'/deals/{c}/ship', {'tracking': 'TH00V6' + c[-4:], 'carrier': 'Kerry Express'}); B.ok(f'/deals/{c}/confirm', {})
B.ok(f'/deals/{c2}/meet-code', {'code': S.ok(f'/deals/{c2}')['meet_code']})
pay = S.ok('/payouts')
g = r2(290 + 390)  # seller_get: 300-10, 400-10
check(f'ยอดรวมรอโอน {g} (2 ดีล)', pay['pending'] == g, pay['pending'])
check('ยอดรวม < 3,000 → ค่าโอนออก 30 บาท', pay['next']['transfer_fee'] == 30 and pay['next']['net'] == r2(g - 30) and pay['rule'] == {'fee': 30, 'free_from': 3000}, pay)
r = ADM.ok('/admin/payouts/run', {})
mine = [b for b in r['batches'] if b['user_id'] == us['id']]
check('โอน 1 ครั้งต่อวันรวมทุกดีล (1 รอบ 2 ดีล)', len(mine) == 1 and S.ok('/payouts')['batches'][0]['n'] == 2)
check('หักค่าโอนออก 30 จากยอดรวม', mine[0]['transfer_fee'] == 30 and mine[0]['net'] == r2(g - 30))
check('แจ้งเตือนผู้ขายแสดงค่าโอนออก', any('ค่าโอนออก −30' in n['text'] for n in S.ok('/notifications')['items']))
c3 = paid_deal(price=600); c4 = paid_deal(price=500)
for c in (c3, c4): S.ok(f'/deals/{c}/ship', {'tracking': 'TH01V6' + c[-4:], 'carrier': 'Kerry Express'}); B.ok(f'/deals/{c}/confirm', {})
pay = S.ok('/payouts')
check('v13: ยอดรวม 1,080 (< 3,000) → ยังเสียค่าโอน 30', pay['pending'] == 1080 and pay['next']['transfer_fee'] == 30 and pay['next']['net'] == 1050, pay['next'])
c3b = paid_deal(price=2000); S.ok(f'/deals/{c3b}/ship', {'tracking': 'TH0BV6' + c3b[-4:], 'carrier': 'Kerry Express'}); B.ok(f'/deals/{c3b}/confirm', {})
pay = S.ok('/payouts')
check('ยอดรวม 3,050 (≥ 3,000) → โอนฟรี', pay['pending'] == 3050 and pay['next']['transfer_fee'] == 0 and pay['next']['net'] == 3050, pay['next'])
r = ADM.ok('/admin/payouts/run', {})
mine = [b for b in r['batches'] if b['user_id'] == us['id']][0]
check('รอบโอนนี้ไม่มีค่าโอนออก', mine['transfer_fee'] == 0 and mine['net'] == 3050)

print('4) ผู้ซื้อยกเลิกเอง → ค่าดำเนินการ = max(10, 2%, ต้นทุนรับเงิน + 5)')
c = paid_deal(price=100, fee_payer='seller')  # จ่าย 100 → max(10, 2, 1.77+5) = 10
d = deal(B, c)
check('มีปุ่มยกเลิกก่อนส่งของ + ยอดจริงก่อนกด', 'buyer_cancel' in d['actions'] and d['cancel_preview'] == {'type': 'buyer_choice', 'paid': 100, 'charge': 10, 'refund': 90, 'card_fee': 0}, d.get('cancel_preview'))
r = B.ok(f'/deals/{c}/cancel', {})
d = deal(B, c)
check('คืน 90 หักค่าดำเนินการ 10 (ขั้นต่ำ)', r['charge'] == 10 and r['refund'] == 90 and d['status'] == 'refunded' and d['refund_amount'] == 90 and d['cancel_charge'] == 10 and d['fault'] == 'buyer')
check('ผู้ขายไม่โดนค่าปรับเมื่อผู้ซื้อยกเลิกเอง', not (deal(S, c)['penalty'] or 0) and S.ok('/payouts')['penalty_owed'] == 0)
c = paid_deal(price=1500)  # จ่าย 1,522.50 → 2% = 30.45 แต่ต้นทุน PromptPay 1.77% = 26.95 + 5 = 31.95 สูงกว่า
r = B.ok(f'/deals/{c}/cancel', {})
check('จ่าย 1,522.50 (พร้อมเพย์) → ค่าดำเนินการ 31.95 (ต้นทุน+5) คืน 1,490.55', r['charge'] == 31.95 and deal(B, c)['refund_amount'] == 1490.55, r)
check('แจ้งเตือนผู้ซื้อระบุค่าดำเนินการ', any('ค่าดำเนินการ' in n['text'] for n in B.ok('/notifications')['items']))
# จ่ายด้วยบัตร: ค่าธรรมเนียมบัตร 4% + 11 ไม่คืน
cc = new_deal(S, price=1000); B.ok(f'/deals/{cc}/accept', {})
po = deal(B, cc)['pay_options']
check('ก่อนจ่าย: เห็นตัวเลือกพร้อมเพย์ (ไม่มีค่าเพิ่ม) / บัตร (+51.60)', po['promptpay']['surcharge'] == 0 and po['promptpay']['total'] == 1015 and po['card']['surcharge'] == 51.6 and po['card']['total'] == 1066.6, po)
s_, e_ = B.req(f'/deals/{cc}/pay', {'method': 'bitcoin'}); check('วิธีจ่ายแปลก ๆ ถูกปฏิเสธ', s_ == 400)
B.ok(f'/deals/{cc}/pay', {'method': 'card'})
d = deal(B, cc)
check('บันทึกวิธีจ่ายบัตร + ค่าธรรมเนียมบัตร', d['pay_method'] == 'card' and d['card_fee'] == 51.6)
check('แจ้งเตือนผู้ซื้อแสดงยอดรวมค่าธรรมเนียมบัตร', any('ค่าธรรมเนียมบัตร' in n['text'] for n in B.ok('/notifications')['items']))
r = B.ok(f'/deals/{cc}/cancel', {})
check('ยกเลิกเอง (บัตร): ค่าดำเนินการ 20.30 คืน 994.70 · ค่าธรรมเนียมบัตรไม่คืน', r['charge'] == 20.3 and r['refund'] == 994.7 and deal(B, cc)['refund_amount'] == 994.7, r)
cc2 = paid_deal(price=500, fee_payer='seller'); S.ok(f'/deals/{cc2}/cancel', {})
check('ผู้ขายยกเลิก: คืนเต็มยอดดีล (บัตร/พร้อมเพย์เหมือนกัน)', deal(B, cc2)['refund_amount'] == 500)
S.ok('/penalties/pay', {})  # ล้างค่าปรับจากเคสนี้ก่อนทดสอบข้ออื่น
# ที่พัก: ยกเลิกในช่วงยกเลิกฟรี (ไม่มีค่าปรับ แต่มีค่าดำเนินการ)
cs = S.ok('/deals', stay_body())['code']; B.ok(f'/deals/{cs}/accept', {}); B.ok(f'/deals/{cs}/pay', {})
pv = deal(B, cs)['cancel_preview']
r = B.ok(f'/deals/{cs}/cancel', {})
check('ผู้เข้าพักยกเลิกในช่วงยกเลิกฟรี → ค่าดำเนินการ 22.97 (1,015 × 1.77% + 5)', pv['charge'] == 22.97 and r['charge'] == 22.97 and deal(B, cs)['refund_amount'] == 992.03 and deal(B, cs)['resolution'] == 'guest_cancel', (pv, r))

print('8) หลังผู้ขายส่งของ/ส่งมอบแล้ว ผู้ซื้อยกเลิกไม่ได้')
c = paid_deal(price=500)
S.ok(f'/deals/{c}/ship', {'tracking': 'TH02V6' + c[-4:], 'carrier': 'Flash Express'})
d = deal(B, c)
check('ส่งพัสดุแล้ว: ไม่มีปุ่มยกเลิก มีแค่ยืนยัน/แจ้งปัญหา', not any(a in d['actions'] for a in ('cancel', 'buyer_cancel')) and 'confirm' in d['actions'] and 'dispute' in d['actions'] and d['cancel_preview'] is None)
s, e = B.req(f'/deals/{c}/cancel', {})
check('API ปฏิเสธการยกเลิกหลังส่งพัสดุ (400)', s == 400 and 'แจ้งปัญหา' in e['error'], e)
B.ok(f'/deals/{c}/simulate-delivered', {})
s, e = B.req(f'/deals/{c}/cancel', {})
check('ของถึงแล้วก็ยกเลิกไม่ได้', s == 400)
cm = paid_deal(price=500, delivery='messenger')
S.ok(f'/deals/{cm}/ship', {'proof_text': 'ไรเดอร์ Grab ทะเบียน 1กข1234'})
s, e = B.req(f'/deals/{cm}/cancel', {})
check('แมสเซนเจอร์ส่งพร้อมหลักฐานแล้ว ยกเลิกไม่ได้', s == 400 and 'cancel' not in deal(B, cm)['actions'])
cs = S.ok('/deals', stay_body(checkin_date=bkk_date(5), checkout_date=bkk_date(6)))['code']; B.ok(f'/deals/{cs}/accept', {}); B.ok(f'/deals/{cs}/pay', {})
B.ok(f'/deals/{cs}/skip', {'to': 'checkin'})
s, e = B.req(f'/deals/{cs}/cancel', {})
check('ที่พักถึงเวลาเช็คอินแล้ว ผู้เข้าพักยกเลิกไม่ได้', s == 400 and 'guest_cancel' not in deal(B, cs)['actions'])

print('5) ผู้ขาย/เจ้าของผิด → คืนเต็ม + ค่าปรับเท่าค่าธรรมเนียม · v13: หักจากยอดรอโอนทันที / ค้าง = ระงับ')
c = paid_deal(price=2000)  # fee 60 คนละครึ่ง → ผู้ซื้อจ่าย 2,030
d = deal(S, c)
check('ผู้ขายเห็นยอดก่อนยกเลิก: คืน 2,030 ค่าปรับ 60', 'seller_cancel' in d['actions'] and d['cancel_preview'] == {'type': 'seller_fault', 'refund': 2030, 'penalty': 60}, d['cancel_preview'])
r = S.ok(f'/deals/{c}/cancel', {})
d = deal(B, c)
check('ผู้ขายยกเลิก → ผู้ซื้อได้คืนเต็ม 2,030 (รวมค่าธรรมเนียม)', d['status'] == 'refunded' and d['refund_amount'] == 2030 and d['fault'] == 'seller' and not d['cancel_charge'])
check('บันทึกค่าปรับ 60 (= ค่าธรรมเนียม 3%) ที่ผู้ขาย', d['penalty'] == 60 and r['penalty'] == 60)
pay = S.ok('/payouts')
check('ไม่มียอดรอโอนให้หัก → ค่าปรับค้าง 60 + ระงับโอนออก', pay['penalty_owed'] == 60 and pay['blocked'], pay['penalty_owed'])
s, e = S.req('/deals', dict(role='seller', title='ดีลใหม่ระหว่างค้างค่าปรับ', price=300, delivery='parcel', due_date=bkk_date(2), fee_payer='half'))
check('ค้างค่าปรับ → สร้างดีลใหม่ไม่ได้ + ข้อความไทยชัดเจน', s == 403 and 'ค่าปรับค้างชำระ 60' in e['error'], e)
s, e = B.req('/deals', dict(role='buyer', title='ซื้อจากร้านที่ค้างค่าปรับ', price=300, delivery='parcel', due_date=bkk_date(2), fee_payer='half'))
code_x = e.get('code') if s == 200 else None
if code_x:
    s, e = S.req(f'/deals/{code_x}/accept', {})
    check('ค้างค่าปรับ → กดรับดีลใหม่ก็ไม่ได้', s == 403 and 'ค่าปรับค้างชำระ' in e['error'], e)
check('me แสดงค่าปรับค้าง', S.ok('/me')['user']['penalty_owed'] == 60)
r = S.ok('/penalties/pay', {})
check('ชำระค่าปรับ (จำลอง) แล้วปลดล็อก', r['paid'] == 60 and S.ok('/payouts')['penalty_owed'] == 0 and bool(new_deal(S, price=150)))
c5 = paid_deal(price=1200); S.ok(f'/deals/{c5}/ship', {'tracking': 'TH03V6' + c5[-4:], 'carrier': 'Kerry Express'}); B.ok(f'/deals/{c5}/confirm', {})
check('ยอดรอโอน 1,182', S.ok('/payouts')['pending'] == 1182)
cl = paid_deal(price=1000, due_date=bkk_date(0))
B.ok(f'/deals/{cl}/skip', {'hours': 48}); B.ok(f'/deals/{cl}/late-refund', {})
pay = S.ok('/payouts')
check('ส่งไม่ทัน → คืนเต็ม 1,015 + ค่าปรับ 30 หักจากยอดรอโอนทันที (1,182 → 1,152)', deal(B, cl)['refund_amount'] == 1015 and deal(S, cl)['penalty'] == 30 and pay['pending'] == 1152 and pay['penalty_owed'] == 0, pay)
cs = S.ok('/deals', stay_body(price=1500))['code']; B.ok(f'/deals/{cs}/accept', {}); B.ok(f'/deals/{cs}/pay', {})
S.ok(f'/deals/{cs}/cancel', {})
pay = S.ok('/payouts')
check('เจ้าของที่พักยกเลิก → คืนเต็ม 1,522.50 + ค่าปรับ 45 หักทันที (→ 1,107)', deal(B, cs)['refund_amount'] == 1522.5 and deal(S, cs)['penalty'] == 45 and pay['pending'] == 1107 and pay['penalty_owed'] == 0, pay['pending'])
check('ประวัติค่าปรับ: หักแล้วทั้งหมด', all(p['deducted'] == p['amount'] for p in pay['penalties']))
fl = [f for f in ADM.ok('/admin/overview')['flags'] if f['kind'] == 'penalty' and f['user_id'] == us['id']]
check('ผิดซ้ำ 3 ครั้งใน 30 วัน → แอดมินเห็นคำเตือน', fl and fl[0]['flagged'] and fl[0]['count'] >= 3 and fl[0]['total'] >= 135, fl)
r = ADM.ok('/admin/payouts/run', {})
mine = [b for b in r['batches'] if b['user_id'] == us['id']][0]
check('รอบโอน: 1,107 + ดีล 150 ที่ยังไม่จบไม่นับ − ค่าโอน 30 = 1,077', mine['net'] == 1077 and mine['transfer_fee'] == 30 and mine['penalty'] == 0, mine)
# S2: ค่าปรับมากกว่ายอดรอโอน → หักเท่าที่มี ที่เหลือค้าง → ระงับ
cy = paid_deal(seller=S2, price=100); S2.ok(f'/deals/{cy}/ship', {'tracking': 'TH04V6' + cy[-4:], 'carrier': 'Kerry Express'}); B.ok(f'/deals/{cy}/confirm', {})
cx = paid_deal(seller=S2, price=2500); S2.ok(f'/deals/{cx}/cancel', {})   # ค่าปรับ 75 · รอโอน 90 → เหลือ 15
p2 = S2.ok('/payouts')
check('S2: ค่าปรับ 75 หักจากรอโอน 90 ทันที → เหลือ 15 ไม่ค้าง', p2['pending'] == 15 and p2['penalty_owed'] == 0, (p2['pending'], p2['penalty_owed']))
cz = paid_deal(seller=S2, price=500); S2.ok(f'/deals/{cz}/cancel', {})  # ค่าปรับ 20 → หักได้ 15 ค้าง 5
p2 = S2.ok('/payouts')
check('S2: ค่าปรับ 20 หักได้ 15 ค้าง 5 → ระงับ', p2['pending'] == 0 and p2['penalty_owed'] == 5 and p2['blocked'], p2['penalty_owed'])
r = ADM.ok('/admin/payouts/run', {})
check('รอบโอน: ผู้ขายที่ค้างค่าปรับถูกระงับการโอนออก', not any(b.get('batch_id') and b['user_id'] == p2.get('uid', -1) for b in r['batches']) and S2.ok('/payouts')['penalty_owed'] == 5)
S2.ok('/penalties/pay', {})
cd = paid_deal(seller=S2, price=800); S2.ok(f'/deals/{cd}/ship', {'tracking': 'TH05V6' + cd[-4:], 'carrier': 'Kerry Express'})
B.ok(f'/deals/{cd}/dispute', {'reason': 'ของไม่ตรงปก', 'detail': 'สีไม่ตรง', 'files': [PNG]})
ADM.ok(f'/admin/deals/{cd}/resolve', {'decision': 'refund', 'note': 'ไม่ตรงปกจริง'})
check('ทีมงานตัดสินว่าไม่ตรงปก → คืนเต็ม 812 + ค่าปรับ 24', deal(B, cd)['refund_amount'] == 812 and deal(S2, cd)['penalty'] == 24)
S2.ok('/penalties/pay', {})
cs = S2.ok('/deals', stay_body(checkin_date=bkk_date(2), checkout_date=bkk_date(3)))['code']; B.ok(f'/deals/{cs}/accept', {}); B.ok(f'/deals/{cs}/pay', {})
check('ยกเลิกช้า (เลยช่วงยกเลิกฟรี): ยอดก่อนกดบอกว่าส่งทีมงานตัดสิน', deal(B, cs)['cancel_preview']['type'] == 'staff')
B.ok(f'/deals/{cs}/cancel', {'reason': 'ติดธุระ'})
ADM.ok(f'/admin/deals/{cs}/resolve', {'decision': 'refund'})
d = deal(S2, cs)
check('ทีมงานคืนเงินกรณีผู้เข้าพักขอยกเลิกช้า → หักค่าดำเนินการ ไม่ปรับเจ้าของ', d['refund_amount'] == 992.03 and d['cancel_charge'] == 22.97 and not d['penalty'], d)

print('6) v13: คืนบางส่วน → ค่าธรรมเนียมเต็มของดีล (ไม่ลดตามยอดคืน) แบ่งตามผู้จ่ายที่ตกลงไว้')
def disputed(price, seller=S, **kw):
    c = paid_deal(seller=seller, price=price, **kw); seller.ok(f'/deals/{c}/ship', {'tracking': 'TH06V6' + c[-4:], 'carrier': 'Kerry Express'})
    B.ok(f'/deals/{c}/dispute', {'reason': 'ได้ไม่ครบ', 'files': [PNG]}); return c
c = disputed(500)  # ผู้ซื้อจ่าย 510 · fee 20 (10/10)
ADM.ok(f'/admin/deals/{c}/resolve', {'decision': 'partial', 'refund_amount': 400})
d = deal(S, c)
check('คืน 400 → ผู้ขายได้ 500 − 400 − 10 = 90 · ค่าธรรมเนียมเต็ม 20', d['payout_amount'] == 90 and d['fee_charged'] == 20, (d['payout_amount'], d['fee_charged']))
c = disputed(3000)  # fee 90 (45/45) ผู้ซื้อจ่าย 3,045
s, e = ADM.req(f'/admin/deals/{c}/resolve', {'decision': 'partial', 'refund_amount': 2960})
check('คืนบางส่วนเกิน ราคา − ส่วนผู้ขาย (2,955) ไม่ได้', s == 400 and '2,955' in e['error'], e)
ADM.ok(f'/admin/deals/{c}/resolve', {'decision': 'partial', 'refund_amount': 1045})
d = deal(S, c)
check('คืน 1,045 → ผู้ขายได้ 3,000 − 1,045 − 45 = 1,910 · ค่าธรรมเนียมเต็ม 90', d['payout_amount'] == 1910 and d['fee_charged'] == 90, d)
c = disputed(1000, fee_payer='seller')  # fee 30 ผู้ขายจ่ายทั้งหมด ผู้ซื้อจ่าย 1,000
ADM.ok(f'/admin/deals/{c}/resolve', {'decision': 'partial', 'refund_amount': 500})
d = deal(S, c)
check('ผู้ขายรับค่าธรรมเนียม: คืน 500 → ผู้ขายได้ 1,000 − 500 − 30 = 470', d['payout_amount'] == 470 and d['fee_charged'] == 30, d)

print('9) v13: ผู้ขายใหม่ (ขายสำเร็จ < 5 ดีล) สูงสุด 3,000 บาท/ดีล')
N = C(); N.login('ร้านใหม่ v13', '089' + stamp + '4'); N.ok('/me/verify', {}) if False else None
s, e = N.req('/deals', dict(role='seller', title='ของแพงร้านใหม่', price=3500, delivery='parcel', due_date=bkk_date(2), fee_payer='half'))
check('ร้านใหม่ 3,500 ไม่ได้ + ข้อความไทย', s == 400 and 'ร้านใหม่' in e['error'] and '3,000' in e['error'], e)
check('ร้านใหม่ 3,000 พอดีได้', bool(new_deal(N, price=3000)))
st = N.ok('/me')['user']['stats']
check('stats: seller_limit 3,000 · level_limit 5,000 · new_seller', st['seller_limit'] == 3000 and st['level_limit'] == 5000 and st['new_seller'], st)

print('8b) ผู้ซื้อแพ้ข้อพิพาท → บันทึก + ≥3 ครั้งใน 90 วัน เสนอระงับบัญชี')
for i in range(3):
    c = disputed(300)
    ADM.ok(f'/admin/deals/{c}/resolve', {'decision': 'release', 'note': 'หลักฐานการส่ง + วิดีโอแพ็กของครบ'})
fl = [f for f in ADM.ok('/admin/overview')['flags'] if f['kind'] == 'lost_dispute' and f['user_id'] == ub['id']]
check('ผู้ซื้อแพ้ข้อพิพาท 3 ครั้ง → แอดมินเห็นธงเสนอระงับ', fl and fl[0]['count'] == 3 and fl[0]['flagged'] and fl[0]['days'] == 90, fl)

print('7) แสดงค่าใช้จ่ายก่อนจ่ายเงิน')
c = new_deal(S, price=1000); B.ok(f'/deals/{c}/accept', {})
d = deal(B, c)
check('ก่อนจ่าย: เห็นค่าดำเนินการถ้ายกเลิก + กฎค่าโอนออก', 'pay' in d['actions'] and d['buyer_cancel_charge'] == 22.97 and d['payout_rule'] == {'fee': 30, 'free_from': 3000})
html = urllib.request.urlopen(BASE + '/terms').read().decode()
check('/terms: มีกฎใหม่ (ค่าดำเนินการ ค่าโอนออก ค่าปรับ ยกเลิกไม่ได้หลังส่ง) และไม่มีหมายเหตุร่างข้อ 6.5',
      all(k in html for k in ('ค่าดำเนินการ', '30 บาท', '3,000 บาท', 'ค่าธรรมเนียมบัตร', 'ค่าปรับ', '100 บาท', 'ยกเลิกไม่ได้')) and '[ร่าง:' not in html and 'อาจปรับก่อนเปิดใช้งานจริง' not in html)
js = urllib.request.urlopen(BASE + '/static/app.js').read().decode()
check('แอปมีข้อความค่าโอนออกตามที่กำหนด', 'ค่าโอนออก 30 บาท/วัน ฟรีเมื่อยอดรวม 3,000 บาทขึ้นไป' in js)

print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {fail}')
sys.exit(1 if fail else 0)
