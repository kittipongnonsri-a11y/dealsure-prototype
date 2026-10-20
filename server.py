#!/usr/bin/env python3
"""ดีลชัวร์ (DealSure) – prototype server.

ใช้แค่ Python 3 ล้วน ๆ (ไม่ต้องติดตั้งอะไรเพิ่ม) + SQLite
โหมดทดลอง: ไม่มีเงินจริง ไม่มี SMS จริง
"""
import base64, json, os, random, re, secrets, sqlite3, threading, time, mimetypes
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urlparse, unquote

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get('DEALSURE_DATA', os.path.join(BASE, 'data'))
DB_PATH = os.path.join(DATA, 'dealsure.db')
UPLOADS = os.path.join(DATA, 'uploads')
STATIC = os.path.join(BASE, 'static')
PORT = int(os.environ.get('PORT', '8787'))
HOST = os.environ.get('HOST', '0.0.0.0')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '').strip()
ADMIN_PASSWORD_GENERATED = not ADMIN_PASSWORD
if ADMIN_PASSWORD_GENERATED:  # ไม่ได้ตั้ง env → สุ่มรหัสใหม่ทุกครั้งที่เปิดเซิร์ฟเวอร์ แล้วพิมพ์ลง log
    ADMIN_PASSWORD = secrets.token_urlsafe(12)
TZ = timezone(timedelta(hours=7))  # Asia/Bangkok
HOUR, DAY = 3600, 86400

# ---- business rules ----
FEE_RATE, FEE_MIN = 0.02, 20
MIN_PRICE, MAX_PRICE = 100, 1_000_000   # ยอดดีลขั้นต่ำ 100 บาท (ยืนยันโดยเจ้าของ ต.ค. 2569)
PAYOUT_FEE, PAYOUT_FREE_FROM = 30, 1000  # ค่าโอนออก 30 บาท/วัน (ผู้ขายจ่าย หักจากยอดรวมโอนรายวัน) ฟรีเมื่อยอดรวม ≥ 1,000 บาท
CANCEL_RATE, CANCEL_MIN = 0.02, 10       # ผู้ซื้อยกเลิกเอง: ค่าดำเนินการ 2% ของยอดที่จ่าย ขั้นต่ำ 10 บาท
PENALTY_FLAG_N, PENALTY_FLAG_DAYS = 3, 30  # ผู้ขายโดนค่าปรับ ≥3 ครั้งใน 30 วัน → แจ้งเตือนแอดมิน
LOST_FLAG_N, LOST_FLAG_DAYS = 3, 90        # ผู้ซื้อแพ้ข้อพิพาท ≥3 ครั้งใน 90 วัน → เสนอระงับบัญชีในหน้าแอดมิน
ID_REQUIRED_OVER = 3000
NEW_LIMIT = 5000
LEVELS = [  # key, name, min deals, min stars, max dispute rate, limit/deal
    ('gold', 'Gold', 100, 4.7, 0.02, 50000),
    ('silver', 'Silver', 20, 4.5, 0.05, 20000),
]
PARCEL_TRANSIT = 2 * DAY      # จำลอง: ขนส่งแจ้งของถึงหลังส่ง 2 วัน
PARCEL_RELEASE = 3 * DAY      # ปล่อยเงินอัตโนมัติ 3 วันหลังของถึง
MESSENGER_RELEASE = 1 * DAY   # แมสเซนเจอร์ 24 ชม.
DISPUTE_WINDOW = 3 * DAY
MAX_BODY = 60 * 1024 * 1024
MAX_FILE = 25 * 1024 * 1024     # รูป
MAX_VIDEO = 30 * 1024 * 1024    # คลิป (~60 วินาที) · mp4 / webm / mov
DELIVERIES = ('parcel', 'meet', 'messenger')
FEE_PAYERS = ('buyer', 'seller', 'half')
CARRIERS = ('Kerry Express', 'Flash Express', 'ไปรษณีย์ไทย (EMS)', 'J&T Express', 'อื่น ๆ')
DISPUTE_REASONS = ('ของไม่ตรงปก', 'ของเสียหาย', 'ไม่ได้รับของ', 'ได้ไม่ครบ', 'อื่น ๆ')
ACTIVE = ('open', 'accepted', 'held', 'shipped', 'delivered', 'disputed')
# ---- ดีลที่พัก (accommodation) ----
STAY_RELEASE = 1 * DAY        # ปล่อยเงินอัตโนมัติ 24 ชม. หลังเวลาเช็คอิน (ถ้าผู้เข้าพักไม่ยืนยัน/ไม่แจ้งปัญหา)
STAY_REASONS = ('ไม่มีที่พักจริง', 'ที่พักไม่ตรงปก', 'เข้าพักไม่ได้', 'อื่น ๆ')
LATE_CANCEL_REASON = 'ขอยกเลิกหลังหมดเวลายกเลิกฟรี'
MAP_RX = re.compile(r'^https?://([\w-]+\.)*(google\.[a-z.]+/maps|maps\.google\.[a-z.]+|maps\.app\.goo\.gl|goo\.gl/maps)', re.I)

os.makedirs(UPLOADS, exist_ok=True)
LOCK = threading.RLock()
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
db.execute('PRAGMA journal_mode=WAL')
db.execute('PRAGMA foreign_keys=ON')

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL, created_at REAL NOT NULL,
  id_verified INTEGER DEFAULT 0, id_doc TEXT, id_verified_at REAL,
  shop_name TEXT, shop_bio TEXT, is_demo INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS otps(phone TEXT PRIMARY KEY, name TEXT, code TEXT, expires REAL, tries INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, created_at REAL);
CREATE TABLE IF NOT EXISTS admin_sessions(token TEXT PRIMARY KEY, created_at REAL);
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT, description TEXT, price REAL,
  photos TEXT DEFAULT '[]', deliveries TEXT DEFAULT '["parcel"]', fee_payer TEXT DEFAULT 'half',
  ship_days INTEGER DEFAULT 3, active INTEGER DEFAULT 1, created_at REAL);
CREATE TABLE IF NOT EXISTS deals(
  id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, creator_id INTEGER, creator_role TEXT,
  seller_id INTEGER, buyer_id INTEGER, product_id INTEGER, source TEXT DEFAULT 'link',
  title TEXT, description TEXT, price REAL, photos TEXT DEFAULT '[]', delivery TEXT, due_date TEXT,
  fee_payer TEXT, fee REAL, buyer_fee REAL, seller_fee REAL, buyer_pay REAL, seller_get REAL,
  status TEXT, meet_code TEXT, meet_tries INTEGER DEFAULT 0, tracking TEXT, carrier TEXT,
  proof_text TEXT, proof_photos TEXT DEFAULT '[]', on_time INTEGER, skew REAL DEFAULT 0,
  created_at REAL, accepted_at REAL, paid_at REAL, shipped_at REAL, delivered_at REAL,
  completed_at REAL, refunded_at REAL, cancelled_at REAL, release_reason TEXT, auto_release_at REAL,
  dispute_reason TEXT, dispute_detail TEXT, dispute_files TEXT DEFAULT '[]', disputed_at REAL,
  resolution TEXT, resolution_note TEXT, refund_amount REAL, payout_amount REAL, is_demo INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS payouts(
  id INTEGER PRIMARY KEY, user_id INTEGER, deal_id INTEGER, amount REAL, status TEXT DEFAULT 'pending',
  created_at REAL, paid_at REAL);
CREATE TABLE IF NOT EXISTS records(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, deal_id INTEGER, kind TEXT NOT NULL, amount REAL DEFAULT 0,
  deducted REAL DEFAULT 0, reason TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS payout_batches(
  id INTEGER PRIMARY KEY, user_id INTEGER, gross REAL, transfer_fee REAL, penalty REAL, net REAL, n INTEGER, created_at REAL);
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY, deal_id INTEGER, from_id INTEGER, to_id INTEGER, target_role TEXT,
  stars INTEGER, text TEXT, created_at REAL, UNIQUE(deal_id, from_id));
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY, user_id INTEGER, deal_code TEXT, text TEXT, icon TEXT DEFAULT 'info',
  read INTEGER DEFAULT 0, created_at REAL);
CREATE TABLE IF NOT EXISTS threads(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, deal_id INTEGER, user_a INTEGER, user_b INTEGER,
  created_at REAL, last_at REAL);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL, sender_id INTEGER, is_admin INTEGER DEFAULT 0,
  text TEXT, photos TEXT DEFAULT '[]', created_at REAL);
CREATE TABLE IF NOT EXISTS thread_reads(thread_id INTEGER, user_id INTEGER, last_read_id INTEGER DEFAULT 0,
  PRIMARY KEY(thread_id, user_id));
CREATE INDEX IF NOT EXISTS ix_threads_a ON threads(user_a);
CREATE INDEX IF NOT EXISTS ix_threads_b ON threads(user_b);
CREATE INDEX IF NOT EXISTS ix_threads_deal ON threads(deal_id, kind);
CREATE INDEX IF NOT EXISTS ix_msg_thread ON messages(thread_id, id);
CREATE INDEX IF NOT EXISTS ix_deals_seller ON deals(seller_id);
CREATE INDEX IF NOT EXISTS ix_deals_buyer ON deals(buyer_id);
CREATE INDEX IF NOT EXISTS ix_notif_user ON notifications(user_id, read);
"""
db.executescript(SCHEMA)


def _migrate():
    """เพิ่มคอลัมน์ใหม่ให้ฐานข้อมูลเดิม (ไม่ลบข้อมูล)"""
    cols = (('users', 'avatar', 'TEXT'), ('notifications', 'link', 'TEXT'),
            ('deals', 'kind', "TEXT DEFAULT 'goods'"), ('deals', 'address', 'TEXT'), ('deals', 'map_url', 'TEXT'),
            ('deals', 'checkin_at', 'REAL'), ('deals', 'checkout_date', 'TEXT'), ('deals', 'nights', 'INTEGER'),
            ('deals', 'guests', 'INTEGER'), ('deals', 'host_contact', 'TEXT'), ('deals', 'free_cancel_days', 'INTEGER'),
            ('deals', 'dispute_location', 'TEXT'),
            ('products', 'kind', "TEXT DEFAULT 'goods'"), ('products', 'address', 'TEXT'), ('products', 'map_url', 'TEXT'),
            ('products', 'checkin_time', 'TEXT'), ('products', 'max_guests', 'INTEGER'), ('products', 'free_cancel_days', 'INTEGER'),
            ('products', 'host_contact', 'TEXT'),
            ('users', 'socials', "TEXT DEFAULT '{}'"), ('reviews', 'photos', "TEXT DEFAULT '[]'"),
            ('deals', 'cancel_charge', 'REAL'), ('deals', 'fee_charged', 'REAL'), ('deals', 'penalty', 'REAL'), ('deals', 'fault', 'TEXT'),
            ('payouts', 'batch_id', 'INTEGER'),
            ('deals', 'pack_video', 'TEXT'), ('deals', 'unbox_video', 'TEXT'), ('deals', 'unbox_requested_at', 'REAL'), ('deals', 'pack_requested_at', 'REAL'))
    for table, col, typ in cols:
        if col not in [r[1] for r in db.execute(f'PRAGMA table_info({table})')]:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {col} {typ}')
    db.commit()


_migrate()


class ApiError(Exception):
    def __init__(self, msg, status=400, field=None):
        super().__init__(msg)
        self.status = status
        self.field = field


def q(sql, a=()): return db.execute(sql, a).fetchall()
def q1(sql, a=()): return db.execute(sql, a).fetchone()
def ex(sql, a=()): return db.execute(sql, a).lastrowid
def now(): return time.time()
def money(x): return round(float(x) + 1e-9, 2)
def jl(s):
    try: return json.loads(s or '[]')
    except Exception: return []


def calc_fee(price, payer):
    fee = money(max(FEE_MIN, price * FEE_RATE))
    if payer == 'buyer': bf, sf = fee, 0.0
    elif payer == 'seller': bf, sf = 0.0, fee
    else:
        bf = money(fee / 2); sf = money(fee - bf)
    return dict(fee=fee, buyer_fee=bf, seller_fee=sf, buyer_pay=money(price + bf), seller_get=money(price - sf))


def cancel_charge(paid):
    """ค่าดำเนินการเมื่อผู้ซื้อยกเลิกเอง: 2% ของยอดที่จ่าย ขั้นต่ำ 10 บาท (ไม่เกินยอดที่จ่าย)"""
    return money(min(paid, max(CANCEL_MIN, paid * CANCEL_RATE)))


def partial_split(buyer_pay, refund):
    """คืนบางส่วน: ค่าธรรมเนียมคิดจากยอดที่ผู้ขายได้จริงเท่านั้น (2% ขั้นต่ำ 20 บาท)"""
    kept = money(buyer_pay - refund)
    fee = money(min(kept, max(FEE_MIN, kept * FEE_RATE)))
    return dict(kept=kept, fee=fee, pay=money(kept - fee))


def payout_calc(gross, owed):
    """รอบโอนรายวัน: ยอดรวม − ค่าโอนออก (ฟรีเมื่อ ≥ 1,000) − ค่าปรับค้าง (หักได้ไม่เกินยอดที่เหลือ)"""
    gross = money(gross)
    fee = 0.0 if gross >= PAYOUT_FREE_FROM else float(PAYOUT_FEE)
    if gross <= 0 or (fee and gross <= fee):
        return dict(gross=gross, transfer_fee=fee, penalty=0.0, net=0.0, rollover=gross > 0)
    ded = money(min(owed, gross - fee))
    return dict(gross=gross, transfer_fee=fee, penalty=ded, net=money(gross - fee - ded), rollover=False)


def penalty_owed(uid):
    r = q1("SELECT COALESCE(SUM(amount - deducted),0) s FROM records WHERE user_id=? AND kind='penalty'", (uid,))
    return money(r['s'])


def due_ts(due_date):
    y, m, d = map(int, due_date.split('-'))
    return datetime(y, m, d, 23, 59, 59, tzinfo=TZ).timestamp()


def today_str(ts=None):
    return datetime.fromtimestamp(ts or now(), TZ).strftime('%Y-%m-%d')


def is_stay(d): return (d['kind'] or 'goods') == 'stay'


def day_start(ts):
    dt = datetime.fromtimestamp(ts, TZ)
    return datetime(dt.year, dt.month, dt.day, tzinfo=TZ).timestamp()


def parse_date(v, msg):
    v = s_(v, 10)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v): raise ApiError(msg)
    try: datetime.strptime(v, '%Y-%m-%d')
    except ValueError: raise ApiError(msg)
    return v


def checkin_ts(date, hm):
    y, m, d = map(int, date.split('-')); hh, mm = map(int, hm.split(':'))
    return datetime(y, m, d, hh, mm, tzinfo=TZ).timestamp()


def stay_common(b):
    """ข้อมูลที่พักที่ใช้ร่วมกันทั้งดีลและสินค้าในร้าน"""
    title = s_(b.get('title'), 120)
    if not title: raise ApiError('กรุณากรอกชื่อที่พัก')
    address = s_(b.get('address'), 300)
    if not address: raise ApiError('กรุณากรอกที่อยู่ที่พัก')
    map_url = s_(b.get('map_url'), 500)
    if not MAP_RX.match(map_url): raise ApiError('กรุณาใส่ลิงก์ Google Maps ของที่พัก (เช่น https://maps.app.goo.gl/…)')
    host = s_(b.get('host_contact'), 60)
    if not host: raise ApiError('กรุณากรอกชื่อผู้ติดต่อของที่พัก')
    try: fcd = int(b.get('free_cancel_days') if b.get('free_cancel_days') not in (None, '') else 3)
    except Exception: raise ApiError('จำนวนวันยกเลิกฟรีไม่ถูกต้อง')
    if not 0 <= fcd <= 30: raise ApiError('ยกเลิกฟรีได้ 0–30 วันก่อนเช็คอิน')
    return dict(title=title, address=address, map_url=map_url, host_contact=host, free_cancel_days=fcd)


def stay_dates(b, max_guests=30):
    cin = parse_date(b.get('checkin_date'), 'กรุณาเลือกวันเช็คอิน')
    hm = s_(b.get('checkin_time'), 5) or '14:00'
    if not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', hm): raise ApiError('เวลาเช็คอินไม่ถูกต้อง (เช่น 14:00)')
    if b.get('nights') not in (None, '') and not b.get('checkout_date'):
        try: n = int(b.get('nights'))
        except Exception: raise ApiError('จำนวนคืนไม่ถูกต้อง')
        cout = (datetime.strptime(cin, '%Y-%m-%d') + timedelta(days=n)).strftime('%Y-%m-%d')
    else:
        cout = parse_date(b.get('checkout_date'), 'กรุณาเลือกวันเช็คเอาต์')
    nights = (datetime.strptime(cout, '%Y-%m-%d') - datetime.strptime(cin, '%Y-%m-%d')).days
    if nights < 1: raise ApiError('วันเช็คเอาต์ต้องหลังวันเช็คอินอย่างน้อย 1 คืน')
    if nights > 60: raise ApiError('จองได้สูงสุด 60 คืนต่อดีล')
    ts = checkin_ts(cin, hm)
    if ts <= now(): raise ApiError('เวลาเช็คอินต้องเป็นเวลาในอนาคต')
    try: guests = int(b.get('guests')) if b.get('guests') not in (None, '') else 1
    except Exception: raise ApiError('จำนวนผู้เข้าพักไม่ถูกต้อง')
    if not 1 <= guests <= max_guests: raise ApiError(f'จำนวนผู้เข้าพักต้องอยู่ระหว่าง 1–{max_guests} คน')
    return dict(checkin_date=cin, checkin_time=hm, checkout_date=cout, nights=nights, checkin_at=ts, guests=guests)


def new_code():
    alpha = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    while True:
        c = 'DS-' + ''.join(random.choice(alpha) for _ in range(6))
        if not q1('SELECT 1 FROM deals WHERE code=?', (c,)): return c


def notify(uid, code, text, icon='info', link=None):
    if not uid: return
    if link:  # แชท: รวมเป็นแจ้งเตือนเดียวต่อห้องแชท จนกว่าจะอ่าน (ไม่ให้กระดิ่งรก)
        old = q1('SELECT id FROM notifications WHERE user_id=? AND link=? AND read=0', (uid, link))
        if old:
            ex('UPDATE notifications SET text=?, icon=?, created_at=? WHERE id=?', (text, icon, now(), old['id']))
            return
    ex('INSERT INTO notifications(user_id,deal_code,text,icon,created_at,link) VALUES(?,?,?,?,?,?)', (uid, code, text, icon, now(), link))


def fmt_baht(x):
    x = money(x)
    return (f'{x:,.0f}' if x == int(x) else f'{x:,.2f}') + ' ฿'


# ---------------- files ----------------
MIME_EXT = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif',
            'video/mp4': '.mp4', 'video/webm': '.webm', 'video/quicktime': '.mov'}


def save_files(items, allow=('image',), max_n=6):
    out = []
    for s in (items or [])[:max_n]:
        if not isinstance(s, str): continue
        # ใช้รูปจากสินค้าขายประจำ / อัปโหลดเดิมได้เลย (ไม่ต้องแปลงเป็น data URL ใหม่)
        if s.startswith('/uploads/') or s.startswith('/static/'):
            if '..' in s or '\0' in s or not re.fullmatch(r'/(?:uploads|static)/[\w./-]+', s):
                raise ApiError('ไฟล์ไม่ถูกต้อง')
            out.append(s); continue
        m = re.match(r'^data:([\w/+.-]+);base64,(.*)$', s, re.S)
        if not m: raise ApiError('ไฟล์ไม่ถูกต้อง')
        mime = m.group(1).lower()
        if mime not in MIME_EXT or mime.split('/')[0] not in allow:
            raise ApiError('รองรับเฉพาะไฟล์รูป' + (' หรือวิดีโอ (mp4 / webm / mov)' if 'video' in allow else ''))
        raw = base64.b64decode(m.group(2))
        if mime.startswith('video/'):
            if len(raw) > MAX_VIDEO: raise ApiError('คลิปใหญ่เกินไป (สูงสุด 30 MB หรือประมาณ 1 นาที) ลองตัดให้สั้นลงหรือลดความละเอียด')
        elif len(raw) > MAX_FILE: raise ApiError('ไฟล์ใหญ่เกินไป (สูงสุด 25 MB)')
        name = secrets.token_hex(12) + MIME_EXT[mime]
        with open(os.path.join(UPLOADS, name), 'wb') as f: f.write(raw)
        out.append('/uploads/' + name)
    return out


def save_video(item):
    """คลิปเดียว (ไม่บังคับ) → path หรือ None"""
    if not item: return None
    f = save_files([item], allow=('video',), max_n=1)
    return f[0] if f else None


# ---------------- users & stats ----------------
def initial(name):
    name = re.sub(r'^(ร้าน|คุณ|น้อง|พี่)\s*', '', name or '?') or name or '?'
    for ch in name:
        if ch not in 'เแโใไ ': return ch
    return '?'


# ---------------- ช่องทางโซเชียล (ผู้ใช้กรอกเอง · ยังไม่ตรวจสอบ เว้นแต่ทีมงานกดยืนยัน) ----------------
SOCIAL_KEYS = ('facebook', 'line', 'instagram', 'tiktok', 'youtube', 'website', 'phone')
SOCIAL_LABEL = {'facebook': 'Facebook', 'line': 'LINE', 'instagram': 'Instagram', 'tiktok': 'TikTok', 'youtube': 'YouTube',
                'website': 'เว็บไซต์', 'phone': 'เบอร์โทร'}
SOCIAL_HOSTS = {
    'facebook': ('facebook.com', 'm.facebook.com', 'web.facebook.com', 'mbasic.facebook.com', 'fb.com', 'fb.me'),
    'line': ('line.me', 'lin.ee', 'page.line.me'),
    'instagram': ('instagram.com', 'instagr.am'),
    'tiktok': ('tiktok.com', 'm.tiktok.com', 'vt.tiktok.com', 'vm.tiktok.com'),
    'youtube': ('youtube.com', 'm.youtube.com', 'youtu.be'),
}
SOCIAL_HINT = {
    'facebook': 'ใส่ชื่อผู้ใช้ เช่น padaeng.shop หรือวางลิงก์เพจ/โปรไฟล์ facebook.com/…',
    'line': 'ใส่ LINE ID เช่น padaeng99 หรือ @padaengshop (LINE OA) หรือวางลิงก์ line.me/… / lin.ee/…',
    'instagram': 'ใส่ชื่อผู้ใช้ เช่น @padaeng.shop หรือวางลิงก์ instagram.com/…',
    'tiktok': 'ใส่ชื่อผู้ใช้ เช่น @padaeng.shop หรือวางลิงก์ tiktok.com/@…',
    'youtube': 'ใส่ชื่อช่อง เช่น @padaengchannel หรือวางลิงก์ youtube.com/…',
    'website': 'ใส่ลิงก์เว็บไซต์ เช่น https://ร้านของคุณ.com',
    'phone': 'ใส่เบอร์โทรไทย 9–10 หลัก เช่น 081-234-5678',
}
_URLISH = re.compile(r'^(https?://|www\.)|^[\w-]+(\.[\w-]+)+/', re.I)


def _host(s):
    """แยก (host, path, query) จากลิงก์ – ถ้าไม่มี http(s):// เติมให้ · ห้ามสคีมอื่น (javascript: ฯลฯ)"""
    if re.match(r'^[a-z][a-z0-9+.-]*:', s, re.I) and not re.match(r'^https?://', s, re.I): return None
    u = urlparse(s if re.match(r'^https?://', s, re.I) else 'https://' + s)
    host = (u.hostname or '').lower()
    if host.startswith('www.'): host = host[4:]
    if not host or ' ' in s: return None
    return host, u.path or '', u.query or ''


def norm_social(key, raw):
    """ตรวจ + แปลงค่าเป็นรูปแบบมาตรฐาน → dict(h=ที่แสดง, u=ลิงก์ที่เปิด, e=ค่าในช่องแก้ไข) · ค่าว่าง = None (ลบ)"""
    v = s_(raw, 300).strip()
    if not v: return None
    bad = lambda: ApiError(f'{SOCIAL_LABEL[key]}: รูปแบบไม่ถูกต้อง – {SOCIAL_HINT[key]}', 400, key)
    if key == 'phone':
        d = re.sub(r'[\s().-]', '', v)
        if d.startswith('+66'): d = '0' + d[3:]
        elif d.startswith('66') and len(d) in (11, 12): d = '0' + d[2:]
        if not re.fullmatch(r'0\d{8,9}', d): raise bad()
        h = f'{d[:3]}-{d[3:6]}-{d[6:]}' if len(d) == 10 else f'{d[:2]}-{d[2:5]}-{d[5:]}'
        return dict(h=h, u='tel:+66' + d[1:], e=h)
    if key == 'website':
        hp = _host(v)
        if not hp or not re.fullmatch(r'([a-z0-9\u0e00-\u0e7f-]+\.)+[a-z\u0e00-\u0e7f]{2,}', hp[0]): raise bad()
        for k, hosts in SOCIAL_HOSTS.items():
            if hp[0] in hosts: raise ApiError(f'เว็บไซต์: ลิงก์นี้เป็น {SOCIAL_LABEL[k]} ใส่ในช่อง {SOCIAL_LABEL[k]} แทนนะคะ', 400, key)
        url = v if re.match(r'^https?://', v, re.I) else 'https://' + v
        return dict(h=hp[0] + (hp[1].rstrip('/') if 1 < len(hp[1]) <= 20 else ''), u=url[:300], e=url[:300])
    hosts = SOCIAL_HOSTS[key]
    is_url = bool(_URLISH.match(v)) or any(v.lower().split('/')[0].removeprefix('www.') == h for h in hosts)
    if is_url:
        hp = _host(v)
        if not hp or hp[0] not in hosts: raise bad()
        host, path, query = hp
        segs = [x for x in path.split('/') if x]
        if not segs and not (key == 'facebook' and 'id=' in query): raise bad()
        if key == 'facebook':
            if segs and segs[0] == 'profile.php':
                m = re.search(r'(?:^|&)id=(\d{5,20})', query)
                if not m: raise bad()
                return dict(h='โปรไฟล์ Facebook', u=f'https://www.facebook.com/profile.php?id={m.group(1)}', e=f'https://www.facebook.com/profile.php?id={m.group(1)}')
            if segs[0] in ('groups', 'people', 'pages', 'share', 'p'):
                url = 'https://www.facebook.com/' + '/'.join(segs)
                return dict(h='กลุ่ม Facebook' if segs[0] == 'groups' else 'เพจ Facebook', u=url, e=url)
            h = segs[0]
            if not re.fullmatch(r'[A-Za-z0-9.\-]{2,80}', h): raise bad()
            return dict(h=h, u=f'https://www.facebook.com/{h}', e=h)
        if key == 'line':
            if host == 'lin.ee':
                url = 'https://lin.ee/' + '/'.join(segs); return dict(h='LINE OA', u=url, e=url)
            m = re.fullmatch(r'/(?:R/)?ti/p/(~|@|%40)?([A-Za-z0-9._-]{3,30})/?', path)
            if not m: raise bad()
            if m.group(1) in ('@', '%40'):
                h = m.group(2).lower(); return dict(h='@' + h, u=f'https://line.me/R/ti/p/@{h}', e='@' + h)
            if m.group(1) == '~':
                h = m.group(2).lower(); return dict(h=h, u=f'https://line.me/ti/p/~{h}', e=h)
            url = 'https://line.me' + path; return dict(h='LINE', u=url, e=url)  # ลิงก์เชิญเพื่อนแบบสุ่ม
        if key == 'instagram':
            h = segs[0]
            if not re.fullmatch(r'[A-Za-z0-9._]{1,30}', h) or h in ('p', 'reel', 'explore', 'stories'): raise bad()
            return dict(h='@' + h.lower(), u=f'https://www.instagram.com/{h.lower()}/', e='@' + h.lower())
        if key == 'tiktok':
            if host in ('vt.tiktok.com', 'vm.tiktok.com'):
                url = f'https://{host}/' + segs[0] + '/'; return dict(h='TikTok', u=url, e=url)
            if not segs[0].startswith('@') or not re.fullmatch(r'@[A-Za-z0-9._]{2,24}', segs[0]): raise bad()
            h = segs[0][1:].lower(); return dict(h='@' + h, u=f'https://www.tiktok.com/@{h}', e='@' + h)
        if key == 'youtube':
            if host == 'youtu.be': raise ApiError('YouTube: นี่คือลิงก์วิดีโอ ใส่ลิงก์หรือชื่อช่องแทน เช่น @padaengchannel', 400, key)
            if segs[0].startswith('@') and re.fullmatch(r'@[A-Za-z0-9._-]{3,30}', segs[0]):
                h = segs[0]; return dict(h=h, u=f'https://www.youtube.com/{h}', e=h)
            if segs[0] in ('channel', 'c', 'user') and len(segs) > 1 and re.fullmatch(r'[A-Za-z0-9._-]{2,60}', segs[1]):
                url = f'https://www.youtube.com/{segs[0]}/{segs[1]}'
                return dict(h='ช่อง YouTube' if segs[0] == 'channel' else segs[1], u=url, e=url)
            raise bad()
    # ไม่ใช่ลิงก์ → ชื่อผู้ใช้ / ID
    if key == 'facebook':
        h = v.lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9.]{5,50}', h): raise bad()
        return dict(h=h, u=f'https://www.facebook.com/{h}', e=h)
    if key == 'line':
        if v.startswith('@'):
            h = v[1:].strip().lower()
            if not re.fullmatch(r'[a-z0-9._-]{3,20}', h): raise bad()
            return dict(h='@' + h, u=f'https://line.me/R/ti/p/@{h}', e='@' + h)
        h = v.lower()
        if not re.fullmatch(r'[a-z0-9._-]{4,20}', h): raise bad()
        return dict(h=h, u=f'https://line.me/ti/p/~{h}', e=h)
    if key == 'instagram':
        h = v.lstrip('@').lower()
        if not re.fullmatch(r'[a-z0-9._]{1,30}', h) or h.startswith('.') or h.endswith('.'): raise bad()
        return dict(h='@' + h, u=f'https://www.instagram.com/{h}/', e='@' + h)
    if key == 'tiktok':
        h = v.lstrip('@').lower()
        if not re.fullmatch(r'[a-z0-9._]{2,24}', h): raise bad()
        return dict(h='@' + h, u=f'https://www.tiktok.com/@{h}', e='@' + h)
    if key == 'youtube':
        h = v.lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9._-]{3,30}', h): raise bad()
        return dict(h='@' + h, u=f'https://www.youtube.com/@{h}', e='@' + h)
    raise bad()


def socials_raw(u):
    try: d = json.loads(u['socials'] or '{}')
    except Exception: d = {}
    return d if isinstance(d, dict) else {}


def socials_view(u):
    d = socials_raw(u)
    return [dict(key=k, label=SOCIAL_LABEL[k], h=d[k]['h'], url=d[k]['u'], edit=d[k].get('e', d[k]['h']), verified=bool(d[k].get('verified')))
            for k in SOCIAL_KEYS if isinstance(d.get(k), dict) and d[k].get('u')]


def user_stats(uid):
    r = q1("""SELECT
      COALESCE(SUM(seller_id=:u AND status IN ('completed','partial')),0) sales,
      COALESCE(SUM(buyer_id=:u AND status IN ('completed','partial')),0) buys,
      COALESCE(SUM(seller_id=:u AND paid_at IS NOT NULL),0) seller_paid,
      COALESCE(SUM(seller_id=:u AND disputed_at IS NOT NULL),0) seller_disputes,
      COALESCE(SUM(seller_id=:u AND on_time IS NOT NULL),0) shipped_n,
      COALESCE(SUM(seller_id=:u AND on_time=1),0) on_time_n,
      COALESCE(SUM(seller_id=:u AND kind='stay' AND status IN ('completed','partial')),0) stays
      FROM deals WHERE seller_id=:u OR buyer_id=:u""", {'u': uid})
    rs = q1("SELECT COUNT(*) n, AVG(stars) a FROM reviews WHERE to_id=? AND target_role='seller'", (uid,))
    rb = q1("SELECT COUNT(*) n, AVG(stars) a FROM reviews WHERE to_id=? AND target_role='buyer'", (uid,))
    dist = {i: 0 for i in range(1, 6)}
    for row in q("SELECT stars, COUNT(*) n FROM reviews WHERE to_id=? AND target_role='seller' GROUP BY stars", (uid,)):
        dist[row['stars']] = row['n']
    sales, buys = r['sales'], r['buys']
    disp_rate = (r['seller_disputes'] / r['seller_paid']) if r['seller_paid'] else 0.0
    rating = round(rs['a'], 2) if rs['n'] else None
    level, level_name, limit = 'new', 'Bronze', NEW_LIMIT
    for key, nm, mn, ms, md, lim in LEVELS:
        if sales >= mn and rating is not None and rating >= ms and disp_rate <= md:
            level, level_name, limit = key, nm, lim
            break
    buyer_limit = NEW_LIMIT if (sales + buys) < 5 else 50000
    return dict(sales=sales, buys=buys, total=sales + buys, rating=rating, reviews=rs['n'], rating_dist=dist,
                buyer_rating=round(rb['a'], 2) if rb['n'] else None, buyer_reviews=rb['n'],
                dispute_rate=round(disp_rate * 100, 1), disputes=r['seller_disputes'],
                on_time_rate=round(100 * r['on_time_n'] / r['shipped_n']) if r['shipped_n'] else None,
                level=level, level_name=level_name, seller_limit=limit, buyer_limit=buyer_limit, stays_hosted=r['stays'])


def public_user(u, stats=True):
    if not u: return None
    d = dict(id=u['id'], name=u['name'], shop_name=u['shop_name'] or u['name'], shop_bio=u['shop_bio'] or '',
             initial=initial(u['shop_name'] or u['name']), verified=bool(u['id_verified']), avatar=u['avatar'] or None,
             member_since=u['created_at'], is_demo=bool(u['is_demo']), socials=socials_view(u))
    if stats: d['stats'] = user_stats(u['id'])
    return d


def get_user(uid): return q1('SELECT * FROM users WHERE id=?', (uid,)) if uid else None


# ---------------- deals ----------------
def dnow(d): return now() + (d['skew'] or 0)
def get_deal(code): return q1('SELECT * FROM deals WHERE code=?', (code,))


def complete(d, reason, at=None):
    at = at or dnow(d)
    on_time = d['on_time']
    if d['delivery'] == 'meet' and on_time is None:
        on_time = 1 if at <= due_ts(d['due_date']) else 0
    ex("UPDATE deals SET status='completed', completed_at=?, release_reason=?, payout_amount=?, on_time=? WHERE id=?",
       (at, reason, d['seller_get'], on_time, d['id']))
    ex('INSERT INTO payouts(user_id,deal_id,amount,created_at) VALUES(?,?,?,?)', (d['seller_id'], d['id'], d['seller_get'], now()))
    why = {'buyer_confirm': 'ผู้ซื้อยืนยันรับของแล้ว', 'meet_code': 'ยืนยันด้วยรหัสนัดรับแล้ว',
           'guest_checkin': 'ผู้เข้าพักยืนยันเช็คอินแล้ว ที่พักตรงปก', 'checkin_code': 'ผู้เข้าพักกรอกรหัสเช็คอินถูกต้อง',
           'auto': 'ครบกำหนดเวลา ระบบปล่อยเงินอัตโนมัติ', 'admin': 'ทีมงานตัดสินให้ปล่อยเงิน'}.get(reason, '')
    notify(d['seller_id'], d['code'], f'{why} · เงิน {fmt_baht(d["seller_get"])} รอโอนรอบถัดไป (วันละครั้ง)', 'wallet')
    notify(d['buyer_id'], d['code'], f'ดีล "{d["title"]}" สำเร็จแล้ว ' + ('ขอให้พักผ่อนให้สนุก อย่าลืมรีวิวที่พักนะ' if is_stay(d) else 'อย่าลืมให้คะแนนผู้ขายนะ'), 'check')


def refund_seller_fault(d, t, resolution, note=None):
    """ผู้ขาย/เจ้าของที่พักเป็นฝ่ายผิด: คืนผู้ซื้อเต็มจำนวนรวมค่าธรรมเนียม + บันทึกค่าปรับ (= ค่าธรรมเนียมของดีล) หักจากยอดโอนรอบถัดไป"""
    pen = money(d['fee'])
    ex("""UPDATE deals SET status='refunded', refunded_at=?, refund_amount=?, resolution=?, resolution_note=COALESCE(?, resolution_note),
          fault='seller', penalty=?, fee_charged=0, cancel_charge=0 WHERE id=?""", (t, d['buyer_pay'], resolution, note, pen, d['id']))
    ex("INSERT INTO records(user_id,deal_id,kind,amount,reason,created_at) VALUES(?,?,'penalty',?,?,?)", (d['seller_id'], d['id'], pen, resolution, now()))
    notify(d['seller_id'], d['code'], f'ค่าปรับ {fmt_baht(pen)} (เท่าค่าธรรมเนียมดีล "{d["title"]}") จะหักจากยอดโอนรอบถัดไป', 'warn')
    return pen


def refund_buyer_choice(d, t, resolution, note=None):
    """ผู้ซื้อ/ผู้เข้าพักยกเลิกเอง: คืนเงินหักค่าดำเนินการ 2% ของยอดที่จ่าย ขั้นต่ำ 10 บาท"""
    ch = cancel_charge(d['buyer_pay']); back = money(d['buyer_pay'] - ch)
    ex("""UPDATE deals SET status='refunded', refunded_at=?, refund_amount=?, resolution=?, resolution_note=COALESCE(?, resolution_note),
          fault='buyer', cancel_charge=?, fee_charged=0, penalty=0 WHERE id=?""", (t, back, resolution, note, ch, d['id']))
    notify(d['buyer_id'], d['code'], f'คืนเงิน {fmt_baht(back)} ให้คุณแล้ว (จำลอง) · หักค่าดำเนินการ {fmt_baht(ch)}', 'wallet')
    return back, ch


def cancel_preview(d, role, t):
    """ยอดที่จะเกิดขึ้นจริงถ้ากดยกเลิกตอนนี้ (แสดงในหน้ายืนยันก่อนกด)"""
    if not role or d['status'] != 'held': return None
    if is_stay(d):
        if role == 'seller': return dict(type='seller_fault', refund=d['buyer_pay'], penalty=money(d['fee']))
        if t >= d['checkin_at']: return None
        if t <= d['checkin_at'] - (d['free_cancel_days'] or 0) * DAY:
            ch = cancel_charge(d['buyer_pay']); return dict(type='buyer_choice', paid=d['buyer_pay'], charge=ch, refund=money(d['buyer_pay'] - ch))
        return dict(type='staff', paid=d['buyer_pay'])
    if role == 'seller': return dict(type='seller_fault', refund=d['buyer_pay'], penalty=money(d['fee']))
    if t > due_ts(d['due_date']): return dict(type='seller_fault', refund=d['buyer_pay'], penalty=money(d['fee']))
    ch = cancel_charge(d['buyer_pay'])
    return dict(type='buyer_choice', paid=d['buyer_pay'], charge=ch, refund=money(d['buyer_pay'] - ch))


def process(d):
    """apply time-based rules (simulated carrier, auto-release)."""
    if not d: return d
    t = dnow(d)
    if d['status'] == 'shipped' and d['delivery'] == 'parcel' and d['shipped_at'] and t >= d['shipped_at'] + PARCEL_TRANSIT:
        at = d['shipped_at'] + PARCEL_TRANSIT
        ex("UPDATE deals SET status='delivered', delivered_at=?, auto_release_at=? WHERE id=?", (at, at + PARCEL_RELEASE, d['id']))
        notify(d['buyer_id'], d['code'], 'พัสดุถึงแล้ว! ตรวจของแล้วกดยืนยัน หรือแจ้งปัญหาภายใน 3 วัน', 'box')
        notify(d['seller_id'], d['code'], 'ขนส่งแจ้งว่าพัสดุถึงผู้ซื้อแล้ว (จำลอง)', 'truck')
        d = get_deal(d['code'])
    if d['status'] == 'delivered' and d['auto_release_at'] and t >= d['auto_release_at']:
        complete(d, 'auto', at=d['auto_release_at'])
        d = get_deal(d['code'])
    if d['status'] == 'held' and is_stay(d) and d['auto_release_at'] and t >= d['auto_release_at']:
        complete(d, 'auto', at=d['auto_release_at'])  # ผู้เข้าพักไม่ยืนยัน/ไม่แจ้งปัญหาภายใน 24 ชม. หลังเวลาเช็คอิน
        d = get_deal(d['code'])
    return d


def process_all():
    with LOCK:
        for d in q("SELECT * FROM deals WHERE status IN ('shipped','delivered') OR (status='held' AND kind='stay')"):
            process(d)
        db.commit()


def deal_view(d, me):
    d = process(d)
    uid = me['id'] if me else None
    role = 'seller' if uid and uid == d['seller_id'] else 'buyer' if uid and uid == d['buyer_id'] else None
    party = role is not None
    t = dnow(d)
    st = d['status']
    if not party and st != 'open':
        raise ApiError('ดีลนี้มีผู้ซื้อและผู้ขายครบแล้ว เฉพาะคู่ดีลเท่านั้นที่ดูรายละเอียดได้', 403)
    acts = []
    stay = is_stay(d)
    overdue = (not stay) and t > due_ts(d['due_date'])
    dispute_until = None
    if st == 'delivered' and d['delivered_at']:
        dispute_until = min(d['delivered_at'] + DISPUTE_WINDOW, d['auto_release_at'] or 1e18)
    if st == 'open':
        if party and d['creator_id'] == uid: acts.append('cancel')
        elif not party: acts.append('accept')
    elif st == 'accepted':
        if role == 'buyer': acts += ['pay', 'cancel']
        elif role == 'seller': acts.append('cancel')
    elif st == 'held' and stay:
        cin = d['checkin_at']
        if role == 'seller': acts += ['checkin_show', 'host_cancel']
        if role == 'buyer':
            if t >= day_start(cin): acts += ['checkin_confirm', 'checkin_enter']
            if t >= cin: acts.append('stay_problem')
            else: acts.append('guest_cancel')
    elif st == 'held':
        if role == 'seller':
            acts.append({'parcel': 'ship_parcel', 'messenger': 'ship_messenger', 'meet': 'meet_show'}[d['delivery']])
            acts.append('seller_cancel')
        if role == 'buyer':
            if d['delivery'] == 'meet': acts.append('meet_enter')
            if overdue: acts.append('late_refund')
            else: acts.append('buyer_cancel')  # ก่อนผู้ขายส่งของ/ส่งมอบเท่านั้น
    elif st == 'shipped':
        if role == 'buyer': acts += ['confirm', 'dispute']
        if party: acts.append('sim_delivered')
    elif st == 'delivered':
        if role == 'buyer':
            acts.append('confirm')
            if dispute_until and t <= dispute_until: acts.append('dispute')
    if st in ('completed', 'partial') and party:
        if not q1('SELECT 1 FROM reviews WHERE deal_id=? AND from_id=?', (d['id'], uid)): acts.append('review')
    if party and st in ('accepted', 'held', 'shipped', 'delivered', 'disputed'): acts.append('skip')
    out = {k: d[k] for k in d.keys() if k not in ('meet_code', 'meet_tries', 'creator_id')}
    for k in ('photos', 'proof_photos', 'dispute_files'): out[k] = jl(d[k])
    if role == 'seller' and (d['delivery'] == 'meet' or stay) and st == 'held': out['meet_code'] = d['meet_code']
    if not party:
        for k in ('dispute_files', 'dispute_detail', 'tracking', 'proof_text', 'proof_photos', 'dispute_location', 'pack_video', 'unbox_video'): out[k] = None
    if stay:
        cin = d['checkin_at']
        fcu = cin - (d['free_cancel_days'] or 0) * DAY
        out.update(checkin_day_start=day_start(cin), free_cancel_until=fcu, free_cancel_now=t <= fcu,
                   release_at=d['auto_release_at'] or cin + STAY_RELEASE)
    if party:
        out['cancel_preview'] = cancel_preview(d, role, t)
        out['buyer_cancel_charge'] = cancel_charge(d['buyer_pay'])
    out['payout_rule'] = dict(fee=PAYOUT_FEE, free_from=PAYOUT_FREE_FROM)
    out.update(my_role=role, actions=acts, deal_now=t, due_ts=due_ts(d['due_date']), overdue=overdue,
               dispute_until=dispute_until, is_creator=bool(uid and d['creator_id'] == uid))
    out['seller'] = public_user(get_user(d['seller_id']))
    out['buyer'] = public_user(get_user(d['buyer_id']))
    out['reviews'] = [dict(dict(r), photos=jl(r['photos'])) for r in q('SELECT from_id,to_id,target_role,stars,text,photos,created_at FROM reviews WHERE deal_id=?', (d['id'],))]
    if party and d['seller_id'] and d['buyer_id']:
        out['chat_thread_id'] = deal_thread(d, 'deal')['id']
        if d['disputed_at']: out['team_thread_id'] = deal_thread(d, 'dispute')['id']
    if role == 'seller':
        p = q1('SELECT status, paid_at FROM payouts WHERE deal_id=?', (d['id'],))
        out['payout'] = dict(p) if p else None
    return out


def require_party(d, me, role=None):
    if not d: raise ApiError('ไม่พบดีลนี้', 404)
    r = 'seller' if me['id'] == d['seller_id'] else 'buyer' if me['id'] == d['buyer_id'] else None
    if not r or (role and r != role):
        raise ApiError({'seller': 'เฉพาะผู้ขายเท่านั้นที่ทำขั้นตอนนี้ได้', 'buyer': 'เฉพาะผู้ซื้อเท่านั้นที่ทำขั้นตอนนี้ได้'}.get(role, 'คุณไม่ได้อยู่ในดีลนี้'), 403)
    return r


def check_limits(user, role, price):
    s = user_stats(user['id'])
    lim = s['seller_limit'] if role == 'seller' else s['buyer_limit']
    if price > lim:
        if role == 'seller':
            raise ApiError(f'วงเงินของร้านระดับ {s["level_name"]} คือ {lim:,} บาท/ดีล — ขายสำเร็จเพิ่มขึ้นเพื่อเลื่อนระดับร้านและปลดล็อกวงเงิน')
        raise ApiError(f'ผู้ใช้ใหม่ซื้อได้สูงสุด {lim:,} บาท/ดีล — ทำดีลสำเร็จครบ 5 ดีลเพื่อปลดล็อกวงเงิน')
    if price > ID_REQUIRED_OVER and not user['id_verified']:
        raise ApiError('ดีลที่เกิน 3,000 บาท ต้องยืนยันตัวตนก่อน', 403)


# ---------------- API ----------------
ROUTES = []
def route(method, pattern, auth=True, admin=False):
    def deco(fn):
        ROUTES.append((method, re.compile('^' + pattern + '$'), fn, auth, admin))
        return fn
    return deco


def s_(v, n=200): return (str(v).strip() if v is not None else '')[:n]


@route('GET', '/api/me', auth=False)
def api_me(req, me, b):
    if not me: return {'user': None}
    u = public_user(me)
    u['phone'] = me['phone']
    u['unread'] = q1('SELECT COUNT(*) n FROM notifications WHERE user_id=? AND read=0', (me['id'],))['n']
    u['chat_unread'] = chat_unread(me['id'])
    return {'user': u}


@route('POST', '/api/login/start', auth=False)
def api_login_start(req, me, b):
    name = s_(b.get('name'), 60)
    phone = re.sub(r'\D', '', s_(b.get('phone'), 20))
    if not name: raise ApiError('กรุณากรอกชื่อ')
    if not re.fullmatch(r'0\d{8,9}', phone): raise ApiError('เบอร์โทรไม่ถูกต้อง (ตัวอย่าง 0812345678)')
    code = f'{random.randint(0, 999999):06d}'
    ex('INSERT OR REPLACE INTO otps(phone,name,code,expires,tries) VALUES(?,?,?,?,0)', (phone, name, code, now() + 600))
    return {'ok': True, 'phone': phone, 'demo_code': code}


@route('POST', '/api/login/verify', auth=False)
def api_login_verify(req, me, b):
    phone = re.sub(r'\D', '', s_(b.get('phone'), 20))
    code = re.sub(r'\D', '', s_(b.get('code'), 10))
    o = q1('SELECT * FROM otps WHERE phone=?', (phone,))
    if not o or o['expires'] < now(): raise ApiError('รหัสหมดอายุ กรุณาขอรหัสใหม่')
    if o['tries'] >= 5: raise ApiError('กรอกผิดหลายครั้งเกินไป กรุณาขอรหัสใหม่')
    if code != o['code']:
        ex('UPDATE otps SET tries=tries+1 WHERE phone=?', (phone,))
        raise ApiError('รหัสไม่ถูกต้อง')
    ex('DELETE FROM otps WHERE phone=?', (phone,))
    u = q1('SELECT * FROM users WHERE phone=?', (phone,))
    if not u:
        uid = ex('INSERT INTO users(name,phone,created_at) VALUES(?,?,?)', (o['name'], phone, now()))
        notify(uid, None, 'ยินดีต้อนรับสู่ดีลชัวร์! ลองสร้างดีลแรกได้เลย (โหมดทดลอง ไม่มีเงินจริง)', 'info')
    else:
        uid = u['id']
    tok = secrets.token_urlsafe(32)
    ex('INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)', (tok, uid, now()))
    req.set_cookie('ds_session', tok)
    return {'ok': True}


@route('POST', '/api/logout', auth=False)
def api_logout(req, me, b):
    tok = req.cookie('ds_session')
    if tok: ex('DELETE FROM sessions WHERE token=?', (tok,))
    req.set_cookie('ds_session', '', clear=True)
    return {'ok': True}


@route('POST', '/api/me/update')
def api_me_update(req, me, b):
    name = s_(b.get('name'), 60) or me['name']
    shop = s_(b.get('shop_name'), 60) or None
    bio = s_(b.get('shop_bio'), 200) or None
    ex('UPDATE users SET name=?, shop_name=?, shop_bio=? WHERE id=?', (name, shop, bio, me['id']))
    return {'ok': True}


@route('POST', '/api/me/socials')
def api_me_socials(req, me, b):
    """บันทึกช่องทางโซเชียล: ส่งเฉพาะช่องที่ต้องการแก้ (ค่าว่าง = ลบ) · ตรวจทุกช่องก่อนบันทึก (ผิดช่องเดียว = ไม่บันทึกเลย)
    ถ้าแก้ค่า ป้าย "ยืนยันแล้ว" ของช่องนั้นจะหายไป (ต้องให้ทีมงานตรวจใหม่)"""
    cur = socials_raw(me); out = dict(cur)
    for k in SOCIAL_KEYS:
        if k not in b: continue
        n = norm_social(k, b.get(k))
        if n is None: out.pop(k, None); continue
        old = cur.get(k) if isinstance(cur.get(k), dict) else {}
        n['verified'] = bool(old.get('verified')) and old.get('u') == n['u']
        out[k] = n
    ex('UPDATE users SET socials=? WHERE id=?', (json.dumps(out, ensure_ascii=False), me['id']))
    return {'ok': True, 'socials': socials_view(get_user(me['id']))}


@route('POST', '/api/me/verify-id')
def api_verify_id(req, me, b):
    files = save_files([b.get('image')], allow=('image',), max_n=1)
    if not files: raise ApiError('กรุณาแนบรูปบัตร (ทดสอบ)')
    ex('UPDATE users SET id_verified=1, id_doc=?, id_verified_at=? WHERE id=?', (files[0], now(), me['id']))
    notify(me['id'], None, 'ยืนยันตัวตนสำเร็จ (ทดสอบ – อนุมัติอัตโนมัติ)', 'shield')
    return {'ok': True}


@route('POST', '/api/me/avatar')
def api_avatar(req, me, b):
    """เปลี่ยนรูปโปรไฟล์: แอปครอปเป็นสี่เหลี่ยมจัตุรัส (512×512) มาให้แล้ว · remove=true = กลับไปใช้รูปเริ่มต้น"""
    if b.get('remove'):
        ex('UPDATE users SET avatar=NULL WHERE id=?', (me['id'],))
        return {'ok': True, 'avatar': None}
    img = b.get('image')
    if isinstance(img, str) and len(img) > 4 * 1024 * 1024: raise ApiError('รูปใหญ่เกินไป ลองรูปอื่น')
    files = save_files([img], allow=('image',), max_n=1)
    if not files: raise ApiError('กรุณาเลือกรูป')
    ex('UPDATE users SET avatar=? WHERE id=?', (files[0], me['id']))
    return {'ok': True, 'avatar': files[0]}


@route('GET', r'/api/users/(\d+)', auth=False)
def api_user(req, me, b, uid):
    u = get_user(int(uid))
    if not u: raise ApiError('ไม่พบผู้ใช้', 404)
    out = public_user(u)
    rows = q("""SELECT d.code,d.title,d.price,d.status,d.completed_at,d.refunded_at,d.created_at,d.seller_id,d.buyer_id,d.photos
                FROM deals d WHERE (d.seller_id=? OR d.buyer_id=?) AND d.status IN ('completed','partial','refunded')
                ORDER BY COALESCE(d.completed_at,d.refunded_at) DESC LIMIT 100""", (u['id'], u['id']))
    out['history'] = [dict(code=r['code'] if me and me['id'] in (r['seller_id'], r['buyer_id']) else None,
                           title=r['title'], price=r['price'], status=r['status'],
                           at=r['completed_at'] or r['refunded_at'], role='seller' if r['seller_id'] == u['id'] else 'buyer',
                           photo=(jl(r['photos']) or [None])[0]) for r in rows]
    out['reviews'] = review_list(u['id'], None, 20)
    out['reviews_top'] = review_page(u['id'], None)
    out['product_count'] = q1('SELECT COUNT(*) n FROM products WHERE user_id=? AND active=1', (u['id'],))['n']
    return out


def review_list(uid, role, limit):
    sql = """SELECT r.stars,r.text,r.photos,r.created_at,r.target_role,u.name from_name,u.id from_id,u.avatar from_avatar,d.title
             FROM reviews r JOIN users u ON u.id=r.from_id JOIN deals d ON d.id=r.deal_id WHERE r.to_id=?"""
    a = [uid]
    if role: sql += ' AND r.target_role=?'; a.append(role)
    sql += ' ORDER BY r.created_at DESC LIMIT ?'; a.append(limit)
    return [dict(dict(r), photos=jl(r['photos'])) for r in q(sql, a)]


# ---------------- รีวิว: สรุป + เรียง "สำคัญที่สุด" + ตัวกรอง ----------------
REVIEW_FILTERS = ('all', '5', '4', 'low', 'photos', 'goods', 'stay')
REVIEW_SORTS = ('important', 'recent')


def review_score(r, t):
    """คะแนนความสำคัญ: มีรูป · ข้อความยาว · ใหม่ · ดีลมูลค่าสูง"""
    import math
    ph, txt = len(r['photos']), len((r['text'] or '').strip())
    age = max(0.0, (t - r['created_at']) / DAY)
    return ((3 + 0.5 * (ph - 1) if ph else 0) + 3 * min(txt, 200) / 200 - (1 if not txt else 0)
            + 3 * math.exp(-age / 90) + min(2.0, math.log10(max(r['price'] or 0, 100) / 100)))


def review_rows(uid, role):
    sql = """SELECT r.id,r.stars,r.text,r.photos,r.created_at,r.target_role,u.name from_name,u.id from_id,u.avatar from_avatar,
             d.title,d.price,COALESCE(d.kind,'goods') kind,d.is_demo FROM reviews r JOIN users u ON u.id=r.from_id JOIN deals d ON d.id=r.deal_id
             WHERE r.to_id=?""" + (' AND r.target_role=?' if role else '')
    out = []
    for r in q(sql, (uid, role) if role else (uid,)):
        x = dict(r); x['photos'] = jl(r['photos']); x['is_demo'] = bool(r['is_demo']); out.append(x)
    return out


def review_match(r, f):
    return (f == 'all' or (f == '5' and r['stars'] == 5) or (f == '4' and r['stars'] == 4) or (f == 'low' and r['stars'] <= 3)
            or (f == 'photos' and bool(r['photos'])) or (f in ('goods', 'stay') and r['kind'] == f))


def review_page(uid, role, f='all', sort='important', offset=0, limit=3):
    """สรุป (เฉลี่ย · จำนวน · แท่งดาว · จำนวนต่อตัวกรอง) + หน้ารีวิว
    สำคัญที่สุด = เรียงตาม review_score แล้ว "ดัน" รีวิวติชม (1–2 ดาว) ล่าสุดขึ้นใน 3 อันดับแรกเสมอ เพื่อความโปร่งใส"""
    f = f if f in REVIEW_FILTERS else 'all'; sort = sort if sort in REVIEW_SORTS else 'important'
    rows = review_rows(uid, role); t = now()
    dist = {i: 0 for i in range(1, 6)}
    for r in rows: dist[r['stars']] += 1
    n = len(rows)
    summary = dict(count=n, avg=round(sum(r['stars'] for r in rows) / n, 2) if n else None, dist=dist,
                   counts={k: sum(1 for r in rows if review_match(r, k)) for k in REVIEW_FILTERS})
    sel = [r for r in rows if review_match(r, f)]
    for r in sel: r['score'] = round(review_score(r, t), 3); r['pinned'] = False
    sel.sort(key=lambda r: (-r['created_at'], -r['id']))
    if sort == 'important':
        crit = next((r for r in sel if r['stars'] <= 2), None)   # sel เรียงใหม่สุดก่อนอยู่แล้ว
        sel.sort(key=lambda r: (-r['score'], -r['created_at'], -r['id']))
        if crit:
            crit['pinned'] = True
            i = sel.index(crit)
            if i > 2: sel.insert(2, sel.pop(i))
    try: offset = max(0, int(offset)); limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError): offset, limit = 0, 3
    return dict(summary=summary, filter=f, sort=sort, total=len(sel), offset=offset, items=sel[offset:offset + limit],
                has_more=offset + limit < len(sel))


@route('GET', r'/api/users/(\d+)/reviews', auth=False)
def api_user_reviews(req, me, b, uid):
    if not get_user(int(uid)): raise ApiError('ไม่พบผู้ใช้', 404)
    a = qs(req)
    role = a.get('role') if a.get('role') in ('seller', 'buyer') else None
    return review_page(int(uid), role, a.get('filter', 'all'), a.get('sort', 'important'), a.get('offset', 0), a.get('limit', 10))


@route('GET', '/api/deals')
def api_deals(req, me, b):
    for d in q("SELECT * FROM deals WHERE (seller_id=? OR buyer_id=?) AND (status IN ('shipped','delivered') OR (status='held' AND kind='stay'))", (me['id'], me['id'])):
        process(d)
    rows = q("""SELECT d.*, s.name s_name, s.shop_name s_shop, s.avatar s_avatar, bu.name b_name, bu.avatar b_avatar FROM deals d
                LEFT JOIN users s ON s.id=d.seller_id LEFT JOIN users bu ON bu.id=d.buyer_id
                WHERE d.seller_id=? OR d.buyer_id=? OR d.creator_id=? ORDER BY COALESCE(d.paid_at,d.created_at) DESC LIMIT 100""",
             (me['id'], me['id'], me['id']))
    out = []
    for r in rows:
        role = 'seller' if r['seller_id'] == me['id'] else 'buyer'
        other = (r['b_name'] if role == 'seller' else (r['s_shop'] or r['s_name']))
        th = q1("SELECT id FROM threads WHERE deal_id=? AND kind='deal'", (r['id'],))
        out.append(dict(code=r['code'], title=r['title'], price=r['price'], buyer_pay=r['buyer_pay'], status=r['status'],
                        delivery=r['delivery'], role=role, other=other, photo=(jl(r['photos']) or [None])[0],
                        other_avatar=r['b_avatar'] if role == 'seller' else r['s_avatar'],
                        other_initial=initial(other) if other else None,
                        created_at=r['created_at'], updated_at=max(x for x in (r['created_at'], r['accepted_at'], r['paid_at'], r['shipped_at'],
                            r['delivered_at'], r['completed_at'], r['refunded_at'], r['cancelled_at'], r['disputed_at']) if x),
                        chat_unread=thread_unread(th['id'], me['id']) if th else 0, is_demo=bool(r['is_demo']),
                        kind=r['kind'] or 'goods', checkin_at=r['checkin_at'], nights=r['nights']))
    p = q1("SELECT COALESCE(SUM(amount),0) s, COUNT(*) n FROM payouts WHERE user_id=? AND status='pending'", (me['id'],))
    return {'deals': out, 'pending_payout': p['s'], 'pending_count': p['n']}


@route('POST', '/api/deals')
def api_create_deal(req, me, b):
    role = b.get('role')
    kind = 'stay' if b.get('kind') == 'stay' else 'goods'
    if role not in ('seller', 'buyer'):
        raise ApiError('กรุณาเลือกว่าคุณเป็นเจ้าของที่พักหรือผู้เข้าพัก' if kind == 'stay' else 'กรุณาเลือกว่าคุณเป็นผู้ขายหรือผู้ซื้อ')
    stay = {}
    if kind == 'stay':
        stay = stay_common(b); stay.update(stay_dates(b))
        title, delivery, due = stay['title'], 'stay', stay['checkin_date']
    else:
        title = s_(b.get('title'), 120)
        if not title: raise ApiError('กรุณากรอกชื่อสินค้า')
    try: price = money(str(b.get('price')).replace(',', ''))
    except Exception: raise ApiError('กรุณากรอกราคาเป็นตัวเลข')
    if price < MIN_PRICE: raise ApiError(f'ยอดดีลขั้นต่ำ {MIN_PRICE} บาท กรุณากรอกราคาตั้งแต่ {MIN_PRICE} บาทขึ้นไป', field='price')
    if price > MAX_PRICE: raise ApiError('ราคาสูงเกินไป')
    if kind == 'goods':
        delivery = b.get('delivery')
        if delivery not in DELIVERIES: raise ApiError('กรุณาเลือกวิธีส่งมอบ')
    fee_payer = b.get('fee_payer')
    if fee_payer not in FEE_PAYERS: raise ApiError('กรุณาเลือกผู้จ่ายค่าธรรมเนียม')
    if kind == 'goods':
        due = s_(b.get('due_date'), 10)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', due): raise ApiError('กรุณาเลือกวันที่ตกลงส่งของ')
        if due < today_str(): raise ApiError('วันที่ส่งของต้องไม่ใช่วันที่ผ่านมาแล้ว')
    # สินค้าขายประจำ → ดึงเป็นแม่แบบ (แก้ชื่อ/ราคาในดีลได้ โดยไม่แก้สินค้าต้นทาง)
    product_id = None
    if b.get('product_id') is not None and b.get('product_id') != '':
        try: product_id = int(b.get('product_id'))
        except Exception: raise ApiError('สินค้าขายประจำไม่ถูกต้อง')
        prod = q1('SELECT * FROM products WHERE id=? AND active=1', (product_id,))
        if not prod: raise ApiError('ไม่พบสินค้าขายประจำนี้', 404)
        if prod['user_id'] != me['id']: raise ApiError('ใช้ได้เฉพาะสินค้าขายประจำของร้านคุณเอง')
        pk = prod['kind'] or 'goods'
        if kind == 'goods' and pk == 'stay': raise ApiError('รายการนี้เป็นที่พัก ไม่ใช่สินค้า')
        if kind == 'stay' and pk != 'stay': raise ApiError('รายการนี้ไม่ใช่ที่พัก')
    check_limits(me, role, price)
    photos = save_files(b.get('photos'), allow=('image', 'video'), max_n=6)
    f = calc_fee(price, fee_payer)
    code = new_code()
    src = 'product' if product_id else 'link'
    did = ex("""INSERT INTO deals(code,creator_id,creator_role,seller_id,buyer_id,product_id,source,title,description,price,photos,delivery,due_date,
          fee_payer,fee,buyer_fee,seller_fee,buyer_pay,seller_get,status,created_at,kind)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open',?,?)""",
       (code, me['id'], role, me['id'] if role == 'seller' else None, me['id'] if role == 'buyer' else None,
        product_id, src, title, s_(b.get('description'), 500), price, json.dumps(photos), delivery, due, fee_payer,
        f['fee'], f['buyer_fee'], f['seller_fee'], f['buyer_pay'], f['seller_get'], now(), kind))
    if stay: set_stay(did, stay)
    # ตัวเลือก: บันทึกดีลนี้เป็นสินค้าขายประจำใหม่ (เมื่อไม่ได้เลือกจากรายการเดิม)
    saved_pid = None
    if kind == 'goods' and role == 'seller' and not product_id and b.get('save_as_product'):
        dl = [delivery] if delivery in DELIVERIES else ['parcel']
        days = 3
        saved_pid = ex('INSERT INTO products(user_id,title,description,price,photos,deliveries,fee_payer,ship_days,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                       (me['id'], title, s_(b.get('description'), 500), price, json.dumps(photos), json.dumps(dl), fee_payer, days, now()))
        ex('UPDATE deals SET product_id=? WHERE id=?', (saved_pid, did))
        product_id = saved_pid
    return {'code': code, 'product_id': product_id, 'saved_as_product': bool(saved_pid)}


def set_stay(did, st):
    ex("""UPDATE deals SET address=?, map_url=?, checkin_at=?, checkout_date=?, nights=?, guests=?, host_contact=?, free_cancel_days=?
          WHERE id=?""", (st['address'], st['map_url'], st['checkin_at'], st['checkout_date'], st['nights'], st['guests'],
                          st['host_contact'], st['free_cancel_days'], did))


@route('GET', r'/api/deals/([A-Z0-9-]+)', auth=False)
def api_deal(req, me, b, code):
    d = get_deal(code)
    if not d: raise ApiError('ไม่พบดีลนี้ ลิงก์อาจไม่ถูกต้อง', 404)
    return deal_view(d, me)


def act(code, me):
    d = process(get_deal(code))
    if not d: raise ApiError('ไม่พบดีลนี้', 404)
    return d


@route('POST', r'/api/deals/([A-Z0-9-]+)/accept')
def api_accept(req, me, b, code):
    d = act(code, me)
    if d['status'] != 'open': raise ApiError('ดีลนี้มีคนรับไปแล้ว หรือถูกยกเลิก')
    if me['id'] in (d['seller_id'], d['buyer_id']): raise ApiError('คุณเป็นคนสร้างดีลนี้เอง ส่งลิงก์ให้อีกฝ่ายกดรับนะ')
    role = 'buyer' if d['creator_role'] == 'seller' else 'seller'
    check_limits(me, role, d['price'])
    other = d['seller_id'] if role == 'buyer' else d['buyer_id']
    if role == 'seller':  # seller's limit applies to seller
        pass
    ex(f"UPDATE deals SET {role}_id=?, status='accepted', accepted_at=? WHERE id=?", (me['id'], dnow(d), d['id']))
    notify(other, code, f'{me["name"]} กดรับดีล "{d["title"]}" แล้ว' + (' · รอผู้ซื้อจ่ายเงิน' if role == 'buyer' else ' · จ่ายเงินเข้าระบบพักเงินได้เลย'), 'check')
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/pay')
def api_pay(req, me, b, code):
    d = act(code, me); require_party(d, me, 'buyer')
    if d['status'] != 'accepted': raise ApiError('ดีลนี้ยังจ่ายไม่ได้ หรือจ่ายไปแล้ว')
    if is_stay(d):
        t = dnow(d)
        if t >= d['checkin_at'] + STAY_RELEASE: raise ApiError('เลยเวลาเช็คอินมานานแล้ว จ่ายดีลนี้ไม่ได้ กรุณาสร้างดีลใหม่')
        code4 = f'{random.randint(0, 9999):04d}'
        ex("UPDATE deals SET status='held', paid_at=?, meet_code=?, auto_release_at=? WHERE id=?",
           (t, code4, max(d['checkin_at'], t) + STAY_RELEASE, d['id']))
        notify(d['seller_id'], code, f'ผู้เข้าพักจ่ายแล้ว {fmt_baht(d["buyer_pay"])} (จำลอง) เงินพักไว้จนเช็คอิน · '
               'วันเช็คอินบอกรหัส 4 หลักให้ผู้เข้าพักกรอกเมื่อเข้าห้องได้แล้ว', 'lock')
        notify(d['buyer_id'], code, f'ชำระเงิน {fmt_baht(d["buyer_pay"])} สำเร็จ (จำลอง) เงินพักไว้ · เจ้าของที่พักได้เงินเมื่อคุณเช็คอินได้จริง', 'lock')
        return {'ok': True}
    meet = f'{random.randint(0, 9999):04d}' if d['delivery'] == 'meet' else None
    ex("UPDATE deals SET status='held', paid_at=?, meet_code=? WHERE id=?", (dnow(d), meet, d['id']))
    notify(d['seller_id'], code, f'ผู้ซื้อจ่ายแล้ว {fmt_baht(d["buyer_pay"])} (จำลอง) เงินพักไว้แล้ว · ' +
           ('นัดรับแล้วบอกรหัส 4 หลักให้ผู้ซื้อหลังเขาตรวจของ' if meet else 'ส่งของได้เลย'), 'lock')
    notify(d['buyer_id'], code, f'ชำระเงิน {fmt_baht(d["buyer_pay"])} สำเร็จ (จำลอง) เงินถูกพักไว้แล้ว', 'lock')
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/ship')
def api_ship(req, me, b, code):
    d = act(code, me); require_party(d, me, 'seller')
    if is_stay(d): raise ApiError('ดีลที่พักไม่มีขั้นตอนส่งของ ผู้เข้าพักยืนยันตอนเช็คอิน')
    if d['status'] != 'held': raise ApiError('ยังส่งของไม่ได้ในขั้นตอนนี้')
    t = dnow(d)
    on_time = 1 if t <= due_ts(d['due_date']) else 0
    pv = save_video(b.get('pack_video'))
    if d['pack_requested_at'] and not pv and not d['pack_video']: raise ApiError('ผู้ซื้อขอคลิปตอนแพ็คของ ต้องแนบคลิปก่อนแจ้งส่งของ')
    if pv: ex('UPDATE deals SET pack_video=? WHERE id=?', (pv, d['id']))
    if d['delivery'] == 'parcel':
        trk = re.sub(r'\s', '', s_(b.get('tracking'), 40)).upper()
        if not re.fullmatch(r'[A-Z0-9-]{6,40}', trk): raise ApiError('กรุณากรอกเลขพัสดุให้ถูกต้อง (อย่างน้อย 6 ตัว)')
        carrier = b.get('carrier') if b.get('carrier') in CARRIERS else 'อื่น ๆ'
        ex("UPDATE deals SET status='shipped', shipped_at=?, tracking=?, carrier=?, on_time=? WHERE id=?", (t, trk, carrier, on_time, d['id']))
        notify(d['buyer_id'], code, f'ผู้ขายส่งของแล้ว · {carrier} เลขพัสดุ {trk}' + (' · มีคลิปตอนแพ็คของ' if pv else '') + ' · 📹 แนะนำให้ถ่ายคลิปตอนแกะกล่องไว้ เผื่อของมีปัญหา จะใช้เป็นหลักฐานได้', 'truck')
    elif d['delivery'] == 'messenger':
        txt = s_(b.get('proof_text'), 300)
        photos = save_files(b.get('photos'), max_n=4)
        if not txt and not photos: raise ApiError('กรุณาแนบหลักฐาน: ลิงก์ติดตามไรเดอร์ หรือรูปตอนส่งของ')
        ex("""UPDATE deals SET status='delivered', shipped_at=?, delivered_at=?, auto_release_at=?, proof_text=?, proof_photos=?, on_time=?
              WHERE id=?""", (t, t, t + MESSENGER_RELEASE, txt, json.dumps(photos), on_time, d['id']))
        notify(d['buyer_id'], code, 'ผู้ขายส่งแมสเซนเจอร์แล้ว ได้ของแล้วกดยืนยัน · ระบบปล่อยเงินอัตโนมัติใน 24 ชม. · 📹 แนะนำให้ถ่ายคลิปตอนแกะกล่องไว้ เผื่อของมีปัญหา จะใช้เป็นหลักฐานได้', 'bike')
    else:
        raise ApiError('ดีลนัดรับ ใช้รหัส 4 หลักแทนการกดส่งของ')
    return {'ok': True}


UNBOX_OK = ('shipped', 'delivered', 'disputed', 'completed', 'partial')


@route('POST', r'/api/deals/([A-Z0-9-]+)/request-unbox')
def api_request_unbox(req, me, b, code):
    d = act(code, me); require_party(d, me, 'seller')
    if is_stay(d) or d['status'] not in ('shipped', 'delivered', 'disputed'): raise ApiError('ขอคลิปได้หลังส่งของแล้ว')
    if d['unbox_video']: raise ApiError('ผู้ซื้อแนบคลิปตอนแกะกล่องแล้ว')
    ex('UPDATE deals SET unbox_requested_at=? WHERE id=?', (now(), d['id']))
    notify(d['buyer_id'], code, f'ผู้ขายขอคลิปตอนแกะกล่อง "{d["title"]}" (ไม่บังคับ) · ช่วยเป็นหลักฐานให้ทั้งสองฝ่าย', 'video')
    th = deal_thread(d, 'deal')
    ex('INSERT INTO messages(thread_id,sender_id,is_admin,text,photos,created_at) VALUES(?,?,0,?,?,?)',
       (th['id'], me['id'], 'รบกวนถ่ายคลิปตอนแกะกล่องแนบในหน้าดีลด้วยนะครับ/คะ (ไม่บังคับ) ขอบคุณมาก 🙏', '[]', now()))
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/unbox-video')
def api_unbox_video(req, me, b, code):
    d = act(code, me); require_party(d, me, 'buyer')
    if is_stay(d) or d['status'] not in UNBOX_OK: raise ApiError('แนบคลิปได้หลังผู้ขายส่งของแล้ว')
    uv = save_video(b.get('video'))
    if not uv: raise ApiError('กรุณาเลือกคลิป')
    ex('UPDATE deals SET unbox_video=? WHERE id=?', (uv, d['id']))
    notify(d['seller_id'], code, f'ผู้ซื้อแนบคลิปตอนแกะกล่อง "{d["title"]}" แล้ว', 'video')
    return {'ok': True, 'unbox_video': uv}


PACK_OK = ('held', 'shipped', 'delivered', 'disputed')


@route('POST', r'/api/deals/([A-Z0-9-]+)/request-pack')
def api_request_pack(req, me, b, code):
    d = act(code, me); require_party(d, me, 'buyer')
    if is_stay(d) or d['delivery'] == 'meet': raise ApiError('ดีลนี้ไม่มีขั้นตอนแพ็คของส่ง')
    if d['status'] != 'held': raise ApiError('ขอคลิปตอนแพ็คของได้ก่อนผู้ขายแจ้งส่งของเท่านั้น')
    if d['pack_video']: raise ApiError('ผู้ขายแนบคลิปตอนแพ็คของแล้ว')
    if d['pack_requested_at']: return {'ok': True, 'already': True}
    ex('UPDATE deals SET pack_requested_at=? WHERE id=?', (now(), d['id']))
    notify(d['seller_id'], code, f'ผู้ซื้อขอคลิปตอนแพ็คของ "{d["title"]}" · ต้องแนบคลิปก่อนแจ้งส่งของ', 'video')
    th = deal_thread(d, 'deal')
    ex('INSERT INTO messages(thread_id,sender_id,is_admin,text,photos,created_at) VALUES(?,?,0,?,?,?)',
       (th['id'], me['id'], 'รบกวนถ่ายคลิปตอนแพ็คของแนบตอนแจ้งส่งของด้วยนะครับ/คะ ขอบคุณมาก 🙏', '[]', now()))
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/pack-video')
def api_pack_video(req, me, b, code):
    d = act(code, me); require_party(d, me, 'seller')
    if is_stay(d) or d['delivery'] == 'meet' or d['status'] not in PACK_OK: raise ApiError('แนบคลิปตอนแพ็คของไม่ได้ในขั้นตอนนี้')
    pv = save_video(b.get('video'))
    if not pv: raise ApiError('กรุณาเลือกคลิป')
    ex('UPDATE deals SET pack_video=? WHERE id=?', (pv, d['id']))
    notify(d['buyer_id'], code, f'ผู้ขายแนบคลิปตอนแพ็คของ "{d["title"]}" แล้ว', 'video')
    return {'ok': True, 'pack_video': pv}


@route('POST', r'/api/deals/([A-Z0-9-]+)/simulate-delivered')
def api_sim_delivered(req, me, b, code):
    d = act(code, me); require_party(d, me)
    if d['status'] != 'shipped': raise ApiError('ใช้ได้เฉพาะตอนพัสดุกำลังส่ง')
    t = dnow(d)
    ex("UPDATE deals SET status='delivered', delivered_at=?, auto_release_at=? WHERE id=?", (t, t + PARCEL_RELEASE, d['id']))
    notify(d['buyer_id'], code, 'พัสดุถึงแล้ว! (จำลอง) ตรวจของแล้วกดยืนยัน หรือแจ้งปัญหาภายใน 3 วัน', 'box')
    notify(d['seller_id'], code, 'ขนส่งแจ้งว่าพัสดุถึงผู้ซื้อแล้ว (จำลอง)', 'truck')
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/confirm')
def api_confirm(req, me, b, code):
    d = act(code, me); require_party(d, me, 'buyer')
    if is_stay(d):
        if d['status'] != 'held': raise ApiError('ยืนยันเช็คอินไม่ได้ในขั้นตอนนี้')
        if dnow(d) < day_start(d['checkin_at']): raise ApiError('ยืนยันเช็คอินได้ตั้งแต่วันเช็คอินเท่านั้น')
        complete(d, 'guest_checkin')
        return {'ok': True}
    if d['status'] not in ('shipped', 'delivered'): raise ApiError('ยังยืนยันรับของไม่ได้ในขั้นตอนนี้')
    complete(d, 'buyer_confirm')
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/meet-code')
def api_meet_code(req, me, b, code):
    d = act(code, me); require_party(d, me, 'buyer')
    if d['status'] != 'held' or d['delivery'] not in ('meet', 'stay'): raise ApiError('ใช้ได้เฉพาะดีลนัดรับ/ดีลที่พักที่จ่ายเงินแล้ว')
    if is_stay(d) and dnow(d) < day_start(d['checkin_at']): raise ApiError('กรอกรหัสเช็คอินได้ตั้งแต่วันเช็คอินเท่านั้น')
    if d['meet_tries'] >= 5: raise ApiError('กรอกผิดเกิน 5 ครั้ง กรุณาติดต่อทีมงาน')
    c = re.sub(r'\D', '', s_(b.get('code'), 10))
    if c != d['meet_code']:
        ex('UPDATE deals SET meet_tries=meet_tries+1 WHERE id=?', (d['id'],))
        raise ApiError(f'รหัสไม่ถูกต้อง (เหลือ {4 - d["meet_tries"]} ครั้ง)')
    complete(d, 'checkin_code' if is_stay(d) else 'meet_code')
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/dispute')
def api_dispute(req, me, b, code):
    d = act(code, me); require_party(d, me, 'buyer')
    t = dnow(d)
    if is_stay(d): return stay_problem(d, b, t)
    if d['status'] not in ('shipped', 'delivered'): raise ApiError('แจ้งปัญหาได้หลังผู้ขายส่งของแล้ว และก่อนเงินถูกปล่อย')
    if d['status'] == 'delivered' and t > min(d['delivered_at'] + DISPUTE_WINDOW, d['auto_release_at']):
        raise ApiError('เลยเวลาแจ้งปัญหาแล้ว')
    reason = b.get('reason')
    if reason not in DISPUTE_REASONS: raise ApiError('กรุณาเลือกปัญหาที่พบ')
    files = save_files(b.get('files'), allow=('image', 'video'), max_n=4)
    uv = save_video(b.get('unbox_video'))
    if uv: ex('UPDATE deals SET unbox_video=? WHERE id=?', (uv, d['id']))
    if not files and not uv and not d['unbox_video']: raise ApiError('กรุณาแนบคลิปแกะกล่องหรือรูปหลักฐานอย่างน้อย 1 ไฟล์')
    ex("""UPDATE deals SET status='disputed', disputed_at=?, dispute_reason=?, dispute_detail=?, dispute_files=? WHERE id=?""",
       (t, reason, s_(b.get('detail'), 1000), json.dumps(files), d['id']))
    notify(d['seller_id'], code, f'ผู้ซื้อแจ้งปัญหา: {reason} · เงินถูกพักไว้ระหว่างทีมงานตรวจสอบ', 'warn')
    notify(d['buyer_id'], code, 'ส่งเรื่องแล้ว ทีมงานจะติดต่อภายใน 24 ชม. เงินยังพักไว้อย่างปลอดภัย', 'warn')
    return {'ok': True}


def stay_problem(d, b, t):
    """ผู้เข้าพักแจ้ง: ไม่มีที่พักจริง / ไม่ตรงปก / เข้าพักไม่ได้ — ตั้งแต่เวลาเช็คอินจนถึงเวลาปล่อยเงินอัตโนมัติ"""
    if d['status'] != 'held': raise ApiError('แจ้งปัญหาได้เฉพาะตอนเงินยังพักไว้')
    if t < d['checkin_at']: raise ApiError('แจ้งปัญหาได้ตั้งแต่เวลาเช็คอิน ถ้ายังไม่ถึงวันเข้าพักให้ใช้ปุ่มยกเลิกการจอง')
    if t > d['auto_release_at']: raise ApiError('เลยเวลาแจ้งปัญหาแล้ว (24 ชม. หลังเวลาเช็คอิน)')
    reason = b.get('reason')
    if reason not in STAY_REASONS: raise ApiError('กรุณาเลือกปัญหาที่พบ')
    loc = s_(b.get('location'), 300)
    if len(loc) < 3: raise ApiError('กรุณาระบุตำแหน่งที่คุณอยู่ตอนนี้ (เช่น หน้าซอย/จุดที่ปักหมุดไว้)')
    files = save_files(b.get('files'), allow=('image', 'video'), max_n=4)
    if not files: raise ApiError('กรุณาแนบรูปหรือวิดีโอหลักฐาน ณ ที่พักอย่างน้อย 1 ไฟล์')
    ex("""UPDATE deals SET status='disputed', disputed_at=?, dispute_reason=?, dispute_detail=?, dispute_files=?, dispute_location=? WHERE id=?""",
       (t, reason, s_(b.get('detail'), 1000), json.dumps(files), loc, d['id']))
    notify(d['seller_id'], d['code'], f'ผู้เข้าพักแจ้งปัญหา: {reason} · เงินถูกพักไว้ระหว่างทีมงานตรวจสอบ', 'warn')
    notify(d['buyer_id'], d['code'], 'ส่งเรื่องแล้ว ทีมงานจะติดต่อโดยเร็ว เงินยังพักไว้อย่างปลอดภัย ไม่โอนให้เจ้าของที่พัก', 'warn')
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/late-refund')
def api_late_refund(req, me, b, code):
    d = act(code, me); require_party(d, me, 'buyer')
    if is_stay(d): raise ApiError('ดีลที่พักใช้ปุ่มยกเลิกการจองแทน')
    if d['status'] != 'held': raise ApiError('ขอคืนเงินแบบนี้ได้เฉพาะตอนผู้ขายยังไม่ส่งของ')
    if dnow(d) <= due_ts(d['due_date']): raise ApiError('ยังไม่เลยวันที่ตกลงส่งของ')
    ex("UPDATE deals SET on_time=0 WHERE id=?", (d['id'],))
    refund_seller_fault(d, dnow(d), 'late')
    notify(d['seller_id'], code, f'ดีล "{d["title"]}" ถูกยกเลิก เพราะเลยวันที่ตกลงส่งของ · คืนเงินผู้ซื้อเต็มจำนวนแล้ว', 'warn')
    notify(d['buyer_id'], code, f'คืนเงิน {fmt_baht(d["buyer_pay"])} ให้คุณเต็มจำนวน รวมค่าธรรมเนียมแล้ว (จำลอง)', 'wallet')
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/cancel')
def api_cancel(req, me, b, code):
    d = act(code, me)
    if d['status'] == 'held' and is_stay(d): return stay_cancel(d, me, b)
    if d['status'] == 'held': return goods_cancel(d, me, b)
    if d['status'] in ('shipped', 'delivered', 'disputed'):
        raise ApiError('ผู้ขายส่งของ/ส่งมอบแล้ว ยกเลิกดีลไม่ได้ · ได้ของแล้วกดยืนยันรับของ หรือถ้ามีปัญหาให้กด "แจ้งปัญหา" พร้อมหลักฐาน')
    if d['status'] not in ('open', 'accepted'): raise ApiError('ดีลนี้จบแล้ว ยกเลิกไม่ได้')
    if me['id'] not in (d['seller_id'], d['buyer_id']): raise ApiError('คุณไม่ได้อยู่ในดีลนี้', 403)
    ex("UPDATE deals SET status='cancelled', cancelled_at=? WHERE id=?", (dnow(d), d['id']))
    other = d['buyer_id'] if me['id'] == d['seller_id'] else d['seller_id']
    notify(other, code, f'{me["name"]} ยกเลิกดีล "{d["title"]}"', 'warn')
    return {'ok': True}


def goods_cancel(d, me, b):
    """ยกเลิกหลังจ่ายเงิน ก่อนผู้ขายส่งของ: ผู้ซื้อยกเลิกเอง = หักค่าดำเนินการ · ผู้ขายยกเลิก / เลยกำหนดส่ง = คืนเต็ม + ค่าปรับผู้ขาย"""
    r = require_party(d, me)
    t = dnow(d); code = d['code']
    if r == 'seller' or t > due_ts(d['due_date']):
        refund_seller_fault(d, t, 'seller_cancel' if r == 'seller' else 'late')
        notify(d['buyer_id'], code, f'{"ผู้ขายยกเลิกดีล" if r == "seller" else "ยกเลิกดีลเพราะเลยวันที่ตกลงส่งของ"} "{d["title"]}" · คืนเงิน {fmt_baht(d["buyer_pay"])} ให้คุณเต็มจำนวนรวมค่าธรรมเนียม (จำลอง)', 'wallet')
        if r == 'seller': notify(d['seller_id'], code, f'คุณยกเลิกดีล "{d["title"]}" แล้ว · คืนเงินผู้ซื้อเต็มจำนวน', 'warn')
        return {'ok': True, 'result': 'refunded', 'fault': 'seller', 'refund': d['buyer_pay'], 'penalty': money(d['fee'])}
    back, ch = refund_buyer_choice(d, t, 'buyer_cancel')
    notify(d['seller_id'], code, f'ผู้ซื้อยกเลิกดีล "{d["title"]}" ก่อนส่งของ · ไม่ต้องส่งของแล้ว', 'warn')
    return {'ok': True, 'result': 'refunded', 'fault': 'buyer', 'refund': back, 'charge': ch}


def stay_cancel(d, me, b):
    """ยกเลิกการจองหลังจ่ายเงินแล้ว: เจ้าของยกเลิก = คืนเต็ม · ผู้เข้าพักยกเลิกในช่วงยกเลิกฟรี = คืนเต็ม · หลังจากนั้น = ส่งทีมงานตัดสิน"""
    r = require_party(d, me)
    t = dnow(d); code = d['code']
    if r == 'seller':
        refund_seller_fault(d, t, 'host_cancel')
        notify(d['seller_id'], code, f'คุณยกเลิกการจอง "{d["title"]}" แล้ว · คืนเงินผู้เข้าพักเต็มจำนวน', 'warn')
        notify(d['buyer_id'], code, f'เจ้าของที่พักยกเลิกการจอง "{d["title"]}" · ระบบคืนเงิน {fmt_baht(d["buyer_pay"])} ให้คุณเต็มจำนวนรวมค่าธรรมเนียม', 'warn')
        return {'ok': True, 'result': 'refunded', 'fault': 'seller', 'refund': d['buyer_pay'], 'penalty': money(d['fee'])}
    if t >= d['checkin_at']: raise ApiError('ถึงเวลาเช็คอินแล้ว ยกเลิกไม่ได้ ถ้ามีปัญหาให้กด "แจ้งปัญหา"')
    if t <= d['checkin_at'] - (d['free_cancel_days'] or 0) * DAY:
        back, ch = refund_buyer_choice(d, t, 'guest_cancel')
        notify(d['seller_id'], code, f'ผู้เข้าพักยกเลิกการจอง "{d["title"]}" ภายในช่วงยกเลิกฟรี · คืนเงินผู้เข้าพักแล้ว', 'warn')
        return {'ok': True, 'result': 'refunded', 'fault': 'buyer', 'refund': back, 'charge': ch}
    detail = s_(b.get('reason'), 1000)
    ex("""UPDATE deals SET status='disputed', disputed_at=?, dispute_reason=?, dispute_detail=?, dispute_files='[]' WHERE id=?""",
       (t, LATE_CANCEL_REASON, detail, d['id']))
    notify(d['seller_id'], code, f'ผู้เข้าพักขอยกเลิกหลังหมดเวลายกเลิกฟรี · ทีมงานจะช่วยตัดสินว่าคืนเงินเท่าไร เงินยังพักไว้', 'warn')
    notify(d['buyer_id'], code, 'ส่งคำขอยกเลิกให้ทีมงานแล้ว (เลยช่วงยกเลิกฟรี) ทีมงานจะคุยกับทั้งสองฝ่ายก่อนตัดสิน', 'warn')
    return {'ok': True, 'result': 'disputed'}


@route('POST', r'/api/deals/([A-Z0-9-]+)/skip')
def api_skip(req, me, b, code):
    d = act(code, me); require_party(d, me)
    to = b.get('to')
    if to in ('checkin', 'after_release'):
        if not is_stay(d): raise ApiError('ใช้ได้เฉพาะดีลที่พัก')
        target = d['checkin_at'] + 60 if to == 'checkin' else (d['auto_release_at'] or d['checkin_at'] + STAY_RELEASE) + 60
        ex('UPDATE deals SET skew=COALESCE(skew,0)+? WHERE id=?', (max(0, target - dnow(d)), d['id']))
        process(get_deal(code))
        return {'ok': True}
    try: hours = float(b.get('hours'))
    except Exception: hours = 24
    hours = max(1, min(hours, 24 * 7))
    ex('UPDATE deals SET skew=COALESCE(skew,0)+? WHERE id=?', (hours * HOUR, d['id']))
    process(get_deal(code))
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/review')
def api_review(req, me, b, code):
    d = act(code, me); role = require_party(d, me)
    if d['status'] not in ('completed', 'partial'): raise ApiError('ให้คะแนนได้หลังดีลจบแล้ว')
    try: stars = int(b.get('stars'))
    except Exception: stars = 0
    if not 1 <= stars <= 5: raise ApiError('กรุณาเลือกคะแนน 1–5 ดาว')
    if q1('SELECT 1 FROM reviews WHERE deal_id=? AND from_id=?', (d['id'], me['id'])): raise ApiError('คุณให้คะแนนดีลนี้ไปแล้ว')
    to = d['seller_id'] if role == 'buyer' else d['buyer_id']
    ph = b.get('photos') or []
    if not isinstance(ph, list): raise ApiError('รูปไม่ถูกต้อง')
    if len(ph) > 3: raise ApiError('แนบรูปรีวิวได้สูงสุด 3 รูป')
    photos = save_files(ph, allow=('image',), max_n=3)
    ex('INSERT INTO reviews(deal_id,from_id,to_id,target_role,stars,text,photos,created_at) VALUES(?,?,?,?,?,?,?,?)',
       (d['id'], me['id'], to, 'seller' if role == 'buyer' else 'buyer', stars, s_(b.get('text'), 500), json.dumps(photos), now()))
    notify(to, code, f'{me["name"]} ให้คะแนนคุณ {"★" * stars} ในดีล "{d["title"]}"', 'star')
    return {'ok': True}


@route('GET', '/api/notifications')
def api_notifs(req, me, b):
    rows = q('SELECT id,deal_code,text,icon,read,created_at,link FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 40', (me['id'],))
    unread = q1('SELECT COUNT(*) n FROM notifications WHERE user_id=? AND read=0', (me['id'],))['n']
    return {'items': [dict(r) for r in rows], 'unread': unread, 'chat_unread': chat_unread(me['id'])}


@route('POST', '/api/notifications/read')
def api_notifs_read(req, me, b):
    ex('UPDATE notifications SET read=1 WHERE user_id=?', (me['id'],))
    return {'ok': True}


def product_view(p):
    d = dict(p); d['photos'] = jl(p['photos']); d['deliveries'] = jl(p['deliveries'])
    n = q1("SELECT COUNT(*) n FROM deals WHERE product_id=? AND status IN ('completed','partial')", (p['id'],))['n']
    if not n:  # ข้อมูลตัวอย่างเก่าไม่มี product_id — นับจากรูปในดีลให้โชว์ "ขายแล้ว" ได้
        frag = None
        for ph in d['photos'] or []:
            m = re.search(r'/([a-z0-9-]+)\.(?:svg|jpe?g|png|webp)(?:\?|$)', ph or '', re.I)
            if m: frag = m.group(1); break
        if frag:
            n = q1("SELECT COUNT(*) n FROM deals WHERE seller_id=? AND photos LIKE ? AND status IN ('completed','partial')",
                   (p['user_id'], '%' + frag + '%'))['n']
    d['sold_count'] = n or 0
    return d


@route('GET', '/api/shops', auth=False)
def api_shops(req, me, b):
    rows = q("""SELECT u.*, (SELECT COUNT(*) FROM products p WHERE p.user_id=u.id AND p.active=1) pc FROM users u
                WHERE pc>0 ORDER BY u.is_demo DESC, u.id LIMIT 20""")
    out = []
    for u in rows:
        pu = public_user(u); pu['product_count'] = u['pc']
        ph = q1('SELECT photos FROM products WHERE user_id=? AND active=1 ORDER BY id LIMIT 1', (u['id'],))
        pu['cover_photo'] = (jl(ph['photos']) or [None])[0] if ph else None
        out.append(pu)
    out.sort(key=lambda x: -x['stats']['sales'])
    return {'shops': out}


@route('GET', r'/api/shops/(\d+)', auth=False)
def api_shop(req, me, b, uid):
    u = get_user(int(uid))
    if not u: raise ApiError('ไม่พบร้านนี้', 404)
    out = public_user(u)
    out['products'] = [product_view(p) for p in q('SELECT * FROM products WHERE user_id=? AND active=1 ORDER BY id DESC', (u['id'],))]
    out['reviews'] = review_list(u['id'], 'seller', 10)
    out['reviews_top'] = review_page(u['id'], 'seller')
    out['levels'] = [dict(key=k, name=n, min_deals=a, min_stars=s, max_dispute=round(m * 100), limit=l) for k, n, a, s, m, l in LEVELS]
    return out


@route('POST', '/api/products')
def api_add_product(req, me, b):
    if b.get('kind') == 'stay': return add_stay_product(me, b)
    title = s_(b.get('title'), 120)
    if not title: raise ApiError('กรุณากรอกชื่อสินค้า')
    try: price = money(str(b.get('price')).replace(',', ''))
    except Exception: raise ApiError('กรุณากรอกราคาเป็นตัวเลข')
    if price < MIN_PRICE: raise ApiError(f'ยอดดีลขั้นต่ำ {MIN_PRICE} บาท กรุณาตั้งราคาสินค้าตั้งแต่ {MIN_PRICE} บาทขึ้นไป', field='price')
    if price > MAX_PRICE: raise ApiError(f'ราคาต้องไม่เกิน {MAX_PRICE:,} บาท')
    dl = [x for x in (b.get('deliveries') or []) if x in DELIVERIES] or ['parcel']
    fp = b.get('fee_payer') if b.get('fee_payer') in FEE_PAYERS else 'half'
    try: days = max(1, min(int(b.get('ship_days') or 3), 14))
    except Exception: days = 3
    photos = save_files(b.get('photos'), allow=('image', 'video'), max_n=6)
    pid = ex('INSERT INTO products(user_id,title,description,price,photos,deliveries,fee_payer,ship_days,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
             (me['id'], title, s_(b.get('description'), 500), price, json.dumps(photos), json.dumps(dl), fp, days, now()))
    return {'id': pid}


def add_stay_product(me, b):
    """ที่พักในหน้าร้าน: ราคาต่อคืน · ลูกค้าเลือกวันเช็คอิน/จำนวนคืน/ผู้เข้าพักตอนจอง"""
    st = stay_common(b)
    try: price = money(str(b.get('price')).replace(',', ''))
    except Exception: raise ApiError('กรุณากรอกราคาต่อคืนเป็นตัวเลข')
    if price < MIN_PRICE: raise ApiError(f'ยอดดีลขั้นต่ำ {MIN_PRICE} บาท กรุณาตั้งราคาต่อคืนตั้งแต่ {MIN_PRICE} บาทขึ้นไป', field='price')
    if price > MAX_PRICE: raise ApiError(f'ราคาต่อคืนต้องไม่เกิน {MAX_PRICE:,} บาท')
    hm = s_(b.get('checkin_time'), 5) or '14:00'
    if not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', hm): raise ApiError('เวลาเช็คอินไม่ถูกต้อง (เช่น 14:00)')
    try: mg = max(1, min(int(b.get('max_guests') or 2), 30))
    except Exception: mg = 2
    fp = b.get('fee_payer') if b.get('fee_payer') in FEE_PAYERS else 'half'
    photos = save_files(b.get('photos'), allow=('image', 'video'), max_n=6)
    pid = ex("""INSERT INTO products(user_id,title,description,price,photos,deliveries,fee_payer,ship_days,created_at,kind,address,map_url,
                  checkin_time,max_guests,free_cancel_days,host_contact) VALUES(?,?,?,?,?,'["stay"]',?,0,?,'stay',?,?,?,?,?,?)""",
             (me['id'], st['title'], s_(b.get('description'), 500), price, json.dumps(photos), fp, now(), st['address'], st['map_url'],
              hm, mg, st['free_cancel_days'], st['host_contact']))
    return {'id': pid}


@route('POST', r'/api/products/(\d+)/delete')
def api_del_product(req, me, b, pid):
    p = q1('SELECT * FROM products WHERE id=?', (int(pid),))
    if not p or p['user_id'] != me['id']: raise ApiError('ไม่พบสินค้า', 404)
    ex('UPDATE products SET active=0 WHERE id=?', (p['id'],))
    return {'ok': True}


@route('POST', r'/api/products/(\d+)/buy')
def api_buy(req, me, b, pid):
    p = q1('SELECT * FROM products WHERE id=? AND active=1', (int(pid),))
    if not p: raise ApiError('สินค้านี้ไม่มีแล้ว', 404)
    if p['user_id'] == me['id']: raise ApiError('นี่คือสินค้าในร้านของคุณเอง')
    seller = get_user(p['user_id'])
    if (p['kind'] or 'goods') == 'stay': return buy_stay(me, seller, p, b)
    dl = b.get('delivery')
    if dl not in jl(p['deliveries']): raise ApiError('กรุณาเลือกวิธีส่งมอบ')
    if p['price'] < MIN_PRICE: raise ApiError(f'ยอดดีลขั้นต่ำ {MIN_PRICE} บาท — สินค้านี้ราคาต่ำกว่าขั้นต่ำ จึงสั่งซื้อผ่านดีลชัวร์ไม่ได้')
    check_limits(me, 'buyer', p['price'])
    check_limits(seller, 'seller', p['price'])
    f = calc_fee(p['price'], p['fee_payer'])
    code = new_code(); t = now()
    due = today_str(t + p['ship_days'] * DAY)
    ex("""INSERT INTO deals(code,creator_id,creator_role,seller_id,buyer_id,product_id,source,title,description,price,photos,delivery,due_date,
          fee_payer,fee,buyer_fee,seller_fee,buyer_pay,seller_get,status,created_at,accepted_at,is_demo)
          VALUES(?,?,'buyer',?,?,?,'shop',?,?,?,?,?,?,?,?,?,?,?,?,'accepted',?,?,?)""",
       (code, me['id'], seller['id'], me['id'], p['id'], p['title'], p['description'], p['price'], p['photos'], dl, due,
        p['fee_payer'], f['fee'], f['buyer_fee'], f['seller_fee'], f['buyer_pay'], f['seller_get'], t, t, 0))
    notify(seller['id'], code, f'มีคำสั่งซื้อใหม่จากหน้าร้าน: "{p["title"]}" โดย {me["name"]} · รอผู้ซื้อจ่ายเงิน', 'store')
    return {'code': code}


def buy_stay(me, seller, p, b):
    sd = stay_dates(dict(b, checkin_time=p['checkin_time'] or '14:00'), max_guests=p['max_guests'] or 30)
    price = money(p['price'] * sd['nights'])
    if price > MAX_PRICE: raise ApiError('ยอดรวมสูงเกินไป')
    if price < MIN_PRICE: raise ApiError(f'ยอดดีลขั้นต่ำ {MIN_PRICE} บาท — ยอดจองนี้ต่ำกว่าขั้นต่ำ')
    check_limits(me, 'buyer', price)
    check_limits(seller, 'seller', price)
    f = calc_fee(price, p['fee_payer'])
    code = new_code(); t = now()
    did = ex("""INSERT INTO deals(code,creator_id,creator_role,seller_id,buyer_id,product_id,source,title,description,price,photos,delivery,due_date,
          fee_payer,fee,buyer_fee,seller_fee,buyer_pay,seller_get,status,created_at,accepted_at,kind)
          VALUES(?,?,'buyer',?,?,?,'shop',?,?,?,?,'stay',?,?,?,?,?,?,?,'accepted',?,?,'stay')""",
       (code, me['id'], seller['id'], me['id'], p['id'], p['title'], p['description'], price, p['photos'], sd['checkin_date'],
        p['fee_payer'], f['fee'], f['buyer_fee'], f['seller_fee'], f['buyer_pay'], f['seller_get'], t, t))
    sd.update(address=p['address'], map_url=p['map_url'], host_contact=p['host_contact'] or seller['name'], free_cancel_days=p['free_cancel_days'] or 0)
    set_stay(did, sd)
    notify(seller['id'], code, f'มีการจองที่พักจากหน้าร้าน: "{p["title"]}" {sd["nights"]} คืน โดย {me["name"]} · รอผู้เข้าพักจ่ายเงิน', 'store')
    return {'code': code}


@route('GET', '/api/payouts')
def api_payouts(req, me, b):
    rows = q("""SELECT p.*, d.code, d.title FROM payouts p JOIN deals d ON d.id=p.deal_id WHERE p.user_id=? ORDER BY p.id DESC LIMIT 50""", (me['id'],))
    pend = q1("SELECT COALESCE(SUM(amount),0) s FROM payouts WHERE user_id=? AND status='pending'", (me['id'],))['s']
    owed = penalty_owed(me['id'])
    pens = [dict(r) for r in q("""SELECT r.amount, r.deducted, r.reason, r.created_at, d.code, d.title FROM records r LEFT JOIN deals d ON d.id=r.deal_id
                                  WHERE r.user_id=? AND r.kind='penalty' ORDER BY r.id DESC LIMIT 20""", (me['id'],))]
    batches = [dict(r) for r in q('SELECT * FROM payout_batches WHERE user_id=? ORDER BY id DESC LIMIT 20', (me['id'],))]
    return {'items': [dict(r) for r in rows], 'pending': money(pend), 'penalty_owed': owed, 'next': payout_calc(pend, owed),
            'penalties': pens, 'batches': batches, 'rule': dict(fee=PAYOUT_FEE, free_from=PAYOUT_FREE_FROM)}


# ---------------- chat (แชทในดีล · ทักร้าน · ทีมงานคุยในข้อพิพาท) ----------------
ADMIN_UID = 0  # ใช้แทน "ทีมงาน" ในตาราง thread_reads
TEAM_NAME = 'ทีมงานดีลชัวร์'
CHAT_WARN = re.compile(r'(\d[\d\s-]{8,}\d|โอนตรง|โอนนอก|นอกแอป|เลขบัญชี|บัญชีธนาคาร|พร้อมเพย์|promptpay|truemoney|ทรูมันนี่|โอนก่อน)', re.I)


def qs(req):
    from urllib.parse import parse_qs
    return {k: v[0] for k, v in parse_qs(urlparse(req.path).query).items()}


def thread_unread(tid, uid):
    r = q1('SELECT last_read_id FROM thread_reads WHERE thread_id=? AND user_id=?', (tid, uid))
    last = r['last_read_id'] if r else 0
    if uid == ADMIN_UID:
        return q1('SELECT COUNT(*) n FROM messages WHERE thread_id=? AND id>? AND is_admin=0', (tid, last))['n']
    return q1('SELECT COUNT(*) n FROM messages WHERE thread_id=? AND id>? AND (sender_id IS NULL OR sender_id!=?)', (tid, last, uid))['n']


def chat_unread(uid):
    return q1("""SELECT COUNT(*) n FROM messages m JOIN threads t ON t.id=m.thread_id
                 LEFT JOIN thread_reads r ON r.thread_id=t.id AND r.user_id=:u
                 WHERE (t.user_a=:u OR t.user_b=:u) AND m.id>COALESCE(r.last_read_id,0)
                 AND (m.sender_id IS NULL OR m.sender_id!=:u)""", {'u': uid})['n']


def mark_read(t, uid):
    last = q1('SELECT COALESCE(MAX(id),0) m FROM messages WHERE thread_id=?', (t['id'],))['m']
    ex('INSERT INTO thread_reads(thread_id,user_id,last_read_id) VALUES(?,?,?) ON CONFLICT(thread_id,user_id) DO UPDATE SET last_read_id=MAX(last_read_id,excluded.last_read_id)',
       (t['id'], uid, last))
    if uid != ADMIN_UID:
        ex('UPDATE notifications SET read=1 WHERE user_id=? AND link=? AND read=0', (uid, thread_link(t)))


def thread_link(t):
    if t['kind'] == 'dispute':
        d = q1('SELECT code FROM deals WHERE id=?', (t['deal_id'],))
        return '#/d/' + d['code'] + '/team'
    return '#/chat/' + str(t['id'])


def get_thread(tid):
    t = q1('SELECT * FROM threads WHERE id=?', (int(tid),))
    if not t: raise ApiError('ไม่พบห้องแชทนี้', 404)
    return t


def deal_thread(d, kind, create=True):
    """ห้องแชทของดีล (kind='deal' ผู้ซื้อ↔ผู้ขาย, kind='dispute' ทีมงาน+ทั้งสองฝ่าย)"""
    t = q1('SELECT * FROM threads WHERE deal_id=? AND kind=?', (d['id'], kind))
    if t or not create: return t
    if not (d['seller_id'] and d['buyer_id']): raise ApiError('แชทได้เมื่ออีกฝ่ายกดรับดีลแล้ว')
    if kind == 'dispute' and not d['disputed_at']: raise ApiError('ดีลนี้ไม่มีการแจ้งปัญหา')
    tid = ex('INSERT INTO threads(kind,deal_id,user_a,user_b,created_at,last_at) VALUES(?,?,?,?,?,?)',
             (kind, d['id'], d['seller_id'], d['buyer_id'], now(), now()))
    return get_thread(tid)


def thread_access(t, me):
    if not me or me['id'] not in (t['user_a'], t['user_b']): raise ApiError('คุณไม่ได้อยู่ในห้องแชทนี้', 403)


def thread_closed(t, d):
    if t['kind'] == 'dispute': return not d or d['status'] != 'disputed'
    return False


def msg_role(t, d, sender_id, is_admin):
    if is_admin: return 'admin'
    if t['kind'] == 'shop': return 'shop' if sender_id == t['user_b'] else 'customer'
    if d: return 'seller' if sender_id == d['seller_id'] else 'buyer'
    return None


def thread_view(t, viewer, after=0):
    """viewer = user id หรือ ADMIN_UID"""
    d = q1('SELECT * FROM deals WHERE id=?', (t['deal_id'],)) if t['deal_id'] else None
    users = {u['id']: public_user(u, stats=False) for u in q('SELECT * FROM users WHERE id IN (?,?)', (t['user_a'], t['user_b']))}
    rows = q('SELECT * FROM messages WHERE thread_id=? AND id>? ORDER BY id LIMIT 300', (t['id'], int(after or 0)))
    msgs = []
    for m in rows:
        msgs.append(dict(id=m['id'], text=m['text'] or '', photos=jl(m['photos']), created_at=m['created_at'], is_admin=bool(m['is_admin']),
                         sender_id=m['sender_id'], mine=(m['is_admin'] if viewer == ADMIN_UID else m['sender_id'] == viewer and not m['is_admin']),
                         role=msg_role(t, d, m['sender_id'], m['is_admin']),
                         warn=bool(not m['is_admin'] and CHAT_WARN.search(m['text'] or ''))))
    out = dict(id=t['id'], kind=t['kind'], users=users, messages=msgs, closed=thread_closed(t, d),
               last_id=msgs[-1]['id'] if msgs else int(after or 0))
    if d: out['deal'] = dict(code=d['code'], title=d['title'], status=d['status'], price=d['price'], photo=(jl(d['photos']) or [None])[0],
                             seller_id=d['seller_id'], buyer_id=d['buyer_id'], kind=d['kind'] or 'goods')
    if viewer != ADMIN_UID:
        oid = t['user_b'] if viewer == t['user_a'] else t['user_a']
        out['other'] = users.get(oid)
        out['my_role'] = msg_role(t, d, viewer, False)
    return out


def post_message(t, sender, is_admin, b):
    d = q1('SELECT * FROM deals WHERE id=?', (t['deal_id'],)) if t['deal_id'] else None
    if not is_admin and thread_closed(t, d): raise ApiError('เรื่องนี้ปิดแล้ว ทีมงานตัดสินเรียบร้อย')
    text = s_(b.get('text'), 1000)
    photos = save_files(b.get('photos'), allow=('image',), max_n=4)
    if not text and not photos: raise ApiError('พิมพ์ข้อความหรือแนบรูปก่อนส่ง')
    t0 = now()
    mid = ex('INSERT INTO messages(thread_id,sender_id,is_admin,text,photos,created_at) VALUES(?,?,?,?,?,?)',
             (t['id'], None if is_admin else sender['id'], 1 if is_admin else 0, text, json.dumps(photos), t0))
    ex('UPDATE threads SET last_at=? WHERE id=?', (t0, t['id']))
    snippet = (text[:60] + ('…' if len(text) > 60 else '')) if text else '📷 ส่งรูปภาพ'
    code = d['code'] if d else None
    link = thread_link(t)
    if is_admin:
        for uid in (t['user_a'], t['user_b']):
            notify(uid, code, f'{TEAM_NAME}: {snippet}', 'team', link)
    else:
        mark_read(t, sender['id'])
        other = t['user_b'] if sender['id'] == t['user_a'] else t['user_a']
        if t['kind'] == 'shop' and sender['id'] == t['user_b']: who = sender['shop_name'] or sender['name']
        elif d and sender['id'] == d['seller_id']: who = sender['shop_name'] or sender['name']
        else: who = sender['name']
        where = f' (ข้อพิพาท "{d["title"]}")' if t['kind'] == 'dispute' else (f' · {d["title"]}' if d else ' · ทักจากหน้าร้าน')
        notify(other, code, f'💬 {who}: {snippet}{where}', 'chat', link)
    return mid


@route('POST', r'/api/deals/([A-Z0-9-]+)/thread')
def api_deal_thread(req, me, b, code):
    d = get_deal(code); require_party(d, me)
    kind = 'dispute' if b.get('kind') == 'dispute' else 'deal'
    return {'thread_id': deal_thread(d, kind)['id']}


@route('POST', r'/api/shops/(\d+)/thread')
def api_shop_thread(req, me, b, uid):
    owner = get_user(int(uid))
    if not owner: raise ApiError('ไม่พบร้านนี้', 404)
    if owner['id'] == me['id']: raise ApiError('นี่คือร้านของคุณเอง')
    t = q1("SELECT * FROM threads WHERE kind='shop' AND user_a=? AND user_b=?", (me['id'], owner['id']))
    if not t:
        tid = ex("INSERT INTO threads(kind,user_a,user_b,created_at,last_at) VALUES('shop',?,?,?,?)", (me['id'], owner['id'], now(), now()))
        t = get_thread(tid)
    return {'thread_id': t['id']}


@route('GET', r'/api/threads/(\d+)')
def api_thread(req, me, b, tid):
    t = get_thread(tid); thread_access(t, me)
    out = thread_view(t, me['id'], qs(req).get('after', 0))
    mark_read(t, me['id'])
    return out


@route('POST', r'/api/threads/(\d+)/messages')
def api_thread_post(req, me, b, tid):
    t = get_thread(tid); thread_access(t, me)
    mid = post_message(t, me, False, b)
    return {'ok': True, 'id': mid}


@route('GET', '/api/chats')
def api_chats(req, me, b):
    rows = q("""SELECT t.*, (SELECT MAX(id) FROM messages m WHERE m.thread_id=t.id) last_id FROM threads t
                WHERE (t.user_a=:u OR t.user_b=:u) AND EXISTS(SELECT 1 FROM messages m WHERE m.thread_id=t.id)
                ORDER BY t.last_at DESC LIMIT 100""", {'u': me['id']})
    out = []
    for t in rows:
        oid = t['user_b'] if me['id'] == t['user_a'] else t['user_a']
        o = public_user(get_user(oid), stats=False)
        d = q1('SELECT code,title,status,seller_id,photos FROM deals WHERE id=?', (t['deal_id'],)) if t['deal_id'] else None
        m = q1('SELECT * FROM messages WHERE id=?', (t['last_id'],))
        other_is_shop = (t['kind'] == 'shop' and oid == t['user_b']) or (d and oid == d['seller_id'])
        if t['kind'] == 'dispute':
            name, sub = TEAM_NAME, f'ข้อพิพาท · {d["title"]}'
        else:
            name = o['shop_name'] if other_is_shop else o['name']
            sub = d['title'] if d else ('ทักจากหน้าร้าน' if me['id'] == t['user_a'] else 'ลูกค้าทักหน้าร้านของคุณ')
        who = TEAM_NAME if m['is_admin'] else ('คุณ' if m['sender_id'] == me['id'] else None)
        out.append(dict(id=t['id'], kind=t['kind'], name=name, sub=sub, other=o, deal_code=d['code'] if d else None,
                        deal_status=d['status'] if d else None, link=thread_link(t),
                        last=dict(text=(m['text'] or '📷 รูปภาพ'), who=who, created_at=m['created_at']),
                        unread=thread_unread(t['id'], me['id'])))
    return {'items': out, 'unread': chat_unread(me['id'])}


# ---------------- admin ----------------
@route('POST', '/api/admin/login', auth=False)
def api_admin_login(req, me, b):
    if not secrets.compare_digest(str(b.get('password') or '').encode(), ADMIN_PASSWORD.encode()): raise ApiError('รหัสผ่านไม่ถูกต้อง', 403)
    tok = secrets.token_urlsafe(32)
    ex('INSERT INTO admin_sessions(token,created_at) VALUES(?,?)', (tok, now()))
    req.set_cookie('ds_admin', tok)
    return {'ok': True}


@route('GET', '/api/admin/overview', auth=False, admin=True)
def api_admin_overview(req, me, b):
    process_all()
    def deal_row(d):
        x = {k: d[k] for k in d.keys()}
        for k in ('photos', 'proof_photos', 'dispute_files'): x[k] = jl(d[k])
        x['seller_name'] = (get_user(d['seller_id']) or {'name': '-'})['name'] if d['seller_id'] else '-'
        x['buyer_name'] = (get_user(d['buyer_id']) or {'name': '-'})['name'] if d['buyer_id'] else '-'
        return x
    disputes = []
    for d in q("SELECT * FROM deals WHERE status='disputed' ORDER BY disputed_at"):
        x = deal_row(d)
        t = deal_thread(d, 'dispute')
        x['thread'] = thread_view(t, ADMIN_UID)
        x['thread']['unread'] = thread_unread(t['id'], ADMIN_UID)
        ct = deal_thread(d, 'deal', create=False)
        x['deal_chat'] = thread_view(ct, ADMIN_UID)['messages'] if ct else []
        disputes.append(x)
    recent = [deal_row(d) for d in q("SELECT * FROM deals WHERE is_demo=0 ORDER BY id DESC LIMIT 40")]
    pays = [dict(r) for r in q("""SELECT p.*, u.name, d.code FROM payouts p JOIN users u ON u.id=p.user_id JOIN deals d ON d.id=p.deal_id
                                  WHERE p.status='pending' ORDER BY p.id""")]
    ids = [dict(r) for r in q('SELECT id,name,phone,id_doc,id_verified_at FROM users WHERE id_verified=1 AND is_demo=0 ORDER BY id_verified_at DESC LIMIT 30')]
    held = q1("SELECT COALESCE(SUM(buyer_pay),0) s FROM deals WHERE status IN ('held','shipped','delivered','disputed')")['s']
    return {'disputes': disputes, 'recent': recent, 'payouts': pays, 'ids': ids, 'held_total': held, 'flags': admin_flags(),
            'users': q1('SELECT COUNT(*) n FROM users WHERE is_demo=0')['n']}


def admin_flags():
    """ผู้ขายโดนค่าปรับบ่อย (≥3 ใน 30 วัน) · ผู้ซื้อแพ้ข้อพิพาทบ่อย (≥3 ใน 90 วัน → เสนอระงับบัญชี)"""
    t = now(); out = []
    for kind, n, days in (('penalty', PENALTY_FLAG_N, PENALTY_FLAG_DAYS), ('lost_dispute', LOST_FLAG_N, LOST_FLAG_DAYS)):
        for r in q("""SELECT r.user_id, u.name, u.phone, COUNT(*) n, COALESCE(SUM(r.amount),0) total FROM records r JOIN users u ON u.id=r.user_id
                      WHERE r.kind=? AND r.created_at>=? GROUP BY r.user_id ORDER BY n DESC""", (kind, t - days * DAY)):
            out.append(dict(kind=kind, user_id=r['user_id'], name=r['name'], phone=r['phone'], count=r['n'], total=money(r['total']),
                            days=days, flagged=r['n'] >= n, threshold=n))
    return out


@route('GET', r'/api/admin/threads/(\d+)', auth=False, admin=True)
def api_admin_thread(req, me, b, tid):
    t = get_thread(tid)
    if t['kind'] != 'dispute': raise ApiError('แอดมินดูได้เฉพาะห้องข้อพิพาท', 403)
    out = thread_view(t, ADMIN_UID, qs(req).get('after', 0))
    mark_read(t, ADMIN_UID)
    return out


@route('POST', r'/api/admin/threads/(\d+)/messages', auth=False, admin=True)
def api_admin_thread_post(req, me, b, tid):
    t = get_thread(tid)
    if t['kind'] != 'dispute': raise ApiError('แอดมินส่งได้เฉพาะห้องข้อพิพาท', 403)
    mid = post_message(t, None, True, b)
    mark_read(t, ADMIN_UID)
    return {'ok': True, 'id': mid}


@route('POST', r'/api/admin/deals/([A-Z0-9-]+)/resolve', auth=False, admin=True)
def api_admin_resolve(req, me, b, code):
    d = get_deal(code)
    if not d or d['status'] != 'disputed': raise ApiError('ดีลนี้ไม่ได้อยู่ระหว่างข้อพิพาท')
    dec = b.get('decision'); note = s_(b.get('note'), 300)
    t = dnow(d)
    late_cancel = d['dispute_reason'] == LATE_CANCEL_REASON  # ผู้เข้าพักขอยกเลิกเองหลังช่วงยกเลิกฟรี (ไม่ใช่ความผิดเจ้าของ)
    if dec == 'release':
        ex('UPDATE deals SET resolution=?, resolution_note=? WHERE id=?', ('release', note, d['id']))
        complete(get_deal(code), 'admin')
        if not late_cancel:  # ผู้ซื้อแพ้ข้อพิพาท → บันทึกประวัติ (แอดมินเห็น)
            ex("INSERT INTO records(user_id,deal_id,kind,reason,created_at) VALUES(?,?,'lost_dispute',?,?)", (d['buyer_id'], d['id'], d['dispute_reason'], now()))
    elif dec == 'refund':
        ex("UPDATE deals SET resolution_note=? WHERE id=?", (note, d['id']))
        if late_cancel:
            back, ch = refund_buyer_choice(d, t, 'refund', note)
            notify(d['seller_id'], code, 'ทีมงานตัดสินให้ยกเลิกและคืนเงินผู้เข้าพัก (หักค่าดำเนินการ)' + (f' · {note}' if note else ''), 'warn')
        else:
            refund_seller_fault(d, t, 'refund', note)
            notify(d['buyer_id'], code, f'ทีมงานตัดสินคืนเงินเต็มจำนวน {fmt_baht(d["buyer_pay"])} รวมค่าธรรมเนียม (จำลอง)', 'wallet')
            notify(d['seller_id'], code, 'ทีมงานตัดสินคืนเงินให้ผู้ซื้อ' + (f' · {note}' if note else ''), 'warn')
    elif dec == 'partial':
        try: amt = money(b.get('refund_amount'))
        except Exception: raise ApiError('กรุณากรอกจำนวนเงินที่คืนผู้ซื้อ')
        if not 0 < amt < d['buyer_pay']: raise ApiError(f'จำนวนเงินคืนต้องมากกว่า 0 และน้อยกว่า {fmt_baht(d["buyer_pay"])}')
        sp = partial_split(d['buyer_pay'], amt); pay = sp['pay']
        ex("""UPDATE deals SET status='partial', completed_at=?, refunded_at=?, refund_amount=?, payout_amount=?, resolution='partial',
              resolution_note=?, fee_charged=? WHERE id=?""", (t, t, amt, pay, note, sp['fee'], d['id']))
        if pay > 0: ex('INSERT INTO payouts(user_id,deal_id,amount,created_at) VALUES(?,?,?,?)', (d['seller_id'], d['id'], pay, now()))
        notify(d['buyer_id'], code, f'ทีมงานตัดสินคืนเงินบางส่วน {fmt_baht(amt)} ให้คุณ (จำลอง)', 'wallet')
        notify(d['seller_id'], code, f'ทีมงานตัดสินแบ่งเงิน: คุณได้รับ {fmt_baht(pay)} รอโอนรอบถัดไป', 'wallet')
    else:
        raise ApiError('กรุณาเลือกผลการตัดสิน')
    return {'ok': True}


@route('POST', r'/api/admin/users/(\d+)/socials/verify', auth=False, admin=True)
def api_admin_social_verify(req, me, b, uid):
    """ทีมงานติ๊ก "ตรวจสอบแล้ว" ให้ช่องทางโซเชียลของผู้ใช้ (เช่น เทียบเพจกับบัตร/ทักทางเพจแล้ว)"""
    u = get_user(int(uid))
    if not u: raise ApiError('ไม่พบผู้ใช้', 404)
    d = socials_raw(u); k = b.get('key')
    if k not in SOCIAL_KEYS or not isinstance(d.get(k), dict): raise ApiError('ผู้ใช้ยังไม่ได้ใส่ช่องทางนี้')
    d[k]['verified'] = bool(b.get('verified', True))
    ex('UPDATE users SET socials=? WHERE id=?', (json.dumps(d, ensure_ascii=False), u['id']))
    return {'ok': True, 'socials': socials_view(get_user(u['id']))}


@route('POST', '/api/admin/payouts/run', auth=False, admin=True)
def api_admin_payouts(req, me, b):
    """รอบโอนรายวัน: 1 ครั้ง/วัน/ผู้ขาย รวมทุกดีลที่ปล่อยเงินแล้ว · หักค่าโอนออก 30 บาท (ฟรีเมื่อยอดรวม ≥ 1,000) และค่าปรับค้าง"""
    rows = q("SELECT user_id, SUM(amount) s, COUNT(*) n FROM payouts WHERE status='pending' GROUP BY user_id")
    t = now(); out = []
    for r in rows:
        c = payout_calc(r['s'], penalty_owed(r['user_id']))
        if c['rollover']:  # ยอดรวมไม่พอค่าโอน → ยกไปรวมรอบถัดไป
            notify(r['user_id'], None, f'ยอดรอโอน {fmt_baht(c["gross"])} ยังไม่พอค่าโอนออก {PAYOUT_FEE} บาท · รวมไปโอนรอบถัดไป', 'wallet')
            out.append(dict(user_id=r['user_id'], **c)); continue
        bid = ex('INSERT INTO payout_batches(user_id,gross,transfer_fee,penalty,net,n,created_at) VALUES(?,?,?,?,?,?,?)',
                 (r['user_id'], c['gross'], c['transfer_fee'], c['penalty'], c['net'], r['n'], t))
        ex("UPDATE payouts SET status='paid', paid_at=?, batch_id=? WHERE status='pending' AND user_id=?", (t, bid, r['user_id']))
        left = c['penalty']
        for pr in q("SELECT id, amount, deducted FROM records WHERE user_id=? AND kind='penalty' AND deducted < amount ORDER BY id", (r['user_id'],)):
            if left <= 0: break
            take = money(min(left, pr['amount'] - pr['deducted'])); left = money(left - take)
            ex('UPDATE records SET deducted=? WHERE id=?', (money(pr['deducted'] + take), pr['id']))
        parts = [f'ยอดรวม {fmt_baht(c["gross"])}', 'ค่าโอนออก ฟรี (ยอดรวม ≥ 1,000)' if not c['transfer_fee'] else f'ค่าโอนออก −{fmt_baht(c["transfer_fee"])}']
        if c['penalty']: parts.append(f'ค่าปรับ −{fmt_baht(c["penalty"])}')
        notify(r['user_id'], None, f'โอนเงินรอบวันนี้ {fmt_baht(c["net"])} ({r["n"]} ดีล · {" · ".join(parts)}) เข้าบัญชีแล้ว (จำลอง)', 'wallet')
        out.append(dict(user_id=r['user_id'], batch_id=bid, **c))
    return {'ok': True, 'users': len(rows), 'batches': out}


# ---------------- HTTP ----------------
CT = {'.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
      '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif',
      '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.json': 'application/json', '.ico': 'image/x-icon'}
SPRITE = open(os.path.join(STATIC, 'sprite.html'), encoding='utf-8').read()


# ---- legal pages (/terms, /privacy): render legal/*.md (Markdown subset) into styled HTML ----
LEGAL_DIR = os.path.join(BASE, 'legal')
LEGAL_PAGES = {'/terms': 'terms', '/privacy': 'privacy'}


def _md_inline(s):
    import html as _h
    s = _h.escape(s, quote=False)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    def link(m):
        url = m.group(2)
        if not re.match(r'^(/|https?://)', url): return m.group(1)
        return f'<a href="{_h.escape(url)}">{m.group(1)}</a>'
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, s)
    s = re.sub(r'\[([^\]<>]{2,80})\]', r'<span class="ph-fill">[\1]</span>', s)  # placeholders like [ที่อยู่]
    return s


def md_blocks(lines):
    """แปลง Markdown แบบง่าย (หัวข้อ ##, ย่อหน้า, รายการ -, ตัวหนา, ลิงก์) เป็น HTML"""
    out, para, items = [], [], []
    def flush():
        if para:
            t = ' '.join(para); m = re.match(r'^(\d+\.\d+)\s+(.*)$', t)
            out.append(f'<p><span class="no">{m.group(1)}</span> {_md_inline(m.group(2))}</p>' if m else f'<p>{_md_inline(t)}</p>')
            para.clear()
        if items:
            out.append('<ul>' + ''.join(f'<li>{_md_inline(i)}</li>' for i in items) + '</ul>'); items.clear()
    for ln in lines:
        ln = ln.rstrip()
        if not ln.strip(): flush(); continue
        if ln.startswith('- '):
            if para: flush()
            items.append(ln[2:].strip()); continue
        if items: flush()
        para.append(ln.strip())
    flush()
    return '\n'.join(out)


def render_legal(key):
    src = open(os.path.join(LEGAL_DIR, key + '.md'), encoding='utf-8').read().splitlines()
    title, meta, summary, sections, cur, quote = '', '', '', [], None, []
    for ln in src:
        if ln.startswith('# ') and not title: title = ln[2:].strip(); continue
        if ln.startswith('>'): quote.append(ln[1:].lstrip() if len(ln) > 1 else ''); continue
        if ln.startswith('## '):
            cur = [ln[3:].strip(), []]; sections.append(cur); continue
        if cur is None:
            if ln.strip() and not meta: meta = ln.strip()
            continue
        cur[1].append(ln)
    if quote:
        head = quote[0]; body = quote[1:]
        summary = (f'<section class="card legal-sum" aria-label="สรุปสั้นๆ"><h3><svg width="18" height="18"><use href="#shield"/></svg>'
                   f'{_md_inline(head.replace("**", ""))}</h3>{md_blocks(body)}</section>')
    toc, body = [], []
    for i, (h, ls) in enumerate(sections, 1):
        sid = f's{i}'
        toc.append(f'<li><a href="#{sid}">{_md_inline(re.sub(r"^[0-9]+\.\s*", "", h))}</a></li>')
        body.append(f'<section class="card legal-sec" id="{sid}"><h2>{_md_inline(h)}</h2>{md_blocks(ls)}</section>')
    short = 'ข้อตกลงการใช้บริการ' if key == 'terms' else 'นโยบายความเป็นส่วนตัว'
    tpl = open(os.path.join(STATIC, 'legal.html'), encoding='utf-8').read()
    rep = {'{{TITLE}}': _md_inline(title.replace(' ดีลชัวร์ (DealSure)', '')), '{{META}}': _md_inline(meta),
           '{{DESC}}': f'{short}ของดีลชัวร์ (DealSure) – ตัวกลางพักเงินสำหรับซื้อขายในกลุ่ม Facebook / LINE และจองที่พัก',
           '{{ON_TERMS}}': 'on' if key == 'terms' else '', '{{ON_PRIVACY}}': 'on' if key == 'privacy' else '',
           '{{SUMMARY}}': summary, '{{NSEC}}': str(len(sections)), '{{TOC}}': ''.join(toc), '{{BODY}}': '\n'.join(body),
           '{{OTHER_HREF}}': '/privacy' if key == 'terms' else '/terms',
           '{{OTHER_LABEL}}': 'อ่านนโยบายความเป็นส่วนตัว' if key == 'terms' else 'อ่านข้อตกลงการใช้บริการ',
           '<!--SPRITE-->': SPRITE}
    for k, v in rep.items(): tpl = tpl.replace(k, v)
    return tpl


class H(BaseHTTPRequestHandler):
    server_version = 'DealSure/0.1'

    def log_message(self, fmt, *a):
        if os.environ.get('DEALSURE_LOG'): super().log_message(fmt, *a)

    def cookie(self, name):
        c = SimpleCookie(self.headers.get('Cookie', ''))
        return c[name].value if name in c else None

    def set_cookie(self, name, val, clear=False):
        secure = '; Secure' if self.headers.get('X-Forwarded-Proto') == 'https' else ''
        age = 0 if clear else 30 * DAY
        self._cookies.append(f'{name}={val}; Path=/; HttpOnly; SameSite=Lax; Max-Age={age}{secure}')

    def send(self, status, body, ctype='application/json; charset=utf-8', extra=None):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str): body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-cache')
        for c in getattr(self, '_cookies', []): self.send_header('Set-Cookie', c)
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            try: self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError): pass  # ผู้ใช้ปิดหน้า/เน็ตหลุดระหว่างส่ง

    def do_HEAD(self): self.do_GET()
    def do_GET(self): self.handle_any('GET')
    def do_POST(self): self.handle_any('POST')

    def handle_any(self, method):
        self._cookies = []
        path = unquote(urlparse(self.path).path)
        if path.startswith('/api/'):
            return self.api(method if method != 'HEAD' else 'GET', path)
        if method not in ('GET', 'HEAD'): return self.send(405, {'error': 'method'})
        return self.static(path)

    def api(self, method, path):
        try:
            b = {}
            if method == 'POST':
                n = int(self.headers.get('Content-Length') or 0)
                if n > MAX_BODY: raise ApiError('ไฟล์ใหญ่เกินไป', 413)
                raw = self.rfile.read(n) if n else b''
                b = json.loads(raw or b'{}')
                if not isinstance(b, dict): raise ApiError('ข้อมูลไม่ถูกต้อง')
            for m, rx, fn, auth, admin in ROUTES:
                if m != method: continue
                mt = rx.match(path)
                if not mt: continue
                with LOCK:
                    try:
                        me = None
                        tok = self.cookie('ds_session')
                        if tok:
                            me = q1('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?', (tok,))
                        if auth and not me: raise ApiError('กรุณาเข้าสู่ระบบก่อน', 401)
                        if admin:
                            at = self.cookie('ds_admin')
                            if not at or not q1('SELECT 1 FROM admin_sessions WHERE token=?', (at,)):
                                raise ApiError('กรุณาเข้าสู่ระบบแอดมิน', 401)
                        res = fn(self, me, b, *mt.groups())
                        db.commit()
                    except Exception:
                        db.rollback(); raise
                return self.send(200, res)
            raise ApiError('ไม่พบ API นี้', 404)
        except ApiError as e:
            self.send(e.status, {'error': str(e), **({'field': e.field} if e.field else {})})
        except json.JSONDecodeError:
            self.send(400, {'error': 'ข้อมูลไม่ถูกต้อง'})
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send(500, {'error': 'ระบบขัดข้อง ลองใหม่อีกครั้ง'})

    def static(self, path):
        if path in ('/', '/index.html') or path.startswith('/d/') or path.startswith('/s/'):
            return self.page('index.html')
        lk = LEGAL_PAGES.get(path.rstrip('/') or '/')
        if lk:
            return self.send(200, render_legal(lk), 'text/html; charset=utf-8', {'Cache-Control': 'no-cache'})
        if path in ('/admin', '/admin/'):
            return self.page('admin.html')
        if path == '/favicon.ico': path = '/static/logo/favicon-32.png'
        if path.startswith('/uploads/'):
            name = os.path.basename(path)
            return self.file(os.path.join(UPLOADS, name))
        if path.startswith('/static/'):
            rel = os.path.normpath(path[len('/static/'):])
            if rel.startswith('..') or os.path.isabs(rel): return self.send(404, 'not found', 'text/plain')
            return self.file(os.path.join(STATIC, rel))
        if path == '/healthz': return self.send(200, {'ok': True})
        return self.send(404, 'ไม่พบหน้านี้', 'text/plain; charset=utf-8')

    def page(self, name):
        html = open(os.path.join(STATIC, name), encoding='utf-8').read().replace('<!--SPRITE-->', SPRITE)
        self.send(200, html, 'text/html; charset=utf-8')

    def file(self, fp):
        if not os.path.isfile(fp): return self.send(404, 'not found', 'text/plain')
        ext = os.path.splitext(fp)[1].lower()
        ctype = CT.get(ext, 'application/octet-stream')
        size = os.path.getsize(fp)
        rng = self.headers.get('Range')
        with open(fp, 'rb') as f:
            m = re.match(r'bytes=(\d*)-(\d*)', rng or '')
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else size - 1
                else:
                    start = max(0, size - int(m.group(2))); end = size - 1
                end = min(end, size - 1)
                if start > end: return self.send(416, b'', ctype, {'Content-Range': f'bytes */{size}'})
                f.seek(start); data = f.read(end - start + 1)
                return self.send(206, data, ctype, {'Content-Range': f'bytes {start}-{end}/{size}', 'Accept-Ranges': 'bytes'})
            data = f.read()
        self.send(200, data, ctype, {'Accept-Ranges': 'bytes'})


def ticker():
    while True:
        time.sleep(20)
        try: process_all()
        except Exception as e: print('ticker error', e)


if __name__ == '__main__':
    with LOCK:
        if not q1('SELECT 1 FROM users LIMIT 1'):
            import seed
            seed.run(db)
            db.commit()
            print('ใส่ข้อมูลตัวอย่าง (demo) แล้ว', flush=True)
        else:
            import seed
            if not q1("SELECT 1 FROM users WHERE phone='0800000003'"):
                seed.run_stay(db); db.commit()
                print('เพิ่มที่พักตัวอย่างแล้ว', flush=True)
            if not q1("SELECT 1 FROM deals WHERE code='DS-REV-0001'"):
                seed.run_v4(db); db.commit()
                print('เพิ่มรีวิวตัวอย่าง + ช่องทางโซเชียลตัวอย่างแล้ว (v4)', flush=True)
            if seed.need_v8(db):
                seed.run_v8(db); db.commit()
                print('เพิ่มสินค้าขายประจำตัวอย่างร้านทองแล้ว (v8)', flush=True)
    threading.Thread(target=ticker, daemon=True).start()
    if ADMIN_PASSWORD_GENERATED:
        print(f'[admin] ไม่ได้ตั้ง ADMIN_PASSWORD – สุ่มรหัสผู้ดูแลชั่วคราว: {ADMIN_PASSWORD}', flush=True)
        try:  # เก็บไว้ในเครื่องให้ทดสอบอ่านได้ (data/ ไม่อยู่ใน git)
            fp = os.path.join(DATA, 'admin_password.txt')
            with open(fp, 'w') as f: f.write(ADMIN_PASSWORD)
            os.chmod(fp, 0o600)
        except OSError: pass
    srv = ThreadingHTTPServer((HOST, PORT), H)
    print(f'ดีลชัวร์ (DealSure) prototype กำลังทำงานที่ http://{HOST}:{PORT}  (แอดมิน: /admin, health: /healthz)', flush=True)
    srv.serve_forever()
