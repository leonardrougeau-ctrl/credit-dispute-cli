from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path
from typing import List

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


DISPUTE_TYPE_MAP = {
    "01": "Paid in full",
    "02": "Never late",
    "03": "Not my account",
}


@dataclass
class ReportDispute:
    customer_name: str
    account_number: str
    dispute_type_code: str
    dispute_type: str
    effective_date: str
    current_balance: int
    dispute_status: str = "Pending review"


class Metro2ReportGenerator:
    def generate_reports(self, input_path: str | Path, bank_name: str, dispute_rows: List[dict] | None = None) -> dict:
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        disputes = self._rows_to_disputes(dispute_rows) if dispute_rows else self._load_rows_from_input(input_path)
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        base_path = input_path.with_suffix("")
        txt_path = base_path.with_name(f"{base_path.name}_report.txt")
        html_path = base_path.with_name(f"{base_path.name}_report.html")
        pdf_path = base_path.with_name(f"{base_path.name}_report.pdf")

        txt_content = self.build_text_report(bank_name, generated_at, disputes)
        html_content = self.build_html_report(bank_name, generated_at, disputes)
        self.build_pdf_report(bank_name, generated_at, disputes, pdf_path)

        txt_path.write_text(txt_content)
        html_path.write_text(html_content)

        return {
            "txt_path": str(txt_path),
            "html_path": str(html_path),
            "pdf_path": str(pdf_path),
            "dispute_count": len(disputes),
        }

    def parse_metro2_file(self, metro2_path: Path) -> List[ReportDispute]:
        disputes: List[ReportDispute] = []
        with metro2_path.open("r") as handle:
            for line in handle:
                if not line.strip():
                    continue
                if line[:2] != "11":
                    continue

                fields = self._slice_fields(line.rstrip("\n"))
                dispute_type_code = ""
                dispute_type = "Unknown"
                effective_date = self._format_date(fields.get("effective_date"))
                current_balance = int(fields.get("current_balance") or 0)

                disputes.append(
                    ReportDispute(
                        customer_name=(fields.get("customer_name") or "Unknown").strip(),
                        account_number=(fields.get("account_number") or "Unknown").strip(),
                        dispute_type_code=dispute_type_code,
                        dispute_type=dispute_type,
                        effective_date=effective_date,
                        current_balance=current_balance,
                        dispute_status="Pending review",
                    )
                )
        return disputes

    def _load_rows_from_input(self, input_path: Path) -> List[ReportDispute]:
        if input_path.suffix.lower() == ".csv":
            return self._load_rows_from_csv(input_path)

        sibling_csv = input_path.with_suffix(".csv")
        if sibling_csv.exists():
            return self._load_rows_from_csv(sibling_csv)

        matched_csv = self._find_best_matching_csv(input_path)
        if matched_csv:
            return self._load_rows_from_csv(matched_csv)

        return self.parse_metro2_file(input_path)

    def _find_best_matching_csv(self, metro2_path: Path) -> Path | None:
        parsed_disputes = self.parse_metro2_file(metro2_path)
        account_numbers = {dispute.account_number for dispute in parsed_disputes if dispute.account_number != "Unknown"}
        if not account_numbers:
            return None

        best_match = None
        best_score = -1
        for csv_path in metro2_path.parent.glob("*.csv"):
            try:
                csv_rows = self._load_rows_from_csv(csv_path)
            except OSError:
                continue

            csv_account_numbers = {row.account_number for row in csv_rows if row.account_number != "Unknown"}
            overlap = len(account_numbers & csv_account_numbers)
            if overlap > best_score:
                best_score = overlap
                best_match = csv_path

        if best_score > 0:
            return best_match
        return None

    def _load_rows_from_csv(self, csv_path: Path) -> List[ReportDispute]:
        rows: List[ReportDispute] = []
        with csv_path.open("r", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                dispute_type_code = str(row.get("dispute_type") or "").strip()
                rows.append(
                    ReportDispute(
                        customer_name=row.get("customer_name") or "Unknown",
                        account_number=row.get("account_number") or "Unknown",
                        dispute_type_code=dispute_type_code,
                        dispute_type=DISPUTE_TYPE_MAP.get(dispute_type_code, f"Unknown ({dispute_type_code or 'N/A'})"),
                        effective_date=self._format_date(str(row.get("effective_date") or "")),
                        current_balance=int(row.get("current_balance") or 0),
                        dispute_status="Pending review",
                    )
                )
        return rows

    def build_text_report(self, bank_name: str, generated_at: str, disputes: List[ReportDispute]) -> str:
        lines = [
            "Credit Dispute Report",
            "=" * 40,
            f"Bank name: {bank_name}",
            f"Date generated: {generated_at}",
            f"Total disputes: {len(disputes)}",
            "",
        ]

        for index, dispute in enumerate(disputes, start=1):
            lines.extend(
                [
                    f"Dispute {index}",
                    f"Customer name: {dispute.customer_name}",
                    f"Account number: {dispute.account_number}",
                    f"Dispute type: {dispute.dispute_type}",
                    f"Effective date: {dispute.effective_date}",
                    f"Current balance: ${dispute.current_balance:,.2f}",
                    f"Dispute status: {dispute.dispute_status}",
                    "-" * 40,
                ]
            )

        return "\n".join(lines) + "\n"

    def build_html_report(self, bank_name: str, generated_at: str, disputes: List[ReportDispute]) -> str:
        rows = []
        for dispute in disputes:
            rows.append(
                """
                <tr>
                    <td>{customer_name}</td>
                    <td>{account_number}</td>
                    <td>{dispute_type}</td>
                    <td>{effective_date}</td>
                    <td>${current_balance:,.2f}</td>
                    <td>{dispute_status}</td>
                </tr>
                """.format(
                    customer_name=escape(dispute.customer_name),
                    account_number=escape(dispute.account_number),
                    dispute_type=escape(dispute.dispute_type),
                    effective_date=escape(dispute.effective_date),
                    current_balance=dispute.current_balance,
                    dispute_status=escape(dispute.dispute_status),
                )
            )

        table_body = "\n".join(rows)
        return f"""<!doctype html>
<html>
<head><meta charset='utf-8'><title>Credit Dispute Report</title></head>
<body style='font-family: Arial, sans-serif; margin: 24px;'>
<h1>Credit Dispute Report</h1>
<p><strong>Bank name:</strong> {escape(bank_name)}</p>
<p><strong>Date generated:</strong> {escape(generated_at)}</p>
<p><strong>Total disputes:</strong> {len(disputes)}</p>
<table border='1' cellspacing='0' cellpadding='6' style='border-collapse: collapse; width: 100%;'>
    <thead>
        <tr style='background:#f0f0f0;'>
            <th>Customer name</th>
            <th>Account number</th>
            <th>Dispute type</th>
            <th>Effective date</th>
            <th>Current balance</th>
            <th>Dispute status</th>
        </tr>
    </thead>
    <tbody>
        {table_body}
    </tbody>
</table>
</body>
</html>
"""

    def build_pdf_report(self, bank_name: str, generated_at: str, disputes: List[ReportDispute], pdf_path: Path) -> None:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        canvas_obj = canvas.Canvas(str(pdf_path), pagesize=letter)
        width, height = letter

        y = height - 36
        canvas_obj.setFont("Helvetica-Bold", 18)
        canvas_obj.drawString(36, y, "Credit Dispute Report")
        y -= 24

        canvas_obj.setFont("Helvetica", 11)
        canvas_obj.drawString(36, y, f"Bank name: {bank_name}")
        y -= 14
        canvas_obj.drawString(36, y, f"Date generated: {generated_at}")
        y -= 14
        canvas_obj.drawString(36, y, f"Total disputes: {len(disputes)}")
        y -= 24

        canvas_obj.setFont("Helvetica-Bold", 12)
        canvas_obj.drawString(36, y, "Disputes")
        y -= 18

        canvas_obj.setFont("Helvetica", 10)
        for index, dispute in enumerate(disputes, start=1):
            line1 = f"{index}. {dispute.customer_name} | Account {dispute.account_number}"
            canvas_obj.drawString(36, y, line1)
            y -= 12
            line2 = f"Type: {dispute.dispute_type} | Effective date: {dispute.effective_date} | Balance: ${dispute.current_balance:,.2f} | Status: {dispute.dispute_status}"
            canvas_obj.drawString(36, y, line2)
            y -= 16

            if y < 60:
                canvas_obj.showPage()
                canvas_obj.setFont("Helvetica", 10)
                y = height - 36

        canvas_obj.save()

    def _rows_to_disputes(self, dispute_rows: List[dict]) -> List[ReportDispute]:
        disputes = []
        for row in dispute_rows:
            dispute_type_code = str(row.get("dispute_type") or "").strip()
            metadata = {
                "customer_name": row.get("customer_name") or "Unknown",
                "account_number": row.get("account_number") or "Unknown",
                "effective_date": str(row.get("effective_date") or "N/A"),
                "current_balance": int(row.get("current_balance") or 0),
                "dispute_status": "Pending review",
            }
            disputes.append(
                ReportDispute(
                    customer_name=metadata["customer_name"],
                    account_number=metadata["account_number"],
                    dispute_type_code=dispute_type_code,
                    dispute_type=DISPUTE_TYPE_MAP.get(dispute_type_code, f"Unknown ({dispute_type_code or 'N/A'})"),
                    effective_date=self._format_date(metadata["effective_date"]),
                    current_balance=metadata["current_balance"],
                    dispute_status=metadata["dispute_status"],
                )
            )
        return disputes

    def _slice_fields(self, line: str) -> dict:
        field_lengths = [
            2, 1, 2, 1, 30, 30, 9, 8, 32, 20, 2, 9, 8, 8, 8, 9, 9, 9, 9, 1, 24, 8, 2, 8,
        ]
        values = []
        cursor = 0
        for length in field_lengths:
            chunk = line[cursor:cursor + length]
            values.append(chunk)
            cursor += length

        fields = {
            "record_type": values[0],
            "metro2_id": values[1],
            "portfolio_type": values[2],
            "account_type": values[3],
            "account_number": values[4],
            "customer_name": values[5],
            "ssn": values[6],
            "date_of_birth": values[7],
            "address": values[8],
            "city": values[9],
            "state": values[10],
            "zip_code": values[11],
            "date_opened": values[12],
            "date_closed": values[13],
            "last_payment_date": values[14],
            "credit_limit": values[15],
            "current_balance": values[16],
            "amount_past_due": values[17],
            "scheduled_payment": values[18],
            "payment_rating": values[19],
            "payment_history_24": values[20],
            "date_of_first_delinq": values[21],
            "compliance_code": values[22],
            "effective_date": values[23],
        }

        if any(char.isalpha() for char in fields["date_of_first_delinq"]):
            fields["date_of_first_delinq"] = ""

        tail = line[-10:].strip()
        if len(tail) >= 10 and tail[:2].isalpha() and tail[2:].isdigit():
            fields["compliance_code"] = tail[:2]
            fields["effective_date"] = tail[2:]

        return fields

    def _format_date(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            return "N/A"
        if len(value) == 8 and value.isdigit():
            return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
        return value
