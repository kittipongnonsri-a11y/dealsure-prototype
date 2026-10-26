"""v15.3: ชื่อจากการสมัครครั้งแรก · รูปโปรไฟล์ใน SQLite · เชื่อมบัญชี Google / LINE / Facebook (ต้องยืนยันเบอร์เสมอ)
เปิดเซิร์ฟเวอร์ในเครื่องด้วย DEALSURE_OAUTH_TEST=1 GOOGLE_CLIENT_ID=x GOOGLE_CLIENT_SECRET=x LINE_CHANNEL_ID=x LINE_CHANNEL_SECRET=x
(FACEBOOK_* ไม่ตั้ง = ต้องแสดงว่าปิดอยู่) · วิธีรัน: python3 tests/api_v15_3_auth_test.py [http://localhost:8787]"""
import os, sys, time, base64, urllib.request, urllib.error, http.cookiejar
from urllib.parse import urlparse, parse_qs, quote
sys.argv = sys.argv[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'api_test.py'), encoding='utf-8').read().split('\nA, B, X = C(), C(), C()')[0]
exec(compile(src, 'api_test_helpers', 'exec'))
if not BASE.startswith(('http://localhost', 'http://127.0.0.1')): sys.exit('รันกับเซิร์ฟเวอร์ในเครื่องเท่านั้น')

class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None

class W(C):
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), NoRedir)
    def get(self, path):
        try:
            with self.op.open(BASE + path) as r: return r.status, r.headers.get('Location'), r.read()
        except urllib.error.HTTPError as e: return e.code, e.headers.get('Location'), e.read()
    def otp(self, phone, name=''):
        j = self.ok('/login/start', {'name': name, 'phone': phone})
        return j, self.ok('/login/verify', {'phone': j['phone'], 'code': j['demo_code']})
    def social(self, p, sub, name, mode='start'):
        s, loc, _ = self.get(f'/auth/{p}/{mode}')
        assert s == 302, (s, loc)
        st = parse_qs(urlparse(loc).query)['state'][0]
        return self.get(f'/auth/{p}/callback?state={st}&code=' + quote(f'test:{sub}:{name}'))[1], loc

stamp = str(int(time.time()))[-6:]
ph = '089' + stamp + '1'
print('1) ชื่อจากการสมัครครั้งแรก')
A = W(); s, e = A.req('/login/start', {'phone': ph})
check('เบอร์ใหม่ไม่มีชื่อ → need_name (ยังไม่ออก OTP)', s == 200 and e.get('need_name') and 'demo_code' not in e, e)
_, v = A.otp(ph, 'ชื่อแรก')
check('สมัครด้วยชื่อแรก', v['name'] == 'ชื่อแรก' and v['returning'] is False, v)
B = W(); j, v = B.otp(ph, 'ชื่อใหม่ที่ไม่ควรใช้')
check('ล็อกอินซ้ำด้วยชื่ออื่น → ใช้ชื่อเดิม + returning', v['name'] == 'ชื่อแรก' and v['returning'] and j['existing'], v)
B2 = W(); _, v = B2.otp(ph)
check('เบอร์เดิมไม่ต้องกรอกชื่อ', v['name'] == 'ชื่อแรก', v)
A.ok('/me/update', {'name': 'ชื่อแก้ไข'})
check('เปลี่ยนชื่อที่หน้าโปรไฟล์ได้', A.ok('/me')['user']['name'] == 'ชื่อแก้ไข')

print('2) รูปโปรไฟล์')
r = A.ok('/me/avatar', {'image': PNG})
check('อัปโหลดรูป → เก็บใน DB, URL /avatar/<id>', r['avatar'].startswith('/avatar/'), r)
s, _, body = A.get(r['avatar'].split('?')[0])
check('เปิดรูปได้ (PNG)', s == 200 and body.startswith(b'\x89PNG'))
s, e = A.req('/me/avatar', {'image': 'data:image/png;base64,' + base64.b64encode(b'not an image').decode()})
check('ไฟล์ปลอมนามสกุลรูป → ปฏิเสธ', s == 400, e)
s, e = A.req('/me/avatar', {'image': 'data:image/svg+xml;base64,' + base64.b64encode(b'<svg/>').decode()})
check('SVG → ปฏิเสธ', s == 400, e)
big = 'data:image/jpeg;base64,' + base64.b64encode(b'\xff\xd8\xff' + b'0' * (2 * 1024 * 1024 + 10)).decode()
s, e = A.req('/me/avatar', {'image': big})
check('เกิน 2 MB → ปฏิเสธ', s == 400, e)
A.ok('/me/avatar', {'remove': True})
check('ลบรูปได้', A.ok('/me')['user']['avatar'] is None)

print('3) บัญชีที่เชื่อมต่อ')
pv = {p['id']: p['enabled'] for p in A.ok('/auth/providers')['providers']}
check('Google/LINE เปิด, Facebook ไม่มี env → ปิด', pv == {'google': True, 'line': True, 'facebook': False}, pv)
s, loc, _ = A.get('/auth/facebook/start')
check('Facebook ปิด → ไม่ไป provider', s == 302 and 'facebook_off' in loc, loc)
loc, auth = A.social('google', 'g' + stamp, 'Gname', 'link')
check('ลิงก์ไป Google มี state + redirect_uri callback', 'accounts.google.com' in auth and 'auth%2Fgoogle%2Fcallback' in auth and 'state=' in auth, auth)
check('เชื่อม Google สำเร็จ', 'linked=google' in loc, loc)
check('/me แสดง identities', [i['provider'] for i in A.ok('/me')['user']['identities']] == ['google'])
G = W(); loc, _ = G.social('google', 'g' + stamp, 'Gname')
check('เข้าด้วย Google ที่เชื่อมแล้ว → เข้าระบบทันที', G.ok('/me')['user']['phone'] == ph, loc)
s, loc, _ = W().get('/auth/google/callback?state=forged&code=test:x:y')
check('state ปลอม → ปฏิเสธ', 'err=state' in loc, loc)
X = W(); s, loc, _ = X.get('/auth/line/start'); st = parse_qs(urlparse(loc).query)['state'][0]
Y = W(); s, loc, _ = Y.get(f'/auth/line/callback?state={st}&code=test:l:z')
check('state จากเบราว์เซอร์อื่น (ไม่มีคุกกี้) → ปฏิเสธ (CSRF)', 'err=state' in loc, loc)

N = W(); loc, _ = N.social('line', 'l' + stamp, 'LineName')
check('LINE ตัวตนใหม่ → ต้องยืนยันเบอร์ก่อน (ยังไม่เข้าระบบ)', 'social=line' in loc and N.ok('/me')['user'] is None, loc)
check('pending แสดงชื่อจาก LINE', N.ok('/auth/providers')['pending']['name'] == 'LineName')
_, v = N.otp(ph)
check('ยืนยันเบอร์ที่มีอยู่แล้ว → ผูกกับผู้ใช้เดิม', v['returning'] and v['linked'] == 'line' and v['name'] == 'ชื่อแก้ไข', v)
check('ผู้ใช้เดิมมี google+line', sorted(i['provider'] for i in A.ok('/me/identities')['identities']) == ['google', 'line'])
M = W(); M.social('line', 'new' + stamp, 'คนใหม่จากไลน์')
ph2 = '089' + stamp + '2'; j, v = M.otp(ph2)
check('LINE ใหม่ + เบอร์ใหม่ → สมัครด้วยชื่อจาก LINE ไม่ต้องกรอก', v['name'] == 'คนใหม่จากไลน์' and not v['returning'], v)
K = W(); K.otp(ph2); loc, _ = K.social('line', 'l' + stamp, 'x', 'link')
check('เชื่อม LINE ที่เป็นของคนอื่น → ปฏิเสธ', 'err=taken' in loc, loc)
r = A.ok('/me/identities/unlink', {'provider': 'google'})
check('ยกเลิกเชื่อม Google ได้ (เบอร์ยังอยู่)', [i['provider'] for i in r['identities']] == ['line'])
G2 = W(); loc, _ = G2.social('google', 'g' + stamp, 'Gname')
check('หลังยกเลิก Google เข้าระบบไม่ได้ทันที ต้องยืนยันเบอร์', 'social=google' in loc and G2.ok('/me')['user'] is None, loc)
print(f'\nผลลัพธ์: ผ่าน {ok} ไม่ผ่าน {fail}'); sys.exit(1 if fail else 0)
