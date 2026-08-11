"""Pipeline stage and result models.

Track the progress and outcome of each stage in the processing pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PipelineStage(Enum):
    """Stages of the processing pipeline."""

    DOWNLOAD = "download"
    CONVERT = "convert"
    METADATA = "metadata"
    ARTWORK = "artwork"
    TAGGING = "tagging"
    TRANSFER = "transfer"
    CLEANUP = "cleanup"

    @property
    def display_name(self) -> str:
        """Human-readable stage name."""
        names = {
            PipelineStage.DOWNLOAD: "Downloading",
            PipelineStage.CONVERT: "Converting",
            PipelineStage.METADATA: "Identifying metadata",
            PipelineStage.ARTWORK: "Finding artwork",
            PipelineStage.TAGGING: "Preparing file",
            PipelineStage.TRANSFER: "Transferring",
            PipelineStage.CLEANUP: "Cleaning",
        }
        return names[self]


@dataclass
class StageResult:
    """Result of a single pipeline stage."""

    stage: PipelineStage
    success: bool = False
    message: str = ""
    error: str | None = None
    duration: float = 0.0  # seconds

    @property
    def status_icon(self) -> str:
        """Status indicator for display."""
        return "✓" if self.success else "✗"

    def display(self) -> str:
        """Human-readable status line."""
        if self.success:
            return f"✓ {self.message}" if self.message else f"✓ {self.stage.display_name}"
        return f"✗ {self.error}" if self.error else f"✗ {self.stage.display_name} failed"


@dataclass
class PipelineResult:
    """Aggregated result of a complete pipeline run."""

    stages: list[StageResult] = field(default_factory=list)
    success: bool = False
    total_duration: float = 0.0  # seconds

    def add_stage(self, result: StageResult) -> None:
        """Record the result of a completed stage."""
        self.stages.append(result)
        self.total_duration += result.duration

    @property
    def failed_stage(self) -> StageResult | None:
        """Return the first failed stage, if any."""
        for stage in self.stages:
            if not stage.success:
                return stage
        return None

    @property
    def completed_stages(self) -> list[StageResult]:
        """Return all successfully completed stages."""
        return [s for s in self.stages if s.success]

    def summary(self) -> str:
        """Human-readable pipeline summary."""
        lines = []
        for stage in self.stages:
            lines.append(stage.display())
        if self.success:
            lines.append(f"\nDone. ({self.total_duration:.1f}s)")
        else:
            failed = self.failed_stage
            if failed:
                lines.append(f"\nFailed at: {failed.stage.display_name}")
        return "\n".join(lines)
