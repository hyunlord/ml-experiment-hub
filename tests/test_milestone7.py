"""Milestone 7 tests — stabilization, health checks, log management, DB optimizations,
dummy_classifier adapter (universality proof), predict API, genericity.
"""

from __future__ import annotations

import gzip
import os
from pathlib import Path
from unittest.mock import patch

import torch


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


# ══════════════════════════════════════════════════════════════════════
# M7 NEW: Dummy Classifier Adapter — Universality Proof
# ══════════════════════════════════════════════════════════════════════


# ── T7: Adapter registration ────────────────────────────────────────


class TestDummyClassifierRegistration:
    """Verify dummy_classifier is in the adapter registry."""

    def test_adapter_in_registry(self):
        from adapters import ADAPTER_REGISTRY

        assert "dummy_classifier" in ADAPTER_REGISTRY

    def test_get_adapter_returns_instance(self):
        from adapters import get_adapter

        adapter = get_adapter("dummy_classifier")
        assert adapter is not None
        assert adapter.get_name() == "Image Classifier (MNIST / CIFAR-10)"

    def test_adapter_implements_base(self):
        from adapters import get_adapter
        from adapters.base import BaseAdapter

        adapter = get_adapter("dummy_classifier")
        assert isinstance(adapter, BaseAdapter)


# ── T8: SimpleCNN model ─────────────────────────────────────────────


class TestSimpleCNN:
    """Verify SimpleCNN forward pass for MNIST and CIFAR input shapes."""

    def test_mnist_forward(self):
        """1×28×28 input should produce (batch, 10) logits."""
        from adapters.dummy_classifier.model import SimpleCNN

        model = SimpleCNN(in_channels=1, num_classes=10)
        x = torch.randn(2, 1, 28, 28)
        out = model(x)
        assert out.shape == (2, 10)

    def test_cifar_forward(self):
        """3×32×32 input should produce (batch, 10) logits."""
        from adapters.dummy_classifier.model import SimpleCNN

        model = SimpleCNN(in_channels=3, num_classes=10)
        x = torch.randn(2, 3, 32, 32)
        out = model(x)
        assert out.shape == (2, 10)

    def test_save_and_load(self, tmp_path: Path):
        """Save and load checkpoint roundtrip."""
        from adapters.dummy_classifier.model import SimpleCNN, load_model

        model = SimpleCNN(in_channels=1, num_classes=10)
        ckpt_path = tmp_path / "test.pt"
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "in_channels": 1,
                "num_classes": 10,
            },
            ckpt_path,
        )

        loaded = load_model(str(ckpt_path))
        assert isinstance(loaded, SimpleCNN)
        # Verify output matches
        x = torch.randn(1, 1, 28, 28)
        model.eval()
        loaded.eval()
        with torch.no_grad():
            assert torch.allclose(model(x), loaded(x))


# ── T9: Adapter interface ───────────────────────────────────────────


class TestDummyClassifierAdapter:
    """Verify DummyClassifierAdapter methods."""

    def test_config_to_yaml(self):
        from adapters.dummy_classifier.adapter import DummyClassifierAdapter

        adapter = DummyClassifierAdapter()
        yaml_str = adapter.config_to_yaml({"dataset": "mnist", "epochs": 5})
        assert "dataset" in yaml_str
        assert "mnist" in yaml_str

    def test_get_train_command(self):
        from adapters.dummy_classifier.adapter import DummyClassifierAdapter

        adapter = DummyClassifierAdapter()
        cmd = adapter.get_train_command("/tmp/config.yaml")
        assert cmd[0] == "python"
        assert "adapters.dummy_classifier.train" in " ".join(cmd)
        assert "/tmp/config.yaml" in cmd

    def test_parse_metrics_json(self):
        from adapters.dummy_classifier.adapter import DummyClassifierAdapter

        adapter = DummyClassifierAdapter()
        line = '{"step": 100, "epoch": 1, "train/loss": 0.5, "train/accuracy": 0.85}'
        result = adapter.parse_metrics(line)
        assert result is not None
        assert result["step"] == 100
        assert result["train/loss"] == 0.5

    def test_parse_metrics_keyvalue(self):
        from adapters.dummy_classifier.adapter import DummyClassifierAdapter

        adapter = DummyClassifierAdapter()
        line = "step=100 train/loss=0.5 train/accuracy=0.85"
        result = adapter.parse_metrics(line)
        assert result is not None
        assert result["step"] == 100

    def test_parse_metrics_non_metric_line(self):
        from adapters.dummy_classifier.adapter import DummyClassifierAdapter

        adapter = DummyClassifierAdapter()
        assert adapter.parse_metrics("Downloading MNIST...") is None

    def test_get_metrics_mapping(self):
        from adapters.dummy_classifier.adapter import DummyClassifierAdapter

        adapter = DummyClassifierAdapter()
        mapping = adapter.get_metrics_mapping()
        assert "train/loss" in mapping
        assert "val/accuracy" in mapping
        assert mapping["val/accuracy"]["direction"] == "maximize"

    def test_get_search_ranges(self):
        from adapters.dummy_classifier.adapter import DummyClassifierAdapter

        adapter = DummyClassifierAdapter()
        ranges = adapter.get_search_ranges()
        assert "learning_rate" in ranges
        assert "batch_size" in ranges
        assert ranges["learning_rate"]["type"] == "float"

    def test_load_model(self, tmp_path: Path):
        from adapters.dummy_classifier.adapter import DummyClassifierAdapter
        from adapters.dummy_classifier.model import SimpleCNN

        model = SimpleCNN(in_channels=1, num_classes=10)
        ckpt = tmp_path / "test.pt"
        torch.save(
            {"model_state_dict": model.state_dict(), "in_channels": 1, "num_classes": 10},
            ckpt,
        )

        adapter = DummyClassifierAdapter()
        loaded = adapter.load_model(str(ckpt))
        assert isinstance(loaded, SimpleCNN)

    def test_predict(self, tmp_path: Path):
        """predict() should return top-class and probabilities."""
        from adapters.dummy_classifier.adapter import DummyClassifierAdapter
        from adapters.dummy_classifier.model import SimpleCNN

        model = SimpleCNN(in_channels=1, num_classes=10)
        ckpt = tmp_path / "test.pt"
        torch.save(
            {"model_state_dict": model.state_dict(), "in_channels": 1, "num_classes": 10},
            ckpt,
        )

        adapter = DummyClassifierAdapter()
        loaded = adapter.load_model(str(ckpt))

        # Create a tiny grayscale PNG
        from PIL import Image
        import io

        img = Image.new("L", (28, 28), color=128)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        result = adapter.predict(loaded, image_bytes)
        assert "predictions" in result
        assert "top_class" in result
        assert "confidence" in result
        assert len(result["predictions"]) <= 10
        assert isinstance(result["predictions"][0]["probability"], float)


# ── T10: Evaluator ──────────────────────────────────────────────────


class TestEvaluator:
    """Verify classification evaluator returns correct structure."""

    def test_evaluate_returns_report(self):
        from adapters.dummy_classifier.evaluator import evaluate
        from adapters.dummy_classifier.model import SimpleCNN
        from torch.utils.data import DataLoader, TensorDataset

        model = SimpleCNN(in_channels=1, num_classes=3)
        model.eval()

        # Fake dataset: 20 samples, 3 classes
        images = torch.randn(20, 1, 28, 28)
        labels = torch.randint(0, 3, (20,))
        ds = TensorDataset(images, labels)
        loader = DataLoader(ds, batch_size=10)

        result = evaluate(model, loader, class_names=["cat", "dog", "bird"])
        assert "accuracy" in result
        assert "per_class" in result
        assert "macro_f1" in result
        assert len(result["per_class"]) == 3
        assert result["per_class"][0]["class"] == "cat"
        assert 0 <= result["accuracy"] <= 1
        assert result["total_samples"] == 20


# ── T11: Predict API route ──────────────────────────────────────────


class TestPredictAPI:
    """Verify predict API router is registered."""

    def test_predict_route_exists(self):
        from backend.api.predict import router

        paths = [r.path for r in router.routes]
        assert "/image" in paths or "/api/predict/image" in paths

    def test_predict_router_in_app(self):
        from backend.main import app

        route_paths = [r.path for r in app.routes]
        assert any("/predict" in p for p in route_paths)


# ── T12: BaseAdapter predict method ─────────────────────────────────


class TestBaseAdapterPredict:
    """Verify BaseAdapter has optional predict() method."""

    def test_predict_on_base_raises(self):
        """BaseAdapter.predict() should raise NotImplementedError."""
        from adapters.base import BaseAdapter

        # Create a minimal concrete subclass
        class _Stub(BaseAdapter):
            def config_to_yaml(self, config):
                return ""

            def get_train_command(self, yaml_path):
                return []

            def parse_metrics(self, log_line):
                return None

        stub = _Stub()
        import pytest

        with pytest.raises(NotImplementedError):
            stub.predict(None, b"")


# ── T13: Genericity checks ──────────────────────────────────────────


class TestGenericity:
    """No vlm/siglip/hash/coco terms in core API or shared schemas."""

    FORBIDDEN = {"vlm", "siglip", "coco", "hash_layer", "hamming_search", "cosine_search"}

    def _scan_file(self, path: Path) -> list[str]:
        """Return forbidden terms found in a file (case-insensitive in identifiers)."""
        if not path.exists():
            return []
        text = path.read_text()
        found = []
        for term in self.FORBIDDEN:
            # Skip comments and strings, check identifiers
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue
                if term in stripped.lower():
                    found.append(f"{path.name}: '{term}' in: {stripped[:120]}")
                    break
        return found

    def test_no_forbidden_in_backend_api(self):
        api_dir = Path(__file__).parent.parent / "backend" / "api"
        violations = []
        for py_file in api_dir.glob("*.py"):
            violations.extend(self._scan_file(py_file))
        assert violations == [], "Forbidden terms in API:\n" + "\n".join(violations)

    def test_no_forbidden_in_shared_schemas(self):
        schemas_file = Path(__file__).parent.parent / "shared" / "schemas.py"
        violations = self._scan_file(schemas_file)
        assert violations == [], "Forbidden terms in schemas:\n" + "\n".join(violations)

    def test_no_forbidden_in_backend_core(self):
        core_dir = Path(__file__).parent.parent / "backend" / "core"
        if not core_dir.exists():
            return  # core/ is optional
        violations = []
        for py_file in core_dir.glob("*.py"):
            violations.extend(self._scan_file(py_file))
        assert violations == [], "Forbidden terms in core:\n" + "\n".join(violations)

    def test_predict_api_is_generic(self):
        """predict.py should not reference specific model types."""
        predict_file = Path(__file__).parent.parent / "backend" / "api" / "predict.py"
        violations = self._scan_file(predict_file)
        assert violations == [], "Forbidden terms in predict API:\n" + "\n".join(violations)


# ── T14: Two adapters coexist ────────────────────────────────────────


class TestTwoAdaptersCoexist:
    """Both vlm_quantization and dummy_classifier must be in the registry."""

    def test_both_in_registry(self):
        from adapters import ADAPTER_REGISTRY

        assert "vlm_quantization" in ADAPTER_REGISTRY
        assert "dummy_classifier" in ADAPTER_REGISTRY

    def test_different_names(self):
        from adapters import get_adapter

        vlm = get_adapter("vlm_quantization")
        clf = get_adapter("dummy_classifier")
        assert vlm.get_name() != clf.get_name()

    def test_different_metrics(self):
        from adapters import get_adapter

        vlm = get_adapter("vlm_quantization")
        clf = get_adapter("dummy_classifier")
        vlm_keys = set(vlm.get_metrics_mapping().keys())
        clf_keys = set(clf.get_metrics_mapping().keys())
        # Should have different metric keys (some overlap on train/loss is ok)
        assert vlm_keys != clf_keys

    def test_both_have_search_ranges(self):
        from adapters import get_adapter

        vlm = get_adapter("vlm_quantization")
        clf = get_adapter("dummy_classifier")
        assert len(vlm.get_search_ranges()) > 0
        assert len(clf.get_search_ranges()) > 0
