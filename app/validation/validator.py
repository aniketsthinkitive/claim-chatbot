from pydantic import BaseModel


class ValidationResult(BaseModel):
    status: str  # "pass", "fail", "needs_review"
    issues: list[str]
    recommendations: list[str]
    raw_output: dict


class ClaimValidator:
    """Adapter for the claim validator package.
    Replace the validate() body with your real package integration.
    """

    def validate(
        self, fields: dict, document_extractions: dict | None = None
    ) -> ValidationResult:
        issues = []
        recommendations = []

        if not fields.get("policy_number"):
            issues.append("Missing policy number")
        if not fields.get("incident_date"):
            issues.append("Missing incident date")

        amount = fields.get("claim_amount", "0")
        try:
            if float(amount) > 50000:
                issues.append("Claim amount exceeds standard threshold")
                recommendations.append(
                    "Requires manual review for high-value claims"
                )
        except (ValueError, TypeError):
            issues.append("Invalid claim amount format")

        if issues:
            status = "needs_review" if len(issues) < 3 else "fail"
        else:
            status = "pass"
            recommendations.append("All automated checks passed.")

        return ValidationResult(
            status=status,
            issues=issues,
            recommendations=recommendations,
            raw_output={"fields_checked": list(fields.keys())},
        )
