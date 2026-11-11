import hashlib, hmac, httpx
from . import config as C

async def create_invoice(amount: float, order_id: str, desc: str) -> dict:
    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.post("https://api.oxapay.com/v1/payment/invoice",
            headers={"merchant_api_key": C.OXAPAY_KEY, "Content-Type": "application/json"},
            json={"amount": amount, "currency": "USDT", "lifetime": 60, "fee_paid_by_payer": 1,
                  "order_id": order_id, "description": desc,
                  "callback_url": f"{C.WEBAPP_URL}/webhook/oxapay",
                  "return_url": f"https://t.me/{C.BOT_USERNAME}"})
    j = r.json()
    if r.status_code != 200 or "data" not in j:
        raise RuntimeError(f"oxapay: {j}")
    return j["data"]  # track_id, payment_url, expired_at

def valid(raw: bytes, header: str) -> bool:
    calc = hmac.new(C.OXAPAY_KEY.encode(), raw, hashlib.sha512).hexdigest()
    return bool(header) and hmac.compare_digest(calc, header.lower())
