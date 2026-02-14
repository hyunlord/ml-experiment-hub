#!/usr/bin/env python3
"""Verification script for MonitorCallback integration.

Tests:
1. Hash analysis data flattening
2. System stats endpoint schema
3. Monitor config injection
4. System monitor service
"""

import asyncio


def test_hash_analysis_flattening():
    """Test hash analysis data flattening logic."""
    print("Testing hash analysis flattening...")

    # Simulate MonitorCallback hash_analysis payload
    data = {
        "step": 100,
        "epoch": 1,
        "activation_rates": [0.5, 0.3, 0.8, 0.2],
        "entropy": [0.9, 0.7, 0.6, 0.85],
        "similarity_matrix": [
            [1.0, 0.8, 0.6],
            [0.8, 1.0, 0.7],
            [0.6, 0.7, 1.0],
        ],
        "augmentation_robustness": {
            "rotation": 0.95,
            "flip": 0.88,
        },
        "samples": [
            {"thumbnail": "base64data", "code": [1, 0, 1, 0]},
        ],
    }

    # Flatten scalar data
    flat_metrics = {}

    activation_rates = data.get("activation_rates")
    if isinstance(activation_rates, list):
        for i, val in enumerate(activation_rates):
            if isinstance(val, (int, float)):
                flat_metrics[f"hash/bit_activation_{i}"] = val

    entropy = data.get("entropy")
    if isinstance(entropy, list):
        for i, val in enumerate(entropy):
            if isinstance(val, (int, float)):
                flat_metrics[f"hash/entropy_{i}"] = val

    similarity_matrix = data.get("similarity_matrix")
    if isinstance(similarity_matrix, list) and len(similarity_matrix) > 0:
        size = len(similarity_matrix)
        flat_metrics["hash/similarity_matrix_size"] = size
        idx = 0
        for row in similarity_matrix:
            if isinstance(row, list):
                for val in row:
                    if isinstance(val, (int, float)):
                        flat_metrics[f"hash/similarity_{idx}"] = val
                        idx += 1

    aug_robustness = data.get("augmentation_robustness")
    if isinstance(aug_robustness, dict):
        for key, val in aug_robustness.items():
            if isinstance(val, (int, float)):
                flat_metrics[f"hash/aug_{key}"] = val

    # Verify results
    assert "hash/bit_activation_0" in flat_metrics
    assert flat_metrics["hash/bit_activation_0"] == 0.5
    assert "hash/entropy_3" in flat_metrics
    assert flat_metrics["hash/entropy_3"] == 0.85
    assert "hash/similarity_matrix_size" in flat_metrics
    assert flat_metrics["hash/similarity_matrix_size"] == 3
    assert "hash/similarity_8" in flat_metrics  # Last element of 3x3 matrix
    assert "hash/aug_rotation" in flat_metrics
    assert flat_metrics["hash/aug_rotation"] == 0.95

    print(f"✅ Flattened {len(flat_metrics)} metrics from hash analysis")
    return True


def test_system_stats_schema():
    """Test SystemStatsIngest schema."""
    print("Testing SystemStatsIngest schema...")

    from backend.api.metrics import SystemStatsIngest

    # Test basic payload
    stats = SystemStatsIngest(
        gpu_util=75.5,
        gpu_memory_used=8192.0,
        gpu_memory_total=16384.0,
        cpu_percent=45.2,
        ram_percent=62.8,
    )
    assert stats.gpu_util == 75.5
    assert stats.cpu_percent == 45.2

    # Test multi-GPU payload
    stats_multi = SystemStatsIngest(
        gpus=[
            {"util": 80.0, "memory_used_mb": 10000, "memory_total_mb": 16384},
            {"util": 60.0, "memory_used_mb": 8000, "memory_total_mb": 16384},
        ]
    )
    assert len(stats_multi.gpus) == 2

    print("✅ SystemStatsIngest schema validated")
    return True


def test_monitor_config_injection():
    """Test monitor config injection."""
    print("Testing monitor config injection...")

    from adapters.pytorch_lightning import PyTorchLightningAdapter

    adapter = PyTorchLightningAdapter()

    # Test config without monitor section
    config = {
        "model": {"name": "test"},
        "trainer": {"max_epochs": 10},
    }

    injected = adapter.inject_monitor_config(config, run_id=42, server_url="http://localhost:8000")

    assert "monitor" in injected
    assert injected["monitor"]["enabled"] is True
    assert injected["monitor"]["run_id"] == 42
    assert injected["monitor"]["server_url"] == "http://localhost:8000"

    print("✅ Monitor config injection works")
    return True


async def test_system_monitor_service():
    """Test SystemMonitorService initialization."""
    print("Testing SystemMonitorService...")

    from backend.core.system_monitor import SystemMonitorService

    monitor = SystemMonitorService()

    # Test start/stop
    monitor.start()
    assert monitor._running is True

    await asyncio.sleep(0.1)  # Let it run briefly

    monitor.stop()
    assert monitor._running is False

    print("✅ SystemMonitorService lifecycle works")
    return True


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("MonitorCallback Integration Verification")
    print("=" * 60)
    print()

    results = []

    try:
        results.append(("Hash Analysis Flattening", test_hash_analysis_flattening()))
    except Exception as e:
        print(f"❌ Hash analysis test failed: {e}")
        results.append(("Hash Analysis Flattening", False))

    try:
        results.append(("System Stats Schema", test_system_stats_schema()))
    except Exception as e:
        print(f"❌ System stats schema test failed: {e}")
        results.append(("System Stats Schema", False))

    try:
        results.append(("Monitor Config Injection", test_monitor_config_injection()))
    except Exception as e:
        print(f"❌ Monitor config injection test failed: {e}")
        results.append(("Monitor Config Injection", False))

    try:
        asyncio.run(test_system_monitor_service())
        results.append(("System Monitor Service", True))
    except Exception as e:
        print(f"❌ System monitor service test failed: {e}")
        results.append(("System Monitor Service", False))

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)
    print()
    if all_passed:
        print("🎉 All verification tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())
