"""Textual TUI for yt2ipod (Phase 14).

This module implements an interactive menu-driven TUI using the textual
library. It consumes events, provides navigation, and displays device status.

The TUI is optional: if textual is not installed, importing this module will
raise ImportError.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

try:
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static, ListView, ListItem
    from textual.containers import Container
    from textual.binding import Binding
    from textual.screen import Screen
except ImportError as e:
    raise ImportError("textual library is not installed. Install with: pip install 'yt2ipod[tui]'") from e

from yt2ipod.core.device.detection import DeviceDetector
from yt2ipod.core.models.config import AppConfig
from yt2ipod.interfaces.textual.screens import (
    AboutScreen,
    DeviceInfoScreen,
    DownloadScreen,
    ImportScreen,
    SelectFilesScreen,
    SettingsScreen,
)

MAIN_MENU = [
    "Download from YouTube",
    "Import local music",
    "Select files",
    "Device Info",
    "Settings",
    "About",
]


class PlaceholderScreen(Screen):
    """Simple placeholder screen for menu navigation."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.title_text = title

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold]{self.title_text}[/bold]\n\n"
            f"This screen is a placeholder in Phase 14.\n\n"
            f"[bold]B[/bold] Back | [bold]Q[/bold] Quit",
            id="placeholder"
        )


class DeviceStatus(Static):
    """Widget to display the status and capabilities of connected devices."""

    def update_status(self, lines: List[str]) -> None:
        self.update("\n".join(lines))


class YT2iPodApp(App):
    """The main Textual application for yt2ipod."""

    CSS = """
    #title {
        text-align: center;
        text-style: bold;
        background: $accent;
        color: $text;
        padding: 1;
        margin-bottom: 1;
    }
    #device-status {
        background: $surface;
        color: $text-muted;
        border: solid $primary;
        padding: 1;
        margin-top: 1;
        height: 6;
    }
    #placeholder {
        align: center middle;
        text-align: center;
        background: $panel;
        border: double $accent;
        padding: 3;
    }
    """

    BINDINGS = [
        Binding("b", "go_back", "Back"),
        Binding("d", "refresh_devices", "Refresh Devices"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, detector: DeviceDetector | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.nav_stack: List[str] = ["main"]
        self.detector = detector or DeviceDetector()
        self.config = AppConfig()
        from pathlib import Path
        default_cookies = Path("cookies.txt")
        if default_cookies.exists():
            self.config.cookies_file = default_cookies
        self.menu_list: Optional[ListView] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container():
            yield Static("yt2ipod - Music to Legacy Devices", id="title")
            self.menu_list = ListView(*[ListItem(Static(m)) for m in MAIN_MENU], id="main-menu")
            yield self.menu_list
            yield DeviceStatus("No device detected", id="device-status")
        yield Footer()

    async def on_mount(self) -> None:
        if self.menu_list:
            self.set_focus(self.menu_list)
        # Initial device detection
        await self.action_refresh_devices()

    def action_go_back(self) -> None:
        if len(self.nav_stack) > 1:
            self.nav_stack.pop()
            # If we pushed a placeholder screen, pop it off Textual screen stack
            if len(self.screen_stack) > 1:
                self.pop_screen()

    async def action_refresh_devices(self) -> None:
        """Query connected devices and update the status widget."""
        ds = self.query_one("#device-status", DeviceStatus)
        ds.update_status(["Detecting devices..."])

        try:
            devices = await self.detector.detect_devices()
            if not devices:
                ds.update_status(["[yellow]No device detected[/yellow]"])
            else:
                lines = [f"[green]{len(devices)} device(s) detected:[/green]"]
                for d in devices:
                    caps = d.capabilities
                    lines.append(
                        f"• {d.model} ({d.ios_version}) - USB: {caps.usb}, "
                        f"AFC: {caps.afc}, SSH: {caps.ssh}, USB-SSH: {caps.usb_ssh}"
                    )
                ds.update_status(lines)
        except Exception as e:
            ds.update_status([f"[red]Device detection failed: {e}[/red]"])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Handle selection from main menu
        selected = event.item
        label = ""

        # Attempt 1: Map by index in MAIN_MENU by scanning list children (most robust and compatible)
        if self.menu_list and selected is not None:
            try:
                # Retrieve index by iterating through the children of ListView
                children_list = list(self.menu_list.children)
                if selected in children_list:
                    idx = children_list.index(selected)
                    if 0 <= idx < len(MAIN_MENU):
                        label = MAIN_MENU[idx]
            except Exception:
                pass

        # Attempt 2: Fallback parsing of static widget (wrapped in try-except to never crash)
        if not label and selected and selected.children:
            try:
                static_widget = selected.children[0]
                if isinstance(static_widget, Static):
                    renderable = getattr(static_widget, "renderable", getattr(static_widget, "_renderable", None))
                    if renderable is not None:
                        if hasattr(renderable, "plain"):
                            label = str(renderable.plain)
                        else:
                            label = str(renderable)
            except Exception:
                pass

        if not label:
            label = "Menu Item"

        self.nav_stack.append(label)
        
        # Route to corresponding operational screens
        if label == "Download from YouTube":
            self.push_screen(DownloadScreen(config=self.config))
        elif label == "Import local music":
            self.push_screen(ImportScreen(config=self.config))
        elif label == "Select files":
            self.push_screen(SelectFilesScreen(config=self.config))
        elif label == "Device Info":
            self.push_screen(DeviceInfoScreen(detector=self.detector))
        elif label == "Settings":
            self.push_screen(SettingsScreen(config=self.config))
        elif label == "About":
            self.push_screen(AboutScreen())
        else:
            self.push_screen_placeholder(label)

    def push_screen_placeholder(self, title: str) -> None:
        self.push_screen(PlaceholderScreen(title))


def run_textual(detector: DeviceDetector | None = None) -> int:
    app = YT2iPodApp(detector=detector)
    app.run()
    return 0


if __name__ == "__main__":
    run_textual()
