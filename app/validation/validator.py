"""Claim validation — thin wrapper around claim-validator library."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_AI_VALIDATORS = [
    "claim_validator.validators.ai.code_validation.CodeValidationAI",
    "claim_validator.validators.ai.coverage_check.CoverageCheckAI",
]

# Check if claim-validator library is available
_library_available = False
_clearinghouse_available = False
try:
    from claim_validator import validate as _cv_validate
    _library_available = True
except ImportError:
    logger.warning("claim-validator library not installed, using fallback validation")

try:
    from claim_validator.clearinghouse.factory import get_clearinghouse_client
    _clearinghouse_available = True
except ImportError:
    pass


def validate_claim(
    payload: dict,
    *,
    clearinghouse_config: dict | None = None,
    ai_config: dict | None = None,
) -> dict:
    """Validate a claim payload and return results as a plain dict."""
    if not _library_available:
        logger.info("Using fallback validation (library unavailable)")
        return _fallback_validate(payload)

    try:
        from claim_validator.conf import ClaimValidatorSettings

        settings_kwargs: dict[str, Any] = {}
        if ai_config:
            settings_kwargs["ai_config"] = ai_config
            settings_kwargs["ai_validators"] = DEFAULT_AI_VALIDATORS
        if clearinghouse_config:
            settings_kwargs["clearinghouse_config"] = clearinghouse_config

        cv_settings = ClaimValidatorSettings(**settings_kwargs) if settings_kwargs else None
        result = _cv_validate(payload, settings=cv_settings)

        findings = []
        for f in result.findings:
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            findings.append({
                "code": f.code,
                "message": f.message,
                "severity": sev,
                "field_name": getattr(f, "field_name", None) or "",
                "suggestion": getattr(f, "suggestion", None) or "",
            })

        errors = [f for f in findings if f["severity"] == "error"]
        warnings = [f for f in findings if f["severity"] == "warning"]

        if result.passed:
            status = "pass"
        elif len(errors) <= 3:
            status = "needs_review"
        else:
            status = "fail"

        return {
            "status": status,
            "passed": result.passed,
            "findings": findings,
            "total_findings": len(findings),
            "total_errors": len(errors),
            "total_warnings": len(warnings),
            "execution_time": result.execution_time,
            "phase_results": [
                {
                    "phase": pr.phase,
                    "findings_count": len(pr.findings),
                    "execution_time": pr.execution_time,
                }
                for pr in result.phase_results
            ],
        }
    except Exception as e:
        logger.error("Validator error, using fallback: %s", e, exc_info=True)
        return _fallback_validate(payload)


def _fallback_validate(payload: dict) -> dict:
    """Basic field checks when claim-validator library is unavailable."""
    issues = []
    npi = payload.get("billing_provider_npi", "")
    if not npi or len(str(npi)) != 10:
        issues.append({
            "code": "BASIC_INVALID_NPI",
            "message": f"Invalid NPI: must be exactly 10 digits (got '{npi}')",
            "severity": "error",
            "field_name": "billing_provider_npi",
            "suggestion": "Provide a valid 10-digit NPI number",
        })
    if not payload.get("subscriber_id"):
        issues.append({
            "code": "BASIC_MISSING_SUBSCRIBER_ID",
            "message": "Missing subscriber/member ID",
            "severity": "error",
            "field_name": "subscriber_id",
            "suggestion": "Provide the subscriber's member ID",
        })
    if not payload.get("diagnosis_codes"):
        issues.append({
            "code": "BASIC_MISSING_DIAGNOSIS",
            "message": "At least one diagnosis code is required",
            "severity": "error",
            "field_name": "diagnosis_codes",
            "suggestion": "Add at least one ICD-10 diagnosis code",
        })
    if not payload.get("lines"):
        issues.append({
            "code": "BASIC_MISSING_LINES",
            "message": "At least one service line is required",
            "severity": "error",
            "field_name": "lines",
            "suggestion": "Add at least one service line with CPT code",
        })

    errors = [f for f in issues if f["severity"] == "error"]
    status = "pass" if not errors else ("needs_review" if len(errors) <= 3 else "fail")

    return {
        "status": status,
        "passed": len(errors) == 0,
        "findings": issues,
        "total_findings": len(issues),
        "total_errors": len(errors),
        "total_warnings": 0,
        "execution_time": 0.0,
        "phase_results": [{"phase": "fallback", "findings_count": len(issues), "execution_time": 0.0}],
        "fallback": True,
    }


def check_eligibility(
    claim_payload: dict,
    clearinghouse_config: dict,
) -> dict:
    """Check patient eligibility using the configured clearinghouse provider.

    Maps claim fields to eligibility request fields and calls the provider.
    Returns a plain dict with eligibility status, plan info, and errors.
    """
    if not _clearinghouse_available:
        return {"status": "unavailable", "message": "Clearinghouse client not available"}

    # Map claim fields → eligibility request fields
    request = {
        "payer_id": claim_payload.get("payer_id", ""),
        "npi": claim_payload.get("billing_provider_npi", ""),
        "organization_name": claim_payload.get("billing_provider_name", ""),
        "subscriber_id": claim_payload.get("subscriber_id", ""),
        "first_name": claim_payload.get("subscriber_first_name", ""),
        "last_name": claim_payload.get("subscriber_last_name", ""),
        "dob": claim_payload.get("subscriber_dob", ""),
        "service_type": "30",
    }

    try:
        config = dict(clearinghouse_config)
        provider = config.pop("provider", "")
        client = get_clearinghouse_client(provider, **config)
        try:
            result = client.check_eligibility(request)
            plan_info = result.plan_info if isinstance(result.plan_info, dict) else {}

            # Parse response — format varies by provider
            subscriber, plans, plan_name = _parse_eligibility_plan_info(plan_info, provider)

            return {
                "status": result.status,
                "eligible": result.eligible,
                "reference_id": result.reference_id,
                "errors": result.errors,
                "subscriber": subscriber,
                "plan_name": plan_name,
                "plans": plans,
                "request": request,
            }
        finally:
            client.close()
    except Exception as e:
        logger.error("Eligibility check failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "eligible": None,
            "errors": [str(e)],
            "request": request,
        }


def _parse_eligibility_plan_info(
    plan_info: dict, provider: str
) -> tuple[dict, list[dict], str]:
    """Extract subscriber, plans, and plan_name from provider-specific response."""
    if provider.lower() == "stedi":
        return _parse_stedi_plan_info(plan_info)
    return _parse_waystar_plan_info(plan_info)


def _parse_waystar_plan_info(plan_info: dict) -> tuple[dict, list[dict], str]:
    """Parse Waystar eligibility response format."""
    subscriber_raw = plan_info.get("Subscriber", {})
    subscriber = {
        "first": subscriber_raw.get("First", ""),
        "last": subscriber_raw.get("Last", ""),
        "dob": subscriber_raw.get("Dob", ""),
        "member_id": subscriber_raw.get("MemberId", ""),
    }
    plans = []
    for p in plan_info.get("Plans", []):
        plans.append({
            "plan_name": p.get("InsurancePlanName", p.get("Name", "")),
            "status": p.get("FileStatusDescription", ""),
            "active": p.get("IsActive", False),
            "deductible_in": p.get("DeductibleInNetwork", ""),
            "deductible_out": p.get("DeductibleOutNetwork", ""),
            "deductible_remaining": p.get("PlanBinDedRem", ""),
            "oop_remaining": p.get("PlanBinOopRem", ""),
            "coinsurance_in": p.get("CoInsuranceInNetwork", ""),
            "coinsurance_out": p.get("CoInsuranceOutNetwork", ""),
        })
    return subscriber, plans, plan_info.get("PlanName", "")


def _parse_stedi_plan_info(plan_info: dict) -> tuple[dict, list[dict], str]:
    """Parse Stedi eligibility response format."""
    subscriber = {"first": "", "last": "", "dob": "", "member_id": ""}
    plan_name = ""
    plans = []

    # Extract plan name from planInformation
    plan_information = plan_info.get("planInformation", {})
    if isinstance(plan_information, dict):
        plan_name = plan_information.get("planName", "")
    elif isinstance(plan_information, list) and plan_information:
        plan_name = plan_information[0].get("planName", "")

    # Extract plan status entries as plan cards
    for ps in plan_info.get("planStatus", []):
        status_desc = ps.get("status", ps.get("statusCode", ""))
        plans.append({
            "plan_name": ps.get("planName", plan_name),
            "status": status_desc,
            "active": status_desc.lower() in ("active coverage", "active"),
            "deductible_in": "",
            "deductible_out": "",
            "deductible_remaining": "",
            "oop_remaining": "",
            "coinsurance_in": "",
            "coinsurance_out": "",
        })

    # Extract benefits for deductible/OOP/coinsurance details
    for ben in plan_info.get("benefitsInformation", []):
        code = ben.get("code", "")
        amount = ben.get("benefitAmount", "")
        in_plan = ben.get("inPlanNetworkIndicatorCode", "") == "Y"
        time_qualifier = ben.get("timeQualifierCode", "")
        # Map common benefit codes to plan summary fields
        if plans:
            target = plans[0]
            if code == "C" and in_plan:  # Deductible
                target["deductible_in"] = amount
            elif code == "C" and not in_plan:
                target["deductible_out"] = amount
            elif code == "G" and in_plan:  # Out of Pocket
                target["oop_remaining"] = amount
            elif code == "A" and in_plan:  # Coinsurance
                pct = ben.get("percent", "")
                target["coinsurance_in"] = f"{pct}%" if pct else amount

    return subscriber, plans, plan_name
