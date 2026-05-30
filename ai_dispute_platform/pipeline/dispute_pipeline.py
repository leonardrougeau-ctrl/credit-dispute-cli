from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from ai_dispute_platform.analysis.ai_analysis import AIAnalyzer
from ai_dispute_platform.reporting.report_generator import Metro2ReportGenerator


class DisputePipeline:
    def __init__(self, bank_name: str = "Bank Customer", preparer: str = "AI Credit Dispute Platform"):
        self.bank_name = bank_name
        self.preparer = preparer

    def generate_reports_only(self, input_path: str | Path, bank_name: str | None = None) -> dict:
        report_generator = Metro2ReportGenerator()
        return report_generator.generate_reports(input_path, bank_name=bank_name or self.bank_name)

    def run(self, pdf_path: str | Path, output_dat: str | Path, output_csv: str | Path | None = None, letter_dir: str | Path | None = None) -> dict:
        pdf_path = Path(pdf_path)
        output_dat = Path(output_dat)
        output_dat.parent.mkdir(parents=True, exist_ok=True)

        analyzer = AIAnalyzer()
        result = analyzer.analyze_pdf(pdf_path, bank_name=self.bank_name)

        if output_csv is None:
            output_csv = output_dat.with_suffix(".csv")
        output_csv = Path(output_csv)

        csv_path = analyzer.export_to_csv(result.metro2_rows, output_csv)

        if letter_dir is not None:
            letter_dir = Path(letter_dir)
            letter_dir.mkdir(parents=True, exist_ok=True)
            for key, letter in result.letters.items():
                safe_name = key.replace("/", "_").replace(" ", "_")
                letter_path = letter_dir / f"{safe_name}.txt"
                letter_path.write_text(letter)

        cli_path = Path(__file__).resolve().parents[2] / "cli.py"
        subprocess.run(
            [
                sys.executable,
                str(cli_path),
                "generate",
                "--input",
                str(csv_path),
                "--output",
                str(output_dat),
                "--bank",
                self.bank_name,
                "--preparer",
                self.preparer,
            ],
            check=True,
        )

        report_generator = Metro2ReportGenerator()
        report_paths = report_generator.generate_reports(output_dat, bank_name=self.bank_name, dispute_rows=result.metro2_rows)

        return {
            "csv_path": str(csv_path),
            "output_dat": str(output_dat),
            "letter_dir": str(letter_dir) if letter_dir else None,
            "finding_count": len(result.findings),
            "report_txt_path": report_paths["txt_path"],
            "report_html_path": report_paths["html_path"],
            "report_pdf_path": report_paths["pdf_path"],
        }
