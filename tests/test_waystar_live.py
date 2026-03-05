"""Live Waystar API tests — verify endpoint availability.

Run with: python -m pytest tests/test_waystar_live.py -v -s
The -s flag prints stdout so you can see the raw responses.

These tests hit the real Waystar API and are skipped if credentials
are not configured in .env.
"""

import os

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("CLEARINGHOUSE_API_KEY", "")
USER_ID = os.getenv("CLEARINGHOUSE_USER_ID", "")
PASSWORD = os.getenv("CLEARINGHOUSE_PASSWORD", "")
CUST_ID = os.getenv("CLEARINGHOUSE_CUST_ID", "")
CLAIMS_BASE = os.getenv("CLEARINGHOUSE_BASE_URL", "https://claimsapi.zirmed.com")

pytestmark = pytest.mark.skipif(
    not API_KEY or not USER_ID,
    reason="Waystar credentials not configured",
)


class TestWaystarEndpoints:
    """Verify which Waystar REST endpoints exist."""

    def setup_method(self):
        self.client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

    def teardown_method(self):
        self.client.close()

    def test_claims_submit_does_not_exist(self):
        """Waystar has NO REST claim submission endpoint — only claim history."""
        url = f"{CLAIMS_BASE}/2.0/v1/Claims/Submit"
        resp = self.client.post(url, json={
            "UserID": USER_ID, "Password": PASSWORD,
            "CustID": CUST_ID, "ClaimData": {},
        })
        # 404 confirms the endpoint doesn't exist
        assert resp.status_code == 404
        print(f"\nConfirmed: POST {url} → 404 (endpoint does not exist)")

    def test_claim_history_endpoint_exists(self):
        """Claim history endpoint exists (400 = valid endpoint, bad params)."""
        import hashlib
        import hmac
        from datetime import UTC, datetime
        from urllib.parse import urlencode

        now = datetime.now(UTC)
        params = {
            "CustID": CUST_ID,
            "DOS": "03/01/2026",
            "ClaimNum": "TEST001",
            "ReqType": "CLMHIST",
            "Version": "2.0",
            "TimeStamp": now.strftime("%m/%d/%Y %I:%M:%S %p"),
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        params["Signature"] = hmac.new(
            API_KEY.encode(), query_string.encode(), hashlib.sha256
        ).hexdigest()
        params["ResponseType"] = "XML"

        url = f"{CLAIMS_BASE}/2.0/v1/History/GetClaimHistory?{urlencode(params)}"
        resp = self.client.get(url)
        # 400 means endpoint exists but params are invalid (expected with test data)
        assert resp.status_code in (200, 400)
        print(f"\nConfirmed: GET .../GetClaimHistory → {resp.status_code} (endpoint exists)")

    def test_eligibility_endpoint_works(self):
        """Eligibility endpoint returns real data."""
        from claim_validator.clearinghouse.providers.waystar import WaystarClient

        client = WaystarClient(
            api_key=API_KEY, user_id=USER_ID,
            password=PASSWORD, cust_id=CUST_ID,
        )
        try:
            result = client.check_eligibility({
                "payer_id": "66666",
                "npi": "1234567890",
                "subscriber_id": "ABC123456",
                "first_name": "JOHN",
                "last_name": "DOE",
                "dob": "1990-01-15",
                "service_type": "30",
            })
            assert result.status == "active"
            assert result.eligible is True
            print(f"\nEligibility: status={result.status}, eligible={result.eligible}")
            print(f"Raw keys: {list(result.raw_response.keys())}")
        finally:
            client.close()
