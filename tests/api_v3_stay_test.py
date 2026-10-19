"""ทดสอบ API ดีลที่พัก (v3): สร้างดีลที่พัก · พักเงินจนเช็คอิน · รหัสเช็คอิน · ปล่อยเงินอัตโนมัติ 24 ชม. · แจ้งที่พักปลอม
· ยกเลิกฟรี/ยกเลิกช้า/เจ้าของยกเลิก · ที่พักในหน้าร้าน · เจ้าของที่พักตัวอย่าง
วิธีรัน: python3 tests/api_v3_stay_test.py [http://localhost:8787]"""
import base64, os, sys, time
from datetime import datetime, timedelta, timezone
sys.argv = sys.argv[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'api_test.py'), encoding='utf-8').read().split('\nA, B, X = C(), C(), C()')[0]
exec(compile(src, 'api_test_helpers', 'exec'))

TZ = timezone(timedelta(hours=7)); DAY = 86400
def bkk_date(days): return (datetime.now(TZ) + timedelta(days=days)).strftime('%Y-%m-%d')
MAP = 'https://maps.app.goo.gl/AbCdEf123'
VID = 'data:video/mp4;base64,' + base64.b64encode(open(os.path.join(HERE, 'unboxing.mp4'), 'rb').read()).decode()
JPG = 'data:image/jpeg;base64,' + base64.b64encode(open(os.path.join(HERE, 'camera.jpg'), 'rb').read()).decode()


def stay(c, **kw):
    b = dict(kind='stay', role='seller', title='บ้านพักทดสอบ ริมทะเล', address='12/3 ม.4 ต.ทดสอบ อ.เมือง จ.ประจวบฯ', map_url=MAP,
             checkin_date=bkk_date(5), checkin_time='14:00', checkout_date=bkk_date(7), guests=2, price=2400, fee_payer='half',
             host_contact='คุณโฮสต์ ทดสอบ', free_cancel_days=3, photos=[PNG])
    b.update(kw)
    return b


def mk(c, **kw): return c.ok('/deals', stay(c, **kw))['code']


def paid(host, guest, **kw):
    code = mk(host, **kw); guest.ok(f'/deals/{code}/accept', {}); guest.ok(f'/deals/{code}/pay', {}); return code


H, G, X, ADM = C(), C(), C(), C()
stamp = str(int(time.time()))[-6:]
uh = H.login('โฮสต์ทดสอบ', '081' + stamp + '7'); ug = G.login('แขกทดสอบ', '082' + stamp + '8'); X.login('คนนอก', '083' + stamp + '9')
ADM.ok('/admin/login', {'password': admin_password()})

print('1) เจ้าของที่พักตัวอย่าง (ข้อมูลปลอม ติดป้ายตัวอย่าง)')
sh = [s for s in C().ok('/shops')['shops'] if s['name'] == 'พี่ปุ้ย (ตัวอย่าง)']
check('มีเจ้าของที่พักตัวอย่าง + ป้ายตัวอย่าง', len(sh) == 1 and sh[0]['is_demo'] and 'ตัวอย่าง' in sh[0]['shop_name'])
demo = C().ok(f'/shops/{sh[0]["id"]}')
check('ยืนยันตัวตน + ระดับร้านเงิน + เข้าพักสำเร็จ ≥ 20', demo['verified'] and demo['stats']['level'] == 'silver' and demo['stats']['stays_hosted'] >= 20, demo['stats'])
check('ที่พักในหน้าร้าน 2 แห่ง (kind=stay, มีที่อยู่ + แผนที่)', len([p for p in demo['products'] if p['kind'] == 'stay' and p['address'] and p['map_url']]) == 2)

print('2) ตรวจข้อมูลตอนสร้างดีลที่พัก')
for label, kw, msg in [('ไม่มีลิงก์แผนที่', {'map_url': ''}, 'Google Maps'), ('ลิงก์ไม่ใช่ Google Maps', {'map_url': 'https://evil.example.com/maps'}, 'Google Maps'),
                       ('ไม่มีที่อยู่', {'address': ''}, 'ที่อยู่'), ('ไม่มีชื่อผู้ติดต่อ', {'host_contact': ''}, 'ผู้ติดต่อ'),
                       ('เช็คเอาต์ก่อนเช็คอิน', {'checkout_date': bkk_date(4)}, 'เช็คเอาต์'), ('เช็คอินย้อนหลัง', {'checkin_date': bkk_date(-1), 'checkout_date': bkk_date(1)}, 'อนาคต'),
                       ('ผู้เข้าพัก 0 คน', {'guests': 0}, 'ผู้เข้าพัก'), ('ราคาต่ำกว่า 50', {'price': 30}, 'ขั้นต่ำ'),
                       ('ยกเลิกฟรีเกิน 30 วัน', {'free_cancel_days': 45}, 'ยกเลิกฟรี')]:
    s, e = H.req('/deals', stay(H, **kw))
    check(f'ปฏิเสธ: {label}', s == 400 and msg in e['error'], e)
s, e = H.req('/deals', stay(H, price=3500))
check('เกิน 3,000 ต้องยืนยันตัวตน (กฎเดิม)', s == 403 and 'ยืนยันตัวตน' in e['error'])
s, e = H.req('/deals', stay(H, price=6000))
check('ผู้ใช้ใหม่เกิน 5,000 ไม่ได้ (กฎเดิม)', s == 400 and '5,000' in e['error'])

print('3) เจ้าของสร้างดีล → ผู้เข้าพักเปิดลิงก์ → จ่าย → พักเงินรอเช็คอิน')
code = mk(H)
d = C().ok('/deals/' + code)
check('คนเปิดลิงก์เห็นข้อมูลที่พัก + ความน่าเชื่อถือเจ้าของ', d['kind'] == 'stay' and d['address'] and d['map_url'] == MAP and d['nights'] == 2 and d['guests'] == 2
      and d['seller']['stats'] is not None and 'stays_hosted' in d['seller']['stats'] and d['actions'] == ['accept'])
check('ค่าธรรมเนียม 2% คนละครึ่ง', d['fee'] == 48 and d['buyer_pay'] == 2424 and d['seller_get'] == 2376)
check('เวลาเช็คอิน 14:00 ตามเวลาไทย', datetime.fromtimestamp(d['checkin_at'], TZ).strftime('%Y-%m-%d %H:%M') == bkk_date(5) + ' 14:00')
G.ok(f'/deals/{code}/accept', {})
check('รับดีลแล้ว = รอจ่าย', deal(G, code)['status'] == 'accepted' and 'pay' in deal(G, code)['actions'])
G.ok(f'/deals/{code}/pay', {})
dg, dh = deal(G, code), deal(H, code)
check('จ่ายแล้ว → held (พักเงินแล้ว รอเช็คอิน)', dg['status'] == 'held')
check('ปล่อยเงินอัตโนมัติ = เวลาเช็คอิน + 24 ชม.', abs(dg['auto_release_at'] - (dg['checkin_at'] + DAY)) < 1 and dg['release_at'] == dg['auto_release_at'])
check('เจ้าของเห็นรหัสเช็คอิน 4 หลัก', len(dh.get('meet_code') or '') == 4 and 'checkin_show' in dh['actions'] and 'host_cancel' in dh['actions'])
check('ผู้เข้าพักไม่เห็นรหัส', 'meet_code' not in dg)
check('ก่อนวันเช็คอิน: ยกเลิกได้ ยังยืนยันเช็คอิน/แจ้งปัญหาไม่ได้', 'guest_cancel' in dg['actions'] and 'checkin_confirm' not in dg['actions'] and 'stay_problem' not in dg['actions'] and dg['free_cancel_now'])
check('มีแจ้งเตือนทั้งสองฝ่าย', any('เช็คอิน' in n['text'] for n in H.ok('/notifications')['items']) and any('พักไว้' in n['text'] for n in G.ok('/notifications')['items']))
for path, body, label in [('confirm', {}, 'ยืนยันเช็คอินก่อนวันเช็คอิน'), ('meet-code', {'code': dh['meet_code']}, 'กรอกรหัสก่อนวันเช็คอิน'),
                          ('dispute', {'reason': 'ไม่มีที่พักจริง', 'location': 'หน้าซอย', 'files': [JPG]}, 'แจ้งปัญหาก่อนเวลาเช็คอิน'),
                          ('ship', {'tracking': 'TH12345678'}, 'ดีลที่พักไม่มีส่งของ'), ('late-refund', {}, 'ขอคืนเงินแบบส่งช้าไม่ได้')]:
    c_ = H if path == 'ship' else G
    s, e = c_.req(f'/deals/{code}/{path}', body)
    check(f'ปฏิเสธ: {label}', s in (400, 403), (s, e))
check('ดีลที่พักอยู่ในรายการดีล (kind=stay)', [x for x in G.ok('/deals')['deals'] if x['code'] == code][0]['kind'] == 'stay')

print('4) เร่งเวลาไปเวลาเช็คอิน → ผู้เข้าพักกรอกรหัสเช็คอิน → ปล่อยเงินทันที')
G.ok(f'/deals/{code}/skip', {'to': 'checkin'})
dg = deal(G, code)
check('ถึงเวลาเช็คอิน: ยืนยัน/กรอกรหัส/แจ้งปัญหาได้, ยกเลิกไม่ได้แล้ว', all(a in dg['actions'] for a in ('checkin_confirm', 'checkin_enter', 'stay_problem')) and 'guest_cancel' not in dg['actions'])
check('ยังไม่ปล่อยเงินเอง', dg['status'] == 'held' and dg['deal_now'] >= dg['checkin_at'])
s, e = G.req(f'/deals/{code}/cancel', {})
check('ผู้เข้าพักยกเลิกหลังถึงเวลาเช็คอินไม่ได้', s == 400 and 'แจ้งปัญหา' in e['error'])
wrong = '0000' if dh['meet_code'] != '0000' else '1111'
s, e = G.req(f'/deals/{code}/meet-code', {'code': wrong})
check('รหัสผิด ไม่ปล่อยเงิน', s == 400 and deal(G, code)['status'] == 'held')
G.ok(f'/deals/{code}/meet-code', {'code': dh['meet_code']})
dh = deal(H, code)
check('รหัสถูก → สำเร็จทันที (checkin_code)', dh['status'] == 'completed' and dh['release_reason'] == 'checkin_code' and dh['payout']['status'] == 'pending')
check('เจ้าของมียอดรอโอน', any(p['code'] == code for p in H.ok('/payouts')['items']))
G.ok(f'/deals/{code}/review', {'stars': 5, 'text': 'ที่พักตรงปก'})
check('ผู้เข้าพักรีวิวเจ้าของได้ + นับเป็นเข้าพักสำเร็จ', C().ok(f'/shops/{uh["id"]}')['stats']['stays_hosted'] == 1)

print('5) ผู้เข้าพักเป็นคนสร้างดีล → เจ้าของรับ → เช็คอินแล้วกด "ที่พักตรงปก"')
code2 = G.ok('/deals', stay(G, role='buyer', price=1500, fee_payer='seller'))['code']
check('ดีลที่ผู้เข้าพักสร้าง รอเจ้าของกดรับ', deal(G, code2)['status'] == 'open' and deal(G, code2)['buyer']['id'] == ug['id'])
H.ok(f'/deals/{code2}/accept', {}); G.ok(f'/deals/{code2}/pay', {})
check('เจ้าของจ่ายค่าธรรมเนียม (ขั้นต่ำ 30)', deal(G, code2)['buyer_pay'] == 1500 and deal(H, code2)['seller_get'] == 1470)
H.ok(f'/deals/{code2}/skip', {'to': 'checkin'})
s, e = H.req(f'/deals/{code2}/confirm', {})
check('เจ้าของกดยืนยันแทนผู้เข้าพักไม่ได้', s == 403)
G.ok(f'/deals/{code2}/confirm', {})
check('ผู้เข้าพักกด "เช็คอินแล้ว ที่พักตรงปก" → สำเร็จ', deal(G, code2)['status'] == 'completed' and deal(G, code2)['release_reason'] == 'guest_checkin')

print('6) ผู้เข้าพักไม่ยืนยันและไม่แจ้งปัญหา → ปล่อยเงินอัตโนมัติ 24 ชม. หลังเวลาเช็คอิน')
code3 = paid(H, G)
H.ok(f'/deals/{code3}/skip', {'to': 'checkin'}); H.ok(f'/deals/{code3}/skip', {'hours': 23})
check('23 ชม. หลังเช็คอิน ยังพักเงินไว้', deal(G, code3)['status'] == 'held')
H.ok(f'/deals/{code3}/skip', {'to': 'after_release'})
d3 = deal(H, code3)
check('เลย 24 ชม. → ปล่อยเงินอัตโนมัติ', d3['status'] == 'completed' and d3['release_reason'] == 'auto' and abs(d3['completed_at'] - d3['auto_release_at']) < 1)
s, e = G.req(f'/deals/{code3}/dispute', {'reason': 'ไม่มีที่พักจริง', 'location': 'หน้าซอย', 'files': [JPG]})
check('หลังปล่อยเงินแล้ว แจ้งปัญหาไม่ได้', s == 400)

print('7) แจ้ง "ไม่มีที่พักจริง" (ต้องมีหลักฐาน + ตำแหน่ง) → ข้อพิพาท → ทีมงานคุย → คืนเงิน')
code4 = paid(H, G)
G.ok(f'/deals/{code4}/skip', {'to': 'checkin'})
for body, label in [({'reason': 'ไม่มีที่พักจริง', 'location': 'หน้าซอย 5'}, 'ไม่มีไฟล์หลักฐาน'), ({'reason': 'ไม่มีที่พักจริง', 'files': [JPG]}, 'ไม่มีตำแหน่ง'),
                    ({'reason': 'ของเสียหาย', 'location': 'หน้าซอย 5', 'files': [JPG]}, 'เหตุผลไม่ใช่ของที่พัก')]:
    s, e = G.req(f'/deals/{code4}/dispute', body)
    check(f'ปฏิเสธการแจ้งปัญหา: {label}', s == 400, e)
s, e = H.req(f'/deals/{code4}/dispute', {'reason': 'ไม่มีที่พักจริง', 'location': 'x', 'files': [JPG]})
check('เจ้าของแจ้งปัญหาแทนไม่ได้', s == 403)
G.ok(f'/deals/{code4}/dispute', {'reason': 'ไม่มีที่พักจริง', 'location': 'ยืนอยู่ตรงหมุดใน Google Maps เป็นที่ดินเปล่า', 'detail': 'โทรหาเจ้าของไม่รับสาย', 'files': [VID, JPG]})
d4 = deal(G, code4)
check('สถานะข้อพิพาท เงินยังพักไว้ + มีห้องทีมงาน', d4['status'] == 'disputed' and d4['dispute_location'].startswith('ยืนอยู่') and len(d4['dispute_files']) == 2 and d4.get('team_thread_id'))
check('เจ้าของได้แจ้งเตือน', any('ไม่มีที่พักจริง' in n['text'] for n in H.ok('/notifications')['items']))
s, e = X.req('/deals/' + code4)
check('คนนอกดูดีลไม่ได้', s == 403)
ov = ADM.ok('/admin/overview')
ad = [x for x in ov['disputes'] if x['code'] == code4]
check('แอดมินเห็นข้อพิพาทที่พัก + ตำแหน่ง + ที่อยู่ + แผนที่ + เวลาเช็คอิน', ad and ad[0]['kind'] == 'stay' and ad[0]['dispute_location'] and ad[0]['address'] and ad[0]['map_url'] and ad[0]['checkin_at'])
check('ไม่ปล่อยเงินอัตโนมัติระหว่างข้อพิพาท', (G.ok(f'/deals/{code4}/skip', {'hours': 72}) and deal(G, code4)['status'] == 'disputed'))
tid = ad[0]['thread']['id']
ADM.ok(f'/admin/threads/{tid}/messages', {'text': 'ทีมงานรับเรื่องแล้ว ขอให้เจ้าของที่พักส่งรูปหน้าบ้านปัจจุบัน'})
check('ทั้งสองฝ่ายเห็นข้อความทีมงาน', G.ok(f'/threads/{tid}')['messages'][-1]['is_admin'] and H.ok(f'/threads/{tid}')['messages'][-1]['is_admin'])
ADM.ok(f'/admin/deals/{code4}/resolve', {'decision': 'refund', 'note': 'ที่พักไม่มีอยู่จริง'})
check('ทีมงานตัดสินคืนเงินเต็มจำนวน', deal(G, code4)['status'] == 'refunded' and deal(G, code4)['refund_amount'] == deal(G, code4)['buyer_pay'])

print('8) ยกเลิกก่อนเช็คอิน')
code5 = paid(H, G, checkin_date=bkk_date(10), checkout_date=bkk_date(11))
check('ยังอยู่ในช่วงยกเลิกฟรี (ก่อน 3 วัน)', deal(G, code5)['free_cancel_now'])
r = G.ok(f'/deals/{code5}/cancel', {})
d5 = deal(G, code5)
# v6: ยกเลิกในช่วงยกเลิกฟรี = ผู้เข้าพักยกเลิกเอง → หักค่าดำเนินการ 2% ขั้นต่ำ 10 บาท
check('ผู้เข้าพักยกเลิกในช่วงยกเลิกฟรี → คืนเงินหักค่าดำเนินการ', r['result'] == 'refunded' and d5['status'] == 'refunded' and d5['resolution'] == 'guest_cancel' and d5['refund_amount'] == round(d5['buyer_pay'] - max(10, d5['buyer_pay'] * 0.02), 2))
code6 = paid(H, G, checkin_date=bkk_date(2), checkout_date=bkk_date(3))
check('เหลือไม่ถึง 3 วัน = เลยช่วงยกเลิกฟรี', not deal(G, code6)['free_cancel_now'] and 'guest_cancel' in deal(G, code6)['actions'])
r = G.ok(f'/deals/{code6}/cancel', {'reason': 'ติดธุระด่วน ขอคืนบางส่วนได้ไหม'})
d6 = deal(G, code6)
check('ยกเลิกช้า → ส่งทีมงานตัดสิน (เงินยังพักไว้)', r['result'] == 'disputed' and d6['status'] == 'disputed' and d6['dispute_reason'] == 'ขอยกเลิกหลังหมดเวลายกเลิกฟรี')
ADM.ok(f'/admin/deals/{code6}/resolve', {'decision': 'partial', 'refund_amount': 1000, 'note': 'คืน 1,000'})
check('ทีมงานแบ่งเงินได้', deal(H, code6)['status'] == 'partial' and deal(H, code6)['refund_amount'] == 1000)
code7 = paid(H, G, free_cancel_days=0)
r = H.ok(f'/deals/{code7}/cancel', {})
d7 = deal(G, code7)
check('เจ้าของยกเลิก → คืนเงินผู้เข้าพักเต็มจำนวน', r['result'] == 'refunded' and d7['resolution'] == 'host_cancel' and d7['refund_amount'] == d7['buyer_pay'])
check('ผู้เข้าพักได้แจ้งเตือนเจ้าของยกเลิก', any('เจ้าของที่พักยกเลิก' in n['text'] for n in G.ok('/notifications')['items']))
code8 = paid(H, G); H.ok(f'/deals/{code8}/skip', {'to': 'checkin'})
H.ok(f'/deals/{code8}/cancel', {})
check('เจ้าของยกเลิกได้ทุกเวลา (แม้ถึงเวลาเช็คอิน) → คืนเต็ม', deal(G, code8)['status'] == 'refunded')

print('9) ที่พักในหน้าร้าน')
pp = min(demo['products'], key=lambda p: p['price']); pid = pp['id']
s, e = G.req(f'/products/{pid}/buy', {'checkin_date': bkk_date(3), 'nights': 2, 'guests': 99})
check('เกินจำนวนผู้เข้าพักสูงสุด → ปฏิเสธ', s == 400 and 'ผู้เข้าพัก' in e['error'])
s, e = G.req(f'/products/{pid}/buy', {'checkin_date': bkk_date(-2), 'nights': 1, 'guests': 1})
check('วันเช็คอินย้อนหลัง → ปฏิเสธ', s == 400)
r = G.ok(f'/products/{pid}/buy', {'checkin_date': bkk_date(3), 'nights': 2, 'guests': 2})
d9 = deal(G, r['code'])
check('จองที่พักจากหน้าร้าน → ดีลที่พักรอจ่าย ราคา = ต่อคืน × คืน', d9['kind'] == 'stay' and d9['status'] == 'accepted' and d9['price'] == pp['price'] * 2 and d9['nights'] == 2
      and d9['address'] == pp['address'] and d9['source'] == 'shop' and d9['seller']['is_demo'])
G.ok(f'/deals/{r["code"]}/pay', {})
check('จ่ายแล้วรอเช็คอิน', deal(G, r['code'])['status'] == 'held')
pr = H.ok('/products', {'kind': 'stay', 'title': 'คอนโดใกล้ BTS (ทดสอบ)', 'price': 900, 'address': 'สุขุมวิท 50', 'map_url': 'https://www.google.com/maps/place/x',
                         'host_contact': 'คุณโฮสต์', 'max_guests': 2, 'checkin_time': '15:00', 'free_cancel_days': 2})
mp = [p for p in C().ok(f'/shops/{uh["id"]}')['products'] if p['id'] == pr['id']][0]
check('เจ้าของลงที่พักในหน้าร้านได้', mp['kind'] == 'stay' and mp['checkin_time'] == '15:00' and mp['max_guests'] == 2 and mp['free_cancel_days'] == 2)
s, e = H.req('/products', {'kind': 'stay', 'title': 'x', 'price': 900, 'address': 'x', 'map_url': 'http://bad', 'host_contact': 'x'})
check('ลงที่พักในร้านต้องมีลิงก์ Google Maps', s == 400)

print('10) แชทในดีลที่พัก')
dd = deal(G, code2)
t = G.ok(f'/threads/{dd["chat_thread_id"]}')
check('ห้องแชทรู้ว่าเป็นดีลที่พัก', t['deal']['kind'] == 'stay')

print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {fail}')
sys.exit(1 if fail else 0)
