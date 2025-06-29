# screen_capture.py
import logging
import os
import re
import sqlite3
import time
import json
import threading
from datetime import datetime
from threading import Thread, Lock
import queue
import pytesseract
from typing import Optional, List, Dict, Any

# --- 动态添加项目根目录到Python路径 ---
# (此部分对于独立运行可能需要，取决于项目结构)

# --- 错误处理和日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 依赖可用性检查 ---
PYWIN32_AVAILABLE = False
try:
    import win32gui
    import win32process
    import win32api
    PYWIN32_AVAILABLE = True
except ImportError:
    logging.warning("pywin32 未安装或不可用。Windows特定的活动窗口信息将无法获取。")

UIAUTOMATION_AVAILABLE = False
try:
    import uiautomation as auto
    UIAUTOMATION_AVAILABLE = True
except ImportError:
    logging.warning("uiautomation 未安装或不可用。将无法从浏览器获取URL。")

try:
    from pynput import mouse, keyboard
except ImportError:
    logging.error("pynput 未安装。鼠标和键盘事件监听将不可用。")
    mouse = None
    keyboard = None

import mss
from PIL import Image

# --- 全局变量和配置 ---
# 导入配置管理
try:
    from gui_config import gui_config
    SCREENSHOT_DIR = gui_config.get('paths.screenshot_directory', 'screen_recordings')
except ImportError:
    SCREENSHOT_DIR = "screen_recordings"

DATABASE_FILE = os.path.join(SCREENSHOT_DIR, "activity_log.db")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# --- Tesseract OCR 配置 ---
# 根据您的Tesseract安装路径进行配置
try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except:
    logging.warning("Tesseract OCR 路径可能需要配置。请确保已正确安装Tesseract-OCR。")

# --- 移除了对 activity_retriever 的导入和实时索引逻辑 ---

# --- 初始化锁 ---
record_file_lock = threading.Lock()
db_connection_lock = Lock()
click_queue = queue.Queue()

# 全局鼠标控制器
mouse_controller = None

# --- Tesseract OCR 函数 ---
def extract_text_with_tesseract(image_path: str) -> str:
    """使用Tesseract-OCR从截图中提取文本"""
    try:
        # 打开图像
        image = Image.open(image_path)
        
        # 使用Tesseract进行OCR识别，支持中文和英文
        ocr_text = pytesseract.image_to_string(
            image, 
            lang='chi_sim+eng',  # 中文简体+英文
            config='--psm 6'     # 页面分割模式6：统一的文本块
        )
        
        # 清理文本：移除多余的换行符和空白字符
        cleaned_text = ' '.join(ocr_text.split())
        
        if cleaned_text.strip():
            logging.info(f"Tesseract OCR 成功提取文本，长度: {len(cleaned_text)}")
            return cleaned_text
        else:
            logging.info("Tesseract OCR 未检测到任何文本")
            return "未检测到文本内容"
            
    except Exception as e:
        logging.error(f"Tesseract OCR 处理失败: {e}")
        return f"OCR处理失败: {str(e)}"

# --- 数据库函数 ---
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file, check_same_thread=False)
    except sqlite3.Error as e:
        logging.error(e)
    return conn

def init_db():
    conn = create_connection(DATABASE_FILE)
    if conn is not None:
        try:
            cursor = conn.cursor()
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                record_type TEXT NOT NULL,
                triggered_by TEXT,
                event_type TEXT,
                window_title TEXT,
                process_name TEXT,
                app_name TEXT,
                page_title TEXT,
                url TEXT,
                pid INTEGER,
                from_app TEXT,
                to_app TEXT,
                to_app_title TEXT,
                screenshot_path TEXT,
                ocr_text TEXT,
                mouse_x INTEGER,
                mouse_y INTEGER,
                button TEXT,
                pressed INTEGER
            );
            """
            cursor.execute(create_table_sql)
            conn.commit()
            logging.info(f"数据库表 'activity_log' 已在 {DATABASE_FILE} 中初始化/验证完毕。")
        except sqlite3.Error as e:
            logging.error(f"创建/验证数据库表失败: {e}")
        finally:
            conn.close()
    else:
        logging.error("未能创建数据库连接，无法初始化数据库。")

def save_record(record_data):
    """将单条活动记录保存到SQLite数据库。"""
    with db_connection_lock:
        conn = create_connection(DATABASE_FILE)
        if not conn:
            logging.error("保存记录时无法创建数据库连接。")
            return

        try:
            # 动态构建INSERT语句
            columns = ', '.join(record_data.keys())
            placeholders = ', '.join('?' * len(record_data))
            sql = f"INSERT INTO activity_log ({columns}) VALUES ({placeholders})"
            
            cursor = conn.cursor()
            cursor.execute(sql, list(record_data.values()))
            conn.commit()
            logging.info(f"成功保存记录到数据库 (类型: {record_data.get('record_type')})")
        except sqlite3.Error as e:
            logging.error(f"保存记录到SQLite时出错: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

# --- 核心功能函数 ---
def get_app_info_from_hwnd(hwnd):
    if not PYWIN32_AVAILABLE or not hwnd:
        return "Unknown", 0, "Unknown"
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
        exe = win32process.GetModuleFileNameEx(handle, 0)
        win32api.CloseHandle(handle)
        app_name = os.path.basename(exe)
        # 简化常见应用名称
        name_map = {
            "chrome.exe": "Chrome",
            "firefox.exe": "Firefox",
            "msedge.exe": "Edge",
            "Code.exe": "VSCode",
            "explorer.exe": "Explorer"
        }
        return name_map.get(app_name, app_name), pid, exe
    except Exception:
        return "Unknown", 0, "Unknown"
        
def get_active_window_info():
    if not PYWIN32_AVAILABLE:
        return "Unknown", 0, "Unknown", "Unknown"
    try:
        hwnd = win32gui.GetForegroundWindow()
        app_name, pid, process_name = get_app_info_from_hwnd(hwnd)
        window_title = win32gui.GetWindowText(hwnd)
        return window_title, pid, process_name, app_name
    except Exception:
        return "Unknown", 0, "Unknown", "Unknown"

def capture_screenshot(filename_prefix="screenshot"):
    try:
        with mss.mss() as sct:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.png"
            filepath = os.path.join(SCREENSHOT_DIR, filename)
            sct.shot(output=filepath, mon=-1) # -1 for all monitors
            return filepath
    except Exception as e:
        logging.error(f"截屏失败: {e}")
        return None

def get_browser_url(app_name, window_title):
    """尝试从浏览器获取当前页面URL"""
    if not UIAUTOMATION_AVAILABLE:
        return ""
    
    try:
        # 检查是否是支持的浏览器
        browser_apps = ['chrome', 'firefox', 'edge', 'msedge']
        if not any(browser in app_name.lower() for browser in browser_apps):
            return ""
        
        # 获取前台窗口
        window = auto.GetForegroundWindow()
        if not window.Exists():
            return ""
        
        # 尝试查找地址栏
        address_bar = None
        
        # Chrome/Edge 地址栏查找
        if 'chrome' in app_name.lower() or 'edge' in app_name.lower() or 'msedge' in app_name.lower():
            # 尝试多种可能的地址栏控件
            address_bar = window.EditControl(searchDepth=10)
            if not address_bar.Exists():
                address_bar = window.ComboBoxControl(searchDepth=10)
        
        # Firefox 地址栏查找
        elif 'firefox' in app_name.lower():
            address_bar = window.EditControl(searchDepth=10)
            if not address_bar.Exists():
                address_bar = window.ComboBoxControl(searchDepth=10)
        
        # 获取URL
        if address_bar and address_bar.Exists():
            url = address_bar.GetValuePattern().Value
            if url and url.startswith(('http://', 'https://', 'file://')):
                return url
                
    except Exception as e:
        logging.debug(f"获取浏览器URL失败: {e}")
    
    return ""

def extract_url_from_ocr(ocr_text):
    """从OCR文本中提取URL作为备用方案"""
    import re
    
    # URL正则表达式模式
    url_patterns = [
        r'https?://[^\s<>"{}|\\^`\[\]]+',  # 标准HTTP/HTTPS URL
        r'www\.[^\s<>"{}|\\^`\[\]]+',      # www开头的URL
        r'[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}[^\s<>"{}|\\^`\[\]]*'  # 域名格式
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, ocr_text)
        if matches:
            # 返回最长的匹配项，通常是最完整的URL
            return max(matches, key=len)
    
    return ""

def record_screen_activity(triggered_by="timer"):
    timestamp = datetime.now().isoformat()
    window_title, pid, process_name, app_name = get_active_window_info()
    
    screenshot_path = capture_screenshot()
    ocr_text = ""
    url = ""
    
    if screenshot_path:
        logging.info(f"截图已保存: {screenshot_path}")
        try:
            ocr_text = extract_text_with_tesseract(screenshot_path)
            logging.info("Tesseract OCR 解析完成。")
        except Exception as e:
            logging.error(f"使用 Tesseract OCR 解析图像时出错: {e}", exc_info=True)
            ocr_text = f"OCR失败: {e}"
    else:
        logging.warning("未捕获截图，OCR步骤已跳过。")
    
    # 尝试获取浏览器URL
    try:
        url = get_browser_url(app_name, window_title)
        if not url and ocr_text:
            # 如果直接获取失败，尝试从OCR文本中提取
            url = extract_url_from_ocr(ocr_text)
        
        if url:
            logging.info(f"获取到URL: {url}")
    except Exception as e:
        logging.debug(f"URL获取过程出错: {e}")
    
    record_data = {
        "timestamp": timestamp,
        "record_type": "screen_content",
        "triggered_by": triggered_by,
        "window_title": window_title,
        "app_name": app_name,
        "pid": pid,
        "process_name": process_name,
        "screenshot_path": screenshot_path,
        "ocr_text": ocr_text,
        "url": url,  # 添加URL字段
    }
    save_record(record_data)

# --- 鼠标点击处理 ---
def process_click_task(task_data):
    time.sleep(1) # 等待1秒，确保点击后的UI变化已经渲染完成
    record_screen_activity(triggered_by="mouse_click")

def click_processing_worker():
    while True:
        task_data = click_queue.get()
        process_click_task(task_data)
        click_queue.task_done()

def handle_mouse_click_activity(x, y, button, pressed):
    if pressed:
        logging.info(f"鼠标点击事件: {button} at ({x}, {y})")
        click_queue.put({"x": x, "y": y, "button": str(button)})

# --- 监听器 ---
def start_mouse_listener():
    if mouse:
        listener = mouse.Listener(on_click=handle_mouse_click_activity)
        listener.start()
        logging.info("鼠标监听器已启动。")
        return listener
    return None

def main():
    init_db()
    
    # 启动点击处理工作线程
    click_worker_thread = Thread(target=click_processing_worker, daemon=True)
    click_worker_thread.start()

    # 启动鼠标监听器
    mouse_listener = start_mouse_listener()

    # 主循环，用于定时截图
    logging.info("屏幕活动记录已开始。定时截图周期为60秒。")
    while True:
        try:
            record_screen_activity(triggered_by="timer")
            time.sleep(60) # 每60秒记录一次
        except KeyboardInterrupt:
            logging.info("接收到中断信号，正在停止...")
            if mouse_listener:
                mouse_listener.stop()
            break
        except Exception as e:
            logging.error(f"主循环发生错误: {e}", exc_info=True)
            time.sleep(60)

if __name__ == '__main__':
    main()
