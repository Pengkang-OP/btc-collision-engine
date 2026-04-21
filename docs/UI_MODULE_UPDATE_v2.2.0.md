# UI 模块更新说明 v2.2.0

## 更新概述

本次更新对 BTC 碰撞引擎的 UI 模块进行了全面升级，提升了用户体验、可配置性和功能完整性。

## 主要改进

### 1. GUI 配置文件增强 (`src/config/gui_config.py`)

#### 新增配置项

- **窗口配置**：
  - 默认窗口尺寸从 600x1000 调整为 800x1200
  - 最小窗口尺寸从 500x900 调整为 600x900
  - 窗口标题更新为 "BTC 碰撞引擎 v2.2.0"

- **布局配置** (新增)：
  - `main_padding_x/y`: 主容器边距 (15px)
  - `section_spacing`: 区块间距 (10px)
  - `alert_panel_ratio`: 告警面板默认占比 (30%)
  - `use_paned_window`: 支持可调整面板

- **交互配置** (新增)：
  - `stats_update_interval`: 统计更新间隔 (100ms)
  - `alert_update_interval`: 告警更新间隔 (5000ms)
  - `button_hover_effect`: 按钮悬停效果开关
  - `theme_switching`: 主题切换支持

- **主题配置** (新增)：
  - `current_theme`: 当前主题 (dark_catppuccin)
  - `available_themes`: 可用主题列表

#### 颜色配置升级

- 采用 Catppuccin Mocha 主题配色方案
- 新增 15+ 种颜色变量：
  - 表面色系列：surface1, surface2
  - 文字色系列：subtext0, subtext1
  - 强调色：blue, lavender, sapphire, sky, teal, green, yellow, peach, maroon, red, mauve, pink, flamingo, rosewater
  - 警告色：warning (peach)

#### 组件尺寸优化

- 目标地址输入框高度：5 → 6 行
- 范围参数输入框宽度：30 → 35
- 批处理大小输入框宽度：12 → 15
- 日志框高度：10 → 12 行
- 新增 GPU 设备下拉框配置

#### 间距调整

- 窗口内边距：10 → 15px
- 区块间距：5 → 10px
- 元素间距：5 → 8px (水平), 2 → 3px (垂直)

### 2. UI 工具函数增强 (`src/utils/ui_helpers.py`)

#### 新增函数

- `format_speed(speed)`: 智能速度格式化 (B/s, K/s, M/s, B/s)
- `format_elapsed_time(seconds)`: 运行时间格式化 (HH:MM:SS)
- `format_eta(seconds)`: 预计剩余时间格式化
- `truncate_address(address, max_length)`: 地址截断显示
- `validate_address_format(address)`: 地址格式验证 (P2PKH/P2SH/Bech32)
- `validate_hex_string(hex_str)`: 十六进制字符串验证
- `format_bytes(bytes_value)`: 字节数格式化 (B/KB/MB/GB/TB)
- `sanitize_display_text(text)`: 清理显示文本，移除不可见字符

#### 改进函数

- `format_number_with_commas()`: 现在支持 float 类型

### 3. 主 GUI 类增强 (`key_collision_gui.py`)

#### 状态栏 (新增)

- 底部状态栏显示实时信息：
  - 已检测数量
  - 当前速度
  - 运行时间
  - 版本信息 (v2.2.0)
- 自动更新：在进度回调时实时更新状态栏

#### 标题更新

- 主标题从 "BTC 私钥对撞工具 v1.0" 更新为 "v2.2.0"
- 文件头部版本号同步更新

#### 颜色类扩展

- 新增颜色属性：
  - SURFACE1, SURFACE2
  - SUBTEXT0, SUBTEXT1
  - BLUE, LAVENDER, SAPPHIRE
  - WARNING

### 4. 目标地址输入区改进

#### 输入验证

- 实时验证输入格式：
  - P2PKH 地址 (以 1 开头)
  - P2SH 地址 (以 3 开头)
  - Bech32 地址 (以 bc1 开头)
  - WIF 私钥 (以 5/K/L 开头)
  - 公钥 (66 或 130 位十六进制)

#### 用户体验

- 无效输入检测和提示
- 显示无效输入示例（最多 3 个）
- 确认对话框：是否继续解析有效输入
- 日志输出使用颜色标签（success/info）
- 地址显示使用截断函数（25 字符）

### 5. 统计显示组件优化

#### ETA 显示

- 使用 `format_eta()` 工具函数
- 智能单位转换：s → m → h → d
- 代码更简洁，逻辑更清晰

### 6. 日志/结果区增强

#### 新功能

- 新增"清空日志"按钮
- 新增警告日志级别（warning tag）
- 日志文本自动清理（移除不可见字符）
- 新增 `log_warning()` 方法

#### 按钮布局

- 导出日志按钮
- 清空日志按钮（新增）

### 7. 控制面板优化

#### GPU 设备选择

- 使用配置文件中的 GPU 下拉框宽度 (45)
- 字体配置从配置文件读取
- 更好的默认值和可配置性

### 8. GPU 组件集成准备

#### 组件导入

- GPUSelectorPanel: GPU 设备选择面板
- MultiGPUMonitorPanel: 多 GPU 监控面板
- 使用 try-except 优雅处理导入失败

#### 集成标志

- `GPU_COMPONENTS_AVAILABLE`: 标识 GPU 组件是否可用

## 技术改进

### 代码质量

- 使用工具函数替代内联代码
- 配置驱动设计，易于定制
- 更好的错误处理和用户提示
- 文本清理和验证

### 可维护性

- 配置集中管理
- 颜色主题化
- 函数职责单一
- 注释完善

### 用户体验

- 实时状态反馈
- 输入验证和提示
- 颜色编码的日志输出
- 更大的默认窗口尺寸
- 更好的间距和布局

## 向后兼容性

所有更新保持向后兼容：

- 旧版配置文件仍可正常工作
- 新增配置项使用默认值
- 颜色配置兼容旧版键名
- 工具函数签名向后兼容

## 使用建议

### 主题定制

在 `src/config/gui_config.py` 中修改 `COLOR_CONFIG` 可自定义主题。

### 窗口尺寸

在 `src/config/gui_config.py` 中修改 `WINDOW_CONFIG` 可调整窗口大小。

### 组件尺寸

在 `src/config/gui_config.py` 中修改 `COMPONENT_CONFIG` 可调整各组件尺寸。

## 已知问题

无

## 未来计划

1. 支持多主题切换
2. 添加 GPU 组件到主界面
3. 支持自定义布局
4. 添加快捷键支持
5. 改进移动端适配

## 更新日志

### v2.2.0 (2026-04-22)

- 全面升级 GUI 配置文件
- 增强 UI 工具函数
- 添加状态栏
- 改进输入验证
- 优化日志功能
- 整合 GPU 组件准备

---

**作者**: BTC Project  
**版本**: v2.2.0  
**更新日期**: 2026-04-22
