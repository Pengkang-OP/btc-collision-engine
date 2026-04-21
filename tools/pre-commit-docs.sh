#!/bin/bash
# Pre-commit Hook: 文档质量检查
# 
# 安装方法:
#   cp tools/pre-commit-docs.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# 或者创建符号链接:
#   ln -s ../../tools/pre-commit-docs.sh .git/hooks/pre-commit

echo "🔍 检查文档质量..."

# 检查是否有文档被修改
changed_docs=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^docs/.*\.md$' || true)

if [ -z "$changed_docs" ]; then
    echo "✅ 没有文档变更，跳过检查"
    exit 0
fi

echo "📄 检测到文档变更:"
echo "$changed_docs"
echo ""

# 运行质量检查
echo "🔧 运行文档质量检查..."
python tools/check_document_quality.py

# 检查退出码
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 文档质量检查失败！"
    echo ""
    echo "请先修复以下问题："
    echo "1. 代码块语言类型标注"
    echo "2. 标题层级连续性"
    echo "3. 版本信息添加"
    echo "4. 断裂链接修复"
    echo ""
    echo "运行以下命令查看详细信息："
    echo "  python tools/check_document_quality.py"
    echo ""
    exit 1
fi

# 检查断裂链接
echo ""
echo "🔗 检查断裂链接..."
python tools/check_broken_links.py

if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  发现断裂链接，但不阻止提交"
    echo "建议修复：python tools/fix_broken_links.py"
fi

echo ""
echo "✅ 文档质量检查通过！"
exit 0
