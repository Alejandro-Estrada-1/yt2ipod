"""CLI entry point for yt2ipod.

Uses argparse (stdlib) to avoid external dependencies for basic operation.
The CLI dispatches to the appropriate interface mode based on arguments.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from yt2ipod import __app_name__, __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for yt2ipod."""
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description="Download music from YouTube, identify metadata, and transfer to legacy Apple devices.",
        epilog="Run without arguments for interactive mode.",
    )

    parser.add_argument(
        "urls",
        nargs="*",
        metavar="URL",
        help="YouTube URL(s) to download. Omit for interactive mode.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"{__app_name__} {__version__}",
    )

    # Interface mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--plain",
        action="store_true",
        default=False,
        help="Use plain terminal output (no TUI).",
    )
    mode_group.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON (for automation).",
    )

    # Pipeline options
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=None,
        help="Directory for output files (default: current directory).",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        default=False,
        help="Keep temporary files after processing (for debugging).",
    )
    parser.add_argument(
        "--no-transfer",
        action="store_true",
        default=False,
        help="Prepare files but skip device transfer.",
    )

    # Transfer
    parser.add_argument(
        "--transfer",
        nargs="+",
        metavar="FILE",
        type=Path,
        default=None,
        help="Transfer existing file(s) to a connected device.",
    )

    # Import local
    parser.add_argument(
        "--import-local",
        nargs="+",
        metavar="FILE",
        type=Path,
        default=None,
        help="Import local audio file(s) for metadata identification and tagging.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for yt2ipod CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Determine mode
    if args.transfer:
        return _handle_transfer(args)
    elif args.import_local:
        return _handle_import(args)
    elif args.urls:
        return _handle_automatic(args)
    else:
        return _handle_interactive(args)


def _handle_interactive(args: argparse.Namespace) -> int:
    """Launch interactive TUI mode."""
    print(f"{__app_name__} {__version__}")
    print()
    print("Interactive mode is not yet implemented.")
    print("Provide a YouTube URL to use automatic mode:")
    print(f"  {__app_name__} <URL>")
    print()
    print("Use --plain for plain terminal output.")
    return 0


def _handle_automatic(args: argparse.Namespace) -> int:
    """Run the full pipeline for given URL(s)."""
    interface = "json" if args.json else ("plain" if args.plain else "auto")
    print(f"{__app_name__} {__version__}")
    print(f"Mode: automatic ({interface})")
    print()
    for url in args.urls:
        print(f"  URL: {url}")
    print()
    print("Pipeline is not yet implemented. Coming in Phase 3+.")
    return 0


def _handle_transfer(args: argparse.Namespace) -> int:
    """Transfer existing files to a connected device."""
    print(f"{__app_name__} {__version__}")
    print("Transfer mode")
    print()
    for f in args.transfer:
        print(f"  File: {f}")
    print()
    print("Transfer is not yet implemented. Coming in Phase 11.")
    return 0


def _handle_import(args: argparse.Namespace) -> int:
    """Import and process local audio files."""
    print(f"{__app_name__} {__version__}")
    print("Import mode")
    print()
    for f in args.import_local:
        print(f"  File: {f}")
    print()
    print("Local import is not yet implemented. Coming in Phase 4+.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
