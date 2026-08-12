import builtins
import pytest
from unittest.mock import patch, AsyncMock

from yt2ipod.core.transfer.manager import TransferManager
from yt2ipod.core.models.device import Device, DeviceCapabilities, ConnectionType, Architecture
from yt2ipod.core.models.config import AppConfig

@pytest.mark.asyncio
async def test_wifi_ssh_ip_prompt(monkeypatch):
    # Prepare a device that supports ssh (wifi)
    caps = DeviceCapabilities(usb=False, afc=False, afc2=False, ssh=True, usb_ssh=False, root_filesystem=False, media_access=False)
    device = Device(
        model="TestDevice",
        model_identifier="TestModel",
        ios_version="9.3.5",
        architecture=Architecture.ARM32,
        serial="device123",
        connection=ConnectionType.WIFI,
        jailbreak_status=None,
        root_access=False,
        capabilities=caps,
    )
    # Config without pre-set host
    config = AppConfig()
    manager = TransferManager(config=config)

    # Mock ask_ip to return a dummy IP and ensure it gets stored in config
    dummy_ip = "192.168.1.42"
    monkeypatch.setattr('yt2ipod.utils.prompt.ask_ip', lambda prompt_message="": dummy_ip)

    # Patch SSHBackend to avoid real ssh calls
    class DummyBackend:
        def __init__(self, host, port, username, identity_file):
            self.host = host
            self.port = port
            self.username = username
            self.identity_file = identity_file
        async def upload(self, *args, **kwargs):
            pass
        async def mkdir(self, *args, **kwargs):
            pass
    monkeypatch.setattr('yt2ipod.core.filesystem.backend.SSHBackend', DummyBackend)

    backend, method, _ = await manager._select_backend(device)
    assert isinstance(backend, DummyBackend)
    assert backend.host == dummy_ip
    assert config.ssh_settings.host == dummy_ip
    assert method.name == "WIFI_SSH"
