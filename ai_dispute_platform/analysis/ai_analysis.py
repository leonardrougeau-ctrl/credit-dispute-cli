from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ai_dispute_platform.generators.dispute_letter import LetterContext, ProfessionalDisputeLetterGenerator
from ai_dispute_platform.ingest.pdf_reader import PDFTextReader


@dataclass
class ExtractedAccount:
    account_number: str = ""
    customer_name: str = ""
    ssn: str = ""
    date_of_birth: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    date_opened: str = ""
    credit_limit: int = 0
    current_balance: int = 0
    last_payment_date: str = ""
    payment_history: str = ""
    raw_text: str = ""
    source_page: int = 0


@dataclass
class DisputeFinding:
    account: ExtractedAccount
    issue_type: str
    severity: str
    evidence: str
    recommended_action: str
    dispute_reason: str
    confidence: float = 0.0
    letter_text: str = ""


@dataclass
class AnalysisResult:
    extracted_accounts: List[ExtractedAccount] = field(default_factory=list)
    findings: List[DisputeFinding] = field(default_factory=list)
    letters: Dict[str, str] = field(default_factory=dict)
    metro2_rows: List[Dict[str, str | int]] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)


class AIAnalyzer:
    """AI-assisted credit report analysis and Metro 2 row generation."""

    def __init__(self, llm_provider=None):
        self.reader = PDFTextReader()
        self.llm_provider = llm_provider
        self.letter_generator = ProfessionalDisputeLetterGenerator()

    def analyze_pdf(self, pdf_path: str | Path, bank_name: str = "Bank Customer") -> AnalysisResult:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        extraction = self.reader.extract_text(pdf_path)
        accounts = self.extract_accounts(extraction.text)

        findings: List[DisputeFinding] = []
        letters: Dict[str, str] = {}

        for account in accounts:
            account_findings = self.detect_issues(account, extraction.text)
            for finding in account_findings:
                finding.account = account
                letter_context = LetterContext(
                    consumer_name=account.customer_name or "Consumer",
                    account_number=account.account_number or "Unknown",
                    issue_type=finding.issue_type,
                    dispute_reason=finding.dispute_reason,
                    evidence=finding.evidence,
                    bureau_name="Credit Bureau",
                    date_text=self._today_text(),
                )
                letter_text = self.letter_generator.generate(letter_context)
                finding.letter_text = letter_text
                findings.append(finding)
                letters[f"{account.account_number}_{finding.issue_type}".replace(" ", "_")] = letter_text

        metro2_rows = self.build_metro2_rows(findings)

        return AnalysisResult(
            extracted_accounts=accounts,
            findings=findings,
            letters=letters,
            metro2_rows=metro2_rows,
            metadata={
                "pdf_path": str(pdf_path),
                "bank_name": bank_name,
                "account_count": len(accounts),
                "finding_count": len(findings),
            },
        )

    def extract_accounts(self, raw_text: str) -> List[ExtractedAccount]:
        accounts: List[ExtractedAccount] = []
        segments = self._split_segments(raw_text)

        for index, segment in enumerate(segments, start=1):
            account = ExtractedAccount(raw_text=segment, source_page=index)
            search_text = raw_text
            account.account_number = self._match_first(
                search_text,
                [
                    r"Account Number[:\s]*([A-Z0-9-]{4,})",
                    r"Account\s*#[:\s]*([A-Z0-9-]{4,})",
                ],
            )
            account.customer_name = self._match_first(
                search_text,
                [
                    r"Name[:\s]*([A-Z][A-Za-z0-9 ,.'-]+)",
                    r"Consumer Name[:\s]*([A-Z][A-Za-z0-9 ,.'-]+)",
                ],
            )
            account.ssn = self._match_first(search_text, [r"SSN[:\s]*([0-9]{3}-?[0-9]{2}-?[0-9]{4})"])
            account.date_of_birth = self._match_first(search_text, [r"Date of Birth[:\s]*([0-9]{4}-?[0-9]{2}-?[0-9]{2})"])
            account.address = self._match_first(search_text, [r"Address[:\s]*([^\n]+)"])
            account.city = self._match_first(search_text, [r"City[:\s]*([A-Za-z][A-Za-z .'-]+)"])
            account.state = self._match_first(search_text, [r"State[:\s]*([A-Z]{2})"])
            account.zip_code = self._match_first(search_text, [r"ZIP[:\s]*([0-9]{5}(?:-[0-9]{4})?)"])
            account.date_opened = self._match_first(search_text, [r"Date Opened[:\s]*([0-9]{4}-?[0-9]{2}-?[0-9]{2})"])
            account.credit_limit = self._to_int(self._match_first(search_text, [r"Credit Limit[:\s]*\$?([0-9,]+)"]))
            account.current_balance = self._to_int(self._match_first(search_text, [r"Current Balance[:\s]*\$?([0-9,]+)"]))
            account.last_payment_date = self._match_first(search_text, [r"Last Payment Date[:\s]*([0-9]{4}-?[0-9]{2}-?[0-9]{2})"])
            account.payment_history = self._match_first(search_text, [r"Payment History[:\s]*([A-Za-z0-9 ,/.-]+)"])

            if not any([account.account_number, account.customer_name, account.ssn]):
                continue
            accounts.append(account)

        if not accounts:
            fallback = ExtractedAccount(
                account_number=self._match_first(raw_text, [r"Account Number[:\s]*([A-Z0-9-]{4,})"]),
                customer_name=self._match_first(raw_text, [r"Name[:\s]*([A-Z][A-Za-z0-9 ,.'-]+)"]),
                ssn=self._match_first(raw_text, [r"SSN[:\s]*([0-9]{3}-?[0-9]{2}-?[0-9]{4})"]),
                raw_text=raw_text,
            )
            if any([fallback.account_number, fallback.customer_name, fallback.ssn]):
                accounts.append(fallback)

        return accounts

    def detect_issues(self, account: ExtractedAccount, raw_text: str) -> List[DisputeFinding]:
        findings: List[DisputeFinding] = []
        lower_raw = raw_text.lower()
        payment_text = (account.payment_history or "").lower()

        if "on time" in payment_text and any(term in lower_raw for term in ["late", "30 days past due", "60 days past due", "90 days past due"]):
            findings.append(
                DisputeFinding(
                    account=account,
                    issue_type="late_payment_reported_as_on_time",
                    severity="high",
                    evidence="The payment history shows on-time reporting while the report includes delinquency language.",
                    recommended_action="Dispute the payment status and request verification of the delinquency history.",
                    dispute_reason="A late payment was reported as on-time.",
                    confidence=0.88,
                )
            )

        if any(term in lower_raw for term in ["not my account", "unknown account", "belongs to someone else", "identity theft", "does not belong to the user", "does not belong"]):
            findings.append(
                DisputeFinding(
                    account=account,
                    issue_type="account_not_belonging_to_consumer",
                    severity="critical",
                    evidence="The report contains language indicating the account may not belong to the consumer.",
                    recommended_action="Dispute the ownership of the account and request removal from the consumer's file.",
                    dispute_reason="The account appears unrelated to the consumer and should not be reported.",
                    confidence=0.96,
                )
            )

        if account.current_balance and account.credit_limit:
            if account.current_balance > account.credit_limit * 1.5:
                findings.append(
                    DisputeFinding(
                        account=account,
                        issue_type="incorrect_balance_or_limit",
                        severity="medium",
                        evidence="The reported balance is significantly higher than the stated credit limit.",
                        recommended_action="Dispute the balance and request verification of the account balance and limits.",
                        dispute_reason="The balance appears inconsistent with the stated limit.",
                        confidence=0.74,
                    )
                )

        if self.llm_provider:
            prompt = (
                "Review the account data and report text. Return JSON with an array named 'findings' where each item includes: "
                "issue_type, severity, evidence, recommended_action, dispute_reason, confidence. If no issues, return {'findings': []}.\n\n"
                f"ACCOUNT: {self._account_to_json(account)}\n\nREPORT_TEXT:\n{raw_text[:6000]}"
            )
            raw_llm = self.llm_provider.analyze(prompt)
            try:
                data = json.loads(self._extract_json_block(raw_llm))
                llm_findings = data.get("findings", [])
                for item in llm_findings:
                    if isinstance(item, dict):
                        findings.append(
                            DisputeFinding(
                                account=account,
                                issue_type=item.get("issue_type", "unknown_issue"),
                                severity=item.get("severity", "medium"),
                                evidence=item.get("evidence", "LLM flagged a potential issue"),
                                recommended_action=item.get("recommended_action", "Review account"),
                                dispute_reason=item.get("dispute_reason", "AI-identified discrepancy"),
                                confidence=float(item.get("confidence", 0.5)),
                            )
                        )
            except Exception:
                pass

        unique_findings = []
        seen = set()
        for finding in findings:
            key = (finding.account.account_number, finding.issue_type)
            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)

        return unique_findings

    def build_metro2_rows(self, findings: List[DisputeFinding]) -> List[Dict[str, str | int]]:
        rows = []
        for finding in findings:
            account = finding.account
            row = {
                "customer_name": account.customer_name,
                "ssn": account.ssn,
                "date_of_birth": account.date_of_birth,
                "address": account.address,
                "city": account.city,
                "state": account.state,
                "zip": account.zip_code,
                "account_number": account.account_number,
                "date_opened": account.date_opened,
                "credit_limit": account.credit_limit or 0,
                "current_balance": account.current_balance or 0,
                "dispute_type": self._map_issue_to_dispute_type(finding.issue_type),
                "effective_date": self._today_iso(),
                "last_payment_date": account.last_payment_date,
                "payment_history_24": self._normalize_payment_history(account.payment_history),
                "compliance_code": "XD",
                "metro2_id": "3",
                "portfolio_type": "10",
                "account_type": "4",
                "amount_past_due": 0,
                "scheduled_payment": 0,
                "payment_rating": "0",
                "date_of_first_delinq": "",
            }
            rows.append(row)
        return rows

    def export_to_csv(self, rows: List[Dict[str, str | int]], csv_path: str | Path) -> str:
        csv_path = Path(csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "customer_name",
            "ssn",
            "date_of_birth",
            "address",
            "city",
            "state",
            "zip",
            "account_number",
            "date_opened",
            "credit_limit",
            "current_balance",
            "dispute_type",
            "effective_date",
            "last_payment_date",
            "payment_history_24",
            "compliance_code",
            "metro2_id",
            "portfolio_type",
            "account_type",
            "amount_past_due",
            "scheduled_payment",
            "payment_rating",
            "date_of_first_delinq",
        ]

        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})

        return str(csv_path)

    def _map_issue_to_dispute_type(self, issue_type: str) -> str:
        mapping = {
            "late_payment_reported_as_on_time": "02",
            "account_not_belonging_to_consumer": "03",
            "incorrect_balance_or_limit": "04",
        }
        return mapping.get(issue_type, "01")

    def _split_segments(self, raw_text: str) -> List[str]:
        markers = list(re.finditer(r"(?im)(Account Number|Account\s*#)", raw_text))
        if markers:
            segments = []
            for index, marker in enumerate(markers):
                start = marker.start()
                end = markers[index + 1].start() if index + 1 < len(markers) else len(raw_text)
                chunk = raw_text[start:end].strip()
                if chunk:
                    segments.append(chunk)
            return segments
        return [raw_text]

    def _match_first(self, text: str, patterns: List[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                return self._clean_value(value)
        return ""

    def _clean_value(self, value: str) -> str:
        value = value.replace("$", "").replace(",", "")
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _to_int(self, value: str) -> int:
        if not value:
            return 0
        try:
            return int(float(value))
        except ValueError:
            return 0

    def _normalize_payment_history(self, payment_history: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]", "", payment_history.lower())
        if len(cleaned) < 24:
            cleaned = (cleaned + "0" * 24)[:24]
        return cleaned[:24].ljust(24, "0")

    def _today_iso(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

    def _today_text(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%B %d, %Y")

    def _account_to_json(self, account: ExtractedAccount) -> str:
        return json.dumps(
            {
                "account_number": account.account_number,
                "customer_name": account.customer_name,
                "ssn": account.ssn,
                "date_of_birth": account.date_of_birth,
                "address": account.address,
                "city": account.city,
                "state": account.state,
                "zip_code": account.zip_code,
                "date_opened": account.date_opened,
                "credit_limit": account.credit_limit,
                "current_balance": account.current_balance,
                "last_payment_date": account.last_payment_date,
                "payment_history": account.payment_history,
            },
            indent=2,
        )

    def _extract_json_block(self, raw: str) -> str:
        if not raw:
            return "{}"
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            return match.group(0)
        return raw
