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
