from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import Dict, Optional

from ai_dispute_platform.pipeline.dispute_pipeline import DisputePipeline
from ai_dispute_platform.pipeline.notification import EmailNotifier


class BatchFolderWatcher:
    def __init__(
        self,
        watch_dir: Path,
        interval: int = 5,
        once: bool = False,
        bank_name: str = "Bank Customer",
        preparer: str = "AI Credit Dispute Platform",
        notify_to: str | None = None,
        notify_on_error_only: bool = False,
        smtp_server: str | None = None,
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        smtp_sender: str | None = None,
    ):
        self.watch_dir = watch_dir
        self.interval = interval
        self.once = once
        self.bank_name = bank_name
        self.preparer = preparer
        self.notify_to = notify_to
        self.notify_on_error_only = notify_on_error_only
        self.pipeline = DisputePipeline(bank_name=self.bank_name, preparer=self.preparer)
        self.completed_dir = self.watch_dir / "completed"
        self.failed_dir = self.watch_dir / "failed"
        self.output_dir = self.watch_dir / "output"
        self._seen_files: Dict[Path, tuple[int, float]] = {}
        self._processing: set[Path] = set()
        self.notifier = EmailNotifier(
            recipient=notify_to,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            smtp_sender=smtp_sender,
        )

    async def run(self) -> int:
        self._ensure_directories()
        await self._watch_loop()
        return 0

    def _ensure_directories(self) -> None:
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.completed_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def _watch_loop(self) -> None:
        if self.once:
            await self._scan_folder()
            await asyncio.sleep(self.interval)
            await self._scan_folder()
            return

        while True:
            await self._scan_folder()
            await asyncio.sleep(self.interval)

    async def _scan_folder(self) -> None:
        pdf_files = [path for path in self.watch_dir.glob("*.pdf") if path.is_file()]
        current_stats: Dict[Path, tuple[int, float]] = {}

        for pdf_path in pdf_files:
            if pdf_path in self._processing:
                continue

            try:
                stat = pdf_path.stat()
            except OSError:
                continue

            current_stats[pdf_path] = (stat.st_size, stat.st_mtime)
            previous_stats = self._seen_files.get(pdf_path)

            if previous_stats is None:
                continue

            if previous_stats != current_stats[pdf_path]:
                continue

            await self._process_file(pdf_path)

        self._seen_files = current_stats

    async def _process_file(self, pdf_path: Path) -> None:
        self._processing.add(pdf_path)
        stem = pdf_path.stem
        output_dat = self.output_dir / f"{stem}.dat"
        output_csv = self.output_dir / f"{stem}.csv"
        letter_dir = self.output_dir / f"{stem}_letters"

        try:
            print(f"Processing PDF: {pdf_path.name}")
            result = await asyncio.to_thread(
                self.pipeline.run,
                pdf_path,
                output_dat,
                output_csv,
                letter_dir,
            )
            destination = self._resolve_destination(self.completed_dir, pdf_path.name)
            pdf_path.replace(destination)
            print(f"Processed successfully: {pdf_path.name} -> {destination}")
            if self.notify_to and not self.notify_on_error_only:
                if self.notifier.is_configured():
                    report_txt = self.output_dir / f"{stem}_report.txt"
                    report_html = self.output_dir / f"{stem}_report.html"
                    report_pdf = self.output_dir / f"{stem}_report.pdf"
                    try:
                        self.notifier.send_completion(
                            file_name=pdf_path.name,
                            bank_name=self.bank_name,
                            finding_count=result.get("finding_count", 0),
                            output_dat=str(output_dat),
                            output_csv=str(output_csv),
                            report_txt=str(report_txt),
                            report_html=str(report_html),
                            report_pdf=str(report_pdf),
                        )
                    except Exception as notify_exc:
                        print(f"Warning: failed to send notification email: {notify_exc}")
                else:
                    print("Warning: SMTP is not configured; skipping notification email")
        except Exception as exc:
            print(f"Error processing {pdf_path.name}: {exc}")
            error_path = self.failed_dir / f"{stem}_error.log"
            with error_path.open("w", encoding="utf-8") as handle:
                handle.write(f"Failed to process {pdf_path.name}\n")
                handle.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            destination = self._resolve_destination(self.failed_dir, pdf_path.name)
            try:
                pdf_path.replace(destination)
            except OSError:
                pass
            print(f"Moved failed PDF to: {destination}")
            print(f"Error log: {error_path}")
            if self.notify_to:
                if self.notifier.is_configured():
                    excerpt = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                    try:
                        self.notifier.send_failure(
                            file_name=pdf_path.name,
                            bank_name=self.bank_name,
                            error_excerpt=excerpt,
                        )
                    except Exception as notify_exc:
                        print(f"Warning: failed to send failure notification email: {notify_exc}")
                else:
                    print("Warning: SMTP is not configured; skipping failure notification email")
        finally:
            self._processing.discard(pdf_path)

    def _resolve_destination(self, folder: Path, file_name: str) -> Path:
        destination = folder / file_name
        if not destination.exists():
            return destination

        stem = Path(file_name).stem
        suffix = Path(file_name).suffix
        counter = 1
        while True:
            candidate = folder / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
