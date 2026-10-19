"""ทดสอบ API ฟีเจอร์ใหม่ (v2): รูปโปรไฟล์ · แชทในดีล · ทักร้าน · ทีมงานคุยในข้อพิพาท
วิธีรัน: python3 tests/api_v2_test.py [http://localhost:8787]"""
import os, sys, time, urllib.request
sys.argv = sys.argv[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# ใช้ตัวช่วยเดียวกับ api_test.py (คลาส C, check, new_deal ฯลฯ) โดยไม่รันชุดทดสอบเดิม
src = open(os.path.join(HERE, 'api_test.py'), encoding='utf-8').read().split('\nA, B, X = C(), C(), C()')[0]
exec(compile(src, 'api_test_helpers', 'exec'))

A, B, X = C(), C(), C()
stamp = str(int(time.time()))[-6:]
ua = A.login('ผู้ขายแชท A', '084' + stamp + '1')
ub = B.login('ผู้ซื้อแชท B', '085' + stamp + '2')
ux = X.login('คนนอก X', '086' + stamp + '3')
JPG = 'data:image/jpeg;base64,' + __import__('base64').b64encode(open(os.path.join(HERE, 'camera.jpg'), 'rb').read()).decode()

print('1) รูปโปรไฟล์')
check('ค่าเริ่มต้นไม่มีรูป (ใช้อักษรย่อ)', ua['avatar'] is None and ua['initial'])
r = A.ok('/me/avatar', {'image': JPG})
check('อัปโหลดรูปโปรไฟล์ได้', r['avatar'].startswith('/uploads/') and r['avatar'].endswith('.jpg'))
with urllib.request.urlopen(BASE + r['avatar']) as f:
    check('ไฟล์รูปเปิดได้ (image/jpeg)', f.status == 200 and f.headers['Content-Type'] == 'image/jpeg')
check('/me มีรูปใหม่', A.ok('/me')['user']['avatar'] == r['avatar'])
check('โปรไฟล์สาธารณะมีรูป', B.ok(f'/users/{ua["id"]}')['avatar'] == r['avatar'])
check('หน้าร้านมีรูป', B.ok(f'/shops/{ua["id"]}')['avatar'] == r['avatar'])
s, e = A.req('/me/avatar', {'image': 'data:text/plain;base64,aGVsbG8='})
check('ไฟล์ที่ไม่ใช่รูปถูกปฏิเสธ', s == 400)
s, e = C().req('/me/avatar', {'image': JPG})
check('ต้องล็อกอินก่อน', s == 401)
B.ok('/me/avatar', {'image': PNG})

print('2) แชทผู้ซื้อ-ผู้ขายในดีล')
code = new_deal(A, title='กล้องสำหรับแชท', price=1200)
d = deal(A, code)
check('ดีลที่ยังไม่มีคู่ ยังไม่มีห้องแชท', 'chat_thread_id' not in d)
s, e = A.req(f'/deals/{code}/thread', {})
check('สร้างห้องแชทก่อนอีกฝ่ายรับดีลไม่ได้', s == 400)
B.ok(f'/deals/{code}/accept', {})
da, db_ = deal(A, code), deal(B, code)
tid = da['chat_thread_id']
check('ทั้งสองฝ่ายได้ห้องแชทเดียวกัน', tid and tid == db_['chat_thread_id'] and B.ok(f'/deals/{code}/thread', {})['thread_id'] == tid)
check('ข้อมูลผู้ขายในดีลมีรูปโปรไฟล์', db_['seller']['avatar'] == r['avatar'])
s, e = X.req(f'/threads/{tid}')
check('คนนอกอ่านแชทไม่ได้', s == 403)
s, e = X.req(f'/threads/{tid}/messages', {'text': 'แอบส่ง'})
check('คนนอกส่งข้อความไม่ได้', s == 403)
s, e = B.req(f'/threads/{tid}/messages', {'text': '   '})
check('ข้อความว่างส่งไม่ได้', s == 400)
m1 = B.ok(f'/threads/{tid}/messages', {'text': 'สวัสดีครับ ของยังอยู่ไหม'})['id']
check('ผู้ขายมีแชทยังไม่อ่าน 1', A.ok('/me')['user']['chat_unread'] == 1 and A.ok('/notifications')['chat_unread'] == 1)
n = A.ok('/notifications')['items'][0]
check('แจ้งเตือนในกระดิ่ง (ไอคอนแชท + ลิงก์ห้อง)', n['icon'] == 'chat' and n['link'] == f'#/chat/{tid}' and 'สวัสดีครับ' in n['text'] and not n['read'])
B.ok(f'/threads/{tid}/messages', {'text': 'ส่งรูปให้ดูหน่อย', 'photos': [JPG]})
nn = [x for x in A.ok('/notifications')['items'] if x['link'] == f'#/chat/{tid}']
check('หลายข้อความรวมเป็นแจ้งเตือนเดียว (ไม่รก)', len(nn) == 1 and 'ส่งรูปให้ดูหน่อย' in nn[0]['text'])
dl = [x for x in A.ok('/deals')['deals'] if x['code'] == code][0]
check('การ์ดดีลมีจำนวนแชทยังไม่อ่าน + ข้อมูลอีกฝ่าย', dl['chat_unread'] == 2 and dl['other'] == 'ผู้ซื้อแชท B' and dl['other_avatar'] and dl['updated_at'] >= dl['created_at'])
th = A.ok(f'/threads/{tid}')
check('ผู้ขายอ่านแชท: 2 ข้อความ ลำดับถูก + รูป', [m['text'] for m in th['messages']] == ['สวัสดีครับ ของยังอยู่ไหม', 'ส่งรูปให้ดูหน่อย'] and len(th['messages'][1]['photos']) == 1)
check('บทบาทผู้ส่ง = ผู้ซื้อ, ไม่ใช่ของฉัน', th['messages'][0]['role'] == 'buyer' and not th['messages'][0]['mine'] and th['my_role'] == 'seller')
check('อ่านแล้ว → ยังไม่อ่านเป็น 0 + แจ้งเตือนแชทถูกอ่าน', A.ok('/me')['user']['chat_unread'] == 0 and all(x['read'] for x in A.ok('/notifications')['items'] if x['link'] == f'#/chat/{tid}'))
A.ok(f'/threads/{tid}/messages', {'text': 'อยู่ครับ โอนตรงมาที่เลขบัญชี 123-4-56789-0 ก็ได้'})
th = B.ok(f'/threads/{tid}?after={m1}')
check('ดึงเฉพาะข้อความใหม่ (after=)', len(th['messages']) == 2 and th['messages'][0]['mine'])
check('ข้อความชวนจ่ายนอกแอปถูกติดคำเตือน', th['messages'][-1]['warn'] and not th['messages'][0]['warn'])
ch = B.ok('/chats')
it = [x for x in ch['items'] if x['id'] == tid][0]
check('รายการแชท: ชื่อร้านอีกฝ่าย + ชื่อดีล + ข้อความล่าสุด', it['name'] == 'ผู้ขายแชท A' and it['sub'] == 'กล้องสำหรับแชท' and 'เลขบัญชี' in it['last']['text'] and it['unread'] == 0)
check('คนนอกไม่เห็นห้องนี้ในรายการแชท', all(x['id'] != tid for x in X.ok('/chats')['items']))

print('3) ทักร้านก่อนซื้อ')
s, e = A.req(f'/shops/{ua["id"]}/thread', {})
check('ทักร้านตัวเองไม่ได้', s == 400)
st = X.ok(f'/shops/{ua["id"]}/thread', {})['thread_id']
check('ทักซ้ำได้ห้องเดิม', X.ok(f'/shops/{ua["id"]}/thread', {})['thread_id'] == st)
X.ok(f'/threads/{st}/messages', {'text': 'มีกล้องตัวอื่นอีกไหมคะ'})
ita = [x for x in A.ok('/chats')['items'] if x['id'] == st][0]
check('เจ้าของร้านเห็นลูกค้าทัก + ยังไม่อ่าน', ita['kind'] == 'shop' and ita['unread'] == 1 and ita['name'] == 'คนนอก X')
A.ok(f'/threads/{st}/messages', {'text': 'มีค่ะ เดี๋ยวลงหน้าร้านให้'})
itx = [x for x in X.ok('/chats')['items'] if x['id'] == st][0]
check('ลูกค้าเห็นร้านตอบ', itx['unread'] == 1 and itx['sub'] == 'ทักจากหน้าร้าน' and X.ok(f'/threads/{st}')['messages'][-1]['role'] == 'shop')
s, e = B.req(f'/threads/{st}')
check('คนอื่นอ่านแชทหน้าร้านของคนอื่นไม่ได้', s == 403)

print('4) ทีมงานคุยกับทั้งสองฝ่ายในข้อพิพาท')
B.ok(f'/deals/{code}/pay', {})
A.ok(f'/deals/{code}/ship', {'tracking': 'TH0000CHAT01', 'carrier': 'Flash Express'})
s, e = B.req(f'/deals/{code}/thread', {'kind': 'dispute'})
check('ยังไม่แจ้งปัญหา → ไม่มีห้องทีมงาน', s == 400 and 'team_thread_id' not in deal(B, code))
B.ok(f'/deals/{code}/dispute', {'reason': 'ของเสียหาย', 'detail': 'เลนส์แตก', 'files': [PNG]})
dt = deal(B, code)['team_thread_id']
check('แจ้งปัญหาแล้ว ทั้งสองฝ่ายมีห้องทีมงานเดียวกัน', dt and deal(A, code)['team_thread_id'] == dt and dt != tid)
ADM = C(); ADM.ok('/admin/login', {'password': admin_password()})
s, e = C().req(f'/admin/threads/{dt}')
check('ห้องแอดมินต้องล็อกอินแอดมิน', s == 401)
ov = [x for x in ADM.ok('/admin/overview')['disputes'] if x['code'] == code][0]
check('หน้าแอดมิน: ข้อพิพาทมีห้องข้อความ + แชทผู้ซื้อผู้ขายเป็นหลักฐาน', ov['thread']['id'] == dt and len(ov['deal_chat']) == 3)
ADM.ok(f'/admin/threads/{dt}/messages', {'text': 'สวัสดีค่ะ ทีมงานขอรูปกล่องพัสดุเพิ่มเติมค่ะ'})
for who, u in ((A, 'ผู้ขาย'), (B, 'ผู้ซื้อ')):
    n = [x for x in who.ok('/notifications')['items'] if x['link'] == f'#/d/{code}/team'][0]
    check(f'{u}ได้แจ้งเตือนจากทีมงานในกระดิ่ง', n['icon'] == 'team' and n['text'].startswith('ทีมงานดีลชัวร์:') and not n['read'])
tm = B.ok(f'/threads/{dt}')
check('ข้อความทีมงานติดป้าย admin', tm['messages'][0]['is_admin'] and tm['messages'][0]['role'] == 'admin' and not tm['messages'][0]['mine'] and tm['kind'] == 'dispute' and not tm['closed'])
B.ok(f'/threads/{dt}/messages', {'text': 'ส่งรูปกล่องให้ค่ะ', 'photos': [JPG]})
A.ok(f'/threads/{dt}/messages', {'text': 'ผู้ขายแพ็คกันกระแทกอย่างดีครับ'})
at = ADM.ok(f'/admin/threads/{dt}')
check('แอดมินเห็นคำตอบทั้งสองฝ่าย + รูป', [m['role'] for m in at['messages']] == ['admin', 'buyer', 'seller'] and len(at['messages'][1]['photos']) == 1 and at['messages'][0]['mine'])
check('แอดมินอ่านแล้ว ยังไม่อ่านเป็น 0', [x for x in ADM.ok('/admin/overview')['disputes'] if x['code'] == code][0]['thread']['unread'] == 0)
check('ผู้ขายเห็นข้อความผู้ซื้อในห้องทีมงาน', [m['role'] for m in A.ok(f'/threads/{dt}')['messages']] == ['admin', 'buyer', 'seller'])
s, e = X.req(f'/threads/{dt}')
check('คนนอกอ่านห้องข้อพิพาทไม่ได้', s == 403)
s, e = ADM.req(f'/admin/threads/{tid}')
check('แอดมินเปิดแชทส่วนตัวผ่าน API ห้องทีมงานไม่ได้', s == 403)
ADM.ok(f'/admin/deals/{code}/resolve', {'decision': 'refund', 'note': 'ของเสียหายจริง'})
s, e = B.req(f'/threads/{dt}/messages', {'text': 'ขอบคุณค่ะ'})
check('ตัดสินแล้ว ห้องทีมงานปิด (อ่านได้ ส่งไม่ได้)', s == 400 and B.ok(f'/threads/{dt}')['closed'])
check('แชทผู้ซื้อ-ผู้ขายยังใช้ได้หลังตัดสิน', B.ok(f'/threads/{tid}/messages', {'text': 'ขอบคุณที่คืนเงินค่ะ'})['ok'])

print('5) ลบรูปโปรไฟล์ → กลับไปใช้รูปเริ่มต้น')
A.ok('/me/avatar', {'remove': True})
check('กลับไปใช้อักษรย่อ', A.ok('/me')['user']['avatar'] is None)

print('6) ประวัติดีลยาว (ให้แอปแบ่งหน้า "ดูเพิ่ม")')
gold = [x for x in B.ok('/shops')['shops'] if x['stats']['level'] == 'gold'][0]
h = B.ok(f'/users/{gold["id"]}')['history']
check('โปรไฟล์ส่งประวัติได้มากกว่า 30 ดีล (สูงสุด 100) ให้แอปกด "ดูเพิ่ม"', 30 < len(h) <= 100, len(h))

print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {fail}')
sys.exit(1 if fail else 0)
