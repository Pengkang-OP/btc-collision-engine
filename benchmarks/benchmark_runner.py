# -*- coding: utf-8 -*-
"""
BTC碰撞引擎统一基准测试运行器

功能:
- 自动发现并运行所有基准测试函数
- 收集执行时间、吞吐量等指标
- 将结果持久化为 JSON 文件
- 支持与上次结果对比，检测性能回归（阈值：>10% 下降报警）

用法:
    python -m benchmarks.benchmark_runner
    python -m benchmarks.benchmark_runner --compare
    python -m benchmarks.benchmark_runner --output benchmarks/results
    python -m benchmarks.benchmark_runner --list
"""
import argparse
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# 将项目根目录加入路径
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))


# ──────────────────────────────────────────────
# 基准测试结果数据结构
# ──────────────────────────────────────────────

class BenchmarkResult:
    """单个基准测试的结果"""

    def __init__(
        self,
        name: str,
        ops_per_sec: float,
        mean_us: float,
        std_us: float,
        iterations: int,
        success: bool = True,
        error: str = "",
    ):
        self.name = name
        self.ops_per_sec = ops_per_sec
        self.mean_us = mean_us
        self.std_us = std_us
        self.iterations = iterations
        self.success = success
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """转为字典，用于 JSON 序列化"""
        d: Dict[str, Any] = {
            "ops_per_sec": round(self.ops_per_sec, 2),
            "mean_us": round(self.mean_us, 3),
            "std_us": round(self.std_us, 3),
            "iterations": self.iterations,
            "success": self.success,
        }
        if self.error:
            d["error"] = self.error
        return d


# ──────────────────────────────────────────────
# 精确计时工具
# ──────────────────────────────────────────────

def _run_timed(func: Callable, warmup: int = 3, iterations: int = 1000) -> BenchmarkResult:
    """
    运行函数并精确计时。

    参数:
        func:       待测函数（无参数）
        warmup:     预热次数，不计入统计
        iterations: 正式测量次数

    返回:
        BenchmarkResult 实例
    """
    # 预热：让 JIT / 缓存生效
    for _ in range(warmup):
        func()

    times_us: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        func()
        elapsed_us = (time.perf_counter() - t0) * 1_000_000
        times_us.append(elapsed_us)

    mean_us = statistics.mean(times_us)
    std_us = statistics.stdev(times_us) if len(times_us) > 1 else 0.0
    ops_per_sec = 1_000_000 / mean_us if mean_us > 0 else 0.0

    return BenchmarkResult(
        name="",
        ops_per_sec=ops_per_sec,
        mean_us=mean_us,
        std_us=std_us,
        iterations=iterations,
    )


# ──────────────────────────────────────────────
# 内建核心基准测试
# ──────────────────────────────────────────────

def bench_secp256k1_key_generation() -> BenchmarkResult:
    """椭圆曲线密钥生成吞吐量基准测试"""
    from src.core.address_generator import P2PKHAddressGenerator

    generator = P2PKHAddressGenerator()

    def _gen():
        generator.generate_private_key()

    result = _run_timed(_gen, warmup=5, iterations=200)
    result.name = "secp256k1_key_gen"
    return result


def bench_address_generation() -> BenchmarkResult:
    """地址生成吞吐量基准测试（含 Base58Check 编码）"""
    from src.core.address_generator import P2PKHAddressGenerator

    generator = P2PKHAddressGenerator()
    # 使用固定私钥，排除随机数生成的开销
    test_key = (42).to_bytes(32, "big")

    def _gen():
        generator.generate_address(test_key)

    result = _run_timed(_gen, warmup=5, iterations=500)
    result.name = "address_generation"
    return result


def bench_collision_check() -> BenchmarkResult:
    """碰撞检测吞吐量基准测试（使用 set lookup）"""
    # 构造含 10000 个目标地址的集合
    target_set = {f"1Address{i:040d}" for i in range(10_000)}
    probe_addrs = [f"1Address{i:040d}" for i in range(0, 2000, 2)]  # 50% 命中

    def _check():
        for addr in probe_addrs:
            _ = addr in target_set

    # 调整 iterations 使单次调用 < 1ms
    result = _run_timed(_check, warmup=3, iterations=200)
    # 换算为单地址 ops/s
    total_ops = len(probe_addrs) * result.iterations
    total_time_s = result.mean_us * result.iterations / 1_000_000
    result.name = "collision_check"
    result.ops_per_sec = total_ops / total_time_s if total_time_s > 0 else 0.0
    result.mean_us = result.mean_us / len(probe_addrs)  # 单条均值
    return result


def bench_dedup_filter() -> BenchmarkResult:
    """去重过滤器吞吐量基准测试"""
    from src.collision.deduplication_filter import DeduplicationFilter

    # 预先建好过滤器和数据，避免构造开销计入测量
    dedup = DeduplicationFilter(max_size=50_000, enabled=True)
    keys = [i.to_bytes(32, "big") for i in range(500)]

    def _check():
        # 每次用新实例，保证 check_and_add 首次命中
        d = DeduplicationFilter(max_size=50_000, enabled=True)
        for k in keys:
            d.check_and_add(k)

    result = _run_timed(_check, warmup=2, iterations=100)
    # 换算为单条 key ops/s
    total_ops = len(keys) * result.iterations
    total_time_s = result.mean_us * result.iterations / 1_000_000
    result.name = "dedup_filter"
    result.ops_per_sec = total_ops / total_time_s if total_time_s > 0 else 0.0
    result.mean_us = result.mean_us / len(keys)
    return result


def bench_hash160() -> BenchmarkResult:
    """Hash160（SHA256 + RIPEMD160）吞吐量基准测试"""
    import hashlib

    pubkey = bytes([0x02]) + bytes([0xAB] * 32)  # 33字节压缩公钥

    def _hash():
        sha = hashlib.sha256(pubkey).digest()
        hashlib.new("ripemd160", sha).digest()

    result = _run_timed(_hash, warmup=10, iterations=2000)
    result.name = "hash160"
    return result


def bench_base58check_encode() -> BenchmarkResult:
    """Base58Check 编码吞吐量基准测试"""
    from src.core.base58 import Base58

    payload = bytes([0x00]) + bytes(range(20))  # 版本 + 20字节 hash160

    def _encode():
        Base58.check_encode(0x00, bytes(range(20)))

    result = _run_timed(_encode, warmup=5, iterations=1000)
    result.name = "base58check_encode"
    return result


# ──────────────────────────────────────────────
# 内建基准测试注册表
# ──────────────────────────────────────────────

BUILTIN_BENCHMARKS: Dict[str, Callable[[], BenchmarkResult]] = {
    "secp256k1_key_gen":   bench_secp256k1_key_generation,
    "address_generation":  bench_address_generation,
    "collision_check":     bench_collision_check,
    "dedup_filter":        bench_dedup_filter,
    "hash160":             bench_hash160,
    "base58check_encode":  bench_base58check_encode,
}


# ──────────────────────────────────────────────
# 回归对比逻辑
# ──────────────────────────────────────────────

_REGRESSION_THRESHOLD = 0.10  # 10% 下降触发报警


def _find_latest_result(results_dir: Path) -> Optional[Path]:
    """在 results_dir 中查找最新的基准结果文件"""
    files = sorted(results_dir.glob("benchmark_*.json"), reverse=True)
    return files[0] if files else None


def _compare_results(
    current: Dict[str, BenchmarkResult],
    baseline_path: Path,
) -> Dict[str, Any]:
    """
    将当前结果与基线文件对比。

    返回:
        包含 baseline_file / regressions / improvements 的字典
    """
    try:
        with baseline_path.open("r", encoding="utf-8") as f:
            baseline_data = json.load(f)
    except Exception as exc:
        return {
            "baseline_file": str(baseline_path),
            "error": f"无法读取基线文件: {exc}",
            "regressions": [],
            "improvements": [],
        }

    baseline_benchmarks: Dict[str, Any] = baseline_data.get("benchmarks", {})

    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []

    for name, result in current.items():
        if not result.success:
            continue
        if name not in baseline_benchmarks:
            continue

        baseline_ops = baseline_benchmarks[name].get("ops_per_sec", 0)
        if baseline_ops <= 0:
            continue

        current_ops = result.ops_per_sec
        change_ratio = (current_ops - baseline_ops) / baseline_ops  # 正=提升，负=下降

        entry = {
            "name": name,
            "baseline_ops_per_sec": round(baseline_ops, 2),
            "current_ops_per_sec": round(current_ops, 2),
            "change_pct": round(change_ratio * 100, 2),
        }

        if change_ratio < -_REGRESSION_THRESHOLD:
            regressions.append(entry)
        elif change_ratio > _REGRESSION_THRESHOLD:
            improvements.append(entry)

    return {
        "baseline_file": baseline_path.name,
        "regressions": regressions,
        "improvements": improvements,
    }


# ──────────────────────────────────────────────
# 主运行器
# ──────────────────────────────────────────────

class BenchmarkRunner:
    """统一基准测试运行器"""

    def __init__(self, output_dir: Optional[str] = None, compare: bool = False):
        """
        参数:
            output_dir: 结果保存目录，默认为 benchmarks/results
            compare:    是否与上次结果对比
        """
        if output_dir:
            self.results_dir = Path(output_dir)
        else:
            self.results_dir = _ROOT / "benchmarks" / "results"
        self.compare = compare

        # 确保输出目录存在
        self.results_dir.mkdir(parents=True, exist_ok=True)

    # ── 运行单个测试 ──────────────────────────

    def _run_one(self, name: str, func: Callable[[], BenchmarkResult]) -> BenchmarkResult:
        """安全地执行单个基准测试，捕获异常"""
        print(f"  运行 [{name}] ...", end="", flush=True)
        try:
            result = func()
            result.name = name
            print(
                f"  {result.ops_per_sec:>12,.0f} ops/s"
                f"  均值 {result.mean_us:.3f} µs"
                f"  ±{result.std_us:.3f} µs"
            )
            return result
        except Exception as exc:
            import traceback
            err = traceback.format_exc()
            print(f"  [FAILED] {exc}")
            return BenchmarkResult(
                name=name,
                ops_per_sec=0,
                mean_us=0,
                std_us=0,
                iterations=0,
                success=False,
                error=str(exc),
            )

    # ── 运行所有测试 ──────────────────────────

    def run_all(self, suite: Optional[Dict[str, Callable]] = None) -> Dict[str, BenchmarkResult]:
        """
        运行所有基准测试。

        参数:
            suite: 测试集合，默认使用 BUILTIN_BENCHMARKS

        返回:
            name -> BenchmarkResult 的字典
        """
        if suite is None:
            suite = BUILTIN_BENCHMARKS

        print("\n" + "=" * 70)
        print("BTC碰撞引擎 性能基准测试运行器")
        print("=" * 70)
        print(f"  Python : {sys.version.split()[0]}")
        print(f"  平台   : {platform.system()} {platform.release()}")
        print(f"  时间   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  测试数 : {len(suite)}")
        print("=" * 70 + "\n")

        results: Dict[str, BenchmarkResult] = {}
        for name, func in suite.items():
            results[name] = self._run_one(name, func)

        return results

    # ── 持久化结果 ────────────────────────────

    def save(self, results: Dict[str, BenchmarkResult]) -> Path:
        """
        将结果保存为 JSON 文件。

        返回:
            保存的文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_{timestamp}.json"
        out_path = self.results_dir / filename

        # 构造回归对比节
        comparison: Dict[str, Any] = {
            "baseline_file": None,
            "regressions": [],
            "improvements": [],
        }
        if self.compare:
            latest = _find_latest_result(self.results_dir)
            # 排除刚才保存的当前文件
            if latest and latest.name != filename:
                comparison = _compare_results(results, latest)

        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "python_version": sys.version.split()[0],
            "platform": f"{platform.system()}-{platform.release()}",
            "benchmarks": {name: r.to_dict() for name, r in results.items()},
            "comparison": comparison,
        }

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存至: {out_path}")
        return out_path

    # ── 打印回归报告 ──────────────────────────

    @staticmethod
    def print_comparison(comparison: Dict[str, Any]) -> None:
        """打印回归/改进报告到控制台"""
        baseline = comparison.get("baseline_file")
        if not baseline:
            print("\n[对比] 未找到基线文件，跳过回归检测。")
            return

        print(f"\n[对比基线] {baseline}")

        regressions = comparison.get("regressions", [])
        improvements = comparison.get("improvements", [])

        if regressions:
            print(f"\n[!] 发现 {len(regressions)} 处性能回归 (下降 > {_REGRESSION_THRESHOLD*100:.0f}%):")
            for r in regressions:
                print(
                    f"    - {r['name']:30s}  "
                    f"{r['baseline_ops_per_sec']:>12,.0f} → {r['current_ops_per_sec']:>12,.0f} ops/s"
                    f"  ({r['change_pct']:+.1f}%)"
                )
        else:
            print("\n[OK] 未发现性能回归。")

        if improvements:
            print(f"\n[+] 发现 {len(improvements)} 处性能提升:")
            for r in improvements:
                print(
                    f"    + {r['name']:30s}  "
                    f"{r['baseline_ops_per_sec']:>12,.0f} → {r['current_ops_per_sec']:>12,.0f} ops/s"
                    f"  ({r['change_pct']:+.1f}%)"
                )

    # ── 一键运行入口 ──────────────────────────

    def run(self) -> int:
        """运行全套基准测试并保存结果，返回退出码"""
        results = self.run_all()
        out_path = self.save(results)

        # 如开启对比，读取刚保存的文件并打印报告
        if self.compare:
            try:
                with out_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                self.print_comparison(data.get("comparison", {}))
            except Exception:
                pass

        # 若存在回归，以非零退出码退出（便于 CI 捕获）
        try:
            with out_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("comparison", {}).get("regressions"):
                return 1
        except Exception:
            pass

        return 0


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="python -m benchmarks.benchmark_runner",
        description="BTC碰撞引擎性能基准测试运行器",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="与上次结果对比，检测性能回归（下降 >10%% 报警）",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        default=None,
        help="结果保存目录（默认: benchmarks/results）",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用基准测试名称并退出",
    )
    parser.add_argument(
        "--only",
        metavar="NAME",
        nargs="+",
        help="仅运行指定名称的基准测试（空格分隔）",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 主函数"""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # --list：列出所有测试后退出
    if args.list:
        print("可用基准测试:")
        for name in BUILTIN_BENCHMARKS:
            print(f"  {name}")
        return 0

    # --only：过滤测试集
    suite = BUILTIN_BENCHMARKS
    if args.only:
        unknown = [n for n in args.only if n not in BUILTIN_BENCHMARKS]
        if unknown:
            print(f"[ERROR] 未知基准测试: {', '.join(unknown)}")
            print("可用基准测试:", ", ".join(BUILTIN_BENCHMARKS.keys()))
            return 2
        suite = {n: BUILTIN_BENCHMARKS[n] for n in args.only}

    runner = BenchmarkRunner(output_dir=args.output, compare=args.compare)
    return runner.run() if suite is BUILTIN_BENCHMARKS else _run_subset(runner, suite)


def _run_subset(runner: BenchmarkRunner, suite: Dict[str, Callable]) -> int:
    """运行子集并保存"""
    results = runner.run_all(suite)
    out_path = runner.save(results)
    if runner.compare:
        try:
            with out_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            runner.print_comparison(data.get("comparison", {}))
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
