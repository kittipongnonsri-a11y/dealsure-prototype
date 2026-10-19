"""ข้อมูลตัวอย่าง (ปลอมทั้งหมด) สำหรับโหมดทดลอง"""
import json, random, time

DAY = 86400
REVIEWS5 = ['ของตรงปก แพ็คมาดีมาก ส่งไวสุด ๆ 👍', 'ครั้งแรกที่กล้าซื้อจากกลุ่มเฟซ เพราะมีระบบพักเงิน', 'ร้านตอบไว ใจดี แนะนำเลยค่ะ',
            'สภาพดีกว่าที่คิด คุ้มมาก', 'ส่งไว ห่อกันกระแทกอย่างดี', 'ซื้อซ้ำรอบที่สามแล้ว ไม่เคยผิดหวัง', '']
REVIEWS4 = ['สินค้าดี แต่ขนส่งช้าไป 1 วัน ร้านแจ้งล่วงหน้าตลอด', 'โอเคครับ ตามรูป', 'ของดี กล่องบุบนิดหน่อย']
REVIEWS3 = ['พอใช้ได้ สีไม่ค่อยตรงรูป']


def run(db):
    rnd = random.Random(42)
    now = time.time()
    ex = lambda sql, a=(): db.execute(sql, a).lastrowid

    def user(name, phone, age_days, shop=None, bio=None, verified=1):
        return ex('INSERT INTO users(name,phone,created_at,id_verified,id_verified_at,shop_name,shop_bio,is_demo) VALUES(?,?,?,?,?,?,?,1)',
                  (name, phone, now - age_days * DAY, verified, now - age_days * DAY if verified else None, shop, bio))

    gold = user('ป้าแดง (ตัวอย่าง)', '0800000001', 2 * 365 + 120, 'ร้านป้าแดงของสะสม (ตัวอย่าง)', 'กล้องฟิล์ม · ของสะสมวินเทจ · กรุงเทพฯ')
    silver = user('มิ้นท์ (ตัวอย่าง)', '0800000002', 200, 'ร้านมิ้นท์เสื้อผ้ามือสอง (ตัวอย่าง)', 'เสื้อผ้าวินเทจคัดเกรด · เชียงใหม่')
    names = ['คุณก้อย (ตัวอย่าง)', 'บอส_ทดสอบ', 'น้องเมย์ (ตัวอย่าง)', 'พี่ต้น (ตัวอย่าง)', 'ลูกค้าทดสอบ 05', 'แนน (ตัวอย่าง)',
             'ลูกค้าทดสอบ 07', 'เจ (ตัวอย่าง)', 'ลูกค้าทดสอบ 09', 'ปอนด์ (ตัวอย่าง)', 'ลูกค้าทดสอบ 11', 'ฝน (ตัวอย่าง)']
    buyers = [user(n, f'08990000{i + 1:02d}', rnd.randint(30, 600), verified=0) for i, n in enumerate(names)]

    P = lambda x: json.dumps(['/static/demo/' + x + '.svg'])
    prods = [
        (gold, 'กล้องฟิล์ม Olympus มือสอง (ตัวอย่าง)', 'สภาพ 90% · พร้อมสายคล้อง · ทดสอบฟิล์มแล้ว', 2500, 'camera', ['parcel', 'meet'], 2),
        (gold, 'วิทยุทรานซิสเตอร์วินเทจ (ตัวอย่าง)', 'เปิดติด เสียงดี ตัวเครื่องมีรอยตามอายุ', 1890, 'radio', ['parcel', 'messenger'], 3),
        (gold, 'แผ่นเสียงลูกกรุง ชุดสะสม (ตัวอย่าง)', '5 แผ่น ปกสวย แผ่นไม่มีรอยลึก', 750, 'vinyl', ['parcel', 'meet', 'messenger'], 2),
        (gold, 'นาฬิกาไขลานมือสอง (ตัวอย่าง)', 'เดินตรง ล้างเครื่องแล้ว · ราคาเกิน 3,000 ต้องยืนยันตัวตน', 3200, 'watch', ['parcel', 'meet'], 3),
        (gold, 'เลนส์ 50mm f/1.4 (ตัวอย่าง)', 'ใสไม่มีฝ้า · ใช้ทดสอบวงเงินผู้ใช้ใหม่ (เกิน 5,000)', 6500, 'lens', ['parcel', 'meet'], 3),
        (gold, 'กล่องฟิล์มมือสอง ชุด 5 ม้วน (ตัวอย่าง)', 'ฟิล์มหมดอายุเล็กน้อย · ขายเป็นชุด', 420, 'box-dent', ['parcel', 'messenger'], 2),
        (gold, 'กระเป๋ากล้องหนังวินเทจ (ตัวอย่าง)', 'หนังแท้ มีรอยตามอายุ · สะพายได้', 980, 'bag', ['parcel', 'meet'], 2),
        (gold, 'กาแฟคั่วบดดอยวาวี ถุงใหญ่ (ตัวอย่าง)', 'คั่วกลาง · กลิ่นหอม · ถุง 500 กรัม', 320, 'coffee', ['parcel', 'messenger'], 2),
        (silver, 'เสื้อเชิ้ตวินเทจ ลายดอก (ตัวอย่าง)', 'อก 42 · ผ้าคอตตอน', 350, 'shirt', ['parcel', 'messenger'], 2),
        (silver, 'กระเป๋าผ้าแคนวาส (ตัวอย่าง)', 'สีเขียวมิ้นต์ · ใบใหญ่', 590, 'bag', ['parcel', 'meet'], 2),
    ]
    pids = {}
    for uid, t, desc, price, img, dl, days in prods:
        pids[img] = ex('INSERT INTO products(user_id,title,description,price,photos,deliveries,fee_payer,ship_days,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                       (uid, t, desc, price, P(img), json.dumps(dl), 'half', days, now - rnd.randint(5, 90) * DAY))

    n = [0]
    def deal(seller, age_days, img, title, price, stars_w, status='completed', disputed=False, on_time=1):
        n[0] += 1
        b = rnd.choice(buyers)
        t0 = now - age_days * DAY
        fee = round(max(20, price * 0.02), 2); bf = round(fee / 2, 2); sf = round(fee - bf, 2)
        dlv = rnd.choice(['parcel', 'parcel', 'parcel', 'meet', 'messenger'])
        due = time.strftime('%Y-%m-%d', time.localtime(t0 + 3 * DAY))
        did = ex("""INSERT INTO deals(code,creator_id,creator_role,seller_id,buyer_id,source,title,price,photos,delivery,due_date,fee_payer,fee,
                buyer_fee,seller_fee,buyer_pay,seller_get,status,on_time,created_at,accepted_at,paid_at,shipped_at,delivered_at,completed_at,
                refunded_at,release_reason,disputed_at,dispute_reason,resolution,refund_amount,payout_amount,is_demo)
                VALUES(?,?,?,?,?,'shop',?,?,?,?,?,'half',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                 (f'DS-TEST-{n[0]:04d}', b, 'buyer', seller, b, title, price, P(img), dlv, due, fee, bf, sf, price + bf, price - sf,
                  status, on_time, t0, t0, t0 + 600, t0 + DAY, t0 + 2 * DAY,
                  t0 + 3 * DAY if status == 'completed' else None, t0 + 4 * DAY if status == 'refunded' else None,
                  'buyer_confirm' if status == 'completed' else None, t0 + 2.5 * DAY if disputed else None,
                  'ของเสียหาย' if disputed else None, ('release' if status == 'completed' else 'refund') if disputed else None,
                  price + bf if status == 'refunded' else None, price - sf if status == 'completed' else None))
        if stars_w and status == 'completed' and rnd.random() < 0.85:
            s = rnd.choices([5, 4, 3], weights=stars_w)[0]
            txt = rnd.choice(REVIEWS5 if s == 5 else REVIEWS4 if s == 4 else REVIEWS3)
            ex('INSERT INTO reviews(deal_id,from_id,to_id,target_role,stars,text,created_at) VALUES(?,?,?,?,?,?,?)',
               (did, b, seller, 'seller', s, txt, t0 + 3.2 * DAY))
            if rnd.random() < 0.5:
                ex('INSERT INTO reviews(deal_id,from_id,to_id,target_role,stars,text,created_at) VALUES(?,?,?,?,?,?,?)',
                   (did, seller, b, 'buyer', 5, 'ผู้ซื้อจ่ายไว คุยง่าย', t0 + 3.3 * DAY))
            ex('INSERT INTO payouts(user_id,deal_id,amount,status,created_at,paid_at) VALUES(?,?,?,?,?,?)',
               (seller, did, price - sf, 'paid', t0 + 3 * DAY, t0 + 3.4 * DAY))

    gold_items = [('camera', 'กล้องฟิล์ม (ตัวอย่าง)', 2500), ('radio', 'วิทยุวินเทจ (ตัวอย่าง)', 1890),
                  ('vinyl', 'แผ่นเสียงลูกกรุง (ตัวอย่าง)', 750), ('watch', 'นาฬิกาไขลาน (ตัวอย่าง)', 3200)]
    for i in range(130):
        img, t, p = rnd.choice(gold_items)
        deal(gold, 840 - i * 6.3, img, t, p, [92, 7, 1], on_time=0 if i % 45 == 7 else 1)
    deal(gold, 300, 'radio', 'วิทยุวินเทจ (ตัวอย่าง)', 1890, None, status='completed', disputed=True)
    deal(gold, 120, 'camera', 'กล้องฟิล์ม (ตัวอย่าง)', 2500, None, status='refunded', disputed=True)
    sil_items = [('shirt', 'เสื้อเชิ้ตวินเทจ (ตัวอย่าง)', 350), ('bag', 'กระเป๋าผ้า (ตัวอย่าง)', 590)]
    for i in range(26):
        img, t, p = rnd.choice(sil_items)
        deal(silver, 190 - i * 7, img, t, p, [72, 20, 8], on_time=0 if i % 9 == 3 else 1)
    deal(silver, 60, 'shirt', 'เสื้อเชิ้ตวินเทจ (ตัวอย่าง)', 350, None, status='refunded', disputed=True)
    run_stay(db)
    run_v4(db)


STAY_REVIEWS5 = ['ที่พักตรงปกมาก วิวดอยสวยกว่าในรูป เจ้าของใจดี', 'จองผ่านดีลชัวร์ สบายใจ เช็คอินแล้วค่อยปล่อยเงิน', 'ห้องสะอาด เงียบสงบ เหมาะกับพักผ่อน',
                 'เจ้าของวิดีโอคอลโชว์ห้องก่อนจอง ตรงตามจริงทุกอย่าง', 'อาหารเช้าอร่อย จะกลับมาอีกแน่นอน', '']
STAY_REVIEWS4 = ['ห้องดี แต่ทางขึ้นชันนิดนึง ขับรถระวังหน่อย', 'โอเคค่ะ ตามรูป น้ำอุ่นมาช้านิดหน่อย']


def run_stay(db):
    """เจ้าของที่พักตัวอย่าง (ปลอม) + ที่พักในหน้าร้าน + ประวัติการเข้าพักที่สำเร็จ (ให้เห็นระดับ/สถิติ)"""
    rnd = random.Random(7)
    now = time.time()
    ex = lambda sql, a=(): db.execute(sql, a).lastrowid
    host = ex('INSERT INTO users(name,phone,created_at,id_verified,id_verified_at,shop_name,shop_bio,is_demo) VALUES(?,?,?,?,?,?,?,1)',
              ('พี่ปุ้ย (ตัวอย่าง)', '0800000003', now - 540 * DAY, 1, now - 530 * DAY, 'บ้านพักริมดอย แม่ริม (ตัวอย่าง)',
               'โฮมสเตย์ริมดอย · แม่ริม เชียงใหม่ · เจ้าของดูแลเอง (ข้อมูลตัวอย่าง)'))
    guests = [r[0] for r in db.execute("SELECT id FROM users WHERE is_demo=1 AND shop_name IS NULL ORDER BY id LIMIT 12").fetchall()]
    if not guests:
        guests = [ex('INSERT INTO users(name,phone,created_at,is_demo) VALUES(?,?,?,1)', (f'แขกทดสอบ {i + 1:02d}', f'08991000{i + 1:02d}', now - 200 * DAY))
                  for i in range(6)]
    P = lambda x: json.dumps(['/static/demo/' + x + '.svg'])
    MAP = 'https://www.google.com/maps/search/?api=1&query=18.9167,98.9333'
    stays = [('บ้านไม้ริมดอย ห้องวิวภูเขา (ตัวอย่าง)', 'ห้องนอนใหญ่ 1 ห้อง · ระเบียงวิวดอย · อาหารเช้า · ที่จอดรถ', 1290, 'house', 4),
             ('กระท่อมกลางสวน สำหรับ 2 คน (ตัวอย่าง)', 'เตียงคิงไซซ์ · อ่างอาบน้ำกลางแจ้ง · เงียบสงบ', 1890, 'cabin', 2)]
    for t, desc, price, img, mg in stays:
        ex("""INSERT INTO products(user_id,title,description,price,photos,deliveries,fee_payer,ship_days,created_at,kind,address,map_url,
              checkin_time,max_guests,free_cancel_days,host_contact) VALUES(?,?,?,?,?,'["stay"]','half',0,?,'stay',?,?,'14:00',?,3,?)""",
           (host, t, desc, price, P(img), now - 120 * DAY, '99 หมู่ 5 ต.ริมเหนือ อ.แม่ริม จ.เชียงใหม่ (ที่อยู่ตัวอย่าง)', MAP, mg, 'พี่ปุ้ย (ตัวอย่าง)'))
    for i in range(34):
        t, desc, ppn, img, mg = stays[i % 2]
        nights = rnd.choice([1, 2, 2, 3]); price = ppn * nights
        g = rnd.choice(guests)
        t0 = now - (500 - i * 14) * DAY
        cin = t0 + 10 * DAY
        fee = round(max(20, price * 0.02), 2); bf = round(fee / 2, 2); sf = round(fee - bf, 2)
        due = time.strftime('%Y-%m-%d', time.localtime(cin))
        did = ex("""INSERT INTO deals(code,creator_id,creator_role,seller_id,buyer_id,source,title,description,price,photos,delivery,due_date,fee_payer,fee,
                buyer_fee,seller_fee,buyer_pay,seller_get,status,created_at,accepted_at,paid_at,completed_at,release_reason,payout_amount,is_demo,
                kind,address,map_url,checkin_at,checkout_date,nights,guests,host_contact,free_cancel_days,auto_release_at)
                VALUES(?,?,'buyer',?,?,'shop',?,?,?,?,'stay',?,'half',?,?,?,?,?,'completed',?,?,?,?,?,?,1,'stay',?,?,?,?,?,?,?,3,?)""",
                 (f'DS-STAY-{i + 1:04d}', g, host, g, t, desc, price, P(img), due, fee, bf, sf, price + bf, price - sf,
                  t0, t0, t0 + 600, cin + 1800, 'guest_checkin' if i % 5 else 'checkin_code', price - sf,
                  '99 หมู่ 5 ต.ริมเหนือ อ.แม่ริม จ.เชียงใหม่ (ที่อยู่ตัวอย่าง)', MAP, cin,
                  time.strftime('%Y-%m-%d', time.localtime(cin + nights * DAY)), nights, rnd.randint(1, mg), 'พี่ปุ้ย (ตัวอย่าง)', cin + DAY))
        if rnd.random() < 0.9:
            s = rnd.choices([5, 4], weights=[88, 12])[0]
            ex('INSERT INTO reviews(deal_id,from_id,to_id,target_role,stars,text,created_at) VALUES(?,?,?,?,?,?,?)',
               (did, g, host, 'seller', s, rnd.choice(STAY_REVIEWS5 if s == 5 else STAY_REVIEWS4), cin + 2 * DAY))
        ex('INSERT INTO payouts(user_id,deal_id,amount,status,created_at,paid_at) VALUES(?,?,?,?,?,?)',
           (host, did, price - sf, 'paid', cin + 1800, cin + 0.4 * DAY))


# ---------------- v4: ช่องทางโซเชียลตัวอย่าง + รีวิวตัวอย่างที่หลากหลาย (มีรูป · ยาว · ติชม 1–3 ดาว · สินค้า/ที่พัก) ----------------
def _soc(**kw):
    """kw: key=(h, url, edit, verified) – ข้อมูลตัวอย่าง (ลิงก์ปลอม/โดเมน .example)"""
    return json.dumps({k: dict(h=v[0], u=v[1], e=v[2], verified=v[3]) for k, v in kw.items()}, ensure_ascii=False)


SOCIALS_V4 = {
    '0800000001': _soc(
        facebook=('dealsure.demo.padaeng', 'https://www.facebook.com/dealsure.demo.padaeng', 'dealsure.demo.padaeng', True),
        line=('@demo-padaeng', 'https://line.me/R/ti/p/@demo-padaeng', '@demo-padaeng', False),
        instagram=('@demo.padaeng.vintage', 'https://www.instagram.com/demo.padaeng.vintage/', '@demo.padaeng.vintage', False),
        tiktok=('@demo.padaeng', 'https://www.tiktok.com/@demo.padaeng', '@demo.padaeng', False),
        website=('padaeng.dealsure.example', 'https://padaeng.dealsure.example', 'https://padaeng.dealsure.example', False),
        phone=('080-000-0001', 'tel:+66800000001', '080-000-0001', False)),
    '0800000002': _soc(
        facebook=('กลุ่ม Facebook', 'https://www.facebook.com/groups/dealsure.demo.vintage', 'https://www.facebook.com/groups/dealsure.demo.vintage', False),
        line=('mint.demo', 'https://line.me/ti/p/~mint.demo', 'mint.demo', False),
        instagram=('@demo.mint.secondhand', 'https://www.instagram.com/demo.mint.secondhand/', '@demo.mint.secondhand', False)),
    '0800000003': _soc(
        facebook=('dealsure.demo.baanrimdoi', 'https://www.facebook.com/dealsure.demo.baanrimdoi', 'dealsure.demo.baanrimdoi', False),
        line=('@demo-baanrimdoi', 'https://line.me/R/ti/p/@demo-baanrimdoi', '@demo-baanrimdoi', True),
        youtube=('@demo-baanrimdoi', 'https://www.youtube.com/@demo-baanrimdoi', '@demo-baanrimdoi', False),
        phone=('080-000-0003', 'tel:+66800000003', '080-000-0003', False)),
}

PH = lambda *xs: json.dumps(['/static/demo/' + x + '.svg' for x in xs])
# (อายุวัน, ดาว, ข้อความ, รูป, สินค้า, ราคา, รูปสินค้า)
GOLD_V4 = [
    (2, 5, 'กล้องสภาพดีมากครับ ร้านอัดวิดีโอทดสอบชัตเตอร์ให้ดูก่อนส่ง แพ็คกันกระแทกสามชั้น ฟิล์มม้วนแรกออกมาสวยทุกรูป จ่ายผ่านดีลชัวร์อุ่นใจมาก ได้ของค่อยกดปล่อยเงิน (รีวิวตัวอย่าง)',
     ('camera', 'box-dent'), 'กล้องฟิล์ม (ตัวอย่าง)', 2500, 'camera'),
    (5, 2, 'ของมาถึงกล่องบุบ ฝาหลังมีรอยที่ไม่ได้แจ้งในประกาศ ทักร้านแล้วร้านเสนอคืนเงินบางส่วนให้ แต่ส่งช้ากว่ากำหนด 2 วัน อยากให้ถ่ายรูปตำหนิให้ครบกว่านี้ (รีวิวตัวอย่าง)',
     ('box-dent',), 'วิทยุวินเทจ (ตัวอย่าง)', 1890, 'radio'),
    (9, 4, 'นาฬิกาเดินตรงดี สายหนังเก่ากว่าในรูปนิดหน่อย แต่ร้านแถมสายใหม่ให้ ใจดีค่ะ (รีวิวตัวอย่าง)', ('watch',), 'นาฬิกาไขลาน (ตัวอย่าง)', 3200, 'watch'),
    (14, 3, 'แผ่นเสียงเล่นได้ แต่มีเสียงซ่าแผ่นที่ 3 มากกว่าที่คิด ราคาโอเค (รีวิวตัวอย่าง)', (), 'แผ่นเสียงลูกกรุง (ตัวอย่าง)', 750, 'vinyl'),
    (21, 5, 'ซื้อเลนส์ราคาสูงครั้งแรกแบบไม่ต้องกลัวโดนโกง ร้านส่งเลขพัสดุไวมาก เลนส์ใสไม่มีฝ้าตามที่บอกจริง ๆ (รีวิวตัวอย่าง)', ('lens',), 'เลนส์ 50mm (ตัวอย่าง)', 6500, 'lens'),
    (40, 1, 'รอของนานมาก ร้านตอบช้า สุดท้ายได้ของแต่ไม่ตรงรุ่นที่คุยไว้ ต้องเปิดข้อพิพาท ทีมงานช่วยตัดสินให้ (รีวิวตัวอย่าง)', (), 'วิทยุวินเทจ (ตัวอย่าง)', 1890, 'radio'),
    (60, 5, 'แผ่นเสียงปกสวยมาก เก็บรักษามาดี ฟังเพลงลูกกรุงทั้งคืนเลย (รีวิวตัวอย่าง)', ('vinyl',), 'แผ่นเสียงลูกกรุง (ตัวอย่าง)', 750, 'vinyl'),
    (75, 3, 'กล้องใช้ได้ แต่ช่องมองภาพมีฝุ่นนิดหน่อย (รีวิวตัวอย่าง)', ('camera',), 'กล้องฟิล์ม (ตัวอย่าง)', 2500, 'camera'),
]
SILVER_V4 = [
    (3, 5, 'เสื้อผ้าคอตตอนนุ่ม ไซซ์ตรงตามที่วัดให้ ซักแล้วสีไม่ตก ร้านถ่ายรูปจริงให้ดูหลายมุม (รีวิวตัวอย่าง)', ('shirt',), 'เสื้อเชิ้ตวินเทจ (ตัวอย่าง)', 350, 'shirt'),
    (8, 2, 'กระเป๋ามีคราบที่ก้นใบ ไม่ได้บอกไว้ในโพสต์ ร้านขอโทษและลดราคาให้ (รีวิวตัวอย่าง)', ('bag',), 'กระเป๋าผ้า (ตัวอย่าง)', 590, 'bag'),
    (30, 4, 'ของดี ส่งไว แพ็คเรียบร้อย (รีวิวตัวอย่าง)', (), 'กระเป๋าผ้า (ตัวอย่าง)', 590, 'bag'),
]
HOST_GOODS_V4 = [
    (4, 5, 'กาแฟดอยคั่วเองหอมมาก เจ้าของบ้านพักส่งมาพร้อมโน้ตวิธีชง แพ็คถุงซิปมีวาล์ว (รีวิวตัวอย่าง)', ('coffee',), 'กาแฟดอยคั่วเอง 500 กรัม (ตัวอย่าง)', 420, 'coffee'),
    (18, 3, 'กาแฟอร่อย แต่ส่งช้าไป 2 วัน (รีวิวตัวอย่าง)', (), 'กาแฟดอยคั่วเอง 500 กรัม (ตัวอย่าง)', 420, 'coffee'),
    (45, 5, 'สั่งรอบที่สองแล้ว คั่วกลางกำลังดี (รีวิวตัวอย่าง)', ('coffee',), 'กาแฟดอยคั่วเอง 1 กก. (ตัวอย่าง)', 790, 'coffee'),
    (70, 4, 'หอมดีครับ ถุงใหญ่คุ้ม (รีวิวตัวอย่าง)', (), 'กาแฟดอยคั่วเอง 1 กก. (ตัวอย่าง)', 790, 'coffee'),
]
HOST_STAY_V4 = [
    (6, 5, 'ห้องวิวดอยสวยกว่าในรูปอีก ตื่นมาเจอทะเลหมอก เจ้าของเตรียมผ้าห่มเพิ่มให้ เช็คอินด้วยรหัส 4 หลักง่ายมาก เงินปล่อยหลังเราเข้าห้องได้จริง สบายใจ (รีวิวตัวอย่าง)',
     ('room', 'house'), 'บ้านไม้ริมดอย ห้องวิวภูเขา (ตัวอย่าง)', 2580, 'house'),
    (12, 2, 'ห้องโอเค แต่ทางขึ้นชันมาก รถเก๋งขึ้นลำบาก ไม่มีบอกในประกาศ ไฟทางเดินดับ 1 ดวง (รีวิวตัวอย่าง)', ('cabin',), 'กระท่อมกลางสวน สำหรับ 2 คน (ตัวอย่าง)', 1890, 'cabin'),
    (25, 3, 'น้ำอุ่นไม่ค่อยแรง นอกนั้นตรงปก (รีวิวตัวอย่าง)', (), 'บ้านไม้ริมดอย ห้องวิวภูเขา (ตัวอย่าง)', 1290, 'house'),
]


def run_v4(db):
    now = time.time()
    ex = lambda sql, a=(): db.execute(sql, a).lastrowid
    one = lambda sql, a=(): db.execute(sql, a).fetchone()
    for ph, soc in SOCIALS_V4.items():
        db.execute('UPDATE users SET socials=? WHERE phone=? AND is_demo=1', (soc, ph))
    buyers = [r[0] for r in db.execute("SELECT id FROM users WHERE is_demo=1 AND shop_name IS NULL ORDER BY id").fetchall()]
    if not buyers: return
    n = [0]

    def add(seller, rows, kind='goods'):
        for i, (age, stars, txt, photos, title, price, img) in enumerate(rows):
            n[0] += 1
            b = buyers[(n[0] * 5) % len(buyers)]
            t0 = now - (age + 4) * 86400
            fee = round(max(20, price * 0.02), 2); bf = round(fee / 2, 2); sf = round(fee - bf, 2)
            due = time.strftime('%Y-%m-%d', time.localtime(t0 + 3 * 86400))
            did = ex("""INSERT INTO deals(code,creator_id,creator_role,seller_id,buyer_id,source,title,price,photos,delivery,due_date,fee_payer,fee,
                    buyer_fee,seller_fee,buyer_pay,seller_get,status,on_time,created_at,accepted_at,paid_at,shipped_at,delivered_at,completed_at,
                    release_reason,payout_amount,is_demo,kind) VALUES(?,?,'buyer',?,?,'link',?,?,?,?,?,'half',?,?,?,?,?,'completed',?,?,?,?,?,?,?,'buyer_confirm',?,1,?)""",
                     (f'DS-REV-{n[0]:04d}', b, seller, b, title, price, PH(img), 'stay' if kind == 'stay' else 'parcel', due, fee, bf, sf,
                      price + bf, price - sf, None if kind == 'stay' else (0 if stars <= 2 else 1), t0, t0, t0 + 600,
                      None if kind == 'stay' else t0 + 86400, None if kind == 'stay' else t0 + 2 * 86400, t0 + 3 * 86400, price - sf, kind))
            ex('INSERT INTO reviews(deal_id,from_id,to_id,target_role,stars,text,photos,created_at) VALUES(?,?,?,?,?,?,?,?)',
               (did, b, seller, 'seller', stars, txt, PH(*photos) if photos else '[]', now - age * 86400))
            ex("INSERT INTO payouts(user_id,deal_id,amount,status,created_at,paid_at) VALUES(?,?,?,'paid',?,?)",
               (seller, did, price - sf, t0 + 3 * 86400, t0 + 3.4 * 86400))

    uid = lambda ph: (one('SELECT id FROM users WHERE phone=? AND is_demo=1', (ph,)) or [None])[0]
    gold, silver, host = uid('0800000001'), uid('0800000002'), uid('0800000003')
    if gold: add(gold, GOLD_V4)
    if silver: add(silver, SILVER_V4)
    if host:
        add(host, HOST_GOODS_V4)
        add(host, HOST_STAY_V4, 'stay')


# ---- v8: สินค้าขายประจำเพิ่มในร้านทอง (สำหรับฐานข้อมูลเดิมที่มีสินค้าน้อย) ----
GOLD_V8_EXTRA = [
    ('กล่องฟิล์มมือสอง ชุด 5 ม้วน (ตัวอย่าง)', 'ฟิล์มหมดอายุเล็กน้อย · ขายเป็นชุด', 420, 'box-dent', ['parcel', 'messenger'], 2),
    ('กระเป๋ากล้องหนังวินเทจ (ตัวอย่าง)', 'หนังแท้ มีรอยตามอายุ · สะพายได้', 980, 'bag', ['parcel', 'meet'], 2),
    ('กาแฟคั่วบดดอยวาวี ถุงใหญ่ (ตัวอย่าง)', 'คั่วกลาง · กลิ่นหอม · ถุง 500 กรัม', 320, 'coffee', ['parcel', 'messenger'], 2),
]


def need_v8(db):
    row = db.execute("SELECT id FROM users WHERE phone='0800000001'").fetchone()
    if not row: return False
    n = db.execute("SELECT COUNT(*) FROM products WHERE user_id=? AND active=1 AND COALESCE(kind,'goods')!='stay'", (row[0],)).fetchone()[0]
    return n < 6


def run_v8(db):
    """เติมสินค้าขายประจำให้ร้านป้าแดง (ทอง) ถ้ายังมีน้อยกว่า 6 ชิ้น"""
    import json, time
    rnd = __import__('random').Random(88)
    now = time.time()
    DAY = 86400
    row = db.execute("SELECT id FROM users WHERE phone='0800000001'").fetchone()
    if not row: return
    gold = row[0]
    have = {r[0] for r in db.execute("SELECT title FROM products WHERE user_id=? AND active=1", (gold,))}
    P = lambda x: json.dumps(['/static/demo/' + x + '.svg'])
    for title, desc, price, img, dl, days in GOLD_V8_EXTRA:
        if title in have: continue
        db.execute('INSERT INTO products(user_id,title,description,price,photos,deliveries,fee_payer,ship_days,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                   (gold, title, desc, price, P(img), json.dumps(dl), 'half', days, now - rnd.randint(3, 40) * DAY))
