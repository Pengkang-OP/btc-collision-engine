# 测试文件归档说明

本目录包含已从主tests/目录移出的测试文件,这些文件被归档以供参考,但不再参与常规测试流程。

## 目录结构

### redundant-tests/

**重复的测试文件**

包含功能被其他测试文件覆盖的重复测试,保留用于参考:

- `test_checkpoint_comprehensive.py` - 与test_checkpoint_manager.py功能重复
- `test_gpu_collision_engine_comprehensive.py` - 与test_gpu_collision_engine.py重复
- `test_gpu_integration_validation.py` - 与test_gpu_integration.py重复
- `test_gpu_selection_simple.py` - 与test_gpu_selection_and_switching.py重复

**说明**: 这些测试的功能已被保留的测试文件完全覆盖,归档以避免维护负担。

### temp-fix-tests/

**临时修复验证测试**

包含针对特定修复(P1/P2优先级)的验证测试,这些修复已合并到主代码:

- `test_p1_1_memory_lock.py` - P1-1内存锁定修复验证
- `test_p1_2_high_priority_fixes.py` - P1-2高优先级修复验证
- `test_p2_1_deprecation.py` - P2-1弃用处理验证
- `test_p2_5_progress.py` - P2-5进度管理验证
- `test_p2_fixes.py` - P2修复验证
- `test_code_quality_fixes.py` - 代码质量修复验证
- `test_project_analysis_fixes.py` - 项目分析修复验证
- `test_config_validation_fixes.py` - 配置验证修复验证

**说明**: 这些测试验证的修复已经合并到主代码并经过充分测试,可以安全归档。如需要验证特定修复,可从archive恢复。

### verify_scripts/

**一次性验证脚本**

包含用于验证特定修复或功能的独立验证脚本(verify_*.py):

**根目录移入**:

- `verify_a_class_fixes.py` - A类修复验证
- `verify_all_fixes.py` - 全量修复验证
- `verify_b_class_fixes.py` - B类修复验证
- `verify_c_class_fixes.py` - C类修复验证
- `verify_no_regression.py` - 无回归验证
- `verify_private_key_hash_fix.py` - 私钥哈希修复验证

**tests目录整理**:

- `verify_gpu_and_export_ui.py` - GPU和导出UI验证
- `verify_gpu_engine_fix.py` - GPU引擎修复验证
- `verify_gpu_module_integration.py` - GPU模块集成验证
- `verify_gpu_priority_fix.py` - GPU优先级修复验证
- `verify_p0_p1_p2_fixes.py` - P0/P1/P2修复验证
- `verify_p1_1_memory_locking.py` - P1-1内存锁定验证
- `verify_ui_fixes.py` - UI修复验证
- `verify_ui_fixes_final.py` - UI最终修复验证

**说明**: 这些是一次性验证脚本,不是常规的pytest单元测试。它们用于特定时间点的验证,不应与测试套件一起运行。

## 如何使用归档文件

### 恢复文件

如需要运行某个归档测试:

```bash
# 从redundant-tests恢复
cp tests/archive/redundant-tests/test_checkpoint_comprehensive.py tests/

# 从temp-fix-tests恢复
cp tests/archive/temp-fix-tests/test_p1_1_memory_lock.py tests/

# 从verify_scripts恢复
cp tests/verify_scripts/verify_no_regression.py .
```

### 运行归档测试

恢复后,可以像普通测试一样运行:

```bash
pytest tests/test_checkpoint_comprehensive.py -v
python verify_no_regression.py
```

## 维护建议

1. **定期清理**: 每6个月审查一次archive目录,删除完全过时的测试
2. **文档更新**: 如主代码发生重大变化,更新此README说明
3. **Git历史**: 所有归档文件都保留在Git历史中,可随时通过git log查看
4. **测试覆盖**: 确保保留的测试文件仍然提供完整的测试覆盖

## 清理记录

**2026-04-22**: 首次测试文件整理

- 归档4个重复测试文件
- 归档8个临时修复测试
- 整理14个验证脚本到verify_scripts/
- 详见: `docs/TEST_CLEANUP_REPORT_20260422.md`
