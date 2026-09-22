"""Command-line interface for preflight, smoke capture, capture, and validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contracts import LABELS
from .preflight import run_preflight


def _capture_command(arguments: argparse.Namespace) -> None:
    from .capture import capture

    capture(arguments)


def _validate_command(arguments: argparse.Namespace) -> None:
    from .validation import finalize_run

    if not arguments.write_final:
        raise SystemExit("Validation is non-destructive by default. Pass --write-final to combine shards and write CSV/Parquet.")
    report = finalize_run(Path(arguments.run_dir), arguments.rows_per_class)
    print(json.dumps(report, indent=2, sort_keys=True))


def _smoke_command(arguments: argparse.Namespace) -> None:
    smoke_args = argparse.Namespace(
        run_dir=arguments.run_dir,
        rows_per_class=1,
        shard_size=1,
        experiment_id="smoke-mininet-ovs-ryu",
        resume=False,
    )
    _capture_command(smoke_args)
    print(f"Captured one measured window for each of {len(LABELS)} classes in {arguments.run_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measured Mininet/OVS/Ryu SDN DDoS dataset lab")
    subcommands = parser.add_subparsers(dest="command", required=True)

    preflight = subcommands.add_parser("preflight", help="check Linux, OVS, Mininet, and controller requirements")
    preflight.add_argument("--strict", action="store_true", help="exit non-zero when a required capability is absent")
    preflight.set_defaults(handler=lambda args: print(json.dumps(run_preflight(strict=args.strict).details, indent=2, sort_keys=True)))

    capture = subcommands.add_parser("capture", help="capture missing per-class windows into resumable shards")
    capture.add_argument("--run-dir", required=True, help="persistent run artifact directory")
    capture.add_argument("--rows-per-class", type=int, default=10_000)
    capture.add_argument("--shard-size", type=int, default=250)
    capture.add_argument("--experiment-id", default=None)
    capture.add_argument("--resume", action="store_true", help="continue from existing completed shards")
    capture.set_defaults(handler=_capture_command)

    smoke = subcommands.add_parser("smoke", help="run one measured window per class")
    smoke.add_argument("--run-dir", default="runs/smoke")
    smoke.set_defaults(handler=_smoke_command)

    validate = subcommands.add_parser("validate", help="validate shards and emit final CSV/Parquet artifacts")
    validate.add_argument("--run-dir", required=True)
    validate.add_argument("--rows-per-class", type=int, default=10_000)
    validate.add_argument("--write-final", action="store_true")
    validate.set_defaults(handler=_validate_command)
    return parser


def main() -> None:
    parser = build_parser()
    arguments = parser.parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
