"""Pipeline orchestrator (Phase 15).

Coordinates the entire download, convert, metadata match, tagging,
and transfer flow asynchronously, emitting structured events at each stage.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from yt2ipod.backends.coverartarchive.client import CoverArtArchiveClient
from yt2ipod.backends.ffmpeg.client import FFmpegClient
from yt2ipod.backends.musicbrainz.client import MusicBrainzClient
from yt2ipod.backends.youtube.client import YtDlpClient
from yt2ipod.core.cleanup.manager import TemporaryFileManager
from yt2ipod.core.device.detection import DeviceDetector
from yt2ipod.core.models import events
from yt2ipod.core.models.config import AppConfig, DownloadQuality
from yt2ipod.core.models.errors import Yt2IpodError, DependencyError
from yt2ipod.core.models.track import Track, TrackMetadata
from yt2ipod.core.transfer.manager import TransferManager
from yt2ipod.utils.filename import sanitize_filename
from yt2ipod.utils.logging import get_logger

logger = get_logger(__name__)


class Pipeline:
    """Orchestrates the entire yt2ipod pipeline flow."""

    def __init__(
        self,
        config: AppConfig | None = None,
        downloader: YtDlpClient | None = None,
        musicbrainz: MusicBrainzClient | None = None,
        coverart: CoverArtArchiveClient | None = None,
        ffmpeg: FFmpegClient | None = None,
        device_detector: DeviceDetector | None = None,
        transfer_manager: TransferManager | None = None,
        temp_manager: TemporaryFileManager | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.temp_manager = temp_manager or TemporaryFileManager()
        self.downloader = downloader or YtDlpClient(cookies_file=self.config.cookies_file)
        self.musicbrainz = musicbrainz or MusicBrainzClient()
        self.coverart = coverart or CoverArtArchiveClient()
        self.ffmpeg = ffmpeg or FFmpegClient()
        self.device_detector = device_detector or DeviceDetector()
        self.transfer_manager = transfer_manager or TransferManager(
            config=self.config,
            temp_manager=self.temp_manager,
        )

    async def _check_dependencies(self) -> None:
        """Verify all system dependencies are available."""
        await self.downloader.check_dependency()
        await self.ffmpeg.check_dependency()
        # Optional dependencies (like Pillow) are checked at runtime in coverart

    async def run(
        self,
        url_or_path: str,
        output_dir: Path,
        event_callback: Callable[[events.PipelineEvent], None] = lambda e: None,
        keep_temp: bool = False,
        transfer: bool = True,
    ) -> Track:
        """Run the pipeline for a single track.

        Args:
            url_or_path: A YouTube URL or a path to a local audio file.
            output_dir: Local directory to save the final tagged MP3.
            event_callback: Callback function invoked for every pipeline event.
            keep_temp: If True, skip deleting temporary files.
            transfer: If True, attempt transferring to a detected device.

        Returns:
            The final Track object.
        """
        # Ensure output directory exists
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        track = Track()

        # Update temp manager config
        self.temp_manager.keep_temp = keep_temp

        try:
            # 0. Check system dependencies
            await self._check_dependencies()

            # Identify input type (URL or local path)
            is_url = url_or_path.startswith("http://") or url_or_path.startswith("https://") or "youtube.com" in url_or_path or "youtu.be" in url_or_path

            # 1. Download/Ingestion stage
            if is_url:
                track.source_url = url_or_path
                event_callback(events.DownloadStarted(url=url_or_path))

                # Fetch video info first
                try:
                    info = await self.downloader.get_metadata(url_or_path)
                    track.youtube_title = info.youtube_title
                    track.youtube_artist = info.youtube_artist
                    track.youtube_duration = info.youtube_duration
                except Exception as e:
                    logger.warning(f"Could not retrieve video metadata: {e}")

                # Download audio to a temporary directory
                temp_dir = self.temp_manager.create_temp_dir(prefix="dl-")
                
                downloaded_file = None
                start_dl = time.monotonic()
                async for res in self.downloader.download_audio(url_or_path, temp_dir):
                    if isinstance(res, Path):
                        downloaded_file = res
                    else:
                        # Propagate progress event
                        event_callback(events.DownloadProgress(
                            percent=res.percent,
                            downloaded_bytes=res.downloaded_bytes if hasattr(res, "downloaded_bytes") else 0,
                            total_bytes=res.total_bytes if hasattr(res, "total_bytes") else 0,
                            speed=res.speed,
                        ))
                dl_duration = time.monotonic() - start_dl

                if not downloaded_file or not downloaded_file.exists():
                    raise FileNotFoundError("Could not find downloaded audio file from yt-dlp.")

                # Register downloaded file to temp manager
                self.temp_manager.register(downloaded_file)
                track.source_path = downloaded_file
                
                file_size = downloaded_file.stat().st_size
                event_callback(events.DownloadCompleted(
                    title=track.youtube_title,
                    duration=dl_duration,
                    file_size=file_size,
                ))
            else:
                local_p = Path(url_or_path)
                if not local_p.exists():
                    raise FileNotFoundError(f"Local file does not exist: {url_or_path}")
                track.source_path = local_p
                # Use ffprobe to get initial metadata if local
                try:
                    duration = await self.ffmpeg.get_duration(local_p)
                    track.youtube_duration = duration
                except Exception:
                    pass
                track.youtube_title = local_p.stem

            # 2. Conversion stage (convert source to intermediate MP3)
            event_callback(events.ConversionStarted(
                source_format=track.source_path.suffix.lstrip("."),
                target_format="mp3"
            ))

            temp_mp3 = self.temp_manager.create_temp_file(suffix=".mp3")
            
            async for progress in self.ffmpeg.convert_to_mp3(
                track.source_path,
                temp_mp3,
                quality=self.config.download_quality,
            ):
                event_callback(events.ConversionProgress(percent=progress.percent))

            event_callback(events.ConversionCompleted())

            # 3. Metadata identification stage (MusicBrainz)
            event_callback(events.MetadataSearchStarted(
                artist=track.youtube_artist,
                title=track.youtube_title
            ))

            confidence, mb_meta = await self.musicbrainz.match_track(track)
            
            if mb_meta:
                track.metadata = mb_meta
                event_callback(events.MetadataMatched(
                    artist=mb_meta.artist,
                    title=mb_meta.title,
                    album=mb_meta.album,
                    recording_id=mb_meta.musicbrainz_recording_id,
                    confidence=confidence,
                ))
            else:
                # Use fallbacks if match not found
                track.metadata = TrackMetadata(
                    title=track.youtube_title,
                    artist=track.youtube_artist,
                    date="",
                )
                event_callback(events.MetadataNotFound(
                    artist=track.youtube_artist,
                    title=track.youtube_title,
                    reason="No confident Match found in MusicBrainz."
                ))

            # 4. Cover Art search (Cover Art Archive)
            if track.metadata.musicbrainz_release_id:
                event_callback(events.ArtworkSearchStarted(
                    release_id=track.metadata.musicbrainz_release_id
                ))
                try:
                    temp_art = self.temp_manager.create_temp_file(suffix=".jpg")
                    artwork = await self.coverart.fetch_front_artwork(
                        track.metadata.musicbrainz_release_id,
                        track.metadata.album,
                        temp_art
                    )
                    if artwork and artwork.is_valid:
                        track.artwork_path = temp_art
                        event_callback(events.ArtworkFound(
                            width=artwork.width,
                            height=artwork.height,
                            release_id=artwork.release_id,
                        ))
                    else:
                        event_callback(events.ArtworkNotFound(
                            release_id=track.metadata.musicbrainz_release_id,
                            reason="Release has no front artwork in Cover Art Archive."
                        ))
                except Exception as e:
                    logger.debug(f"Cover Art search failed: {e}")
                    event_callback(events.ArtworkNotFound(
                        release_id=track.metadata.musicbrainz_release_id,
                        reason=str(e)
                    ))

            # 5. Tagging stage
            event_callback(events.TaggingStarted())
            
            sanitized_title = sanitize_filename(track.metadata.title or track.youtube_title)
            final_mp3 = output_dir / f"{sanitized_title}.mp3"
            
            await self.ffmpeg.embed_metadata(
                temp_mp3,
                final_mp3,
                track.metadata,
                track.artwork_path
            )
            track.output_path = final_mp3

            event_callback(events.TaggingCompleted(
                has_artwork=track.artwork_path is not None,
                has_metadata=track.metadata.has_musicbrainz_ids
            ))

            # 6. Final verification & validation
            try:
                audio_info = await self.ffmpeg.probe(final_mp3)
                track.audio_info = audio_info
            except Exception as e:
                logger.warning(f"Probe validation failed for {final_mp3.name}: {e}")

            # 7. Device Transfer stage
            if transfer:
                devices = await self.device_detector.detect_devices()
                if devices:
                    device = devices[0]
                    event_callback(events.DeviceDetected(
                        model=device.model,
                        ios_version=device.ios_version,
                        connection=device.connection.value if device.connection else "USB",
                        capabilities=device.capabilities.available_methods_summary if hasattr(device.capabilities, "available_methods_summary") else "AFC/SSH"
                    ))

                    event_callback(events.TransferStarted(
                        method=device.connection.value if device.connection else "USB",
                        file_count=1,
                        total_bytes=final_mp3.stat().st_size if final_mp3.exists() else 0
                    ))

                    result = await self.transfer_manager.transfer_files([final_mp3], device)
                    if result.success:
                        event_callback(events.TransferCompleted(
                            method=result.method.value if result.method else "USB",
                            files_transferred=result.files_transferred,
                            duration=result.duration
                        ))
                    else:
                        event_callback(events.TransferFailed(
                            method=result.method.value if result.method else "USB",
                            error=result.errors[0] if result.errors else "Unknown transfer error"
                        ))
                else:
                    event_callback(events.DeviceNotFound())

        finally:
            # 8. Cleanup stage
            if not keep_temp:
                event_callback(events.CleanupStarted(file_count=len(self.temp_manager.registered_files)))
                self.temp_manager.cleanup()
                event_callback(events.CleanupCompleted())

        return track
