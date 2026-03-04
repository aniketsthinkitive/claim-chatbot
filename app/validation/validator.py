from pydantic import BaseModel


class ValidationResult(BaseModel):
    status: str  # "pass", "fail", "needs_review"
    issues: list[str]
    recommendations: list[str]
    raw_output: dict


class ClaimValidator:
    """Validates the collected claim payload before submission to ClaimMD."""

    def validate(self, payload: dict) -> ValidationResult:
        issues = []
        recommendations = []

        # Billing provider checks
        npi = payload.get("billing_provider_npi", "")
        if not npi or len(str(npi)) != 10:
            issues.append(f"Invalid NPI: must be exactly 10 digits (got '{npi}')")

        taxonomy = payload.get("billing_provider_taxonomy", "")
        if not taxonomy:
            issues.append("Missing billing provider taxonomy code")

        # Subscriber checks
        if not payload.get("subscriber_id"):
            issues.append("Missing subscriber/member ID")
        if not payload.get("subscriber_first_name"):
            issues.append("Missing subscriber first name")
        if not payload.get("subscriber_last_name"):
            issues.append("Missing subscriber last name")
        if not payload.get("subscriber_dob"):
            issues.append("Missing subscriber date of birth")
        if payload.get("subscriber_gender", "") not in ("M", "F"):
            issues.append("Subscriber gender must be 'M' or 'F'")

        # Patient checks
        if not payload.get("patient_first_name"):
            issues.append("Missing patient first name")
        if not payload.get("patient_last_name"):
            issues.append("Missing patient last name")
        if payload.get("patient_gender", "") not in ("M", "F"):
            issues.append("Patient gender must be 'M' or 'F'")

        relationship = payload.get("patient_relationship", "")
        if relationship not in ("self", "spouse", "child", "other"):
            issues.append(f"Invalid patient relationship: '{relationship}'")

        # Payer checks
        if not payload.get("payer_id"):
            issues.append("Missing payer ID")
        if not payload.get("payer_name"):
            issues.append("Missing payer name")

        # Claim type
        claim_type = payload.get("claim_type", "")
        if claim_type not in ("professional", "institutional"):
            issues.append(f"Invalid claim type: '{claim_type}' (must be 'professional' or 'institutional')")

        # Place of service
        pos = payload.get("place_of_service", "")
        if not pos or len(str(pos)) != 2:
            issues.append(f"Invalid place of service code: '{pos}' (must be 2 digits)")

        # Total charge
        total_charge = payload.get("total_charge", 0)
        try:
            charge_val = float(total_charge)
            if charge_val <= 0:
                issues.append("Total charge must be greater than 0")
            if charge_val > 999999:
                recommendations.append("Very high total charge - verify amount is correct")
        except (ValueError, TypeError):
            issues.append(f"Invalid total charge: '{total_charge}'")

        # Diagnosis codes
        diag_codes = payload.get("diagnosis_codes", [])
        if not diag_codes:
            issues.append("At least one diagnosis code is required")
        else:
            has_principal = any(d.get("type") == "principal" for d in diag_codes)
            if not has_principal:
                issues.append("At least one principal diagnosis code is required")

        # Service lines
        lines = payload.get("lines", [])
        if not lines:
            issues.append("At least one service line is required")
        else:
            line_total = sum(float(l.get("charge_amount", 0)) for l in lines)
            try:
                if abs(line_total - float(total_charge)) > 0.01:
                    recommendations.append(
                        f"Service line charges ({line_total:.2f}) don't match "
                        f"total charge ({float(total_charge):.2f}) - please verify"
                    )
            except (ValueError, TypeError):
                pass

        # Determine status
        if issues:
            status = "needs_review" if len(issues) <= 3 else "fail"
        else:
            status = "pass"
            recommendations.append("All validation checks passed. Ready for ClaimMD submission.")

        return ValidationResult(
            status=status,
            issues=issues,
            recommendations=recommendations,
            raw_output={"fields_checked": list(payload.keys())},
        )
