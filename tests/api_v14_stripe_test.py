"""v14: Stripe TEST mode สำหรับจ่ายบัตร (Checkout + คืนเงินจริงใน test mode)
ต้องเปิดเซิร์ฟเวอร์ในเครื่องด้วย STRIPE_TEST_SECRET_KEY=sk_test_... และ DEALSURE_STRIPE_DEV=1
ถ้าเซิร์ฟเวอร์ไม่ได้เปิด Stripe → ทดสอบว่ายังใช้โหมดจำลองได้ตามเดิม
วิธีรัน: python3 tests/api_v14_stripe_test.py [http://localhost:8787]   (ห้ามรันกับเว็บจริง)"""
import os, sys, time
sys.argv = sys.argv[:2]
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'api_test.py'), encoding='utf-8').read().split('\nA, B, X = C(), C(), C()')[0]
exec(compile(src, 'api_test_helpers', 'exec'))
if not BASE.startswith(('http://localhost', 'http://127.0.0.1')): sys.exit('รันกับเซิร์ฟเวอร์ในเครื่องเท่านั้น')
def r2(x): return round(x + 1e-9, 2)
def surcharge(p): return r2(p * 0.04 + 11)
def cancel_ch(p, cf=0): return r2(min(p, max(10, p * 0.02, (p * 3.9055 / 100 + 10.70) + 5 if cf else p * 1.77 / 100 + 5)))

stamp = str(int(time.time()))[-6:]
S, B, ADM = C(), C(), C()
S.login('ผู้ขาย v14', '087' + stamp + '1'); B.login('ผู้ซื้อ v14', '088' + stamp + '2')
ADM.ok('/admin/login', {'password': admin_password()})
def accepted(**kw):
    code = new_deal(S, **kw); B.ok(f'/deals/{code}/accept', {}); return code

c = accepted(price=1000, fee_payer='buyer')
d = deal(B, c); on = d['stripe']['enabled']
print('Stripe เปิดอยู่:', on)
if not on:
    B.ok(f'/deals/{c}/pay', {'method': 'card'})
    check('ไม่มีคีย์ → จ่ายบัตรแบบจำลองได้ตามเดิม', deal(B, c)['status'] == 'held')
    s, e = B.req(f'/deals/{accepted()}/stripe-checkout', {})
    check('ไม่มีคีย์ → สร้าง Checkout ไม่ได้ (503)', s == 503, e)
else:
    paid = d['buyer_pay']; cf = surcharge(paid); total = r2(paid + cf)
    print('1) Checkout Session')
    s, e = B.req(f'/deals/{c}/pay', {'method': 'card'})
    check('มีคีย์ → /pay แบบบัตรจำลองถูกปิด (409)', s == 409, e)
    s, e = S.req(f'/deals/{c}/stripe-checkout', {})
    check('ผู้ขายสร้าง Checkout แทนผู้ซื้อไม่ได้', s in (400, 403), e)
    r = B.ok(f'/deals/{c}/stripe-checkout', {})
    check('สร้าง Checkout Session ได้ (cs_test_ + URL checkout.stripe.com)', r['session_id'].startswith('cs_test_') and 'checkout.stripe.com' in r['url'], r['session_id'])
    check(f'ยอด Checkout = {total} (ยอดดีล {paid} + ค่าบัตร {cf})', r['amount'] == total, r['amount'])
    r2_ = B.ok(f'/deals/{c}/stripe-confirm', {'session_id': r['session_id']})
    check('ดึง session จาก Stripe ได้ · ยังไม่จ่าย → ไม่ปล่อยสถานะ held', r2_['ok'] is False and r2_['status'] == 'unpaid' and deal(B, c)['status'] == 'accepted', r2_)
    s, e = B.req(f'/deals/{c}/stripe-confirm', {'session_id': 'cs_test_fake'})
    check('session ปลอม → ปฏิเสธ', s == 400, e)
    print('2) จ่ายจริง (test) ด้วย pm_card_visa แล้วผู้ซื้อยกเลิกเอง → คืน ยอด − ค่าดำเนินการ (ค่าบัตรไม่คืน)')
    r = B.ok(f'/deals/{c}/stripe-test-pay', {})
    d = deal(B, c)
    check('PaymentIntent สำเร็จ → ดีล held, จ่ายด้วยบัตร', d['status'] == 'held' and d['stripe']['paid'] and r['payment_intent'].startswith('pi_'), r)
    st = ADM.ok(f'/admin/stripe/deal/{c}')
    check(f'Stripe เก็บเงินจริง {total} บาท (test mode)', st['amount'] == total and st['status'] == 'succeeded' and st['livemode'] is False, st)
    ch = d['buyer_cancel_charge']
    r = B.ok(f'/deals/{c}/cancel', {})
    st = ADM.ok(f'/admin/stripe/deal/{c}')
    check(f'คืนผ่าน Stripe {r2(paid - ch)} (= {paid} − ค่าดำเนินการ {ch}) · ค่าบัตร {cf} ไม่คืน', r['refund'] == r2(paid - ch) and st['amount_refunded'] == r2(paid - ch) and st['refund_id'].startswith('re_'), (r, st))
    check('ค่าดำเนินการ ≥ max(10, 2%, ต้นทุน+5)', ch >= max(10, paid * 0.02), ch)
    print('3) ผู้ขายยกเลิก → คืนเต็มยอดดีล (ไม่รวมค่าบัตร)')
    c2 = accepted(price=500, fee_payer='seller'); p2 = deal(B, c2)['buyer_pay']
    B.ok(f'/deals/{c2}/stripe-test-pay', {}); r = S.ok(f'/deals/{c2}/cancel', {})
    st = ADM.ok(f'/admin/stripe/deal/{c2}')
    check(f'คืนผ่าน Stripe เต็ม {p2} · Stripe เก็บไป {st["amount"]}', st['amount_refunded'] == p2 and st['amount'] == r2(p2 + surcharge(p2)), st)
    print('4) PromptPay ยังเป็นเงินจำลอง')
    S3 = C(); S3.login('ผู้ขาย v14 ร้านสอง', '089' + stamp + '3')  # ผู้ขายแรกมีค่าปรับค้างจากข้อ 3 (กฎ v13 บล็อกดีลใหม่ถูกต้อง)
    c3 = new_deal(S3, price=300); B.ok(f'/deals/{c3}/accept', {}); B.ok(f'/deals/{c3}/pay', {'method': 'promptpay'})
    s, e = ADM.req(f'/admin/stripe/deal/{c3}')
    check('PromptPay → held โดยไม่แตะ Stripe', deal(B, c3)['status'] == 'held' and s == 404, e)
print(f'\nผลรวม: ผ่าน {ok} / ไม่ผ่าน {fail}')
sys.exit(1 if fail else 0)
