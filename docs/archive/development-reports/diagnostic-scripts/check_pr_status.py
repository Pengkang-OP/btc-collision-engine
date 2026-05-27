"""检查GitHub PR状态"""
import sys
import io
import urllib.request
import json

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except (OSError, AttributeError):
        pass
    
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

url = "https://api.github.com/repos/pengkang2017/btc-collision-engine/pulls?state=all"

try:
    with urllib.request.urlopen(url) as response:
        prs = json.loads(response.read().decode())
        
        print(f"📊 总PR数: {len(prs)}\n")
        
        if prs:
            for pr in prs[:5]:  # 显示最近5个
                print(f"{'='*60}")
                print(f"PR #{pr['number']}: {pr['title']}")
                print(f"状态: {pr['state']}")
                print(f"创建时间: {pr['created_at']}")
                print(f"URL: {pr['html_url']}")
                print(f"{'='*60}\n")
        else:
            print("暂无PR")
            
except Exception as e:
    print(f"❌ 查询失败: {e}")
    print("\n请手动访问以下URL查看PR状态:")
    print("https://github.com/pengkang2017/btc-collision-engine/pulls")
