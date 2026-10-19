"""v9: สร้างดีลจากสินค้าขายประจำ — prefill ผ่าน product_id, แก้ราคาไม่กระทบสินค้า, นับขายแล้ว
วิธีรัน: python3 tests/api_v9_product_deal_test.py [http://localhost:8787]"""
import os, sys, time
sys.argv = sys.argv[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'api_test.py'), encoding='utf-8').read().split('\nA, B, X = C(), C(), C()')[0]
exec(compile(src, 'api_test_helpers', 'exec'))
if not BASE.startswith(('http://localhost', 'http://127.0.0.1')): sys.exit('รันกับเซิร์ฟเวอร์ในเครื่องเท่านั้น')

from datetime import datetime, timedelta, timezone
TZ = timezone(timedelta(hours=7))
def bkk_date(days): return (datetime.now(TZ) + timedelta(days=days)).strftime('%Y-%m-%d')

stamp = str(int(time.time()))[-6:]
S, B = C(), C()
us = S.login('ผู้ขาย v9', '081' + stamp + '1')
ub = B.login('ผู้ซื้อ v9', '082' + stamp + '2')

print('1) เพิ่มสินค้าขายประจำ แล้วสร้างดีลจากแม่แบบ (แก้ราคา)')
pid = S.ok('/products', {'title': 'เสื้อวินเทจแม่แบบ', 'price': '450', 'description': 'ผ้าดี สีไม่ตก', 'deliveries': ['parcel', 'meet'], 'fee_payer': 'half', 'ship_days': 2})['id']
shop = S.ok(f'/shops/{us["id"]}')
prod = [p for p in shop['products'] if p['id'] == pid][0]
sold0 = prod.get('sold_count') or 0
check('มีสินค้าขายประจำในหน้าร้าน', prod['title'] == 'เสื้อวินเทจแม่แบบ' and prod['price'] == 450)

code = S.ok('/deals', {
    'role': 'seller', 'title': 'เสื้อวินเทจแม่แบบ (ลดพิเศษ)', 'description': 'ผ้าดี สีไม่ตก',
    'price': 399, 'photos': prod['photos'], 'delivery': 'meet', 'due_date': bkk_date(2),
    'fee_payer': 'half', 'product_id': pid
})['code']
d = S.ok(f'/deals/{code}')
check('ดีลเก็บ product_id', d.get('product_id') == pid, d.get('product_id'))
check('ดีลใช้ราคาที่แก้แล้ว', d['price'] == 399)
check('source=product', d.get('source') == 'product', d.get('source'))

shop2 = S.ok(f'/shops/{us["id"]}')
prod2 = [p for p in shop2['products'] if p['id'] == pid][0]
check('สินค้าต้นทางไม่เปลี่ยนชื่อ/ราคา', prod2['title'] == 'เสื้อวินเทจแม่แบบ' and prod2['price'] == 450, prod2)

print('2) ทำดีลสำเร็จ → ขายแล้ว N ครั้ง เพิ่มขึ้น')
B.ok(f'/deals/{code}/accept', {})
B.ok(f'/deals/{code}/pay', {})
B.ok(f'/deals/{code}/meet-code', {'code': S.ok(f'/deals/{code}')['meet_code']})
shop3 = S.ok(f'/shops/{us["id"]}')
prod3 = [p for p in shop3['products'] if p['id'] == pid][0]
check('ขายแล้ว +1 หลังจบดีล', prod3.get('sold_count') == sold0 + 1, {'before': sold0, 'after': prod3.get('sold_count')})

print('3) product_id ของคนอื่นใช้ไม่ได้')
# gold shop product
gold = [s for s in C().ok('/shops')['shops'] if s['stats']['level'] == 'gold'][0]
gp = C().ok(f'/shops/{gold["id"]}')['products'][0]
s, e = S.req('/deals', {'role': 'seller', 'title': 'x', 'price': 200, 'delivery': 'parcel', 'due_date': bkk_date(2), 'fee_payer': 'half', 'product_id': gp['id']})
check('ห้ามใช้สินค้าขายประจำของร้านอื่น', s == 400 and 'ร้านคุณเอง' in e['error'], e)

print('4) บันทึกเป็นสินค้าขายประจำตอนสร้างมือ')
r = S.ok('/deals', {'role': 'seller', 'title': 'กระเป๋าใหม่จากดีล', 'price': 280, 'delivery': 'parcel', 'due_date': bkk_date(3), 'fee_payer': 'seller', 'save_as_product': True})
check('สร้างดีลมือ + บันทึกสินค้าได้', r.get('saved_as_product') and r.get('product_id'), r)
shop4 = S.ok(f'/shops/{us["id"]}')
check('สินค้าใหม่อยู่ในหน้าร้าน', any(p['id'] == r['product_id'] and p['title'] == 'กระเป๋าใหม่จากดีล' and p['price'] == 280 for p in shop4['products']))

print('5) ที่พักให้จอง — สร้างดีลที่พักพร้อม product_id')
MAP = 'https://maps.app.goo.gl/AbCdEf123'
spid = S.ok('/products', {'kind': 'stay', 'title': 'บ้านไม้ทดสอบ v9', 'price': 900, 'address': '1 ม.1', 'map_url': MAP, 'host_contact': 'โฮสต์', 'checkin_time': '14:00', 'max_guests': 3, 'free_cancel_days': 2})['id']
sc = S.ok('/deals', {'kind': 'stay', 'role': 'seller', 'title': 'บ้านไม้ทดสอบ v9', 'price': 1800, 'address': '1 ม.1', 'map_url': MAP,
    'checkin_date': bkk_date(5), 'checkin_time': '14:00', 'checkout_date': bkk_date(7), 'guests': 2, 'host_contact': 'โฮสต์',
    'free_cancel_days': 2, 'fee_payer': 'half', 'product_id': spid})['code']
sd = S.ok(f'/deals/{sc}')
check('ดีลที่พักเก็บ product_id', sd.get('product_id') == spid and sd.get('kind') == 'stay')
stay_prod = [p for p in S.ok(f'/shops/{us["id"]}')['products'] if p['id'] == spid][0]
check('ที่พักให้จองต้นทางไม่เปลี่ยนราคาต่อคืน', stay_prod['price'] == 900)

print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {fail}')
sys.exit(1 if fail else 0)
