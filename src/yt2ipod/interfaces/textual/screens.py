"""Textual TUI screen definitions for yt2ipod (Phase 14).

Implements interactive screens using textual widgets.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from textual import work
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, Log, ProgressBar, Select, Static

from yt2ipod.core.device.detection import DeviceDetector
from yt2ipod.core.models.config import AppConfig
from yt2ipod.core.models.transfer import TransferMethod
from yt2ipod.core.pipeline import Pipeline
from yt2ipod.core.transfer.manager import TransferManager
from yt2ipod.utils.dialogs import is_gui_dialog_available, pick_directory_dialog, pick_files_dialog

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
            self.run_pipeline_task(url, not skip_transfer)

    @work(exclusive=True)
    async def run_pipeline_task(self, url: str, transfer: bool) -> None:
        def event_callback(event) -> None:
            if not self.is_mounted:
                return
            if threading.current_thread() is threading.main_thread():
                self.process_pipeline_event(event)
            else:
                try:
                    self.app.call_from_thread(self.process_pipeline_event, event)
                except RuntimeError:
                    pass

        try:
            await self.pipeline.run(
                url_or_path=url,
                output_dir=self.config.effective_output_dir,
                event_callback=event_callback,
                keep_temp=self.config.keep_temp,
                transfer=transfer,
            )
            if self.is_mounted:
                try:
                    self.query_one("#download-status-text", Label).update("[green]Process finished successfully![/green]")
                    self.app.notify("YouTube download and transfer completed!")
                except Exception:
                    pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self.is_mounted:
                try:
                    self.query_one("#download-status-text", Label).update(f"[red]Error: {e}[/red]")
                    self.query_one("#download-log", Log).write_line(f"ERROR: {e}")
                    self.app.notify(f"Process failed: {e}", severity="error")
                except Exception:
                    pass
        finally:
            if self.is_mounted:
                try:
                    self.query_one("#btn-download", Button).disabled = False
                except Exception:
                    pass

    def process_pipeline_event(self, event) -> None:
        if not self.is_mounted:
            return
        try:
            log = self.query_one("#download-log", Log)
            progress_bar = self.query_one("#download-progress", ProgressBar)
            status_label = self.query_one("#download-status-text", Label)
        except Exception:
            return

        from yt2ipod.core.models import events

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
    """Screen for importing and tagging local music files or entire folders."""

    def __init__(self, config: AppConfig | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config or AppConfig()
        self.pipeline = Pipeline(config=self.config)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="import-container"):
            yield Label("Import Local Music (Tag & Transfer)", id="import-title")
            
            yield Label("Local File or Folder Path:")
            yield Input(placeholder="/path/to/song.wav or /path/to/folder", id="import-file-path")
            with Horizontal(id="import-browse-row"):
                yield Button("Browse File...", variant="primary", id="btn-browse-import-file")
                yield Button("Browse Folder...", variant="primary", id="btn-browse-import-dir")

            yield Checkbox("Skip device transfer (tag local files only)", value=False, id="import-skip-transfer")
            
            yield Button("Import and Tag", variant="success", id="btn-import")
            
            yield Label("", id="import-status-text")
            yield ProgressBar(id="import-progress", show_percentage=True, show_eta=False)
            yield Log(id="import-log")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-browse-import-file":
            selected = pick_files_dialog(title="Select Audio File to Import", multiple=False)
            if selected:
                self.query_one("#import-file-path", Input).value = str(selected[0])
            elif not is_gui_dialog_available():
                self.app.notify("GUI file chooser not available in terminal/SSH session", severity="warning")

        elif btn_id == "btn-browse-import-dir":
            selected_dir = pick_directory_dialog(title="Select Music Directory to Import")
            if selected_dir:
                self.query_one("#import-file-path", Input).value = str(selected_dir)
            elif not is_gui_dialog_available():
                self.app.notify("GUI directory chooser not available in terminal/SSH session", severity="warning")

        elif btn_id == "btn-import":
            path_str = self.query_one("#import-file-path", Input).value.strip()
            if not path_str:
                self.app.notify("Please enter or select a valid file/folder path", severity="warning")
                return

            path = Path(path_str).expanduser().resolve()
            if not path.exists():
                self.app.notify(f"Path not found: {path_str}", severity="error")
                return

            audio_extensions = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma", ".alac"}
            if path.is_file():
                files = [path]
            elif path.is_dir():
                files = [f for f in path.rglob("*") if f.is_file() and f.suffix.lower() in audio_extensions]
                if not files:
                    self.app.notify(f"No audio files found in: {path_str}", severity="warning")
                    return
            else:
                self.app.notify(f"Invalid path: {path_str}", severity="error")
                return

            skip_transfer = self.query_one("#import-skip-transfer", Checkbox).value

            btn = self.query_one("#btn-import", Button)
            btn.disabled = True

            self.query_one("#import-status-text", Label).update(f"Starting import for {len(files)} file(s)...")
            self.query_one("#import-progress", ProgressBar).update(total=len(files), progress=0)
            self.query_one("#import-log", Log).clear()

            self.run_import_task(files, not skip_transfer)

    @work(exclusive=True)
    async def run_import_task(self, files: list[Path], transfer: bool) -> None:
        def event_callback(event) -> None:
            if not self.is_mounted:
                return
            if threading.current_thread() is threading.main_thread():
                self.process_import_event(event)
            else:
                try:
                    self.app.call_from_thread(self.process_import_event, event)
                except RuntimeError:
                    pass

        total = len(files)
        success_count = 0
        fail_count = 0

        for idx, file_path in enumerate(files, start=1):
            if not self.is_mounted:
                break
            try:
                self.query_one("#import-status-text", Label).update(
                    f"[{idx}/{total}] Processing: {file_path.name}"
                )
                self.query_one("#import-log", Log).write_line(f"\n--- [{idx}/{total}] Importing: {file_path.name} ---")

                await self.pipeline.run(
                    url_or_path=str(file_path),
                    output_dir=self.config.effective_output_dir,
                    event_callback=event_callback,
                    keep_temp=self.config.keep_temp,
                    transfer=transfer,
                )
                success_count += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                fail_count += 1
                if self.is_mounted:
                    try:
                        self.query_one("#import-log", Log).write_line(f"[!] Error on {file_path.name}: {e}")
                    except Exception:
                        pass
            finally:
                if self.is_mounted:
                    try:
                        self.query_one("#import-progress", ProgressBar).update(progress=idx)
                    except Exception:
                        pass

        if self.is_mounted:
            try:
                status_msg = f"[green]Import finished: {success_count} succeeded[/green]"
                if fail_count > 0:
                    status_msg += f", [red]{fail_count} failed[/red]"
                self.query_one("#import-status-text", Label).update(status_msg)
                self.app.notify(f"Import finished! {success_count}/{total} files processed.")
            except Exception:
                pass
            try:
                self.query_one("#btn-import", Button).disabled = False
            except Exception:
                pass

    def process_import_event(self, event) -> None:
        if not self.is_mounted:
            return
        try:
            log = self.query_one("#import-log", Log)
            status_label = self.query_one("#import-status-text", Label)
        except Exception:
            return

        from yt2ipod.core.models import events

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


class SelectFilesScreen(Screen):
    """Screen for selecting and transferring existing local MP3 files from any directory."""

    def __init__(self, config: AppConfig | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config or AppConfig()
        self.transfer_manager = TransferManager(config=self.config)
        self.detector = DeviceDetector()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with ScrollableContainer(id="select-container"):
            yield Label("Select Files to Transfer", id="select-title")
            with Horizontal(id="select-actions-row"):
                yield Button("Browse Files (GUI)...", variant="primary", id="btn-browse-files")
                yield Button("Add Folder...", id="btn-add-folder")
                yield Button("Select All", id="btn-select-all")
                yield Button("Deselect All", id="btn-deselect-all")
                yield Button("Clear", id="btn-clear-table")
                yield Button("Default Dir", id="btn-reload-dir")
            yield Label("Scanning output directory for MP3 files...", id="select-scan-status")
            yield DataTable(id="files-table")
            yield Button("Transfer Selected Files", variant="success", id="btn-transfer-selected")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_files()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-transfer-selected":
            self.transfer_selected_files()
        elif btn_id == "btn-browse-files":
            selected = pick_files_dialog(
                title="Select MP3 Files to Transfer",
                multiple=True,
                file_filter="MP3 Audio (*.mp3) | *.mp3",
            )
            if selected:
                self.add_files_to_table(selected, checked=True)
                self.query_one("#select-scan-status", Label).update(
                    f"[green]Added {len(selected)} file(s) from file browser[/green]"
                )
            elif not is_gui_dialog_available():
                self.app.notify("GUI file chooser not available in terminal/SSH session", severity="warning")
        elif btn_id == "btn-add-folder":
            folder = pick_directory_dialog(title="Select Folder with MP3 Files")
            if folder:
                mp3s = list(folder.glob("*.mp3")) + list(folder.glob("*.MP3"))
                if mp3s:
                    self.add_files_to_table(mp3s, checked=True)
                    self.query_one("#select-scan-status", Label).update(
                        f"[green]Added {len(mp3s)} MP3 file(s) from folder: {folder.name}[/green]"
                    )
                else:
                    self.app.notify(f"No MP3 files found in {folder}", severity="warning")
            elif not is_gui_dialog_available():
                self.app.notify("GUI directory chooser not available in terminal/SSH session", severity="warning")
        elif btn_id == "btn-select-all":
            self.set_all_checkboxes("[X]")
        elif btn_id == "btn-deselect-all":
            self.set_all_checkboxes("[ ]")
        elif btn_id == "btn-clear-table":
            if self.is_mounted:
                try:
                    table = self.query_one("#files-table", DataTable)
                    table.clear()
                    self.query_one("#select-scan-status", Label).update("[yellow]Table cleared.[/yellow]")
                except Exception:
                    pass
        elif btn_id == "btn-reload-dir":
            self.run_worker(self.refresh_files())

    def set_all_checkboxes(self, state: str) -> None:
        if not self.is_mounted:
            return
        try:
            table = self.query_one("#files-table", DataTable)
            for row_key in table.rows:
                table.update_cell(row_key, "Sync", state)
        except Exception:
            pass

    def add_files_to_table(self, paths: list[Path], checked: bool = True) -> None:
        if not self.is_mounted:
            return
        try:
            table = self.query_one("#files-table", DataTable)
            if not table.columns:
                table.add_columns("Sync", "File Name", "Size", "Folder")

            existing_keys = set(str(k.value) if hasattr(k, "value") else str(k) for k in table.rows)
            for f in paths:
                if str(f) in existing_keys:
                    continue
                size_mb = f.stat().st_size / (1024 * 1024) if f.exists() else 0.0
                table.add_row("[X]" if checked else "[ ]", f.name, f"{size_mb:.2f} MB", str(f.parent), key=str(f))
        except Exception:
            pass

    async def refresh_files(self) -> None:
        if not self.is_mounted:
            return
        try:
            status_label = self.query_one("#select-scan-status", Label)
            table = self.query_one("#files-table", DataTable)
        except Exception:
            return

        table.clear(columns=True)
        table.add_columns("Sync", "File Name", "Size", "Folder")

        out_dir = self.config.effective_output_dir
        if not out_dir.exists():
            status_label.update("[yellow]Output directory does not exist yet.[/yellow]")
            return

        mp3_files = list(out_dir.glob("*.mp3")) + list(out_dir.glob("*.MP3"))
        if not mp3_files:
            status_label.update(f"[yellow]No MP3 files found in default output: {out_dir}[/yellow]")
            return

        status_label.update(f"[green]Found {len(mp3_files)} MP3 file(s) in default directory[/green]")
        for f in mp3_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            table.add_row("[ ]", f.name, f"{size_mb:.2f} MB", str(f.parent), key=str(f))

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        if not self.is_mounted:
            return
        try:
            table = self.query_one("#files-table", DataTable)
        except Exception:
            return
        row_key = event.row_key
        if row_key is None:
            return

        current_val = table.get_cell(row_key, "Sync")
        new_val = "[X]" if current_val == "[ ]" else "[ ]"
        table.update_cell(row_key, "Sync", new_val)

    @work(exclusive=True)
    async def transfer_selected_files(self) -> None:
        if not self.is_mounted:
            return
        try:
            status_label = self.query_one("#select-scan-status", Label)
            table = self.query_one("#files-table", DataTable)
        except Exception:
            return

        selected_paths: list[Path] = []
        for row_key in table.rows:
            sync_val = table.get_cell(row_key, "Sync")
            if sync_val == "[X]":
                val = row_key.value if hasattr(row_key, "value") else row_key
                selected_paths.append(Path(str(val)))

        if not selected_paths:
            self.app.notify("Please select at least one file to transfer", severity="warning")
            return

        status_label.update("Scanning for connected devices...")
        devices = await self.detector.detect_devices()
        if not devices:
            self.app.notify("No iOS devices detected via USB", severity="error")
            status_label.update("[red]No devices detected. Connect device and retry.[/red]")
            return

        device = devices[0]
        status_label.update(f"Transferring {len(selected_paths)} file(s) to {device.model}...")

        try:
            self.query_one("#btn-transfer-selected", Button).disabled = True
        except Exception:
            pass

        try:
            result = await self.transfer_manager.transfer_files(selected_paths, device)
            if self.is_mounted:
                if result.success:
                    self.app.notify(f"Transferred {len(selected_paths)} file(s) successfully!")
                    status_label.update(
                        f"[green]Successfully transferred {len(selected_paths)} file(s) via {result.method.display_name}![/green]"
                    )
                    for row_key in table.rows:
                        table.update_cell(row_key, "Sync", "[ ]")
                else:
                    err_msg = "; ".join(result.errors) if result.errors else "Unknown error"
                    self.app.notify(f"Transfer failed: {err_msg}", severity="error")
                    status_label.update(f"[red]Transfer failed: {err_msg}[/red]")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self.is_mounted:
                self.app.notify(f"Transfer error: {e}", severity="error")
                status_label.update(f"[red]Transfer error: {e}[/red]")
        finally:
            if self.is_mounted:
                try:
                    self.query_one("#btn-transfer-selected", Button).disabled = False
                except Exception:
                    pass
