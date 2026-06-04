#!/usr/bin/env python3
"""
Job Hunter 启动脚本（跨平台）
用法: python run.py [--port 8000] [--host 0.0.0.0] [--no-reload]
"""
import argparse
import sys
import os


def main():
    parser = argparse.ArgumentParser(description="Job Hunter - 智能求职推荐系统")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="监听端口 (默认: 8000)")
    parser.add_argument("--no-reload", action="store_true", help="禁用自动重载")
    args = parser.parse_args()

    # 确保在项目根目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 检查 .env 文件
    if not os.path.exists(".env"):
        print("\n⚠️  未找到 .env 配置文件！")
        print("   请复制 .env.example 为 .env 并填写你的 API Key 和配置：")
        print("   cp .env.example .env  (Linux/Mac)")
        print("   copy .env.example .env  (Windows)\n")
        sys.exit(1)

    # 检查关键依赖
    try:
        import uvicorn
    except ImportError:
        print("\n⚠️  依赖未安装，正在安装...")
        os.system(f"{sys.executable} -m pip install -r requirements.txt")
        import uvicorn

    print(f"""
╔══════════════════════════════════════════╗
║   🎯 Job Hunter - 智能求职推荐系统      ║
╠══════════════════════════════════════════╣
║   管理面板: http://localhost:{args.port:<5}      ║
║   按 Ctrl+C 停止                        ║
╚══════════════════════════════════════════╝
""")

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
