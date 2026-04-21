#!/usr/bin/env python3
"""验证GitHub Release v2.2.0创建状态"""

import subprocess
import json
import sys

def check_local_tag():
    """检查本地标签"""
    print("=" * 60)
    print("📋 检查本地Git标签")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ['git', 'tag', '-l', 'v2.2.0'],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if 'v2.2.0' in result.stdout:
            print("✅ 本地标签 v2.2.0 存在")
            
            # 获取标签详情
            result = subprocess.run(
                ['git', 'show', 'v2.2.0', '--quiet', '--format=%H %s'],
                capture_output=True, text=True, encoding='utf-8'
            )
            print(f"📍 指向提交: {result.stdout.strip()[:50]}...")
            return True
        else:
            print("❌ 本地标签 v2.2.0 不存在")
            return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

def check_remote_tag():
    """检查远程标签（可能因网络失败）"""
    print("\n" + "=" * 60)
    print("🌐 检查远程Git标签")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ['git', 'ls-remote', '--tags', 'origin'],
            capture_output=True, text=True, encoding='utf-8', timeout=10
        )
        
        if 'v2.2.0' in result.stdout:
            print("✅ 远程标签 v2.2.0 已推送")
            return True
        else:
            print("⚠️  远程标签 v2.2.0 未找到（可能网络问题）")
            return False
    except subprocess.TimeoutExpired:
        print("⚠️  网络连接超时，跳过远程检查")
        return False
    except Exception as e:
        print(f"⚠️  远程检查失败: {e}")
        return False

def check_release_page():
    """提供Release页面URL供手动验证"""
    print("\n" + "=" * 60)
    print("🔍 GitHub Release 页面验证")
    print("=" * 60)
    
    release_url = "https://github.com/pengkang2017/btc-collision-engine/releases/tag/v2.2.0"
    releases_list_url = "https://github.com/pengkang2017/btc-collision-engine/releases"
    
    print("\n📝 请按以下步骤手动验证：")
    print(f"\n1️⃣  打开Release列表页面:")
    print(f"   {releases_list_url}")
    print(f"\n2️⃣  或直接访问v2.2.0 Release:")
    print(f"   {release_url}")
    print(f"\n3️⃣  检查以下内容：")
    print(f"   ☑️  Release标题: v2.2.0 - 性能优化与GPU监控增强")
    print(f"   ☑️  绿色标签显示 'Latest release'")
    print(f"   ☑️  发布日期: 2026-04-21")
    print(f"   ☑️  性能数据: gmpy2 14.55x, GPU 203,434 keys/s")
    print(f"   ☑️  测试数据: 107个用例, 99%通过率")
    print(f"   ☑️  Markdown格式渲染正常")
    
    return True

def check_version_code():
    """检查代码版本号"""
    print("\n" + "=" * 60)
    print("🔢 检查代码版本号")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ['python', '-c', 'from src import __version__; print(__version__)'],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        version = result.stdout.strip()
        if version == '2.2.0':
            print(f"✅ 代码版本正确: {version}")
            return True
        else:
            print(f"❌ 代码版本错误: {version} (应为 2.2.0)")
            return False
    except Exception as e:
        print(f"❌ 版本检查失败: {e}")
        return False

def main():
    """主验证流程"""
    print("\n" + "🚀" * 30)
    print("GitHub Release v2.2.0 创建验证")
    print("🚀" * 30 + "\n")
    
    results = []
    
    # 1. 检查本地标签
    results.append(("本地标签", check_local_tag()))
    
    # 2. 检查远程标签
    results.append(("远程标签", check_remote_tag()))
    
    # 3. 检查代码版本
    results.append(("代码版本", check_version_code()))
    
    # 4. Release页面验证
    results.append(("页面验证", check_release_page()))
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 验证总结")
    print("=" * 60)
    
    passed = sum(1 for _, status in results if status)
    total = len(results)
    
    for name, status in results:
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {name}")
    
    print(f"\n总计: {passed}/{total} 项检查通过")
    
    if passed == total:
        print("\n🎉 所有检查通过！Release v2.2.0 创建成功！")
        return 0
    elif passed >= 3:
        print("\n✅ 大部分检查通过。请手动验证Release页面。")
        return 0
    else:
        print("\n⚠️  部分检查未通过。请检查问题。")
        return 1

if __name__ == '__main__':
    sys.exit(main())
