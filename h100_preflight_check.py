#!/usr/bin/env python3
"""H100 Pre-Flight Verification — Validate safety fixes before batch execution.

Usage:
    python h100_preflight_check.py
    python h100_preflight_check.py --verbose
    
Checks:
    1. Framework pre_run_validation() can be imported
    2. GPU memory cleanup in runner.run_experiment()
    3. Data validation in data.py (_load_jsonl raises on corrupt data)
    4. Progress logging in real_backend (distillation loops)
    5. Asset availability checks before expensive compute
"""
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("preflight")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

def check_imports():
    """Verify safety modules can be imported."""
    logger.info("Checking imports...")
    try:
        from experiments.framework import pre_run_validation, ExperimentRuntimeError
        logger.info("✓ framework.pre_run_validation importable")
    except ImportError as e:
        logger.error("✗ framework.pre_run_validation import failed: %s", e)
        return False
    
    try:
        from experiments.runner import run_experiment
        logger.info("✓ runner.run_experiment importable")
    except ImportError as e:
        logger.error("✗ runner.run_experiment import failed: %s", e)
        return False
    
    try:
        from realeval.data import _load_jsonl
        logger.info("✓ data._load_jsonl importable")
    except ImportError as e:
        logger.error("✗ data._load_jsonl import failed: %s", e)
        return False
    
    return True

def check_preflight_logic():
    """Verify pre_run_validation logic."""
    logger.info("Checking pre_run_validation logic...")
    from experiments.framework import pre_run_validation, ExperimentRuntimeError
    
    # Test 1: Smoke mode should skip H100 checks
    smoke_config = {"_smoke": True}
    try:
        pre_run_validation(smoke_config, "test_exp")
        logger.info("✓ pre_run_validation skips H100 checks for smoke mode")
    except Exception as e:
        logger.error("✗ pre_run_validation smoke mode failed: %s", e)
        return False
    
    # Test 2: Paper mode should check GPU (but may pass or fail depending on environment)
    paper_config = {"_smoke": False}
    try:
        pre_run_validation(paper_config, "test_exp")
        logger.info("✓ pre_run_validation runs H100 checks for paper mode (passed)")
    except ExperimentRuntimeError as e:
        # Expected if GPU not available or weights not found
        if "Insufficient GPU" in str(e) or "unavailable" in str(e):
            logger.info("✓ pre_run_validation runs H100 checks (failed as expected: %s)", str(e)[:60])
        else:
            logger.error("✗ Unexpected validation error: %s", e)
            return False
    except Exception as e:
        logger.error("✗ pre_run_validation unexpected error: %s", e)
        return False
    
    return True

def check_data_validation():
    """Verify data validation catches corrupted files."""
    logger.info("Checking data validation...")
    from realeval.data import _load_jsonl
    import tempfile
    import json
    
    # Test 1: Normal JSONL should load
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        for i in range(20):
            f.write(json.dumps({"text": f"Sample {i}", "label": i % 2}) + "\n")
        normal_file = f.name
    
    try:
        texts, labels = _load_jsonl(Path(normal_file))
        if len(texts) >= 10:
            logger.info("✓ data validation loads normal JSONL correctly (%d samples)", len(texts))
        else:
            logger.error("✗ Normal JSONL load returned too few samples: %d", len(texts))
            return False
    except Exception as e:
        logger.error("✗ Normal JSONL load failed: %s", e)
        return False
    finally:
        Path(normal_file).unlink()
    
    # Test 2: Corrupted JSONL should raise ValueError
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write("not valid json\n")
        f.write("also not json\n")
        corrupt_file = f.name
    
    try:
        texts, labels = _load_jsonl(Path(corrupt_file))
        logger.error("✗ Corrupted JSONL did not raise ValueError (got %d samples)", len(texts))
        return False
    except ValueError as e:
        if "validation failed" in str(e).lower():
            logger.info("✓ data validation rejects corrupted JSONL: %s", str(e)[:60])
        else:
            logger.error("✗ Unexpected ValueError message: %s", e)
            return False
    except Exception as e:
        logger.error("✗ Corrupted JSONL raised unexpected error: %s", e)
        return False
    finally:
        Path(corrupt_file).unlink()
    
    return True

def check_memory_cleanup():
    """Verify GPU memory cleanup code exists."""
    logger.info("Checking GPU memory cleanup...")
    runner_path = ROOT / "experiments" / "runner.py"
    content = runner_path.read_text()
    
    required_patterns = [
        "torch.cuda.empty_cache()",
        "torch.cuda.max_memory_allocated()",
    ]
    
    for pattern in required_patterns:
        if pattern in content:
            logger.info("✓ runner.py contains '%s'", pattern)
        else:
            logger.error("✗ runner.py missing '%s'", pattern)
            return False
    
    return True

def check_progress_logging():
    """Verify progress logging code exists."""
    logger.info("Checking progress logging...")
    backend_path = ROOT / "realeval" / "real_backend.py"
    content = backend_path.read_text()
    
    required_patterns = [
        "Progress logging",
        "torch.cuda.synchronize()",
        "GPU free=",
    ]
    
    for pattern in required_patterns:
        if pattern in content:
            logger.info("✓ real_backend.py contains '%s'", pattern)
        else:
            logger.error("✗ real_backend.py missing '%s'", pattern)
            return False
    
    return True

def main():
    """Run all pre-flight checks."""
    logger.info("=" * 70)
    logger.info("H100 PRE-FLIGHT VERIFICATION")
    logger.info("=" * 70)
    
    checks = [
        ("Imports", check_imports),
        ("Preflight Logic", check_preflight_logic),
        ("Data Validation", check_data_validation),
        ("Memory Cleanup", check_memory_cleanup),
        ("Progress Logging", check_progress_logging),
    ]
    
    passed = 0
    failed = 0
    
    for check_name, check_func in checks:
        logger.info("\n[%s]", check_name)
        try:
            if check_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error("✗ Check crashed: %s", e)
            failed += 1
    
    logger.info("\n" + "=" * 70)
    logger.info("RESULTS: %d passed, %d failed", passed, failed)
    
    if failed == 0:
        logger.info("✓ All safety fixes verified. H100 batch execution is safer.")
        logger.info("=" * 70)
        return 0
    else:
        logger.error("✗ Some checks failed. Review fixes before H100 execution.")
        logger.info("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(main())
