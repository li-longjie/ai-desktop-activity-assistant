#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理脚本 - 清空ChromaDB数据
"""

import os
import shutil
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 从配置文件读取路径
try:
    from gui_config import gui_config
    chroma_path = gui_config.get('paths.database_directory', 'chroma_db_activity')
except ImportError:
    chroma_path = "chroma_db_activity"

def clear_chromadb():
    """清空ChromaDB数据"""
    try:
        if os.path.exists(chroma_path):
            logging.info(f"🗑️  正在删除ChromaDB目录: {chroma_path}")
            shutil.rmtree(chroma_path)
            logging.info("✅ ChromaDB数据已清空")
        else:
            logging.info("📁 ChromaDB目录不存在，无需清理")
        
        # 创建新的空目录
        os.makedirs(chroma_path, exist_ok=True)
        logging.info("📁 已创建新的ChromaDB目录")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ 清理ChromaDB失败: {e}")
        return False

def main():
    """主函数"""
    print("=== AI桌面助手数据清理工具 ===")
    print("此工具将清空所有向量数据库数据")
    
    # 确认操作
    confirm = input("确认要清空所有数据吗？(输入 'yes' 确认): ")
    if confirm.lower() != 'yes':
        print("❌ 操作已取消")
        return
    
    # 执行清理
    success = clear_chromadb()
    
    if success:
        print("🎉 数据清理完成！现在可以重新启动应用程序")
        print("💡 运行命令: python start_modern_gui.py")
    else:
        print("❌ 数据清理失败，请检查日志")

if __name__ == "__main__":
    main() 