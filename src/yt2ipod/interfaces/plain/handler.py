"""Plain CLI event handler (Phase 13).

Outputs clean, formatted text to stdout/stderr in response to pipeline events.
"""

from __future__ import annotations

import sys
from typing import Any

from yt2ipod.core.models import events


class PlainCLIEventHandler:
    """Listens to pipeline events and prints user-friendly progress information."""

    def __init__(self, use_color: bool = True) -> None:
        self.use_color = use_color

    def _color(self, text: str, color_code: str) -> str:
        if not self.use_color:
            return text
        return f"\033[{color_code}m{text}\033[0m"

    def green(self, text: str) -> str:
        return self._color(text, "32")

    def yellow(self, text: str) -> str:
        return self._color(text, "33")

    def blue(self, text: str) -> str:
        return self._color(text, "34")

    def red(self, text: str) -> str:
        return self._color(text, "31")

    def bold(self, text: str) -> str:
        return self._color(text, "1")

    def draw_progress_bar(self, percent: float, width: int = 30) -> str:
        """Create a simple ASCII progress bar."""
        filled_len = int(round(width * percent / 100))
        bar = "=" * filled_len + "-" * (width - filled_len)
        return f"[{bar}] {percent:3.0f}%"

    def handle_event(self, event: events.PipelineEvent) -> None:
        """Process and print a pipeline event."""
        if isinstance(event, events.DownloadStarted):
            print(self.blue(f"[*] Downloading: {event.url}"))
            if event.title:
                print(f"    Title: {event.title}")

        elif isinstance(event, events.DownloadProgress):
            bar = self.draw_progress_bar(event.percent)
            speed = f" @ {event.speed}" if event.speed else ""
            sys.stdout.write(f"\r    {bar}{speed}")
            sys.stdout.flush()

        elif isinstance(event, events.DownloadCompleted):
            # Print newline to clear the progress bar line
            sys.stdout.write("\n")
            print(self.green(f"[+] Download completed! {event.file_size / (1024 * 1024):.2f} MB in {event.duration:.1f}s"))

        elif isinstance(event, events.ConversionStarted):
            print(self.blue(f"[*] Converting audio from {event.source_format} to {event.target_format}..."))

        elif isinstance(event, events.ConversionProgress):
            bar = self.draw_progress_bar(event.percent)
            sys.stdout.write(f"\r    {bar}")
            sys.stdout.flush()

        elif isinstance(event, events.ConversionCompleted):
            sys.stdout.write("\n")
            print(self.green("[+] Audio conversion finished successfully."))

        elif isinstance(event, events.MetadataSearchStarted):
            print(self.blue(f"[*] Querying MusicBrainz for: '{event.artist} - {event.title}'"))

        elif isinstance(event, events.MetadataMatched):
            confidence_pct = event.confidence * 100
            color_fn = self.green if event.confidence >= 0.7 else self.yellow
            print(color_fn(f"[+] Match found! (Confidence: {confidence_pct:.1f}%)"))
            print(f"    Artist: {event.artist}")
            print(f"    Title:  {event.title}")
            print(f"    Album:  {event.album}")

        elif isinstance(event, events.MetadataNotFound):
            print(self.yellow(f"[!] No metadata match found: {event.reason}"))

        elif isinstance(event, events.ArtworkSearchStarted):
            print(self.blue(f"[*] Querying Cover Art Archive for release: {event.release_id}"))

        elif isinstance(event, events.ArtworkFound):
            print(self.green(f"[+] Cover art found: {event.width}x{event.height} pixels."))

        elif isinstance(event, events.ArtworkNotFound):
            print(self.yellow(f"[!] No cover art found: {event.reason}"))

        elif isinstance(event, events.TaggingStarted):
            print(self.blue("[*] Embedding metadata and artwork into output file..."))

        elif isinstance(event, events.TaggingCompleted):
            print(self.green("[+] Output file tagged successfully."))

        elif isinstance(event, events.DeviceDetected):
            print(self.green(f"[+] Device detected: {event.model} (iOS {event.ios_version}) via {event.connection}"))
            print(f"    Capabilities: {event.capabilities}")

        elif isinstance(event, events.DeviceNotFound):
            print(self.yellow("[!] No compatible iOS/iPod device detected."))

        elif isinstance(event, events.TransferStarted):
            print(self.blue(f"[*] Transferring to device using {event.method}..."))

        elif isinstance(event, events.TransferProgress):
            bar = self.draw_progress_bar(event.percent)
            sys.stdout.write(f"\r    {bar} ({event.files_completed}/{event.files_total} files)")
            sys.stdout.flush()

        elif isinstance(event, events.TransferCompleted):
            sys.stdout.write("\n")
            print(self.green(f"[+] Transfer completed! {event.files_transferred} files in {event.duration:.1f}s"))

        elif isinstance(event, events.TransferFailed):
            sys.stdout.write("\n")
            print(self.red(f"[-] Transfer failed: {event.error}"))

        elif isinstance(event, events.CleanupStarted):
            print(self.blue("[*] Cleaning up temporary files..."))

        elif isinstance(event, events.CleanupCompleted):
            print(self.green("[+] Cleanup completed."))
