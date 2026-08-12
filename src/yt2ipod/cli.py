"""CLI entry point for yt2ipod.

Uses argparse (stdlib) to avoid external dependencies for basic operation.
The CLI dispatches to the appropriate interface mode based on arguments.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from yt2ipod import __app_name__, __version__
from yt2ipod.core.device.detection import DeviceDetector
from yt2ipod.core.models.config import AppConfig
from yt2ipod.core.pipeline.orchestrator import Pipeline
from yt2ipod.core.transfer.manager import TransferManager
from yt2ipod.interfaces.plain.handler import PlainCLIEventHandler


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

    parser.add_argument(
        "--transfer-method", "-m",
        choices=["afc", "afc2", "usb_ssh", "wifi_ssh"],
        default=None,
        help="Force a specific transfer method (choices: afc, afc2, usb_ssh, wifi_ssh).",
    )

    parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help="Path to cookies file (e.g. cookies.txt) for YouTube download authentication.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for yt2ipod CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Dispatch to handlers
    if args.transfer:
        return asyncio.run(_handle_transfer(args))
    elif args.import_local:
        return asyncio.run(_handle_import(args))
    elif args.urls:
        return asyncio.run(_handle_automatic(args))
    else:
        return _handle_interactive(args)


def _handle_interactive(args: argparse.Namespace) -> int:
    """Launch interactive TUI mode."""
    try:
        from yt2ipod.interfaces.textual.app import run_textual
        detector = DeviceDetector()
        return run_textual(detector=detector)
    except ImportError as e:
        print(f"[!] Warning: {e}", file=sys.stderr)
        print("Please install textual dependencies via: pip install 'yt2ipod[tui]'", file=sys.stderr)
        print("Or run using --plain mode for command line progress.", file=sys.stderr)
        return 1


async def _handle_automatic(args: argparse.Namespace) -> int:
    """Run the full pipeline for given URL(s)."""
    config = AppConfig(
        output_dir=args.output_dir,
        keep_temp=args.keep_temp,
        cookies_file=args.cookies,
    )
    if args.transfer_method:
        config.preferred_transfer_order = [args.transfer_method]

    pipeline = Pipeline(config=config)
    
    if args.json:
        # JSON output mode (emits events as JSON line by line)
        def json_callback(event):
            # Serialize basic events
            event_name = event.__class__.__name__
            data = {"event": event_name, **event.__dict__}
            print(json.dumps(data))
            sys.stdout.flush()

        callback = json_callback
    else:
        # Plain terminal progress
        handler = PlainCLIEventHandler(use_color=True)
        callback = handler.handle_event

    success = True
    for url in args.urls:
        try:
            await pipeline.run(
                url_or_path=url,
                output_dir=config.effective_output_dir,
                event_callback=callback,
                keep_temp=config.keep_temp,
                transfer=not args.no_transfer,
            )
        except Exception as e:
            if args.json:
                print(json.dumps({"event": "Error", "message": str(e)}))
            else:
                print(f"\n[!] Error processing {url}: {e}", file=sys.stderr)
            success = False

    return 0 if success else 1


async def _handle_transfer(args: argparse.Namespace) -> int:
    """Transfer existing files to a connected device."""
    detector = DeviceDetector()
    config = AppConfig()
    if args.transfer_method:
        config.preferred_transfer_order = [args.transfer_method]
    manager = TransferManager(config=config)

    devices = await detector.detect_devices()
    if not devices:
        print("[!] Error: No legacy Apple device detected.", file=sys.stderr)
        return 1

    device = devices[0]
    print(f"[*] Detected device: {device.model} ({device.ios_version})")

    file_paths = []
    for f in args.transfer:
        path = Path(f)
        if not path.exists():
            print(f"[!] Error: File not found: {f}", file=sys.stderr)
            return 1
        file_paths.append(path)

    print(f"[*] Transferring {len(file_paths)} file(s)...")
    result = await manager.transfer_files(file_paths, device)
    if result.success:
        print(f"[OK] Transfer completed successfully using {result.method.value if result.method else 'USB'}.")
        return 0
    else:
        print(f"[!] Transfer failed: {', '.join(result.errors) if result.errors else 'Unknown error'}", file=sys.stderr)
        return 1


async def _handle_import(args: argparse.Namespace) -> int:
    """Import and process local audio files."""
    config = AppConfig(
        output_dir=args.output_dir,
        keep_temp=args.keep_temp,
        cookies_file=args.cookies,
    )
    if args.transfer_method:
        config.preferred_transfer_order = [args.transfer_method]

    pipeline = Pipeline(config=config)
    handler = PlainCLIEventHandler(use_color=True)
    callback = handler.handle_event

    success = True
    for f in args.import_local:
        path = Path(f)
        if not path.exists():
            print(f"[!] Error: File not found: {f}", file=sys.stderr)
            success = False
            continue

        try:
            await pipeline.run(
                url_or_path=str(path),
                output_dir=config.effective_output_dir,
                event_callback=callback,
                keep_temp=config.keep_temp,
                transfer=not args.no_transfer,
            )
        except Exception as e:
            print(f"\n[!] Error importing {f}: {e}", file=sys.stderr)
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
