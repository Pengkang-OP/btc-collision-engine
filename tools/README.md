# 工具脚本目录

本目录存放项目开发和维护过程中使用的辅助工具脚本。

## 🚨 Windows UTF-8 编码问题

**问题**：在Windows系统中，中文和emoji字符可能显示为乱码，特别是使用管道时。

**解决方案**：

1. **直接运行**（推荐）：
   ```powershell
   python tools/check_document_quality.py
   ```

2. **使用管道**：
   ```powershell
   .\tools\run_utf8.ps1 -Script "python tools/check_document_quality.py" | Select-Object -First 20
   ```

3. **批处理环境**：
   ```cmd
   tools\run_utf8.bat python tools\check_document_quality.py
   ```

**详细文档**：
- [UTF8编码完整指南](UTF8_ENCODING_GUIDE.md)
- [UTF-8快速参考](UTF8_QUICK_REFERENCE.md)

## 工具分类

### 🔧 数据工具
- 地址提取和验证
- 密钥生成和转换
- 数据格式化工具

### 📊 分析工具
- 性能基准测试
- 日志分析工具
- 数据可视化工具

### 🛠️ 开发工具
- 代码质量检查
- 文档链接验证
- 配置管理工具

### 🚀 部署工具
- SSH配置脚本
- 远程推送脚本
- 环境设置工具

## 使用规范

1. **脚本命名**：使用小写字母和下划线，如 `extract_addresses.py`
2. **文档要求**：每个脚本应包含使用说明和示例
3. **依赖管理**：如需要额外依赖，在脚本开头注明
4. **清理原则**：不再使用的工具应及时删除

## 现有工具

### 📝 文档工具
- **check_document_quality.py** - 文档质量检查
- **add_version_info.py** - 批量添加版本信息
- **add_table_of_contents.py** - 自动添加目录
- **check_broken_links.py** - 断裂链接检查
- **fix_heading_levels.py** - 标题层级修复
- **fix_code_blocks.py** - 代码块语言类型修复

### 🔍 系统工具
- **audit_resource_cleanup.py** - 资源清理审计
- **check_pr_status.py** - GitHub PR状态检查
- **cleanup_monitoring_data.py** - 监控数据清理

### 🌐 UTF-8编码支持
- **run_utf8.ps1** - PowerShell UTF-8包装器（支持管道）
- **run_utf8.bat** - CMD UTF-8包装器（支持管道）

> 💡 提示：所有文档工具已内置UTF-8编码支持，直接运行即可正常显示中文和emoji。

## 相关文档

- 项目清理脚本：`../cleanup.py`
- 归档文档：`../docs/archive/`
- 示例代码：`../examples/`

## 维护记录

- **2026-04-21**：修复Windows UTF-8编码问题，添加包装器脚本和文档
  - 修复8个Python脚本的UTF-8编码支持
  - 创建run_utf8.ps1和run_utf8.bat包装器
  - 编写UTF8_ENCODING_GUIDE.md和UTF8_QUICK_REFERENCE.md
  - 完全解决PowerShell管道乱码问题
- **2026-04-20**：创建tools目录，整理项目结构
