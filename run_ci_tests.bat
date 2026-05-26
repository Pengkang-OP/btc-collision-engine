@echo off
cd /d f:\Qoder\btc-collision-engine
python -m pytest tests/ -v --tb=short -p no:cacheprovider -m "not (gpu or gpu_kernel or multi_gpu or gpu_hardware or integration)" --ignore=tests/test_comprehensive_simulation.py --ignore=tests/acceptance/test_acceptance_e2e.py --ignore=tests/acceptance/test_acceptance_e2e_cancellation.py --ignore=tests/test_multi_format_conversion.py --timeout=120 --timeout-method=thread --cov=src --cov-report=term --cov-fail-under=30 > ci_test_result.txt 2>&1
