#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


venv_dir = Path(__file__).resolve().parents[1] / "venv"
venv_python = venv_dir / "bin" / "python"
if venv_python.exists() and sys.prefix != str(venv_dir.resolve()):
    subprocess.run([str(venv_python), __file__], check=True)
    sys.exit(0)

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


SAMPLE_PDF = Path(__file__).resolve().parents[1] / "examples" / "sample_credit_report.pdf"
SAMPLE_CSV = Path(__file__).resolve().parents[1] / "examples" / "generated_sample_disputes.csv"
SAMPLE_DAT = Path(__file__).resolve().parents[1] / "examples" / "sample_pipeline_output.dat"
LETTER_DIR = Path(__file__).resolve().parents[1] / "examples" / "sample_letters"


def build_minimal_pdf(pdf_path: Path, text: str) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica", 10)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    y = 750
    for line in lines:
        c.drawString(40, y, line)
        y -= 14
    c.showPage()
    c.save()


def main() -> int:
    venv_python = Path(__file__).resolve().parents[1] / "venv" / "bin" / "python"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        subprocess.run([str(venv_python), __file__], check=True)
        return 0

    SAMPLE_PDF.parent.mkdir(parents=True, exist_ok=True)

    sample_text = """
    Credit Report Summary
    Name: Jane Consumer
    SSN: 123-45-6789
    Account Number: ACCT-1001
    Date Opened: 2020-01-15
    Current Balance: $2500
    Credit Limit: $3000
    Payment History: on time, but 60 days past due is reflected in the report.
    The account does not belong to the user and appears to be unrelated.
    Last Payment Date: 2024-05-13
    """.strip()

    build_minimal_pdf(SAMPLE_PDF, sample_text)

    python_exec = sys.executable
    venv_python = Path(__file__).resolve().parents[1] / "venv" / "bin" / "python"
    if venv_python.exists():
        python_exec = str(venv_python)

    pipeline_cmd = [
        python_exec,
        "-m",
        "ai_dispute_platform.pipeline.cli",
        "--pdf",
        str(SAMPLE_PDF),
        "--output",
        str(SAMPLE_DAT),
        "--csv-output",
        str(SAMPLE_CSV),
        "--letter-dir",
        str(LETTER_DIR),
    ]

    subprocess.run(pipeline_cmd, check=True)

    print(f"Sample PDF written to: {SAMPLE_PDF}")
    print(f"Generated CSV written to: {SAMPLE_CSV}")
    print(f"Generated Metro 2 file written to: {SAMPLE_DAT}")
    print(f"Generated letters written to: {LETTER_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
