"""ทดสอบหน้าเอกสาร (v5): /terms และ /privacy โหลดได้ มีสรุปสั้นๆ สารบัญ หัวข้อเลขกำกับ และลิงก์ถึงกัน
วิธีรัน: python3 tests/legal_test.py [http://localhost:8787]"""
import re, sys, urllib.request
BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8787').rstrip('/')
ok = bad = 0


def check(cond, msg):
    global ok, bad
    print(('  ✓ ' if cond else '  ✗ ') + msg); ok += bool(cond); bad += (not cond)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r: return r.status, r.headers.get('Content-Type', ''), r.read().decode('utf-8')


for path, title, must in [('/terms', 'ข้อตกลงและเงื่อนไขการใช้บริการ', ['3% ของราคาดีล', '2% ของยอดที่ผู้ซื้อจ่าย', '20 บาท', '5,000 บาท', '3,000 บาท', 'พระราชบัญญัติระบบการชำระเงิน พ.ศ. 2560', '5 วันทำการ', 'Gold', 'นอกแอป']),
                          ('/privacy', 'นโยบายความเป็นส่วนตัว', ['พ.ศ. 2562', 'บัตรประชาชน', 'สคส.', 'คุกกี้', 'ถอนความยินยอม', '10 ปี', 'DPO'])]:
    print(path)
    st, ct, html = get(path)
    check(st == 200 and 'text/html' in ct, f'{path} โหลดได้ (200, HTML)')
    check(f'<h1>{title}</h1>' in html, f'หัวเรื่อง: {title}')
    lis = re.search(r'<section class="card legal-sum".*?</section>', html, re.S)
    n = len(re.findall(r'<li>', lis.group(0))) if lis else 0
    check(5 <= n <= 7, f'กล่องสรุปสั้นๆ มี {n} ข้อ (5–7)')
    secs = re.findall(r'<section class="card legal-sec" id="s(\d+)"><h2>(\d+)\.', html)
    check(len(secs) >= 10 and all(a == b for a, b in secs), f'หัวข้อมีเลขกำกับเรียงกัน {len(secs)} หัวข้อ')
    check(html.count('<li><a href="#s') == len(secs), 'สารบัญครบทุกหัวข้อ')
    for m in must: check(m in html, f'มีเนื้อหา “{m}”')
    check('[ชื่อบริษัท/ผู้ให้บริการ]' in html and 'ph-fill' in html, 'มีช่องเว้นให้เติม (placeholder) เน้นสีไว้')
    check('href="/terms"' in html and 'href="/privacy"' in html, 'ลิงก์ไปอีกเอกสารได้')
    check('<script' not in html.lower(), 'ไม่มี script (หน้าอ่านอย่างเดียว)')
st, _, _ = get('/terms/'); check(st == 200, '/terms/ (มี / ท้าย) ใช้ได้')
js = get('/static/app.js')[2]
check('href="/terms"' in js and 'การเข้าใช้งานถือว่าคุณยอมรับ' in js and 'legalCard' in js, 'แอปมีลิงก์ข้อตกลง/นโยบายในหน้าเข้าสู่ระบบ บัญชี และท้ายหน้า')
print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {bad}')
sys.exit(1 if bad else 0)
