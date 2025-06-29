#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
现代化AI桌面活动助手启动脚本
"""

import os
import sys
import logging
import subprocess

def setup_environment():
    """设置环境变量"""
    # 启用嵌入功能
    os.environ['LOAD_EMBEDDINGS'] = 'true'
    
    # 数据库已清空，不需要强制重新索引
    # os.environ['FORCE_REINDEX'] = 'true'
    
    # 如果想跳过索引快速启动，可以设置：
    # os.environ['SKIP_INDEXING'] = 'true'

def check_dependencies():
    """检查依赖"""
    try:
        import PySide6
        import sentence_transformers
        import chromadb
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("💡 请运行: pip install -r requirements.txt")
        return False

def main():
    """主启动函数"""
    print("🚀 启动现代化AI桌面活动助手...")
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 设置环境
    setup_environment()
    
    try:
        # 导入并启动主程序
        from modern_gui import main as gui_main
        gui_main()
        
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        logging.error(f"启动失败: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 