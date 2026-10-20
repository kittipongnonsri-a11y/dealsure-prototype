"""v10: คลิปวิดีโอ (ไม่บังคับ) — สินค้า, คลิปแพ็คของ, ขอ/แนบคลิปแกะกล่อง, ข้อพิพาท, จำกัดขนาด
วิธีรัน: python3 tests/api_v10_video_test.py [http://localhost:8787]"""
import os, sys, time, base64
sys.argv = sys.argv[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'api_test.py'), encoding='utf-8').read().split('\nA, B, X = C(), C(), C()')[0]
exec(compile(src, 'api_test_helpers', 'exec'))
if not BASE.startswith(('http://localhost', 'http://127.0.0.1')): sys.exit('รันกับเซิร์ฟเวอร์ในเครื่องเท่านั้น')
from datetime import datetime, timedelta, timezone
def due(n): return (datetime.now(timezone(timedelta(hours=7))) + timedelta(days=n)).strftime('%Y-%m-%d')
VID = 'data:video/mp4;base64,' + base64.b64encode(open(os.path.join(HERE, 'unboxing.mp4'), 'rb').read()).decode()
st = str(int(time.time()))[-6:]
S, B, X = C(), C(), C()
us = S.login('ผู้ขาย v10', '083' + st + '1'); B.login('ผู้ซื้อ v10', '084' + st + '2'); X.login('คนนอก v10', '085' + st + '3')

def mk(delivery='parcel'):
    c = S.ok('/deals', {'role': 'seller', 'title': 'ของทดสอบคลิป', 'price': 300, 'delivery': delivery, 'due_date': due(2), 'fee_payer': 'half'})['code']
    B.ok(f'/deals/{c}/accept', {}); B.ok(f'/deals/{c}/pay', {}); return c

print('1) สินค้าขายประจำแนบคลิปได้')
pid = S.ok('/products', {'title': 'สินค้ามีคลิป', 'price': 200, 'photos': [VID]})['id']
p = [p for p in S.ok(f'/shops/{us["id"]}')['products'] if p['id'] == pid][0]
check('เก็บคลิปเป็น .mp4', p['photos'][0].endswith('.mp4'), p['photos'])
check('ดีลแนบคลิปได้', S.ok('/deals', {'role': 'seller', 'title': 'ดีลมีคลิป', 'price': 200, 'delivery': 'parcel', 'due_date': due(2), 'fee_payer': 'half', 'photos': [VID]})['code'])

print('2) แจ้งส่งของ — ไม่มีคลิปก็ได้')
c1 = mk(); S.ok(f'/deals/{c1}/ship', {'tracking': 'TH0000V10A', 'carrier': 'Kerry Express'})
d = S.ok(f'/deals/{c1}'); check('ส่งได้โดยไม่มีคลิป', d['status'] == 'shipped' and not d.get('pack_video'))
txt = ' '.join(x['text'] for x in B.ok('/notifications')['items'])
check('แจ้งเตือนส่งของมีคำแนะนำถ่ายคลิปแกะกล่อง', 'ถ่ายคลิปตอนแกะกล่อง' in txt)
B.ok(f'/deals/{c1}/confirm', {}); check('ยืนยันรับได้โดยไม่ต้องมีคลิป', B.ok(f'/deals/{c1}')['status'] == 'completed')

print('3) แจ้งส่งของพร้อมคลิปแพ็ค + ขอคลิปแกะกล่อง')
c2 = mk(); S.ok(f'/deals/{c2}/ship', {'tracking': 'TH0000V10B', 'carrier': 'Kerry Express', 'pack_video': VID})
check('ผู้ซื้อเห็นคลิปแพ็ค', (B.ok(f'/deals/{c2}').get('pack_video') or '').endswith('.mp4'))
s, e = X.req(f'/deals/{c2}'); check('คนนอกไม่เห็นคลิป', s == 403 or not (e or {}).get('pack_video'))
s, e = B.req(f'/deals/{c2}/request-unbox', {}); check('ผู้ซื้อกดขอคลิปไม่ได้', s in (400, 403))
S.ok(f'/deals/{c2}/request-unbox', {}); check('บันทึกเวลาขอคลิป', S.ok(f'/deals/{c2}').get('unbox_requested_at'))
s, e = S.req(f'/deals/{c2}/unbox-video', {'video': VID}); check('ผู้ขายแนบคลิปแกะกล่องแทนไม่ได้', s in (400, 403))
B.ok(f'/deals/{c2}/unbox-video', {'video': VID}); check('ผู้ขายเห็นคลิปแกะกล่อง', (S.ok(f'/deals/{c2}').get('unbox_video') or '').endswith('.mp4'))

print('4) จำกัดชนิด/ขนาด')
s, e = S.req('/products', {'title': 'x', 'price': 200, 'photos': ['data:application/pdf;base64,AAAA']}); check('ปฏิเสธไฟล์ที่ไม่ใช่รูป/คลิป', s == 400)
big = 'data:video/mp4;base64,' + base64.b64encode(b'\0' * (31 * 1024 * 1024)).decode()
c3 = mk(); s, e = S.req(f'/deals/{c3}/ship', {'tracking': 'TH0000V10C', 'carrier': 'Kerry Express', 'pack_video': big})
check('คลิปเกิน 30 MB แจ้งเป็นภาษาไทย', s in (400, 413) and 'ใหญ่เกิน' in (e or {}).get('error', ''), (s, e))
check('ดีลยังไม่ถูกเปลี่ยนสถานะเมื่อคลิปใหญ่เกิน', S.ok(f'/deals/{c3}')['status'] == 'held')

print('5) ข้อพิพาทแนบคลิปแกะกล่องอย่างเดียวได้')
S.ok(f'/deals/{c3}/ship', {'tracking': 'TH0000V10C', 'carrier': 'Kerry Express'})
B.ok(f'/deals/{c3}/dispute', {'reason': 'ของไม่ตรงปก', 'detail': 'สีไม่ตรง', 'files': [], 'unbox_video': VID})
d = B.ok(f'/deals/{c3}'); check('เปิดข้อพิพาทด้วยคลิป', d['status'] == 'disputed' and (d.get('unbox_video') or '').endswith('.mp4'))
print('6) v11: ผู้ซื้อขอคลิปตอนแพ็คของ → ผู้ขายต้องแนบก่อนส่ง')
c4 = mk()
s, e = S.req(f'/deals/{c4}/request-pack', {}); check('ผู้ขายขอคลิปแพ็คเองไม่ได้', s in (400, 403))
B.ok(f'/deals/{c4}/request-pack', {}); check('บันทึกเวลาขอคลิปแพ็ค', S.ok(f'/deals/{c4}').get('pack_requested_at'))
check('ผู้ขายได้แจ้งเตือน', any('ผู้ซื้อขอคลิปตอนแพ็คของ' in x['text'] for x in S.ok('/notifications')['items']))
s, e = S.req(f'/deals/{c4}/ship', {'tracking': 'TH0000V11A', 'carrier': 'Kerry Express'})
check('ถูกขอแล้ว ส่งของโดยไม่มีคลิปไม่ได้', s == 400 and 'ต้องแนบคลิปก่อนแจ้งส่งของ' in e['error'], e)
check('สถานะยังเป็น held', S.ok(f'/deals/{c4}')['status'] == 'held')
S.ok(f'/deals/{c4}/ship', {'tracking': 'TH0000V11A', 'carrier': 'Kerry Express', 'pack_video': VID})
check('แนบคลิปแล้วส่งได้', S.ok(f'/deals/{c4}')['status'] == 'shipped')
c6 = mk(); S.ok(f'/deals/{c6}/ship', {'tracking': 'TH0000V11B', 'carrier': 'Kerry Express'})
s, e = B.req(f'/deals/{c6}/request-pack', {}); check('ขอคลิปหลังส่งของแล้วไม่ได้', s == 400 and 'ก่อนผู้ขายแจ้งส่งของ' in e['error'], e)
c5 = mk('meet'); s, e = B.req(f'/deals/{c5}/request-pack', {}); check('ดีลนัดรับขอคลิปแพ็คไม่ได้', s == 400)
c8 = mk('messenger'); B.ok(f'/deals/{c8}/request-pack', {})
s, e = S.req(f'/deals/{c8}/ship', {'proof_text': 'https://track.example/1', 'photos': []}); check('แมสเซนเจอร์ถูกขอแล้วต้องแนบคลิป', s == 400)
print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {fail}'); sys.exit(1 if fail else 0)
