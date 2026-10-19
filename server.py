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
MIN_PRICE, MAX_PRICE = 50, 1_000_000
ID_REQUIRED_OVER = 3000
NEW_LIMIT = 5000
LEVELS = [  # key, name, min deals, min stars, max dispute rate, limit/deal
    ('gold', 'ร้านทอง', 100, 4.7, 0.02, 50000),
    ('silver', 'ร้านเงิน', 20, 4.5, 0.05, 20000),
]
PARCEL_TRANSIT = 2 * DAY      # จำลอง: ขนส่งแจ้งของถึงหลังส่ง 2 วัน
PARCEL_RELEASE = 3 * DAY      # ปล่อยเงินอัตโนมัติ 3 วันหลังของถึง
MESSENGER_RELEASE = 1 * DAY   # แมสเซนเจอร์ 24 ชม.
DISPUTE_WINDOW = 3 * DAY
MAX_BODY = 45 * 1024 * 1024
MAX_FILE = 25 * 1024 * 1024
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
            ('products', 'host_contact', 'TEXT'))
    for table, col, typ in cols:
        if col not in [r[1] for r in db.execute(f'PRAGMA table_info({table})')]:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {col} {typ}')
    db.commit()


_migrate()


class ApiError(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status


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
        m = re.match(r'^data:([\w/+.-]+);base64,(.*)$', s, re.S)
        if not m: raise ApiError('ไฟล์ไม่ถูกต้อง')
        mime = m.group(1).lower()
        if mime not in MIME_EXT or mime.split('/')[0] not in allow:
            raise ApiError('รองรับเฉพาะไฟล์รูป' + (' หรือวิดีโอ' if 'video' in allow else ''))
        raw = base64.b64decode(m.group(2))
        if len(raw) > MAX_FILE: raise ApiError('ไฟล์ใหญ่เกินไป (สูงสุด 25 MB)')
        name = secrets.token_hex(12) + MIME_EXT[mime]
        with open(os.path.join(UPLOADS, name), 'wb') as f: f.write(raw)
        out.append('/uploads/' + name)
    return out


# ---------------- users & stats ----------------
def initial(name):
    name = re.sub(r'^(ร้าน|คุณ|น้อง|พี่)\s*', '', name or '?') or name or '?'
    for ch in name:
        if ch not in 'เแโใไ ': return ch
    return '?'


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
    level, level_name, limit = 'new', 'ร้านใหม่', NEW_LIMIT
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
             member_since=u['created_at'], is_demo=bool(u['is_demo']))
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
        if role == 'buyer':
            if d['delivery'] == 'meet': acts.append('meet_enter')
            if overdue: acts.append('late_refund')
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
        for k in ('dispute_files', 'dispute_detail', 'tracking', 'proof_text', 'proof_photos', 'dispute_location'): out[k] = None
    if stay:
        cin = d['checkin_at']
        fcu = cin - (d['free_cancel_days'] or 0) * DAY
        out.update(checkin_day_start=day_start(cin), free_cancel_until=fcu, free_cancel_now=t <= fcu,
                   release_at=d['auto_release_at'] or cin + STAY_RELEASE)
    out.update(my_role=role, actions=acts, deal_now=t, due_ts=due_ts(d['due_date']), overdue=overdue,
               dispute_until=dispute_until, is_creator=bool(uid and d['creator_id'] == uid))
    out['seller'] = public_user(get_user(d['seller_id']))
    out['buyer'] = public_user(get_user(d['buyer_id']))
    out['reviews'] = [dict(r) for r in q('SELECT from_id,to_id,target_role,stars,text,created_at FROM reviews WHERE deal_id=?', (d['id'],))]
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
            raise ApiError(f'วงเงินของ{s["level_name"]}คือ {lim:,} บาท/ดีล — ขายสำเร็จเพิ่มขึ้นเพื่อเลื่อนระดับร้านและปลดล็อกวงเงิน')
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
    out['product_count'] = q1('SELECT COUNT(*) n FROM products WHERE user_id=? AND active=1', (u['id'],))['n']
    return out


def review_list(uid, role, limit):
    sql = """SELECT r.stars,r.text,r.created_at,r.target_role,u.name from_name,u.id from_id,u.avatar from_avatar,d.title
             FROM reviews r JOIN users u ON u.id=r.from_id JOIN deals d ON d.id=r.deal_id WHERE r.to_id=?"""
    a = [uid]
    if role: sql += ' AND r.target_role=?'; a.append(role)
    sql += ' ORDER BY r.created_at DESC LIMIT ?'; a.append(limit)
    return [dict(r) for r in q(sql, a)]


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
    if price < MIN_PRICE: raise ApiError(f'ราคาขั้นต่ำ {MIN_PRICE} บาท')
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
    check_limits(me, role, price)
    photos = save_files(b.get('photos'), max_n=6)
    f = calc_fee(price, fee_payer)
    code = new_code()
    did = ex("""INSERT INTO deals(code,creator_id,creator_role,seller_id,buyer_id,title,description,price,photos,delivery,due_date,
          fee_payer,fee,buyer_fee,seller_fee,buyer_pay,seller_get,status,created_at,kind)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open',?,?)""",
       (code, me['id'], role, me['id'] if role == 'seller' else None, me['id'] if role == 'buyer' else None,
        title, s_(b.get('description'), 500), price, json.dumps(photos), delivery, due, fee_payer,
        f['fee'], f['buyer_fee'], f['seller_fee'], f['buyer_pay'], f['seller_get'], now(), kind))
    if stay: set_stay(did, stay)
    return {'code': code}


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
    if d['delivery'] == 'parcel':
        trk = re.sub(r'\s', '', s_(b.get('tracking'), 40)).upper()
        if not re.fullmatch(r'[A-Z0-9-]{6,40}', trk): raise ApiError('กรุณากรอกเลขพัสดุให้ถูกต้อง (อย่างน้อย 6 ตัว)')
        carrier = b.get('carrier') if b.get('carrier') in CARRIERS else 'อื่น ๆ'
        ex("UPDATE deals SET status='shipped', shipped_at=?, tracking=?, carrier=?, on_time=? WHERE id=?", (t, trk, carrier, on_time, d['id']))
        notify(d['buyer_id'], code, f'ผู้ขายส่งของแล้ว · {carrier} เลขพัสดุ {trk}', 'truck')
    elif d['delivery'] == 'messenger':
        txt = s_(b.get('proof_text'), 300)
        photos = save_files(b.get('photos'), max_n=4)
        if not txt and not photos: raise ApiError('กรุณาแนบหลักฐาน: ลิงก์ติดตามไรเดอร์ หรือรูปตอนส่งของ')
        ex("""UPDATE deals SET status='delivered', shipped_at=?, delivered_at=?, auto_release_at=?, proof_text=?, proof_photos=?, on_time=?
              WHERE id=?""", (t, t, t + MESSENGER_RELEASE, txt, json.dumps(photos), on_time, d['id']))
        notify(d['buyer_id'], code, 'ผู้ขายส่งแมสเซนเจอร์แล้ว ได้ของแล้วกดยืนยัน · ระบบปล่อยเงินอัตโนมัติใน 24 ชม.', 'bike')
    else:
        raise ApiError('ดีลนัดรับ ใช้รหัส 4 หลักแทนการกดส่งของ')
    return {'ok': True}


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
    if not files: raise ApiError('กรุณาแนบคลิปแกะกล่องหรือรูปหลักฐานอย่างน้อย 1 ไฟล์')
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
    ex("UPDATE deals SET status='refunded', refunded_at=?, refund_amount=?, resolution='late', on_time=0 WHERE id=?",
       (dnow(d), d['buyer_pay'], d['id']))
    notify(d['seller_id'], code, f'ดีล "{d["title"]}" ถูกยกเลิก เพราะเลยวันที่ตกลงส่งของ · คืนเงินผู้ซื้อแล้ว', 'warn')
    notify(d['buyer_id'], code, f'คืนเงิน {fmt_baht(d["buyer_pay"])} ให้คุณแล้ว (จำลอง)', 'wallet')
    return {'ok': True}


@route('POST', r'/api/deals/([A-Z0-9-]+)/cancel')
def api_cancel(req, me, b, code):
    d = act(code, me)
    if d['status'] == 'held' and is_stay(d): return stay_cancel(d, me, b)
    if d['status'] not in ('open', 'accepted'): raise ApiError('ยกเลิกได้เฉพาะก่อนจ่ายเงิน')
    if me['id'] not in (d['seller_id'], d['buyer_id']): raise ApiError('คุณไม่ได้อยู่ในดีลนี้', 403)
    ex("UPDATE deals SET status='cancelled', cancelled_at=? WHERE id=?", (dnow(d), d['id']))
    other = d['buyer_id'] if me['id'] == d['seller_id'] else d['seller_id']
    notify(other, code, f'{me["name"]} ยกเลิกดีล "{d["title"]}"', 'warn')
    return {'ok': True}


def stay_cancel(d, me, b):
    """ยกเลิกการจองหลังจ่ายเงินแล้ว: เจ้าของยกเลิก = คืนเต็ม · ผู้เข้าพักยกเลิกในช่วงยกเลิกฟรี = คืนเต็ม · หลังจากนั้น = ส่งทีมงานตัดสิน"""
    r = require_party(d, me)
    t = dnow(d); code = d['code']
    def refund(why):
        ex("UPDATE deals SET status='refunded', refunded_at=?, refund_amount=?, resolution=? WHERE id=?", (t, d['buyer_pay'], why, d['id']))
        notify(d['buyer_id'], code, f'คืนเงิน {fmt_baht(d["buyer_pay"])} ให้คุณเต็มจำนวนแล้ว (จำลอง)', 'wallet')
    if r == 'seller':
        refund('host_cancel')
        notify(d['seller_id'], code, f'คุณยกเลิกการจอง "{d["title"]}" แล้ว · คืนเงินผู้เข้าพักเต็มจำนวน', 'warn')
        notify(d['buyer_id'], code, f'เจ้าของที่พักยกเลิกการจอง "{d["title"]}" · ระบบคืนเงินให้คุณเต็มจำนวน', 'warn')
        return {'ok': True, 'result': 'refunded'}
    if t >= d['checkin_at']: raise ApiError('ถึงเวลาเช็คอินแล้ว ยกเลิกไม่ได้ ถ้ามีปัญหาให้กด "แจ้งปัญหา"')
    if t <= d['checkin_at'] - (d['free_cancel_days'] or 0) * DAY:
        refund('guest_cancel')
        notify(d['seller_id'], code, f'ผู้เข้าพักยกเลิกการจอง "{d["title"]}" ภายในช่วงยกเลิกฟรี · คืนเงินผู้เข้าพักแล้ว', 'warn')
        return {'ok': True, 'result': 'refunded'}
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
    ex('INSERT INTO reviews(deal_id,from_id,to_id,target_role,stars,text,created_at) VALUES(?,?,?,?,?,?,?)',
       (d['id'], me['id'], to, 'seller' if role == 'buyer' else 'buyer', stars, s_(b.get('text'), 300), now()))
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
    out['levels'] = [dict(key=k, name=n, min_deals=a, min_stars=s, max_dispute=round(m * 100), limit=l) for k, n, a, s, m, l in LEVELS]
    return out


@route('POST', '/api/products')
def api_add_product(req, me, b):
    if b.get('kind') == 'stay': return add_stay_product(me, b)
    title = s_(b.get('title'), 120)
    if not title: raise ApiError('กรุณากรอกชื่อสินค้า')
    try: price = money(str(b.get('price')).replace(',', ''))
    except Exception: raise ApiError('กรุณากรอกราคาเป็นตัวเลข')
    if price < MIN_PRICE or price > MAX_PRICE: raise ApiError(f'ราคาต้องอยู่ระหว่าง {MIN_PRICE} – {MAX_PRICE:,} บาท')
    dl = [x for x in (b.get('deliveries') or []) if x in DELIVERIES] or ['parcel']
    fp = b.get('fee_payer') if b.get('fee_payer') in FEE_PAYERS else 'half'
    try: days = max(1, min(int(b.get('ship_days') or 3), 14))
    except Exception: days = 3
    photos = save_files(b.get('photos'), max_n=6)
    pid = ex('INSERT INTO products(user_id,title,description,price,photos,deliveries,fee_payer,ship_days,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
             (me['id'], title, s_(b.get('description'), 500), price, json.dumps(photos), json.dumps(dl), fp, days, now()))
    return {'id': pid}


def add_stay_product(me, b):
    """ที่พักในหน้าร้าน: ราคาต่อคืน · ลูกค้าเลือกวันเช็คอิน/จำนวนคืน/ผู้เข้าพักตอนจอง"""
    st = stay_common(b)
    try: price = money(str(b.get('price')).replace(',', ''))
    except Exception: raise ApiError('กรุณากรอกราคาต่อคืนเป็นตัวเลข')
    if price < MIN_PRICE or price > MAX_PRICE: raise ApiError(f'ราคาต่อคืนต้องอยู่ระหว่าง {MIN_PRICE} – {MAX_PRICE:,} บาท')
    hm = s_(b.get('checkin_time'), 5) or '14:00'
    if not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', hm): raise ApiError('เวลาเช็คอินไม่ถูกต้อง (เช่น 14:00)')
    try: mg = max(1, min(int(b.get('max_guests') or 2), 30))
    except Exception: mg = 2
    fp = b.get('fee_payer') if b.get('fee_payer') in FEE_PAYERS else 'half'
    photos = save_files(b.get('photos'), max_n=6)
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
    pend = sum(r['amount'] for r in rows if r['status'] == 'pending')
    return {'items': [dict(r) for r in rows], 'pending': money(pend)}


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
    return {'disputes': disputes, 'recent': recent, 'payouts': pays, 'ids': ids, 'held_total': held,
            'users': q1('SELECT COUNT(*) n FROM users WHERE is_demo=0')['n']}


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
    if dec == 'release':
        ex('UPDATE deals SET resolution=?, resolution_note=? WHERE id=?', ('release', note, d['id']))
        complete(get_deal(code), 'admin')
    elif dec == 'refund':
        ex("UPDATE deals SET status='refunded', refunded_at=?, refund_amount=?, resolution='refund', resolution_note=? WHERE id=?",
           (t, d['buyer_pay'], note, d['id']))
        notify(d['buyer_id'], code, f'ทีมงานตัดสินคืนเงินเต็มจำนวน {fmt_baht(d["buyer_pay"])} (จำลอง)', 'wallet')
        notify(d['seller_id'], code, 'ทีมงานตัดสินคืนเงินให้ผู้ซื้อ' + (f' · {note}' if note else ''), 'warn')
    elif dec == 'partial':
        try: amt = money(b.get('refund_amount'))
        except Exception: raise ApiError('กรุณากรอกจำนวนเงินที่คืนผู้ซื้อ')
        if not 0 < amt < d['buyer_pay']: raise ApiError(f'จำนวนเงินคืนต้องมากกว่า 0 และน้อยกว่า {fmt_baht(d["buyer_pay"])}')
        pay = money(max(0, d['seller_get'] - amt))
        ex("""UPDATE deals SET status='partial', completed_at=?, refunded_at=?, refund_amount=?, payout_amount=?, resolution='partial',
              resolution_note=? WHERE id=?""", (t, t, amt, pay, note, d['id']))
        if pay > 0: ex('INSERT INTO payouts(user_id,deal_id,amount,created_at) VALUES(?,?,?,?)', (d['seller_id'], d['id'], pay, now()))
        notify(d['buyer_id'], code, f'ทีมงานตัดสินคืนเงินบางส่วน {fmt_baht(amt)} ให้คุณ (จำลอง)', 'wallet')
        notify(d['seller_id'], code, f'ทีมงานตัดสินแบ่งเงิน: คุณได้รับ {fmt_baht(pay)} รอโอนรอบถัดไป', 'wallet')
    else:
        raise ApiError('กรุณาเลือกผลการตัดสิน')
    return {'ok': True}


@route('POST', '/api/admin/payouts/run', auth=False, admin=True)
def api_admin_payouts(req, me, b):
    rows = q("SELECT user_id, SUM(amount) s, COUNT(*) n FROM payouts WHERE status='pending' GROUP BY user_id")
    ex("UPDATE payouts SET status='paid', paid_at=? WHERE status='pending'", (now(),))
    for r in rows:
        notify(r['user_id'], None, f'โอนเงินรอบวันนี้ {fmt_baht(r["s"])} ({r["n"]} ดีล) เข้าบัญชีแล้ว (จำลอง)', 'wallet')
    return {'ok': True, 'users': len(rows)}


# ---------------- HTTP ----------------
CT = {'.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
      '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif',
      '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.json': 'application/json', '.ico': 'image/x-icon'}
SPRITE = open(os.path.join(STATIC, 'sprite.html'), encoding='utf-8').read()


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
            self.send(e.status, {'error': str(e)})
        except json.JSONDecodeError:
            self.send(400, {'error': 'ข้อมูลไม่ถูกต้อง'})
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send(500, {'error': 'ระบบขัดข้อง ลองใหม่อีกครั้ง'})

    def static(self, path):
        if path in ('/', '/index.html') or path.startswith('/d/') or path.startswith('/s/'):
            return self.page('index.html')
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
        elif not q1("SELECT 1 FROM users WHERE phone='0800000003'"):
            import seed
            seed.run_stay(db)
            db.commit()
            print('เพิ่มที่พักตัวอย่างแล้ว', flush=True)
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
