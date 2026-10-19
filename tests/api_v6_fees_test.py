"""ทดสอบ API v6: กฎค่าธรรมเนียม/คืนเงิน/โอนเงินที่เจ้าของยืนยันแล้ว
1) ค่าธรรมเนียม 2% ขั้นต่ำ 20 บาท เลือกผู้จ่ายได้   2) ยอดดีลขั้นต่ำ 100 บาท (สร้างดีล + หน้าร้าน)
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

print('1) ค่าธรรมเนียม 2% ขั้นต่ำ 20 บาท · เลือกผู้จ่าย')
for payer, bp, sg in (('buyer', 2550, 2500), ('seller', 2500, 2450), ('half', 2525, 2475)):
    d = deal(B, new_deal(S, price=2500, fee_payer=payer))
    check(f'2,500 บาท {payer}: ค่าธรรมเนียม 50 · ผู้ซื้อจ่าย {bp} · ผู้ขายได้ {sg}', d['fee'] == 50 and d['buyer_pay'] == bp and d['seller_get'] == sg, d['fee'])
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
db = sqlite3.connect(os.path.join(HERE, '..', 'data', 'dealsure.db'))
db.execute('UPDATE products SET price=80 WHERE id=?', (pid,)); db.commit(); db.close()
s, e = B.req(f'/products/{pid}/buy', {'delivery': 'parcel'})
check('สั่งซื้อสินค้าหน้าร้านที่ต่ำกว่า 100 ไม่ได้ + ข้อความชัดเจน', s == 400 and 'ขั้นต่ำ 100 บาท' in e['error'], e)

print('3) ค่าโอนออก 30 บาท/วัน · รวมโอนวันละครั้ง · ฟรีเมื่อยอดรวม ≥ 1,000')
c1 = paid_deal(price=300); c2 = paid_deal(price=400, delivery='meet')
for c in (c1,):
    S.ok(f'/deals/{c}/ship', {'tracking': 'TH00V6' + c[-4:], 'carrier': 'Kerry Express'}); B.ok(f'/deals/{c}/confirm', {})
B.ok(f'/deals/{c2}/meet-code', {'code': S.ok(f'/deals/{c2}')['meet_code']})
pay = S.ok('/payouts')
g = r2(290 + 390)  # seller_get: 300-10, 400-10
check(f'ยอดรวมรอโอน {g} (2 ดีล)', pay['pending'] == g, pay['pending'])
check('ยอดรวม < 1,000 → ค่าโอนออก 30 บาท', pay['next']['transfer_fee'] == 30 and pay['next']['net'] == r2(g - 30) and pay['rule'] == {'fee': 30, 'free_from': 1000})
r = ADM.ok('/admin/payouts/run', {})
mine = [b for b in r['batches'] if b['user_id'] == us['id']]
check('โอน 1 ครั้งต่อวันรวมทุกดีล (1 รอบ 2 ดีล)', len(mine) == 1 and S.ok('/payouts')['batches'][0]['n'] == 2)
check('หักค่าโอนออก 30 จากยอดรวม', mine[0]['transfer_fee'] == 30 and mine[0]['net'] == r2(g - 30))
check('แจ้งเตือนผู้ขายแสดงค่าโอนออก', any('ค่าโอนออก −30' in n['text'] for n in S.ok('/notifications')['items']))
c3 = paid_deal(price=600); c4 = paid_deal(price=500)
for c in (c3, c4): S.ok(f'/deals/{c}/ship', {'tracking': 'TH01V6' + c[-4:], 'carrier': 'Kerry Express'}); B.ok(f'/deals/{c}/confirm', {})
pay = S.ok('/payouts')
check('ยอดรวม 1,080 (≥ 1,000) → โอนฟรี', pay['pending'] == 1080 and pay['next']['transfer_fee'] == 0 and pay['next']['net'] == 1080, pay['next'])
r = ADM.ok('/admin/payouts/run', {})
mine = [b for b in r['batches'] if b['user_id'] == us['id']][0]
check('รอบโอนนี้ไม่มีค่าโอนออก', mine['transfer_fee'] == 0 and mine['net'] == 1080)

print('4) ผู้ซื้อยกเลิกเอง (ก่อนผู้ขายส่งของ) → ค่าดำเนินการ 2% ขั้นต่ำ 10 บาท')
c = paid_deal(price=100, fee_payer='seller')  # จ่าย 100 → ค่าดำเนินการขั้นต่ำ 10
d = deal(B, c)
check('มีปุ่มยกเลิกก่อนส่งของ + ยอดจริงก่อนกด', 'buyer_cancel' in d['actions'] and d['cancel_preview'] == {'type': 'buyer_choice', 'paid': 100, 'charge': 10, 'refund': 90}, d.get('cancel_preview'))
r = B.ok(f'/deals/{c}/cancel', {})
d = deal(B, c)
check('คืน 90 หักค่าดำเนินการ 10 (ขั้นต่ำ)', r['charge'] == 10 and r['refund'] == 90 and d['status'] == 'refunded' and d['refund_amount'] == 90 and d['cancel_charge'] == 10 and d['fault'] == 'buyer')
check('ผู้ขายไม่โดนค่าปรับเมื่อผู้ซื้อยกเลิกเอง', not (deal(S, c)['penalty'] or 0) and S.ok('/payouts')['penalty_owed'] == 0)
c = paid_deal(price=1500)  # จ่าย 1,515 → 2% = 30.30
r = B.ok(f'/deals/{c}/cancel', {})
check('จ่าย 1,515 → ค่าดำเนินการ 30.30 คืน 1,484.70', r['charge'] == 30.3 and deal(B, c)['refund_amount'] == 1484.7)
check('แจ้งเตือนผู้ซื้อระบุค่าดำเนินการ', any('ค่าดำเนินการ' in n['text'] for n in B.ok('/notifications')['items']))
# ที่พัก: ยกเลิกในช่วงยกเลิกฟรี
cs = S.ok('/deals', stay_body())['code']; B.ok(f'/deals/{cs}/accept', {}); B.ok(f'/deals/{cs}/pay', {})
pv = deal(B, cs)['cancel_preview']
r = B.ok(f'/deals/{cs}/cancel', {})
check('ผู้เข้าพักยกเลิกในช่วงยกเลิกฟรี → ค่าดำเนินการ 2% (1,010 → 20.20)', pv['charge'] == 20.2 and r['charge'] == 20.2 and deal(B, cs)['refund_amount'] == 989.8 and deal(B, cs)['resolution'] == 'guest_cancel')

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

print('5) ผู้ขาย/เจ้าของผิด → คืนเต็มรวมค่าธรรมเนียม + ค่าปรับเท่าค่าธรรมเนียม')
c = paid_deal(price=2000)  # fee 40 คนละครึ่ง → ผู้ซื้อจ่าย 2,020
d = deal(S, c)
check('ผู้ขายเห็นยอดก่อนยกเลิก: คืน 2,020 ค่าปรับ 40', 'seller_cancel' in d['actions'] and d['cancel_preview'] == {'type': 'seller_fault', 'refund': 2020, 'penalty': 40})
r = S.ok(f'/deals/{c}/cancel', {})
d = deal(B, c)
check('ผู้ขายยกเลิก → ผู้ซื้อได้คืนเต็ม 2,020 (รวมค่าธรรมเนียม)', d['status'] == 'refunded' and d['refund_amount'] == 2020 and d['fault'] == 'seller' and not d['cancel_charge'])
check('บันทึกค่าปรับ 40 ที่ผู้ขาย', d['penalty'] == 40 and r['penalty'] == 40)
cl = paid_deal(price=1000, due_date=bkk_date(0))
B.ok(f'/deals/{cl}/skip', {'hours': 48}); B.ok(f'/deals/{cl}/late-refund', {})
check('ส่งไม่ทัน → คืนเต็ม 1,010 + ค่าปรับ 20', deal(B, cl)['refund_amount'] == 1010 and deal(S, cl)['penalty'] == 20)
cs = S.ok('/deals', stay_body(price=1500))['code']; B.ok(f'/deals/{cs}/accept', {}); B.ok(f'/deals/{cs}/pay', {})
S.ok(f'/deals/{cs}/cancel', {})
check('เจ้าของที่พักยกเลิก → คืนเต็ม 1,515 + ค่าปรับ 30', deal(B, cs)['refund_amount'] == 1515 and deal(S, cs)['penalty'] == 30)
pay = S.ok('/payouts')
check('หน้ารับเงินผู้ขายแสดงค่าปรับค้าง 90 (40+20+30)', pay['penalty_owed'] == 90 and len(pay['penalties']) == 3, pay['penalty_owed'])
fl = [f for f in ADM.ok('/admin/overview')['flags'] if f['kind'] == 'penalty' and f['user_id'] == us['id']]
check('ผิดซ้ำ 3 ครั้งใน 30 วัน → แอดมินเห็นคำเตือน', fl and fl[0]['flagged'] and fl[0]['count'] == 3 and fl[0]['total'] == 90, fl)
# ค่าปรับหักจากยอดโอนรอบถัดไป
c = paid_deal(price=1200); S.ok(f'/deals/{c}/ship', {'tracking': 'TH03V6' + c[-4:], 'carrier': 'Kerry Express'}); B.ok(f'/deals/{c}/confirm', {})
pay = S.ok('/payouts')
check('ยอดโอนถัดไป: 1,188 − ค่าโอน 0 (≥1,000) − ค่าปรับ 90 = 1,098', pay['next'] == {'gross': 1188, 'transfer_fee': 0, 'penalty': 90, 'net': 1098, 'rollover': False}, pay['next'])
r = ADM.ok('/admin/payouts/run', {})
mine = [b for b in r['batches'] if b['user_id'] == us['id']][0]
pay = S.ok('/payouts')
check('รอบโอนหักค่าปรับแล้ว ค่าปรับค้างเหลือ 0', mine['penalty'] == 90 and mine['net'] == 1098 and pay['penalty_owed'] == 0 and all(p['deducted'] == p['amount'] for p in pay['penalties']))
# ค่าปรับมากกว่ายอดโอน → หักเท่าที่มี ส่วนที่เหลือยกไปรอบถัดไป
cx = paid_deal(seller=S2, price=2500); S2.ok(f'/deals/{cx}/cancel', {})   # ค่าปรับ 50
cy = paid_deal(seller=S2, price=100); S2.ok(f'/deals/{cy}/ship', {'tracking': 'TH04V6' + cy[-4:], 'carrier': 'Kerry Express'}); B.ok(f'/deals/{cy}/confirm', {})
p2 = S2.ok('/payouts')
check('ยอด 90 (< 1,000) − ค่าโอน 30 − ค่าปรับ 50 = โอน 10', p2['next'] == {'gross': 90, 'transfer_fee': 30, 'penalty': 50, 'net': 10, 'rollover': False}, p2['next'])
cz = paid_deal(seller=S2, price=500); S2.ok(f'/deals/{cz}/cancel', {})  # 500 → ค่าปรับ 20 ⇒ ค้างรวม 70
p2 = S2.ok('/payouts')
check('ค่าปรับค้าง 70 > ยอดหลังหักค่าโอน 60 → หัก 60 เหลือยกไป 10', p2['next']['penalty'] == 60 and p2['next']['net'] == 0)
ADM.ok('/admin/payouts/run', {})
check('ค่าปรับที่เหลือ 10 ยกไปรอบถัดไป', S2.ok('/payouts')['penalty_owed'] == 10)
# ทีมงานตัดสินให้ผู้ซื้อ (ไม่ตรงปก) → ค่าปรับ · ทีมงานคืนเงินกรณีผู้เข้าพักยกเลิกช้า → หักค่าดำเนินการ ไม่ปรับเจ้าของ
cd = paid_deal(seller=S2, price=800); S2.ok(f'/deals/{cd}/ship', {'tracking': 'TH05V6' + cd[-4:], 'carrier': 'Kerry Express'})
B.ok(f'/deals/{cd}/dispute', {'reason': 'ของไม่ตรงปก', 'detail': 'สีไม่ตรง', 'files': [PNG]})
ADM.ok(f'/admin/deals/{cd}/resolve', {'decision': 'refund', 'note': 'ไม่ตรงปกจริง'})
check('ทีมงานตัดสินว่าไม่ตรงปก → คืนเต็ม 810 + ค่าปรับ 20', deal(B, cd)['refund_amount'] == 810 and deal(S2, cd)['penalty'] == 20)
cs = S2.ok('/deals', stay_body(checkin_date=bkk_date(2), checkout_date=bkk_date(3)))['code']; B.ok(f'/deals/{cs}/accept', {}); B.ok(f'/deals/{cs}/pay', {})
check('ยกเลิกช้า (เลยช่วงยกเลิกฟรี): ยอดก่อนกดบอกว่าส่งทีมงานตัดสิน', deal(B, cs)['cancel_preview']['type'] == 'staff')
B.ok(f'/deals/{cs}/cancel', {'reason': 'ติดธุระ'})
ADM.ok(f'/admin/deals/{cs}/resolve', {'decision': 'refund'})
d = deal(S2, cs)
check('ทีมงานคืนเงินกรณีผู้เข้าพักขอยกเลิกช้า → หักค่าดำเนินการ ไม่ปรับเจ้าของ', d['refund_amount'] == 989.8 and d['cancel_charge'] == 20.2 and not d['penalty'])

print('6) คืนบางส่วน → ค่าธรรมเนียมคิดจากยอดที่ผู้ขายได้จริง (ขั้นต่ำ 20)')
def disputed(price, seller=S):
    c = paid_deal(seller=seller, price=price); seller.ok(f'/deals/{c}/ship', {'tracking': 'TH06V6' + c[-4:], 'carrier': 'Kerry Express'})
    B.ok(f'/deals/{c}/dispute', {'reason': 'ได้ไม่ครบ', 'files': [PNG]}); return c
c = disputed(500)  # ผู้ซื้อจ่าย 510
ADM.ok(f'/admin/deals/{c}/resolve', {'decision': 'partial', 'refund_amount': 400})
d = deal(S, c)
check('คืน 400 → ผู้ขายได้ส่วน 110 ค่าธรรมเนียมขั้นต่ำ 20 → ได้ 90', d['payout_amount'] == 90 and d['fee_charged'] == 20, (d['payout_amount'], d['fee_charged']))
c = disputed(3000)  # ผู้ซื้อจ่าย 3,030 (ต้องยืนยันตัวตน: 3,000 ไม่เกิน)
ADM.ok(f'/admin/deals/{c}/resolve', {'decision': 'partial', 'refund_amount': 1030})
d = deal(S, c)
check('คืน 1,030 → ส่วนผู้ขาย 2,000 ค่าธรรมเนียม 2% = 40 → ได้ 1,960', d['payout_amount'] == 1960 and d['fee_charged'] == 40)

print('8b) ผู้ซื้อแพ้ข้อพิพาท → บันทึก + ≥3 ครั้งใน 90 วัน เสนอระงับบัญชี')
for i in range(3):
    c = disputed(300)
    ADM.ok(f'/admin/deals/{c}/resolve', {'decision': 'release', 'note': 'หลักฐานการส่ง + วิดีโอแพ็กของครบ'})
fl = [f for f in ADM.ok('/admin/overview')['flags'] if f['kind'] == 'lost_dispute' and f['user_id'] == ub['id']]
check('ผู้ซื้อแพ้ข้อพิพาท 3 ครั้ง → แอดมินเห็นธงเสนอระงับ', fl and fl[0]['count'] == 3 and fl[0]['flagged'] and fl[0]['days'] == 90, fl)

print('7) แสดงค่าใช้จ่ายก่อนจ่ายเงิน')
c = new_deal(S, price=1000); B.ok(f'/deals/{c}/accept', {})
d = deal(B, c)
check('ก่อนจ่าย: เห็นค่าดำเนินการถ้ายกเลิก + กฎค่าโอนออก', 'pay' in d['actions'] and d['buyer_cancel_charge'] == 20.2 and d['payout_rule'] == {'fee': 30, 'free_from': 1000})
html = urllib.request.urlopen(BASE + '/terms').read().decode()
check('/terms: มีกฎใหม่ (ค่าดำเนินการ ค่าโอนออก ค่าปรับ ยกเลิกไม่ได้หลังส่ง) และไม่มีหมายเหตุร่างข้อ 6.5',
      all(k in html for k in ('ค่าดำเนินการ', '30 บาท', '1,000 บาท', 'ค่าปรับ', '100 บาท', 'ยกเลิกไม่ได้')) and '[ร่าง:' not in html and 'อาจปรับก่อนเปิดใช้งานจริง' not in html)
js = urllib.request.urlopen(BASE + '/static/app.js').read().decode()
check('แอปมีข้อความค่าโอนออกตามที่กำหนด', 'ค่าโอนออก 30 บาท/วัน ฟรีเมื่อยอดรวม 1,000 บาทขึ้นไป' in js)

print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {fail}')
sys.exit(1 if fail else 0)
