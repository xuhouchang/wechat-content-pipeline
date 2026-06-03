import argparse


JOB_NAMES = ("collect-daily", "article-daily", "case-daily", "cleanup")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("job_name", choices=JOB_NAMES)
    run_parser.add_argument("--date", required=True)

    return parser
