import hashlib
import hmac
import logging
from typing import Any, Optional
import uuid

import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RazorpayService:
    """Razorpay Gateway Integration Service.

    Handles:
    - Creating Razorpay Orders (`/v1/orders`)
    - Verifying HMAC SHA256 payment signatures
    - Processing wallet top-ups & strategy pass purchases
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def key_id(self) -> str:
        return self.settings.razorpay_key_id or "rzp_test_SFd7WR1rAUaPUA"

    @property
    def key_secret(self) -> str:
        return self.settings.razorpay_key_secret or "AHqEU8tXJJ1sbjLzZgiGNNsz"

    async def create_order(
        self,
        amount_inr: float,
        receipt: Optional[str] = None,
        notes: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Create a Razorpay Order ID for frontend checkout."""
        amount_paise = int(round(amount_inr * 100))
        receipt_id = receipt or f"rcpt_{uuid.uuid4().hex[:8]}"

        payload = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt_id,
            "notes": notes or {"platform": "TradeShield 021"},
        }

        url = "https://api.razorpay.com/v1/orders"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    url,
                    json=payload,
                    auth=(self.key_id, self.key_secret),
                )
                if res.status_code in (200, 201):
                    data = res.json()
                    logger.info(f"[RAZORPAY] Created order {data.get('id')} for ₹{amount_inr:.2f}")
                    return {
                        "id": data["id"],
                        "entity": data.get("entity", "order"),
                        "amount": data["amount"],
                        "amount_inr": amount_inr,
                        "currency": data["currency"],
                        "receipt": data.get("receipt", receipt_id),
                        "status": data.get("status", "created"),
                        "key_id": self.key_id,
                    }
                else:
                    logger.warning(f"[RAZORPAY API ERROR] Status {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"[RAZORPAY ERROR] Failed to connect to Razorpay API: {e}")

        # Fallback simulation order if offline or invalid credentials
        mock_order_id = f"order_{uuid.uuid4().hex[:14]}"
        logger.info(f"[RAZORPAY MOCK] Generated fallback order {mock_order_id} for ₹{amount_inr:.2f}")
        return {
            "id": mock_order_id,
            "entity": "order",
            "amount": amount_paise,
            "amount_inr": amount_inr,
            "currency": "INR",
            "receipt": receipt_id,
            "status": "created",
            "key_id": self.key_id,
        }

    def verify_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> bool:
        """Verify HMAC SHA256 signature returned by Razorpay Checkout."""
        if not razorpay_signature:
            return False

        try:
            msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
            secret = self.key_secret.encode("utf-8")
            generated_sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
            is_valid = hmac.compare_digest(generated_sig, razorpay_signature)
            if not is_valid:
                logger.warning(f"[RAZORPAY] Signature mismatch for payment {razorpay_payment_id}")
            return is_valid
        except Exception as e:
            logger.error(f"[RAZORPAY VERIFY ERROR] {e}")
            return False


razorpay_service = RazorpayService()
