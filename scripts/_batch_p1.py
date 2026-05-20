"""批量应用P1-1/P1-2/P1-3/P2-3到data_logger.py"""
import os

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src", "monitoring", "data_logger.py")
with open(path, encoding="utf-8") as f:
    content = f.read()

changes = 0

# === P1-2: GPU指标集成 - 扩展record_performance_data参数 ===
old1 = (
    "    def record_performance_data(\n"
    "        self,\n"
    "        speed: float,\n"
    "        total_checked: int,\n"
    "        matches_found: int,\n"
    "        cpu_usage: float = 0.0,\n"
    "        memory_usage: float = 0.0,\n"
    "        thread_count: int = 0,\n"
    "    ) -> None:\n"
    "        \"\"\"\n"
    "        记录性能数据（添加数据验证）\n"
    "\n"
    "        Args:\n"
    "            speed: 每秒检测速率\n"
    "            total_checked: 已检测总数\n"
    "            matches_found: 找到的匹配数\n"
    "            cpu_usage: CPU使用率\n"
    "            memory_usage: 内存使用率(MB)\n"
    "            thread_count: 线程数\n"
    "        \"\"\""
)
if old1 in content:
    new1 = (
        "    def record_performance_data(\n"
        "        self,\n"
        "        speed: float,\n"
        "        total_checked: int,\n"
        "        matches_found: int,\n"
        "        cpu_usage: float = 0.0,\n"
        "        memory_usage: float = 0.0,\n"
        "        thread_count: int = 0,\n"
        "        # P1-2: GPU性能指标\n"
        "        gpu_temperature: float = 0.0,\n"
        "        gpu_memory_usage: float = 0.0,\n"
        "        gpu_utilization: float = 0.0,\n"
        "    ) -> None:\n"
        "        \"\"\"\n"
        "        记录性能数据（添加数据验证）\n"
        "\n"
        "        Args:\n"
        "            speed: 每秒检测速率\n"
        "            total_checked: 已检测总数\n"
        "            matches_found: 找到的匹配数\n"
        "            cpu_usage: CPU使用率\n"
        "            memory_usage: 内存使用率(MB)\n"
        "            thread_count: 线程数\n"
        "            gpu_temperature: GPU温度(°C) (P1-2)\n"
        "            gpu_memory_usage: GPU显存使用(MB) (P1-2)\n"
        "            gpu_utilization: GPU利用率(%) (P1-2)\n"
        "        \"\"\""
    )
    content = content.replace(old1, new1, 1)
    changes += 1
    print("P1-2: record_performance_data 签名已扩展（GPU参数）")
else:
    print("P1-2: record_performance_data 签名未找到")

# P1-2: Add GPU data validation and inclusion in perf_data
old1b = (
        "        if not isinstance(thread_count, int) or thread_count < 0:\n"
        "            self.logger.warning(f\"无效的thread_count值: {thread_count}，使用0代替\")\n"
        "            thread_count = 0\n"
        "\n"
        "        # 在锁内更新数据"
)
if old1b in content:
    new1b = (
        "        if not isinstance(thread_count, int) or thread_count < 0:\n"
        "            self.logger.warning(f\"无效的thread_count值: {thread_count}，使用0代替\")\n"
        "            thread_count = 0\n"
        "\n"
        "        # P1-2: GPU数据验证\n"
        "        if not isinstance(gpu_temperature, (int, float)) or gpu_temperature < 0:\n"
        "            gpu_temperature = 0.0\n"
        "        if not isinstance(gpu_memory_usage, (int, float)) or gpu_memory_usage < 0:\n"
        "            gpu_memory_usage = 0.0\n"
        "        if not isinstance(gpu_utilization, (int, float)) or gpu_utilization < 0:\n"
        "            gpu_utilization = 0.0\n"
        "\n"
        "        # 在锁内更新数据"
    )
    content = content.replace(old1b, new1b, 1)
    changes += 1
    print("P1-2: GPU数据验证已添加")
else:
    print("P1-2: GPU数据验证插入点未找到")

# P1-2: Add GPU fields to perf_data dict
old1c = (
        "            perf_data = {\n"
        "                \"timestamp\": timestamp,\n"
        "                \"datetime\": datetime.fromtimestamp(timestamp).isoformat(),\n"
        "                \"speed\": float(speed),\n"
        "                \"total_checked\": int(total_checked),\n"
        "                \"matches_found\": int(matches_found),\n"
        "                \"cpu_usage\": float(cpu_usage),\n"
        "                \"memory_usage\": float(memory_usage),\n"
        "                \"thread_count\": int(thread_count),\n"
        "                \"avg_speed\": statistics.mean(self._speed_samples) if self._speed_samples else 0,\n"
        "            }"
)
if old1c in content:
    new1c = (
        "            perf_data = {\n"
        "                \"timestamp\": timestamp,\n"
        "                \"datetime\": datetime.fromtimestamp(timestamp).isoformat(),\n"
        "                \"speed\": float(speed),\n"
        "                \"total_checked\": int(total_checked),\n"
        "                \"matches_found\": int(matches_found),\n"
        "                \"cpu_usage\": float(cpu_usage),\n"
        "                \"memory_usage\": float(memory_usage),\n"
        "                \"thread_count\": int(thread_count),\n"
        "                # P1-2: GPU性能指标\n"
        "                \"gpu_temperature\": float(gpu_temperature),\n"
        "                \"gpu_memory_usage\": float(gpu_memory_usage),\n"
        "                \"gpu_utilization\": float(gpu_utilization),\n"
        "                \"avg_speed\": statistics.mean(self._speed_samples) if self._speed_samples else 0,\n"
        "            }"
    )
    content = content.replace(old1c, new1c, 1)
    changes += 1
    print("P1-2: perf_data字典已包含GPU字段")
else:
    print("P1-2: perf_data字典未找到")

# P1-2: Update CSV format comment
old1d = (
        "                        \"# 格式: timestamp,speed,total_checked,matches,cpu_usage,memory_usage,threads\\n\"  # noqa: E501"
)
if old1d in content:
    new1d = (
        "                        \"# 格式: timestamp,speed,total_checked,matches,cpu_usage,memory_usage,threads,gpu_temp,gpu_mem,gpu_util\\n\"  # noqa: E501"
    )
    content = content.replace(old1d, new1d, 1)
    changes += 1
    print("P1-2: CSV格式注释已更新")
else:
    print("P1-2: CSV格式注释未找到")

# P1-2: Update CSV line format
old1e = (
        "            csv_line = f\"{timestamp},{speed},{total_checked},{matches_found},{cpu_usage},{memory_usage},{thread_count}\\n\"  # noqa: E501"
)
if old1e in content:
    new1e = (
        "            # P1-2: 包含GPU指标\n"
        "            csv_line = f\"{timestamp},{speed},{total_checked},{matches_found},{cpu_usage},{memory_usage},{thread_count},{gpu_temperature},{gpu_memory_usage},{gpu_utilization}\\n\"  # noqa: E501"
    )
    content = content.replace(old1e, new1e, 1)
    changes += 1
    print("P1-2: CSV写入已包含GPU字段")
else:
    print("P1-2: CSV写入未找到")

# === P1-1: 碰撞匹配详情记录 - 在record_engine_data之后添加record_match_event ===
old2 = (
        "            self._current_data[\"engine\"] = engine_data\n"
        "            self.logger.debug(f\"引擎数据: 模式={mode}, 目标数={target_count}, 运行中={is_running}\")\n"
        "\n"
        "    def record_error("
)
if old2 in content:
    new2 = (
        "            self._current_data[\"engine\"] = engine_data\n"
        "            self.logger.debug(f\"引擎数据: 模式={mode}, 目标数={target_count}, 运行中={is_running}\")\n"
        "\n"
        "    # P2-3: 在engine_data中记录去重效率\n"
        "    def set_dedup_stats(self, skipped: int = 0, hit_rate: float = 0.0) -> None:\n"
        "        \"\"\"P2-3: 设置去重/过滤统计指标\n"
        "\n"
        "        Args:\n"
        "            skipped: 去重跳过的密钥数量\n"
        "            hit_rate: Bloom Filter命中率 (0.0-1.0)\n"
        "        \"\"\"\n"
        "        with self._lock:\n"
        "            if \"engine\" in self._current_data:\n"
        "                self._current_data[\"engine\"][\"dedup_skipped\"] = int(skipped)\n"
        "                self._current_data[\"engine\"][\"bloom_hit_rate\"] = float(hit_rate)\n"
        "\n"
        "    def record_match_event(\n"
        "        self,\n"
        "        matched_address: str,\n"
        "        collision_mode: str = \"\",\n"
        "        match_type: str = \"address\",\n"
        "    ) -> None:\n"
        "        \"\"\"P1-1: 记录碰撞匹配详情\n"
        "\n"
        "        记录脱敏后的匹配地址和碰撞时间，不存储私钥原文。\n"
        "        私钥过滤由SecurityLogFilter在日志层防护。\n"
        "\n"
        "        Args:\n"
        "            matched_address: 匹配到的BTC地址（仅地址，不含私钥）\n"
        "            collision_mode: 碰撞模式(\"random\"/\"range_scan\"/\"brute_force\")\n"
        "            match_type: 匹配类型(\"address\"/\"hash160\")\n"
        "        \"\"\"\n"
        "        # 安全脱敏：只保留地址前6位+后4位用于日志审计\n"
        "        if len(matched_address) > 10:\n"
        "            safe_addr = matched_address[:6] + \"...\" + matched_address[-4:]\n"
        "        else:\n"
        "            safe_addr = matched_address[:3] + \"...\"\n"
        "\n"
        "        with self._lock:\n"
        "            match_record = {\n"
        "                \"timestamp\": time.time(),\n"
        "                \"datetime\": datetime.now().isoformat(),\n"
        "                \"matched_address_masked\": safe_addr,\n"
        "                \"collision_mode\": collision_mode,\n"
        "                \"match_type\": match_type,\n"
        "            }\n"
        "\n"
        "            # 追加到current_data\n"
        "            if \"matches\" not in self._current_data:\n"
        "                self._current_data[\"matches\"] = []\n"
        "            self._current_data[\"matches\"].append(match_record)\n"
        "\n"
        "            # 限制匹配记录数\n"
        "            if len(self._current_data[\"matches\"]) > 100:\n"
        "                self._current_data[\"matches\"] = self._current_data[\"matches\"][-100:]\n"
        "\n"
        "            self._matches_found += 1\n"
        "\n"
        "        self.logger.info(\n"
        "            f\"碰撞匹配事件: 地址={safe_addr}, 模式={collision_mode}, 类型={match_type}\"\n"
        "        )\n"
        "\n"
        "    def record_error("
    )
    content = content.replace(old2, new2, 1)
    changes += 1
    print("P1-1: record_match_event 方法已添加")
    print("P2-3: set_dedup_stats 方法已添加")
else:
    print("P1-1: record_engine_data之后插入点未找到")

# === P1-3: _analyze_trends 升级为线性回归 ===
old3 = (
        "    def _analyze_trends(self, data: list[dict[str, Any]]) -> dict[str, Any]:\n"
        "        \"\"\"分析数据趋势\"\"\"\n"
        "        if len(data) < 2:\n"
        "            return {\"message\": \"数据点不足，无法分析趋势\"}\n"
        "\n"
        "        # 分析速度趋势\n"
        "        speeds = [d.get(\"speed\", 0) for d in data]\n"
        "        cpu_usages = [d.get(\"cpu_usage\", 0) for d in data]\n"
        "        memory_usages = [d.get(\"memory_usage\", 0) for d in data]\n"
        "\n"
        "        def calculate_trend(values: list[float]) -> str:\n"
        "            if len(values) < 2:\n"
        "                return \"stable\"\n"
        "            first_half_avg = statistics.mean(values[: len(values) // 2])\n"
        "            second_half_avg = statistics.mean(values[len(values) // 2 :])\n"
        "\n"
        "            if second_half_avg > first_half_avg * 1.05:  # 5% 增长阈值\n"
        "                return \"increasing\"\n"
        "            elif second_half_avg < first_half_avg * 0.95:  # 5% 下降阈值\n"
        "                return \"decreasing\"\n"
        "            else:\n"
        "                return \"stable\""
)
if old3 in content:
    new3 = (
        "    def _analyze_trends(self, data: list[dict[str, Any]]) -> dict[str, Any]:\n"
        "        \"\"\"分析数据趋势\n"
        "\n"
        "        P1-3: 使用线性回归替代简单的前半/后半均值比较，\n"
        "        提高趋势判断的准确性和灵敏度（阈值2%）。\n"
        "        \"\"\"\n"
        "        if len(data) < 2:\n"
        "            return {\"message\": \"数据点不足，无法分析趋势\"}\n"
        "\n"
        "        # 分析速度趋势\n"
        "        speeds = [d.get(\"speed\", 0) for d in data]\n"
        "        cpu_usages = [d.get(\"cpu_usage\", 0) for d in data]\n"
        "        memory_usages = [d.get(\"memory_usage\", 0) for d in data]\n"
        "\n"
        "        # P1-3: 使用线性回归计算趋势\n"
        "        def calculate_trend(values: list[float]) -> str:\n"
        "            if len(values) < 3:\n"
        "                return \"stable\"\n"
        "            try:\n"
        "                n = len(values)\n"
        "                x_sum = sum(range(n))\n"
        "                y_sum = sum(values)\n"
        "                xy_sum = sum(i * v for i, v in enumerate(values))\n"
        "                x2_sum = sum(i * i for i in range(n))\n"
        "                denominator = n * x2_sum - x_sum * x_sum\n"
        "                if denominator == 0:\n"
        "                    return \"stable\"\n"
        "                slope = (n * xy_sum - x_sum * y_sum) / denominator\n"
        "                avg = y_sum / n if n > 0 else 0\n"
        "                if avg == 0:\n"
        "                    return \"stable\"\n"
        "                normalized_slope = slope / abs(avg)\n"
        "                threshold = 0.02  # 2%阈值\n"
        "                if normalized_slope > threshold:\n"
        "                    return \"increasing\"\n"
        "                elif normalized_slope < -threshold:\n"
        "                    return \"decreasing\"\n"
        "                else:\n"
        "                    return \"stable\"\n"
        "            except Exception:\n"
        "                # 降级：前半/后半均值比较\n"
        "                if len(values) < 2:\n"
        "                    return \"stable\"\n"
        "                first_half_avg = statistics.mean(values[: len(values) // 2])\n"
        "                second_half_avg = statistics.mean(values[len(values) // 2 :])\n"
        "                if second_half_avg > first_half_avg * 1.05:\n"
        "                    return \"increasing\"\n"
        "                elif second_half_avg < first_half_avg * 0.95:\n"
        "                    return \"decreasing\"\n"
        "                else:\n"
        "                    return \"stable\""
    )
    content = content.replace(old3, new3, 1)
    changes += 1
    print("P1-3: _analyze_trends 已升级为线性回归")
else:
    print("P1-3: _analyze_trends 未找到")

# P2-3: Update CSV format for rotation header
old4 = (
        "                    f.write(\n"
        "                        \"# 格式: timestamp,speed,total_checked,matches,cpu_usage,memory_usage,threads\\n\"  # noqa: E501\n"
        "                    )"
)
if old4 in content:
    new4 = (
        "                    f.write(\n"
        "                        \"# 格式: timestamp,speed,total_checked,matches,cpu_usage,memory_usage,threads,gpu_temp,gpu_mem,gpu_util\\n\"  # noqa: E501\n"
        "                    )"
    )
    content = content.replace(old4, new4, 1)
    changes += 1
    print("P1-2: 轮转时CSV格式注释已更新")
else:
    print("P1-2: 轮转CSV格式注释未找到")

# Write
with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n总计: {changes} 处修改")
