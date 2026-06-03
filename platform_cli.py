from pathlib import Path

from content_platform.cli import build_parser
from content_platform.runtime import run_cleanup, run_collect_daily


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace_dir = Path(args.workspace_dir).resolve() if getattr(args, "workspace_dir", None) else None

    if args.command == "run":
        if args.job_name == "collect-daily":
            run_collect_daily(args.date, workspace_dir=workspace_dir)
            return 0
        if args.job_name == "cleanup":
            run_cleanup(args.date, workspace_dir=workspace_dir)
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
