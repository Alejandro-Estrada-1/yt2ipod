"""Tests for PipelineStage, StageResult, and PipelineResult."""

from yt2ipod.core.models.pipeline import PipelineResult, PipelineStage, StageResult


class TestPipelineStage:
    """Tests for PipelineStage enum."""

    def test_all_stages_exist(self):
        stages = list(PipelineStage)
        assert len(stages) == 7
        assert PipelineStage.DOWNLOAD in stages
        assert PipelineStage.CONVERT in stages
        assert PipelineStage.METADATA in stages
        assert PipelineStage.ARTWORK in stages
        assert PipelineStage.TAGGING in stages
        assert PipelineStage.TRANSFER in stages
        assert PipelineStage.CLEANUP in stages

    def test_display_names(self):
        assert PipelineStage.DOWNLOAD.display_name == "Downloading"
        assert PipelineStage.METADATA.display_name == "Identifying metadata"
        assert PipelineStage.CLEANUP.display_name == "Cleaning"


class TestStageResult:
    """Tests for StageResult dataclass."""

    def test_success(self):
        result = StageResult(
            stage=PipelineStage.METADATA,
            success=True,
            message="Little Jesus — La magia",
            duration=1.5,
        )
        assert result.status_icon == "✓"
        assert result.display() == "✓ Little Jesus — La magia"

    def test_failure(self):
        result = StageResult(
            stage=PipelineStage.DOWNLOAD,
            success=False,
            error="HTTP 429 Too Many Requests",
        )
        assert result.status_icon == "✗"
        assert "✗ HTTP 429" in result.display()

    def test_success_no_message(self):
        result = StageResult(stage=PipelineStage.CLEANUP, success=True)
        assert result.display() == "✓ Cleaning"

    def test_failure_no_error(self):
        result = StageResult(stage=PipelineStage.CONVERT, success=False)
        assert result.display() == "✗ Converting failed"


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_add_stages(self):
        result = PipelineResult()
        result.add_stage(StageResult(
            stage=PipelineStage.DOWNLOAD,
            success=True,
            message="Downloaded",
            duration=3.0,
        ))
        result.add_stage(StageResult(
            stage=PipelineStage.CONVERT,
            success=True,
            message="Converted",
            duration=2.0,
        ))
        assert len(result.stages) == 2
        assert result.total_duration == 5.0

    def test_failed_stage_detection(self):
        result = PipelineResult()
        result.add_stage(StageResult(stage=PipelineStage.DOWNLOAD, success=True))
        result.add_stage(StageResult(
            stage=PipelineStage.METADATA,
            success=False,
            error="No match found",
        ))
        assert result.failed_stage is not None
        assert result.failed_stage.stage == PipelineStage.METADATA

    def test_no_failed_stage(self):
        result = PipelineResult()
        result.add_stage(StageResult(stage=PipelineStage.DOWNLOAD, success=True))
        assert result.failed_stage is None

    def test_completed_stages(self):
        result = PipelineResult()
        result.add_stage(StageResult(stage=PipelineStage.DOWNLOAD, success=True))
        result.add_stage(StageResult(stage=PipelineStage.CONVERT, success=False))
        result.add_stage(StageResult(stage=PipelineStage.METADATA, success=True))
        assert len(result.completed_stages) == 2

    def test_summary_success(self):
        result = PipelineResult(success=True)
        result.add_stage(StageResult(
            stage=PipelineStage.DOWNLOAD,
            success=True,
            message="Downloaded",
            duration=1.0,
        ))
        summary = result.summary()
        assert "✓ Downloaded" in summary
        assert "Done." in summary

    def test_summary_failure(self):
        result = PipelineResult(success=False)
        result.add_stage(StageResult(
            stage=PipelineStage.METADATA,
            success=False,
            error="No match",
        ))
        summary = result.summary()
        assert "Failed at:" in summary

    def test_empty_result(self):
        result = PipelineResult()
        assert result.stages == []
        assert result.total_duration == 0.0
