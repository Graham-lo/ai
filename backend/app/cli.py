import argparse

from app.db.session import SessionLocal
from app.schemas.report import ReportRequest
from app.services.report_service import run_report
from app.services.sync_service import run_sync


def main() -> None:
    parser = argparse.ArgumentParser(description="Trade Check CLI")
    sub = parser.add_subparsers(dest="command")

    sync_cmd = sub.add_parser("sync")
    sync_cmd.add_argument("--preset", default=None)
    sync_cmd.add_argument("--exchange", default=None)

    report_cmd = sub.add_parser("report")
    report_cmd.add_argument("--preset", default=None)
    report_cmd.add_argument("--net-mode", default="fees_only")
    report_cmd.add_argument("--exchange", default=None)

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.command == "sync":
            payload = ReportRequest(preset=args.preset, exchange_id=args.exchange)
            run_sync(db, payload)
        elif args.command == "report":
            payload = ReportRequest(preset=args.preset, exchange_id=args.exchange, net_mode=args.net_mode)
            run_report(db, payload)
        else:
            parser.print_help()
    finally:
        db.close()


if __name__ == "__main__":
    main()
