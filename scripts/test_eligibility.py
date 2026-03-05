"""Quick eligibility check — run directly without the chatbot.

Usage:
    python scripts/test_eligibility.py
    python scripts/test_eligibility.py --payer-id 66666 --subscriber-id ABC123456
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from claim_validator.clearinghouse.providers.waystar import WaystarClient


def run_eligibility_check(request: dict) -> dict:
    client = WaystarClient(
        api_key=os.getenv("CLEARINGHOUSE_API_KEY", ""),
        user_id=os.getenv("CLEARINGHOUSE_USER_ID", ""),
        password=os.getenv("CLEARINGHOUSE_PASSWORD", ""),
        cust_id=os.getenv("CLEARINGHOUSE_CUST_ID", ""),
    )
    try:
        result = client.check_eligibility(request)
        return {
            "status": result.status,
            "eligible": result.eligible,
            "reference_id": result.reference_id,
            "errors": result.errors,
            "plan_info": result.plan_info,
            "raw_response": result.raw_response,
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Test Waystar eligibility check")
    parser.add_argument("--payer-id", default="66666", help="Payer ID (default: 66666 = test)")
    parser.add_argument("--npi", default="1234567890", help="Provider NPI")
    parser.add_argument("--subscriber-id", default="ABC123456", help="Subscriber/member ID")
    parser.add_argument("--first-name", default="JOHN", help="Patient first name")
    parser.add_argument("--last-name", default="DOE", help="Patient last name")
    parser.add_argument("--dob", default="1990-01-15", help="Date of birth (YYYY-MM-DD)")
    parser.add_argument("--service-type", default="30", help="Service type code (default: 30)")
    args = parser.parse_args()

    request = {
        "payer_id": args.payer_id,
        "npi": args.npi,
        "subscriber_id": args.subscriber_id,
        "first_name": args.first_name,
        "last_name": args.last_name,
        "dob": args.dob,
        "service_type": args.service_type,
    }

    print("=" * 60)
    print("  ELIGIBILITY CHECK REQUEST")
    print("=" * 60)
    print(json.dumps(request, indent=2))

    print("\nSending to Waystar...")
    response = run_eligibility_check(request)

    print("\n" + "=" * 60)
    print("  ELIGIBILITY CHECK RESPONSE")
    print("=" * 60)
    print(json.dumps(response, indent=2, default=str))

    if response.get("eligible"):
        print("\n✓ ELIGIBLE — Patient is active")
    elif response.get("error"):
        print(f"\n✗ ERROR — {response['error']}")
    else:
        print("\n✗ NOT ELIGIBLE")


if __name__ == "__main__":
    main()
