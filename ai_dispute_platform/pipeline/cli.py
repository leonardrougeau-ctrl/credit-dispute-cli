from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from pathlib import Path

from ai_dispute_platform.pipeline.batch_watcher import BatchFolderWatcher
from ai_dispute_platform.pipeline.dispute_pipeline import DisputePipeline
from ai_dispute_platform.pipeline.notification import EmailNotifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Credit Dispute Automation Pipeline")
    parser.add_argument("--pdf", default=None, help="Path to the input PDF credit report")
    parser.add_argument("--output", default=None, help="Output Metro 2 file path")
    parser.add_argument("--input", default=None, help="Existing CSV or Metro 2 file for report-only mode")
    parser.add_argument("--watch", default=None, help="Watch a folder for new PDF files to process")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds when watching a folder")
    parser.add_argument("--once", action="store_true", help="Process existing files once and exit when watching")
    parser.add_argument("--notify", default=None, help="Email address to notify when processing completes")
    parser.add_argument("--notify-on-error-only", action="store_true", help="Only send email notifications when processing fails")
    parser.add_argument("--smtp-server", default=None, help="SMTP server hostname")
    parser.add_argument("--smtp-port", type=int, default=587, help="SMTP server port")
    parser.add_argument("--smtp-user", default=None, help="SMTP username")
    parser.add_argument("--smtp-password", default=None, help="SMTP password")
    parser.add_argument("--smtp-sender", default=None, help="From email address for SMTP notifications")
    parser.add_argument("--bank", default="Bank Customer", help="Bank name written into the Metro 2 header")
    parser.add_argument("--preparer", default="AI Credit Dispute Platform", help="Preparer name")
    parser.add_argument("--csv-output", default=None, help="Optional CSV file path for intermediate dispute rows")
    parser.add_argument("--letter-dir", default=None, help="Optional directory to save generated letters")
    parser.add_argument("--report-only", action="store_true", help="Generate human-readable reports from an existing CSV or Metro 2 file")
    return parser


def _get_error_excerpt(exc: Exception) -> str:
    stack = traceback.format_exception(type(exc), exc, exc.__traceback__)
    excerpt = "".join(stack[-10:])
    return excerpt.strip()


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    pipeline = DisputePipeline(bank_name=args.bank, preparer=args.preparer)
    notifier = EmailNotifier(
        recipient=args.notify,
        smtp_server=args.smtp_server,
        smtp_port=args.smtp_port,
        smtp_user=args.smtp_user,
        smtp_password=args.smtp_password,
        smtp_sender=args.smtp_sender,
    )

    if args.report_only:
        if args.watch:
            parser.error("--watch cannot be used with --report-only")
        if not args.input:
            parser.error("--input is required when --report-only is used")

        try:
            result = pipeline.generate_reports_only(args.input, bank_name=args.bank)
            print("Human-readable reports generated")
            print(f"TXT report: {result['txt_path']}")
            print(f"HTML report: {result['html_path']}")
            print(f"PDF report: {result['pdf_path']}")
            print(f"Disputes included: {result['dispute_count']}")

            if args.notify and not args.notify_on_error_only:
                if notifier.is_configured():
                    notifier.send_completion(
                        file_name=Path(args.input).name,
                        bank_name=args.bank,
                        finding_count=result['dispute_count'],
                        output_dat=args.input,
                        output_csv=args.input,
                        report_txt=result['txt_path'],
                        report_html=result['html_path'],
                        report_pdf=result['pdf_path'],
                    )
                else:
                    print("Warning: SMTP is not configured; skipping notification email")
            return 0
        except Exception as exc:
            error_excerpt = _get_error_excerpt(exc)
            print(f"Error: {exc}")
            if args.notify:
                if notifier.is_configured():
                    notifier.send_failure(
                        file_name=Path(args.input).name,
                        bank_name=args.bank,
                        error_excerpt=error_excerpt,
                    )
                else:
                    print("Warning: SMTP is not configured; skipping failure notification email")
            return 1

    if args.watch:
        if args.pdf or args.output:
            parser.error("--watch cannot be used with --pdf or --output")

        watch_path = Path(args.watch)
        watcher = BatchFolderWatcher(
            watch_dir=watch_path,
            interval=args.interval,
            once=args.once,
            bank_name=args.bank,
            preparer=args.preparer,
            notify_to=args.notify,
            notify_on_error_only=args.notify_on_error_only,
            smtp_server=args.smtp_server,
            smtp_port=args.smtp_port,
            smtp_user=args.smtp_user,
            smtp_password=args.smtp_password,
            smtp_sender=args.smtp_sender,
        )
        print(f"Watching folder: {watch_path.resolve()}\nPoll interval: {args.interval}s\nOnce mode: {args.once}")
        return asyncio.run(watcher.run())

    if not args.pdf or not args.output:
        parser.error("--pdf and --output are required unless --report-only or --watch is used")

    try:
        result = pipeline.run(
            pdf_path=args.pdf,
            output_dat=args.output,
            output_csv=args.csv_output,
            letter_dir=args.letter_dir,
        )
        print("AI dispute pipeline complete")
        print(f"Generated CSV: {result['csv_path']}")
        print(f"Generated Metro 2 file: {result['output_dat']}")
        print(f"Disputes detected: {result['finding_count']}")

        if args.notify and not args.notify_on_error_only:
            if notifier.is_configured():
                notifier.send_completion(
                    file_name=Path(args.pdf).name,
                    bank_name=args.bank,
                    finding_count=result['finding_count'],
                    output_dat=result['output_dat'],
                    output_csv=result['csv_path'],
                    report_txt=result['report_txt_path'],
                    report_html=result['report_html_path'],
                    report_pdf=result['report_pdf_path'],
                )
            else:
                print("Warning: SMTP is not configured; skipping notification email")

        return 0
    except Exception as exc:
        error_excerpt = _get_error_excerpt(exc)
        print(f"Error: {exc}")
        if args.notify:
            if notifier.is_configured():
                notifier.send_failure(
                    file_name=Path(args.pdf).name,
                    bank_name=args.bank,
                    error_excerpt=error_excerpt,
                )
            else:
                print("Warning: SMTP is not configured; skipping failure notification email")
        return 1


if __name__ == "__main__":
    sys.exit(main())
