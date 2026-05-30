from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class LetterContext:
    consumer_name: str
    account_number: str
    issue_type: str
    dispute_reason: str
    evidence: str
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    contact_email: str = "contact@clearwatercodes.com"
    bureau_name: str = "Credit Bureau"
    date_text: str = ""


class ProfessionalDisputeLetterGenerator:
    """Professional dispute letters with issue-specific templates."""

    def __init__(self, bureau_name: str = "Credit Bureau"):
        self.bureau_name = bureau_name

    def generate(self, context: LetterContext) -> str:
        template = self._get_template(context.issue_type)
        replacement_map = {
            "{{consumer_name}}": context.consumer_name or "Consumer",
            "{{account_number}}": context.account_number or "Unknown",
            "{{bureau_name}}": context.bureau_name,
            "{{dispute_reason}}": context.dispute_reason,
            "{{evidence}}": context.evidence,
            "{{date_text}}": context.date_text or "[Date]",
            "{{contact_email}}": context.contact_email,
        }

        letter = template
        for key, value in replacement_map.items():
            letter = letter.replace(key, value)

        return letter.strip()

    def generate_many(self, contexts: List[LetterContext]) -> Dict[str, str]:
        return {f"{ctx.account_number}_{ctx.issue_type}".replace(" ", "_"): self.generate(ctx) for ctx in contexts}

    def _get_template(self, issue_type: str) -> str:
        templates = {
            "late_payment_reported_as_on_time": self._late_payment_template(),
            "account_not_belonging_to_consumer": self._foreign_account_template(),
            "incorrect_balance_or_limit": self._balance_error_template(),
        }
        return templates.get(issue_type, self._generic_template())

    def _late_payment_template(self) -> str:
        return """
[Date: {{date_text}}]

{{bureau_name}}

Re: Notice of Dispute – Account {{account_number}}

Dear Credit Reporting Representative,

I am writing to formally dispute the information reported on my credit file regarding account {{account_number}}. The account has been reported in a manner that is inconsistent with the payment history and actual account status.

The specific error is: {{dispute_reason}}

Supporting evidence:
{{evidence}}

Please investigate this account, correct the inaccurate reporting, and provide written confirmation of the updated status. I request that the disputed information be removed or corrected in a timely manner.

Sincerely,
{{consumer_name}}
{{contact_email}}
""".strip()

    def _foreign_account_template(self) -> str:
        return """
[Date: {{date_text}}]

{{bureau_name}}

Re: Identity / Ownership Dispute – Account {{account_number}}

Dear Credit Reporting Representative,

I am writing to dispute the inclusion of account {{account_number}} on my credit file. This account appears to be unrelated to my identity and should not be reported on my credit report.

The specific error is: {{dispute_reason}}

Supporting evidence:
{{evidence}}

Please investigate the source of this account, remove the unrelated item from my credit report, and send confirmation of the correction.

Sincerely,
{{consumer_name}}
{{contact_email}}
""".strip()

    def _balance_error_template(self) -> str:
        return """
[Date: {{date_text}}]

{{bureau_name}}

Re: Balance / Limit Dispute – Account {{account_number}}

Dear Credit Reporting Representative,

I am writing to dispute the reported balance and/or credit limit information associated with account {{account_number}}. The reported figures appear inconsistent with the account's actual status.

The specific error is: {{dispute_reason}}

Supporting evidence:
{{evidence}}

Please verify the account balance and limit, correct any inaccurate figures, and notify me of the resulting change.

Sincerely,
{{consumer_name}}
{{contact_email}}
""".strip()

    def _generic_template(self) -> str:
        return """
[Date: {{date_text}}]

{{bureau_name}}

Re: Dispute of Inaccurate Credit Report Information – Account {{account_number}}

Dear Credit Reporting Representative,

I am submitting this formal dispute regarding account {{account_number}}. The information reported on my credit file appears inaccurate.

The specific error is: {{dispute_reason}}

Supporting evidence:
{{evidence}}

Please review the account, correct the disputed information, and provide confirmation of the corrected records.

Sincerely,
{{consumer_name}}
{{contact_email}}
""".strip()
