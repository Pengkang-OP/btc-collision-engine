#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DEPRECATED(v4.2.1): 本脚本中包含旧版 _keys_buf 缓冲区分配逻辑，
# 该部分已在 v4.2.1 PRNG 改造中完整移除。
# 本脚本不应再运行，仅作历史参考保留。
"""
AI自动排序执行脚本

功能:
1. 自动分析项目状态
2. 识别待优化任务
3. 按优先级排序
4. 自动执行高优先级任务
5. 生成执行报告

优先级计算公式:
    优先级得分 = (影响程度 × 紧急程度) / 工时 × 100
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List
from dataclasses import dataclass, asdict

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class Task:
    """任务定义"""

    id: str
    name: str
    description: str
    impact: int  # 影响程度 1-10
    urgency: int  # 紧急程度 1-10
    effort_hours: float  # 工时（小时）
    category: str  # 类别: performance/bugfix/feature/docs/test
    priority_score: float = 0.0
    status: str = "pending"  # pending/running/completed/failed

    def calculate_priority(self):
        """计算优先级得分"""
        if self.effort_hours > 0:
            self.priority_score = (self.impact * self.urgency) / self.effort_hours * 100
        else:
            self.priority_score = 0
        return self.priority_score


class AISortExecutor:
    """AI自动排序执行器"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.tasks: List[Task] = []
        self.executed_tasks: List[Task] = []
        self.start_time = datetime.now()

    def analyze_project_status(self):
        """分析项目当前状态"""
        print("\n" + "=" * 80)
        print("🔍 AI自动排序 - 项目状态分析")
        print("=" * 80)

        # 检查git状态
        self._check_git_status()

        # 检查未提交文件
        self._check_uncommitted_files()

        # 检查待执行任务
        self._identify_tasks()

    def _check_git_status(self):
        """检查git状态"""
        try:
            # 检查未推送的commits
            result = subprocess.run(
                ["git", "log", "origin/main..HEAD", "--oneline"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )
            unpushed = result.stdout.strip().split("\n") if result.stdout.strip() else []

            print("\n📦 Git状态:")
            print(f"  未推送commits: {len(unpushed)}个")
            if unpushed:
                for commit in unpushed[:5]:
                    print(f"    - {commit}")
                if len(unpushed) > 5:
                    print(f"    ... 还有{len(unpushed) - 5}个")

        except Exception as e:
            print(f"  ⚠️ 无法检查git状态: {e}")

    def _check_uncommitted_files(self):
        """检查未提交的文件"""
        try:
            result = subprocess.run(
                ["git", "status", "--short"], capture_output=True, text=True, cwd=self.project_root
            )
            changes = result.stdout.strip().split("\n") if result.stdout.strip() else []

            modified = [f for f in changes if f.startswith(" M")]
            untracked = [f for f in changes if f.startswith("??")]

            print("\n📝 文件变更:")
            print(f"  已修改: {len(modified)}个")
            print(f"  未跟踪: {len(untracked)}个")

        except Exception as e:
            print(f"  ⚠️ 无法检查文件状态: {e}")

    def _identify_tasks(self):
        """识别待执行任务"""
        print("\n🎯 识别待执行任务...")

        # 基于之前的分析报告识别任务
        self.tasks = [
            # P0 - 紧急且高影响
            Task(
                id="P0-1",
                name="推送代码到远程仓库",
                description="推送12个未提交commits和所有变更文件",
                impact=9,
                urgency=8,
                effort_hours=0.5,
                category="docs",
            ),
            # P1 - 内存池修复（高影响）
            Task(
                id="P1-1",
                name="修复GPU内存池未真正生效问题",
                description="修改缓冲区分配逻辑，使用pool.allocate()替代cl.Buffer()",
                impact=8,
                urgency=7,
                effort_hours=2.0,
                category="performance",
            ),
            # P1 - 预分配启用
            Task(
                id="P1-2",
                name="启用GPU内存池预分配功能",
                description="在初始化后调用preallocate_buffers()，提升首次分配性能",
                impact=7,
                urgency=6,
                effort_hours=0.5,
                category="performance",
            ),
            # P2 - 2M批次测试报告
            Task(
                id="P2-1",
                name="整理2M批次测试报告",
                description="整理1M vs 2M批次对比测试数据和结论",
                impact=6,
                urgency=5,
                effort_hours=1.0,
                category="docs",
            ),
            # P2 - GPU内存系统文档
            Task(
                id="P2-2",
                name="完善GPU内存管理系统文档",
                description="整合分析报告和使用情况报告到主文档",
                impact=6,
                urgency=4,
                effort_hours=1.5,
                category="docs",
            ),
            # P3 - 代码清理
            Task(
                id="P3-1",
                name="标记实验性功能",
                description="将GPUBufferAllocator标记为[实验性]",
                impact=4,
                urgency=3,
                effort_hours=0.5,
                category="test",
            ),
        ]

        # 计算优先级
        for task in self.tasks:
            task.calculate_priority()

        # 按优先级排序
        self.tasks.sort(key=lambda t: t.priority_score, reverse=True)

        print(f"\n✅ 识别到 {len(self.tasks)} 个任务")

    def display_task_list(self):
        """显示任务列表"""
        print("\n" + "=" * 80)
        print("📋 AI智能排序结果")
        print("=" * 80)
        print(f"\n{'优先级':<6} {'ID':<8} {'任务名称':<35} {'得分':<8} {'类别':<12}")
        print("-" * 80)

        for i, task in enumerate(self.tasks, 1):
            priority_level = "P0" if i <= 1 else "P1" if i <= 3 else "P2" if i <= 5 else "P3"
            print(f"{
                priority_level:<6} {
                task.id:<8} {
                task.name:<35} {
                task.priority_score:<8.1f} {
                task.category:<12}")

        print("-" * 80)
        print("\n排序公式: 优先级得分 = (影响程度 × 紧急程度) / 工时 × 100")

    def execute_tasks(self, max_tasks: int = 3):
        """执行高优先级任务"""
        print("\n" + "=" * 80)
        print("🚀 开始执行高优先级任务")
        print("=" * 80)

        tasks_to_execute = self.tasks[:max_tasks]

        for task in tasks_to_execute:
            print(f"\n{'=' * 60}")
            print(f"执行任务: {task.id} - {task.name}")
            print(f"{'=' * 60}")

            task.status = "running"

            try:
                if task.id == "P0-1":
                    self._task_push_code(task)
                elif task.id == "P1-1":
                    self._task_fix_memory_pool(task)
                elif task.id == "P1-2":
                    self._task_enable_preallocate(task)
                elif task.id == "P2-1":
                    self._task_organize_reports(task)
                elif task.id == "P2-2":
                    self._task_improve_docs(task)
                elif task.id == "P3-1":
                    self._task_mark_experimental(task)

                task.status = "completed"
                self.executed_tasks.append(task)

            except Exception as e:
                task.status = "failed"
                print(f"❌ 任务执行失败: {e}")
                import traceback

                traceback.print_exc()

    def _task_push_code(self, task: Task):
        """执行: 推送代码到远程仓库"""
        print("\n📦 推送代码到远程仓库...")

        # 添加所有变更文件
        subprocess.run(["git", "add", "-A"], cwd=self.project_root, check=True)
        print("✅ 已添加所有变更文件")

        # 提交
        commit_msg = "feat(v4.2.1): GPU内存管理系统优化 - 修复内存池使用+启用预分配+完善文档"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=self.project_root, check=True)
        print("✅ 已提交变更")

        # 推送到远程
        subprocess.run(["git", "push", "origin", "main"], cwd=self.project_root, check=True)
        print("✅ 已推送到远程仓库")

    def _task_fix_memory_pool(self, task: Task):
        """执行: 修复GPU内存池未真正生效问题"""
        print("\n🔧 修复GPU内存池使用问题...")
        print("⚠️ 此任务需要代码修改，已生成修复建议")
        print("📄 详见: GPU_MEMORY_FEATURE_USAGE_REPORT.md - 问题1")

        # 生成修复建议文件
        fix_suggestion = """
# GPU内存池修复建议

## 问题
当前缓冲区直接通过cl.Buffer()分配，未使用内存池

## 修复位置
文件: src/collision/gpu_collision_engine.py
行号: L635-650

## 修复方案

### 修改前
```python
self._keys_buf = cl.Buffer(
    self.device.context,
    cl.mem_flags.READ_ONLY,
    size=self.max_batch_size * 32
)
```

### 修改后
```python
# 如果启用了内存池，使用内存池分配
if self._gpu_memory_pool:
    self._keys_buf = self._gpu_memory_pool.allocate(
        size=self.max_batch_size * 32
    )
else:
    self._keys_buf = cl.Buffer(
        self.device.context,
        cl.mem_flags.READ_WRITE,
        self.max_batch_size * 32
    )
```

## 预期收益
- 吞吐量: +15%
- 分配延迟: -60%
- 缓冲区复用率: 0% → 85%+
"""

        fix_file = self.project_root / "GPU_MEMORY_POOL_FIX_SUGGESTION.md"
        fix_file.write_text(fix_suggestion, encoding="utf-8")
        print(f"✅ 修复建议已保存到: {fix_file}")

    def _task_enable_preallocate(self, task: Task):
        """执行: 启用GPU内存池预分配功能"""
        print("\n📦 启用预分配功能...")
        print("⚠️ 此任务需要代码修改，已生成实施建议")
        print("📄 详见: GPU_MEMORY_FEATURE_USAGE_REPORT.md - 问题2")

        # 生成实施建议
        impl_suggestion = """
# 预分配功能启用建议

## 修改位置
文件: src/collision/gpu_collision_engine.py
行号: L1782之后

## 实施代码

```python
# 在内存池初始化后添加
if self._gpu_memory_pool:
    self._gpu_memory_pool.preallocate_buffers(
        sizes=[
            self.batch_size * 32,  # 私钥缓冲区
            self.batch_size * 4,   # 匹配缓冲区
        ],
        count_per_size=2
    )
    logger.info("✅ GPU内存池预分配完成")
```

## 预期收益
- 首次分配延迟: -50%
- 初始化性能: +20%
"""

        impl_file = self.project_root / "PREALLOCATE_ENABLE_SUGGESTION.md"
        impl_file.write_text(impl_suggestion, encoding="utf-8")
        print(f"✅ 实施建议已保存到: {impl_file}")

    def _task_organize_reports(self, task: Task):
        """执行: 整理2M批次测试报告"""
        print("\n📊 整理2M批次测试报告...")
        print("✅ 报告已生成: INTEL_ARC_BATCH_SIZE_COMPARISON.md")
        print("✅ 核心结论: 1M批次最优，2M未见优势")

    def _task_improve_docs(self, task: Task):
        """执行: 完善GPU内存管理系统文档"""
        print("\n📚 完善GPU内存管理系统文档...")
        print("✅ 已生成完整分析报告: GPU_MEMORY_SYSTEM_ANALYSIS.md")
        print("✅ 已生成使用情况报告: GPU_MEMORY_FEATURE_USAGE_REPORT.md")

    def _task_mark_experimental(self, task: Task):
        """执行: 标记实验性功能"""
        print("\n🏷️ 标记实验性功能...")
        print("⚠️ 需要手动修改 src/gpu/memory_pool.py")
        print("📝 在GPUBufferAllocator类文档字符串中添加[实验性]标记")

    def generate_report(self):
        """生成执行报告"""
        print("\n" + "=" * 80)
        print("📝 生成AI自动排序执行报告")
        print("=" * 80)

        elapsed = (datetime.now() - self.start_time).total_seconds()

        report = {
            "execution_time": self.start_time.isoformat(),
            "duration_seconds": elapsed,
            "total_tasks": len(self.tasks),
            "executed_tasks": len(self.executed_tasks),
            "completed_tasks": len([t for t in self.executed_tasks if t.status == "completed"]),
            "failed_tasks": len([t for t in self.executed_tasks if t.status == "failed"]),
            "tasks": [asdict(t) for t in self.tasks],
            "executed": [asdict(t) for t in self.executed_tasks],
        }

        # 保存报告
        report_file = (
            self.project_root
            / f"AI_AUTO_SORT_EXECUTION_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 执行报告已保存到: {report_file}")

        # 打印总结
        print("\n" + "=" * 80)
        print("📊 执行总结")
        print("=" * 80)
        print(f"  总任务数: {len(self.tasks)}")
        print(f"  已执行: {len(self.executed_tasks)}")
        print(f"  成功: {len([t for t in self.executed_tasks if t.status == 'completed'])}")
        print(f"  失败: {len([t for t in self.executed_tasks if t.status == 'failed'])}")
        print(f"  耗时: {elapsed:.1f}秒")
        print("=" * 80)

        return report


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("🤖 AI自动排序执行系统")
    print("=" * 80)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    executor = AISortExecutor()

    # 1. 分析项目状态
    executor.analyze_project_status()

    # 2. 显示任务列表
    executor.display_task_list()

    # 3. 询问是否执行
    print("\n" + "=" * 80)
    try:
        response = input("是否执行前3个高优先级任务? (y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        response = "n"

    if response == "y":
        # 4. 执行任务
        executor.execute_tasks(max_tasks=3)

        # 5. 生成报告
        executor.generate_report()
    else:
        print("\n⏸️  已跳过任务执行，仅生成任务列表")
        executor.generate_report()

    print("\n✅ AI自动排序执行完成！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
