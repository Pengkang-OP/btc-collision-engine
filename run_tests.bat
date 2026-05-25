@echo off
cd /d f:\Qoder\btc-collision-engine
python -m pytest tests/test_data_conversion.py -v --tb=short -p no:cacheprovider 2>&1 | head -50
pause
