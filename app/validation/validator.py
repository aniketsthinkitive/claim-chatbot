"""Claim validation — thin wrapper around claim-validator library."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Check if claim-validator library is available
_library_available = False
try:
    from claim_validator import validate as _cv_validate
    _library_available = True
except ImportError:
    logger.warning("claim-validator library not installed, using fallback validation")


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
        kwargs: dict[str, Any] = {}
        if clearinghouse_config:
            kwargs["clearinghouse_config"] = clearinghouse_config
        if ai_config:
            kwargs["ai_config"] = ai_config
        result = _cv_validate(payload, **kwargs)

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
