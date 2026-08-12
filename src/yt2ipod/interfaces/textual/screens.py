"""Textual TUI screen definitions for yt2ipod (Phase 14).

Implements interactive screens using textual widgets.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, Log, ProgressBar, Select, Static

from yt2ipod.core.device.detection import DeviceDetector
from yt2ipod.core.models.config import AppConfig
from yt2ipod.core.models.transfer import TransferMethod
from yt2ipod.core.pipeline import Pipeline
from yt2ipod.core.transfer.manager import TransferManager

if TYPE_CHECKING:
    from textual.app import App


class AboutScreen(Screen):
    """Screen displaying information about yt2ipod."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="about-container"):
            yield Static(
                "[bold accent]yt2ipod[/bold accent] - Music to Legacy Devices\n\n"
                "Version: 0.1.0\n"
                "License: MIT\n\n"
                "A specialized tool that automates downloading audio from YouTube, "
                "resolving high-quality metadata via MusicBrainz, obtaining album artwork, "
                "tagging MP3 files, and transferring them to legacy Apple devices (iPods/iPhones).\n\n"
                "Built with Textual, Rich, and open-source binaries (yt-dlp, FFmpeg, ifuse).\n\n"
                "Press [bold]B[/bold] to go back.",
                id="about-text"
            )
        yield Footer()


class SettingsScreen(Screen):
    """Screen for configuring application settings."""

    def __init__(self, config: AppConfig | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config or AppConfig()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="settings-container"):
            yield Label("Application Settings", id="settings-title")

            yield Label("Default Output Directory:")
            yield Input(
                value=str(self.config.output_dir or Path.cwd()),
                placeholder="Path to output directory...",
                id="setting-output-dir"
            )

            yield Label("SSH Identity File (Optional):")
            yield Input(
                value=str(self.config.ssh_settings.identity_file or ""),
                placeholder="Path to private key...",
                id="setting-ssh-key"
            )

            yield Label("SSH Host Username:")
            yield Input(
                value=self.config.ssh_settings.username or "mobile",
                placeholder="mobile",
                id="setting-ssh-user"
            )

            yield Label("Duplicate Music Policy:")
            yield Select(
                options=[("Rename file", "rename"), ("Overwrite file", "overwrite"), ("Skip", "skip")],
                value=self.config.duplicate_policy.value,
                id="setting-duplicate-policy"
            )

            yield Label("iPod Music Directory:")
            yield Input(
                value=self.config.device_music_dir or "/var/mobile/Media/",
                placeholder="/var/mobile/Media/mImport/",
                id="setting-device-music-dir"
            )

            with Horizontal():
                yield Button("Save", variant="success", id="settings-save")
                yield Button("Cancel", variant="error", id="settings-cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-save":
            out_dir = self.query_one("#setting-output-dir", Input).value
            ssh_key = self.query_one("#setting-ssh-key", Input).value
            ssh_user = self.query_one("#setting-ssh-user", Input).value
            policy = self.query_one("#setting-duplicate-policy", Select).value
            dev_music = self.query_one("#setting-device-music-dir", Input).value

            self.config.output_dir = Path(out_dir) if out_dir else None
            self.config.ssh_settings.username = ssh_user
            self.config.ssh_settings.identity_file = Path(ssh_key) if ssh_key else None
            self.config.device_music_dir = dev_music or "/var/mobile/Media/"
            
            from yt2ipod.core.models.config import DuplicatePolicy
            if policy:
                self.config.duplicate_policy = DuplicatePolicy(policy)

            self.app.notify("Settings saved successfully!")
            self.app.pop_screen()
        elif event.button.id == "settings-cancel":
            self.app.pop_screen()


class DeviceInfoScreen(Screen):
    """Screen showing detailed information of connected devices."""

    def __init__(self, detector: DeviceDetector | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.detector = detector or DeviceDetector()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="device-info-container"):
            yield Label("Connected Apple Devices", id="device-title")
            yield Label("Scanning devices...", id="device-scan-status")
            yield DataTable(id="device-table")
            yield Button("Refresh", variant="primary", id="device-refresh")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_devices()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "device-refresh":
            await self.refresh_devices()

    async def refresh_devices(self) -> None:
        status_label = self.query_one("#device-scan-status", Label)
        table = self.query_one("#device-table", DataTable)
        table.clear(columns=True)
        
        status_label.update("Scanning USB bus for iOS devices...")
        
        try:
            devices = await self.detector.detect_devices()
            if not devices:
                status_label.update("[yellow]No iOS devices detected. Connect your device via USB and accept the trust prompt.[/yellow]")
                return

            status_label.update(f"[green]Found {len(devices)} device(s)[/green]")
            
            # Setup columns
            table.add_columns("Property", "Value")
            
            device = devices[0]
            caps = device.capabilities
            
            rows = [
                ("Device Model", device.model),
                ("iOS Version", device.ios_version),
                ("CPU Architecture", device.architecture.value),
                ("UDID / Identifier", device.serial),
                ("USB Connection", "Yes" if caps.usb else "No"),
                ("AFC (Mounting)", "Supported" if caps.afc else "Not supported"),
                ("AFC2 (Root mount)", "Available" if caps.afc2 else "Not detected"),
                ("SSH Over WiFi", "Yes" if caps.ssh else "No"),
                ("SSH Over USB", "Yes" if caps.usb_ssh else "No"),
            ]
            table.add_rows(rows)
            
        except Exception as e:
            status_label.update(f"[red]Scan failed: {e}[/red]")


class DownloadScreen(Screen):
    """Screen for downloading videos from YouTube with visual progress."""

    def __init__(self, config: AppConfig | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config or AppConfig()
        self.pipeline = Pipeline(config=self.config)
        self.active_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="download-container"):
            yield Label("Download from YouTube", id="download-title")
            
            yield Label("YouTube URL:")
            yield Input(placeholder="https://youtu.be/...", id="youtube-url")
            
            yield Label("Forced Transfer Method (Optional):")
            yield Select(
                options=[
                    ("Automatic Selection", "auto"),
                    ("USB / AFC (Standard)", "afc"),
                    ("USB / AFC2 (Jailbroken Root)", "afc2"),
                    ("USB / SSH (Jailbroken)", "usb_ssh"),
                    ("Wi-Fi / SSH (Jailbroken)", "wifi_ssh")
                ],
                value="auto",
                id="transfer-method-select"
            )

            yield Checkbox("Skip device transfer (download local copy only)", value=False, id="skip-transfer-checkbox")
            
            yield Button("Download and Process", variant="success", id="btn-download")
            
            yield Label("", id="download-status-text")
            yield ProgressBar(id="download-progress", show_percentage=True, show_eta=False)
            yield Log(id="download-log")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-download":
            url = self.query_one("#youtube-url", Input).value.strip()
            if not url:
                self.app.notify("Please enter a valid YouTube URL", severity="warning")
                return

            method = self.query_one("#transfer-method-select", Select).value
            skip_transfer = self.query_one("#skip-transfer-checkbox", Checkbox).value

            # Configure transfer method order
            if method and method != "auto":
                self.config.preferred_transfer_order = [method]
            else:
                self.config.preferred_transfer_order = ["afc", "afc2", "usb_ssh", "wifi_ssh"]

            # Disable button during execution
            btn = self.query_one("#btn-download", Button)
            btn.disabled = True

            # Clear status and progress
            self.query_one("#download-status-text", Label).update("Initializing download...")
            self.query_one("#download-progress", ProgressBar).update(total=100, progress=0)
            log = self.query_one("#download-log", Log)
            log.clear()

            # Start pipeline run task
            self.active_task = asyncio.create_task(
                self.run_pipeline_task(url, not skip_transfer)
            )

    async def run_pipeline_task(self, url: str, transfer: bool) -> None:
        log = self.query_one("#download-log", Log)
        progress_bar = self.query_one("#download-progress", ProgressBar)
        status_label = self.query_one("#download-status-text", Label)

        def event_callback(event) -> None:
            # Safely handle events from any thread
            if threading.current_thread() is threading.main_thread():
                self.process_pipeline_event(event)
            else:
                self.app.call_from_thread(self.process_pipeline_event, event)

        try:
            await self.pipeline.run(
                url_or_path=url,
                output_dir=self.config.effective_output_dir,
                event_callback=event_callback,
                keep_temp=self.config.keep_temp,
                transfer=transfer
            )
            status_label.update("[green]Process finished successfully![/green]")
            self.app.notify("YouTube download and transfer completed!")
        except Exception as e:
            status_label.update(f"[red]Error: {e}[/red]")
            log.write_line(f"ERROR: {e}")
            self.app.notify(f"Process failed: {e}", severity="error")
        finally:
            self.query_one("#btn-download", Button).disabled = False

    def process_pipeline_event(self, event) -> None:
        log = self.query_one("#download-log", Log)
        progress_bar = self.query_one("#download-progress", ProgressBar)
        status_label = self.query_one("#download-status-text", Label)

        from yt2ipod.core.models import events
        event_name = event.__class__.__name__

        if isinstance(event, events.DownloadStarted):
            status_label.update(f"Downloading: {event.url}")
            log.write_line(f"[*] Starting download from YouTube...")
        elif isinstance(event, events.DownloadProgress):
            progress_bar.update(progress=int(event.percent))
            status_label.update(f"Downloading: {event.percent:.1f}% ({event.speed})")
        elif isinstance(event, events.DownloadCompleted):
            log.write_line(f"[+] Download finished ({event.file_size / (1024*1024):.2f} MB)")
            progress_bar.update(progress=100)
        elif isinstance(event, events.ConversionStarted):
            status_label.update("Converting to MP3...")
            log.write_line(f"[*] Converting audio to MP3 format...")
        elif isinstance(event, events.ConversionProgress):
            progress_bar.update(progress=int(event.percent))
        elif isinstance(event, events.ConversionCompleted):
            log.write_line(f"[+] Audio converted successfully to MP3")
            progress_bar.update(progress=100)
        elif isinstance(event, events.MetadataSearchStarted):
            status_label.update("Querying MusicBrainz metadata...")
            log.write_line(f"[*] Searching MusicBrainz database...")
        elif isinstance(event, events.MetadataMatched):
            log.write_line(f"[+] Metadata match found! ({event.confidence*100:.1f}% confidence)")
            log.write_line(f"    Artist: {event.artist} | Title: {event.title} | Album: {event.album}")
        elif isinstance(event, events.MetadataNotFound):
            log.write_line(f"[!] No confident metadata found: {event.reason}")
        elif isinstance(event, events.ArtworkSearchStarted):
            status_label.update("Querying artwork cover...")
            log.write_line(f"[*] Querying Cover Art Archive for release: {event.release_id}")
        elif isinstance(event, events.ArtworkFound):
            log.write_line(f"[+] Artwork cover found: {event.width}x{event.height}")
        elif isinstance(event, events.ArtworkNotFound):
            log.write_line(f"[!] Cover artwork not found: {event.reason}")
        elif isinstance(event, events.TaggingStarted):
            status_label.update("Embedding metadata...")
        elif isinstance(event, events.TaggingCompleted):
            log.write_line(f"[+] Metadata tags embedded successfully")
        elif isinstance(event, events.DeviceDetected):
            log.write_line(f"[+] Device detected: {event.model} via {event.connection}")
        elif isinstance(event, events.TransferStarted):
            status_label.update("Transferring to device...")
            log.write_line(f"[*] Transferring to iPod via {event.method}...")
        elif isinstance(event, events.TransferProgress):
            progress_bar.update(progress=int(event.percent))
        elif isinstance(event, events.TransferCompleted):
            log.write_line(f"[+] Transfer completed successfully!")
            progress_bar.update(progress=100)
        elif isinstance(event, events.CleanupStarted):
            status_label.update("Cleaning up...")
        elif isinstance(event, events.CleanupCompleted):
            log.write_line(f"[+] Temporaries cleaned up.")
            status_label.update("Ready.")


class ImportScreen(Screen):
    """Screen for importing and tagging local music files."""

    def __init__(self, config: AppConfig | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config or AppConfig()
        self.pipeline = Pipeline(config=self.config)
        self.active_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="import-container"):
            yield Label("Import Local Music", id="import-title")
            
            yield Label("Local File Path:")
            yield Input(placeholder="/path/to/song.wav or .mp3", id="import-file-path")
            
            yield Checkbox("Skip device transfer (tag local file only)", value=False, id="import-skip-transfer")
            
            yield Button("Import and Tag", variant="success", id="btn-import")
            
            yield Label("", id="import-status-text")
            yield Log(id="import-log")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-import":
            path_str = self.query_one("#import-file-path", Input).value.strip()
            if not path_str:
                self.app.notify("Please enter a valid file path", severity="warning")
                return

            path = Path(path_str)
            if not path.exists():
                self.app.notify(f"File not found: {path_str}", severity="error")
                return

            skip_transfer = self.query_one("#import-skip-transfer", Checkbox).value

            btn = self.query_one("#btn-import", Button)
            btn.disabled = True

            self.query_one("#import-status-text", Label).update("Starting import...")
            self.query_one("#import-log", Log).clear()

            self.active_task = asyncio.create_task(
                self.run_import_task(path, not skip_transfer)
            )

    async def run_import_task(self, path: Path, transfer: bool) -> None:
        log = self.query_one("#import-log", Log)
        status_label = self.query_one("#import-status-text", Label)

        def event_callback(event) -> None:
            # Safely handle events from any thread
            if threading.current_thread() is threading.main_thread():
                self.process_import_event(event)
            else:
                self.app.call_from_thread(self.process_import_event, event)

        try:
            await self.pipeline.run(
                url_or_path=str(path),
                output_dir=self.config.effective_output_dir,
                event_callback=event_callback,
                keep_temp=self.config.keep_temp,
                transfer=transfer
            )
            status_label.update("[green]Import completed successfully![/green]")
            self.app.notify("Music file imported and processed!")
        except Exception as e:
            status_label.update(f"[red]Error: {e}[/red]")
            log.write_line(f"ERROR: {e}")
            self.app.notify(f"Import failed: {e}", severity="error")
        finally:
            self.query_one("#btn-import", Button).disabled = False

    def process_import_event(self, event) -> None:
        log = self.query_one("#import-log", Log)
        status_label = self.query_one("#import-status-text", Label)

        from yt2ipod.core.models import events
        event_name = event.__class__.__name__

        if isinstance(event, events.ConversionStarted):
            status_label.update("Converting audio...")
            log.write_line(f"[*] Converting audio to MP3 format...")
        elif isinstance(event, events.ConversionCompleted):
            log.write_line(f"[+] Audio converted successfully")
        elif isinstance(event, events.MetadataSearchStarted):
            status_label.update("Identifying metadata...")
            log.write_line(f"[*] Querying MusicBrainz database...")
        elif isinstance(event, events.MetadataMatched):
            log.write_line(f"[+] Matches: {event.artist} - {event.title} ({event.album})")
        elif isinstance(event, events.ArtworkSearchStarted):
            status_label.update("Downloading cover art...")
        elif isinstance(event, events.ArtworkFound):
            log.write_line(f"[+] Cover art found successfully")
        elif isinstance(event, events.TaggingCompleted):
            log.write_line(f"[+] Metadata tags embedded")
        elif isinstance(event, events.TransferStarted):
            status_label.update("Transferring to device...")
            log.write_line(f"[*] Transferring to iPod via {event.method}...")
        elif isinstance(event, events.TransferCompleted):
            log.write_line(f"[+] Transfer completed successfully")
        elif isinstance(event, events.CleanupCompleted):
            log.write_line(f"[+] Cleaned up temporary files")
            status_label.update("Ready.")


class SelectFilesScreen(Screen):
    """Screen for selecting and transferring existing local MP3 files."""

    def __init__(self, config: AppConfig | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config or AppConfig()
        self.transfer_manager = TransferManager(config=self.config)
        self.detector = DeviceDetector()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="select-container"):
            yield Label("Select Files to Transfer", id="select-title")
            yield Label("Scanning output directory for MP3 files...", id="select-scan-status")
            yield DataTable(id="files-table")
            yield Button("Transfer Selected Files", variant="success", id="btn-transfer-selected")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_files()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-transfer-selected":
            await self.transfer_selected_files()

    async def refresh_files(self) -> None:
        status_label = self.query_one("#select-scan-status", Label)
        table = self.query_one("#files-table", DataTable)
        table.clear(columns=True)
        
        out_dir = self.config.effective_output_dir
        if not out_dir.exists():
            status_label.update("[yellow]Output directory does not exist yet.[/yellow]")
            return

        mp3_files = list(out_dir.glob("*.mp3"))
        if not mp3_files:
            status_label.update(f"[yellow]No MP3 files found in: {out_dir}[/yellow]")
            return

        status_label.update(f"[green]Found {len(mp3_files)} MP3 file(s) in output directory[/green]")
        
        # Setup columns (Select checkbox represented by text, File Name, Size)
        table.add_columns("Sync", "File Name", "Size")
        
        for idx, f in enumerate(mp3_files):
            size_mb = f.stat().st_size / (1024 * 1024)
            # Row ID is stored as file absolute path
            table.add_row("[ ]", f.name, f"{size_mb:.2f} MB", key=str(f))

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        # Toggle checkbox state when row is clicked
        table = self.query_one("#files-table", DataTable)
        row_key = event.row_key
        if row_key is None:
            return
            
        current_val = table.get_cell(row_key, "Sync")
        new_val = "[X]" if current_val == "[ ]" else "[ ]"
        table.update_cell(row_key, "Sync", new_val)

    async def transfer_selected_files(self) -> None:
        status_label = self.query_one("#select-scan-status", Label)
        table = self.query_one("#files-table", DataTable)
        
        # Gather all rows where "Sync" is [X]
        selected_paths: list[Path] = []
        for row_key in table.rows:
            sync_val = table.get_cell(row_key, "Sync")
            if sync_val == "[X]":
                selected_paths.append(Path(str(row_key.value)))

        if not selected_paths:
            self.app.notify("Please select at least one file to transfer", severity="warning")
            return

        # Find connected devices
        status_label.update("Scanning for connected devices...")
        devices = await self.detector.detect_devices()
        if not devices:
            self.app.notify("No iOS devices detected via USB", severity="error")
            status_label.update("[red]No devices detected. Connect device and retry.[/red]")
            return

        device = devices[0]
        status_label.update(f"Transferring {len(selected_paths)} file(s) to {device.model}...")
        
        btn = self.query_one("#btn-transfer-selected", Button)
        btn.disabled = True

        try:
            result = await self.transfer_manager.transfer_files(selected_paths, device)
            if result.success:
                self.app.notify(f"Transferred {len(selected_paths)} file(s) successfully!")
                status_label.update(f"[green]Successfully transferred {len(selected_paths)} file(s) via {result.method.display_name}![/green]")
                # Reset selections
                for row_key in table.rows:
                    table.update_cell(row_key, "Sync", "[ ]")
            else:
                err_msg = "; ".join(result.errors) if result.errors else "Unknown error"
                self.app.notify(f"Transfer failed: {err_msg}", severity="error")
                status_label.update(f"[red]Transfer failed: {err_msg}[/red]")
        except Exception as e:
            self.app.notify(f"Transfer error: {e}", severity="error")
            status_label.update(f"[red]Transfer error: {e}[/red]")
        finally:
            btn.disabled = False
