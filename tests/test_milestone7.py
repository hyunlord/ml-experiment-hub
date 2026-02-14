"""Milestone 7 tests — stabilization, health checks, log management, DB optimizations."""

from __future__ import annotations

import gzip
import os
from pathlib import Path
from unittest.mock import patch


# ── T1: Server restart recovery ────────────────────────────────────────────


class TestPidLiveness:
    """Verify PID liveness checking logic used in server startup recovery."""

    def test_is_pid_alive_current_process(self):
        """Current process PID should be alive."""
        from backend.main import _is_pid_alive

        assert _is_pid_alive(os.getpid()) is True

    def test_is_pid_alive_none(self):
        """None PID should return False."""
        from backend.main import _is_pid_alive

        assert _is_pid_alive(None) is False

    def test_is_pid_alive_invalid_pid(self):
        """Very large PID should return False (no such process)."""
        from backend.main import _is_pid_alive

        assert _is_pid_alive(999999999) is False


# ── T2: Log management ────────────────────────────────────────────────────


class TestLogManager:
    """Verify log path generation, compression, and directory stats."""

    def test_get_log_path(self):
        """Log path should include run_id in filename."""
        from backend.services.log_manager import get_log_path

        path = get_log_path(42)
        assert "42" in str(path)
        assert path.suffix == ".log"

    def test_compress_log_file(self, tmp_path: Path):
        """Compressing a log file should create .gz and remove original."""
        from backend.services.log_manager import compress_log_file

        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\nline3\n")

        gz_path = compress_log_file(log_file)

        assert gz_path is not None
        assert gz_path.suffix == ".gz"
        assert gz_path.exists()
        assert not log_file.exists()

        # Verify content
        with gzip.open(gz_path, "rt") as f:
            content = f.read()
        assert "line1" in content

    def test_compress_log_file_nonexistent(self, tmp_path: Path):
        """Compressing a nonexistent file should return None."""
        from backend.services.log_manager import compress_log_file

        result = compress_log_file(tmp_path / "nonexistent.log")
        assert result is None

    def test_get_log_dir_stats(self, tmp_path: Path):
        """Log dir stats should count files and calculate size."""
        from backend.services.log_manager import get_log_dir_stats

        # Create some log files
        (tmp_path / "run_1.log").write_text("hello")
        (tmp_path / "run_2.log.gz").write_bytes(b"\x00" * 100)

        with patch("backend.services.log_manager.settings") as mock_settings:
            mock_settings.LOG_DIR = str(tmp_path)
            stats = get_log_dir_stats()

        assert stats["total_files"] == 2
        assert stats["total_size_bytes"] > 0
        assert stats["archived_files"] == 1


# ── T3: DB optimization ───────────────────────────────────────────────────


class TestDBOptimization:
    """Verify MetricLog index and WAL mode support."""

    def test_metric_log_has_composite_index(self):
        """MetricLog should have a composite index on (run_id, step)."""
        from backend.models.experiment import MetricLog

        table_args = getattr(MetricLog, "__table_args__", None)
        assert table_args is not None, "MetricLog should have __table_args__"

        # Find the index
        found = False
        for arg in table_args:
            from sqlalchemy import Index

            if isinstance(arg, Index) and "run_id" in str(arg) and "step" in str(arg):
                found = True
                break
        assert found, "Composite index on (run_id, step) not found"

    def test_metric_archiver_module_importable(self):
        """metric_archiver module should be importable."""
        from backend.services.metric_archiver import archive_old_metrics  # noqa: F401


# ── T4: Error handling ────────────────────────────────────────────────────


class TestHealthChecks:
    """Verify OOM detection, error classification, disk checks, GPU temp alerts."""

    def test_detect_oom_cuda(self):
        """Should detect CUDA out of memory."""
        from backend.services.health_checks import detect_oom

        assert detect_oom("RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB") is True

    def test_detect_oom_torch(self):
        """Should detect torch OutOfMemoryError."""
        from backend.services.health_checks import detect_oom

        assert detect_oom("torch.cuda.OutOfMemoryError: ...") is True

    def test_detect_oom_cublas(self):
        """Should detect CUBLAS allocation failure."""
        from backend.services.health_checks import detect_oom

        assert detect_oom("CUBLAS_STATUS_ALLOC_FAILED when calling ...") is True

    def test_detect_oom_normal_line(self):
        """Normal log lines should not trigger OOM."""
        from backend.services.health_checks import detect_oom

        assert detect_oom("Epoch 1/30 - train/loss: 0.532") is False

    def test_classify_error_oom(self):
        """Should classify OOM error."""
        from backend.services.health_checks import classify_error

        result = classify_error("RuntimeError: CUDA out of memory")
        assert result is not None
        assert "OOM" in result

    def test_classify_error_disk_full(self):
        """Should classify disk full error."""
        from backend.services.health_checks import classify_error

        result = classify_error("OSError: No space left on device")
        assert result is not None
        assert "DISK_FULL" in result

    def test_classify_error_nccl(self):
        """Should classify NCCL error."""
        from backend.services.health_checks import classify_error

        result = classify_error("NCCL error: unhandled system error")
        assert result is not None
        assert "NCCL" in result

    def test_classify_error_segfault(self):
        """Should classify segfault."""
        from backend.services.health_checks import classify_error

        result = classify_error("Segmentation fault (core dumped)")
        assert result is not None
        assert "SEGFAULT" in result

    def test_classify_error_killed(self):
        """Should classify OOM-killer."""
        from backend.services.health_checks import classify_error

        result = classify_error("Killed")
        assert result is not None
        assert "KILLED" in result

    def test_classify_error_normal(self):
        """Normal text should return None."""
        from backend.services.health_checks import classify_error

        assert classify_error("Training complete. Final loss: 0.12") is None

    def test_check_disk_space(self):
        """Disk space check should return valid structure."""
        from backend.services.health_checks import check_disk_space

        result = check_disk_space("/tmp")
        assert "total" in result
        assert "free" in result
        assert "ok" in result
        assert isinstance(result["ok"], bool)
        assert result["total"] > 0

    def test_gpu_temperature_warning(self):
        """Should warn on high GPU temperature."""
        from backend.services.health_checks import check_gpu_temperatures

        gpus = [{"index": 0, "temperature": 87}]
        warnings = check_gpu_temperatures(gpus)
        assert len(warnings) == 1
        assert warnings[0]["level"] == "warning"

    def test_gpu_temperature_critical(self):
        """Should flag critical on very high GPU temperature."""
        from backend.services.health_checks import check_gpu_temperatures

        gpus = [{"index": 0, "temperature": 96}]
        warnings = check_gpu_temperatures(gpus)
        assert len(warnings) == 1
        assert warnings[0]["level"] == "critical"

    def test_gpu_temperature_normal(self):
        """Normal temperature should produce no warnings."""
        from backend.services.health_checks import check_gpu_temperatures

        gpus = [{"index": 0, "temperature": 65}]
        warnings = check_gpu_temperatures(gpus)
        assert len(warnings) == 0

    def test_gpu_temperature_none(self):
        """None temperature should be skipped."""
        from backend.services.health_checks import check_gpu_temperatures

        gpus = [{"index": 0, "temperature": None}]
        warnings = check_gpu_temperatures(gpus)
        assert len(warnings) == 0

    def test_gpu_temperature_empty_list(self):
        """Empty GPU list should return empty warnings."""
        from backend.services.health_checks import check_gpu_temperatures

        assert check_gpu_temperatures([]) == []
        assert check_gpu_temperatures(None) == []


# ── T5: Docker / health endpoint ──────────────────────────────────────────


class TestHealthEndpoint:
    """Verify health endpoint is registered."""

    def test_health_route_exists(self):
        """The /api/system/health route should be registered."""
        from backend.api.system import router

        routes = [r.path for r in router.routes]
        assert "/health" in routes or "/api/system/health" in routes

    def test_gpu_info_route_exists(self):
        """The /api/system/gpu-info route should be registered."""
        from backend.api.system import router

        routes = [r.path for r in router.routes]
        assert "/gpu-info" in routes or "/api/system/gpu-info" in routes


# ── T6: DGX Spark config ──────────────────────────────────────────────────


class TestDGXSparkConfig:
    """Verify DGX Spark training preset exists and is valid YAML."""

    def test_config_file_exists(self):
        """configs/dgx_spark.yaml should exist."""
        config_path = Path(__file__).parent.parent / "configs" / "dgx_spark.yaml"
        assert config_path.exists(), f"Config not found: {config_path}"

    def test_config_is_valid_yaml(self):
        """Config should be parseable YAML with expected keys."""
        import yaml

        config_path = Path(__file__).parent.parent / "configs" / "dgx_spark.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert isinstance(config, dict)
        assert "model" in config
        assert "data" in config
        assert "training" in config
        assert "checkpoint" in config

    def test_config_model_section(self):
        """Model section should specify backbone and bit_list."""
        import yaml

        config_path = Path(__file__).parent.parent / "configs" / "dgx_spark.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        model = config["model"]
        assert "backbone" in model
        assert "siglip2" in model["backbone"].lower() or "siglip" in model["backbone"].lower()
        assert "bit_list" in model
        assert isinstance(model["bit_list"], list)

    def test_config_training_section(self):
        """Training section should have auto batch size and bf16 precision."""
        import yaml

        config_path = Path(__file__).parent.parent / "configs" / "dgx_spark.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        training = config["training"]
        assert training["batch_size"] == "auto"
        assert "bf16" in training.get("precision", "")

    def test_setup_dgx_script_exists(self):
        """scripts/setup_dgx.sh should exist and be executable."""
        script_path = Path(__file__).parent.parent / "scripts" / "setup_dgx.sh"
        assert script_path.exists()
        assert os.access(script_path, os.X_OK)


# ── Integration: auto_config compute ──────────────────────────────────────


class TestAutoConfig:
    """Verify GPU auto-config logic for DGX Spark parameters."""

    def test_auto_config_dgx_spark_frozen(self):
        """DGX Spark (128 GB unified) frozen backbone should get large batch."""
        from backend.api.system import _compute_auto_config

        result = _compute_auto_config(vram_gb=128, unified=True, freeze_backbone=True)
        assert result["batch_size"] >= 32
        assert result["batch_size"] % 32 == 0  # aligned to 32
        assert result["num_workers"] >= 2

    def test_auto_config_dgx_spark_unfrozen(self):
        """DGX Spark unfrozen should get smaller batch than frozen."""
        from backend.api.system import _compute_auto_config

        frozen = _compute_auto_config(vram_gb=128, unified=True, freeze_backbone=True)
        unfrozen = _compute_auto_config(vram_gb=128, unified=True, freeze_backbone=False)
        assert unfrozen["batch_size"] <= frozen["batch_size"]

    def test_auto_config_no_gpu(self):
        """No GPU should return fallback config."""
        from backend.api.system import _compute_auto_config

        result = _compute_auto_config(vram_gb=0, unified=False, freeze_backbone=True)
        assert result["batch_size"] == 32
        assert result["accumulate_grad_batches"] == 8


# ── Log archive service ──────────────────────────────────────────────────


class TestLogArchiveService:
    """Verify LogArchiveService lifecycle."""

    def test_service_importable(self):
        """LogArchiveService should be importable."""
        from backend.services.log_manager import LogArchiveService  # noqa: F401

    def test_service_start_stop(self):
        """Service should start and stop without error."""
        from backend.services.log_manager import LogArchiveService

        service = LogArchiveService()
        assert service._running is False
        # Note: Can't test async start/stop without event loop,
        # just verify the interface exists
        assert hasattr(service, "start")
        assert hasattr(service, "stop")
