@echo off
cd /d f:\Qoder\btc-collision-engine
python -m pytest tests/unit/collision/test_collision_stats.py -v --tb=short -p no:cacheprovider > test_stats_output.txt 2>&1
