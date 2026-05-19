"""
CryptoBot (CryptoPay) integration via official API.
Docs: https://help.crypt.bot/crypto-pay-api
"""
import aiohttp
from config import CRYPTOPAY_TOKEN, CRYPTOPAY_API_URL, BOT_USERNAME

HEADERS = {
    "Crypto-Pay-API-Token": CRYPTOPAY_TOKEN,
    "Content-Type": "application/json",
}


async def create_invoice(amount: float, asset: str = "USDT",
                          description: str = "Lira Premium",
                          payload: str = "") -> dict | None:
    """Create a payment invoice via POST. Returns invoice dict or None on error."""
    body = {
        "asset": asset,
        "amount": str(round(amount, 2)),
        "description": description,
        "payload": payload,
        "expires_in": 3600,
        # paid_btn_name requires paid_btn_url — use bot link
        "paid_btn_name": "openBot",
        "paid_btn_url": f"https://t.me/{BOT_USERNAME}",
    }
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.post(
                f"{CRYPTOPAY_API_URL}/createInvoice",
                json=body,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                print(f"[CryptoPay] createInvoice status={resp.status} response={data}")
                if data.get("ok"):
                    return data["result"]
                err = data.get("error", {})
                print(f"[CryptoPay] API error: code={err.get('code')} name={err.get('name')}")
    except Exception as e:
        print(f"[CryptoPay] createInvoice exception: {e}")
    return None


async def check_invoice(invoice_id: int) -> str | None:
    """Returns invoice status: 'active', 'paid', 'expired' or None."""
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.post(
                f"{CRYPTOPAY_API_URL}/getInvoices",
                json={"invoice_ids": str(invoice_id)},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                print(f"[CryptoPay] getInvoices response={data}")
                if data.get("ok"):
                    items = data["result"].get("items", [])
                    if items:
                        return items[0]["status"]
    except Exception as e:
        print(f"[CryptoPay] checkInvoice error: {e}")
    return None
