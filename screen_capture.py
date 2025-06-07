import time
import os
from PIL import Image
import mss
import pytesseract
import pygetwindow as gw
import logging
from datetime import datetime
import json
import psutil # 导入psutil
import threading # 导入threading
from pynput import mouse # 导入pynput.mouse
import queue # 导入queue模块
import sqlite3 # <--- 新增：导入sqlite3模块
import re # <--- 新增：导入re模块
from typing import Optional # <--- 新增：导入Optional类型
from dotenv import load_dotenv

load_dotenv()

# 尝试导入 pywin32，如果失败则记录错误，并在后续逻辑中回退
try:
    import win32process
    import win32gui
    import win32api # 用于获取屏幕指标，可能在DPI处理时有用
    PYWIN32_AVAILABLE = True
    logging.info("pywin32库 (win32process, win32gui, win32api) 加载成功。")
except ImportError:
    PYWIN32_AVAILABLE = False
    logging.warning("pywin32库加载失败。在Windows上获取精确的应用名称、PID和窗口截图可能会受限。请尝试 `pip install pywin32`")

# 尝试设置DPI感知 (仅Windows)
if os.name == 'nt' and PYWIN32_AVAILABLE: # 检查是否为Windows且pywin32可用
    try:
        import ctypes
        # Per-Monitor DPI Aware V2: 对于现代应用最理想
        # 1 表示 System DPI Aware, 0 表示 Unaware
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logging.info("成功将进程DPI感知设置为 Per-Monitor Aware V2。")
    except AttributeError:
        # shcore.dll 可能在非常旧的Windows版本上不可用，或者 SetProcessDpiAwareness 不存在
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            logging.info("成功将进程DPI感知设置为 System DPI Aware (回退方案)。")
        except Exception as e_dpi_fallback:
            logging.warning(f"设置DPI感知失败: {e_dpi_fallback}")
    except Exception as e_dpi:
        logging.warning(f"设置DPI感知时发生未知错误: {e_dpi}")

# 导入活动索引功能
try:
    from activity_retriever import index_single_activity_record
    logging.info("成功导入index_single_activity_record函数")
except ImportError as e:
    logging.error(f"导入index_single_activity_record函数失败: {e}")
    # 定义一个替代函数，在真正的函数不可用时使用
    def index_single_activity_record(record):
        logging.error("无法使用实际的index_single_activity_record函数，只记录数据到文件")
        return False

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s') # 将日志级别改为DEBUG

# --- Tesseract OCR 配置 ---
# 根据您的Tesseract安装路径进行配置
# Windows示例:
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe' # 注意路径中的反斜杠
# Linux/macOS 通常不需要特别指定，如果已添加到PATH

# --- 全局变量 ---
SCREENSHOT_DIR = "screen_recordings"
# 使用jsonl格式，每行一个json对象, 文件名可以更明确
# RECORD_DATA_FILE = os.path.join(SCREENSHOT_DIR, "screen_activity_log.jsonl") # <--- 注释或删除这行
DATABASE_FILE = os.path.join(SCREENSHOT_DIR, "activity_log.db") # <--- 新增：SQLite数据库文件名
CAPTURE_INTERVAL_SECONDS = 10 # 每10秒捕获一次，您可以按需调整
MOUSE_CLICK_CAPTURE_INTERVAL_SECONDS = 2 # 鼠标点击后至少2秒才再次因点击而截图

# 特殊应用名称的大小写映射
KNOWN_APP_CASINGS = {
    "qq": "QQ",        # 修正：键应该是全小写 "qq"
    "vscode": "VSCode",
    "code": "VSCode",    # VS Code 的进程名通常是 Code.exe
    # 在这里可以添加更多自定义的大小写规则
    # "wechat": "WeChat", # 如果您希望微信显示为 WeChat 而不是 Wechat
}

# 用于检测应用切换的全局变量
last_active_app_name = None
last_window_title = None # 可选：也跟踪窗口标题变化，以记录更细微的切换

# 用于鼠标点击截图的全局变量
last_mouse_click_screenshot_time = 0
record_file_lock = threading.Lock() # 用于同步对记录文件的写入
mouse_controller = None # pynput鼠标控制器实例
click_task_queue = queue.Queue() # 用于处理鼠标点击任务的队列

# 尝试导入 uiautomation，如果失败则记录错误，并在后续逻辑中回退
try:
    import uiautomation as auto
    UIAUTOMATION_AVAILABLE = True
    logging.info("uiautomation库加载成功。可以尝试获取浏览器URL。")
except ImportError:
    UIAUTOMATION_AVAILABLE = False
    logging.warning("uiautomation库加载失败。无法获取浏览器URL。请尝试 `pip install uiautomation`")

# --- 确保截图目录存在 ---
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

def create_connection(db_file):
    """ 创建一个数据库连接到SQLite数据库 """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        # logging.debug(f"成功连接到SQLite数据库: {db_file}")
    except sqlite3.Error as e:
        logging.error(f"连接SQLite数据库失败 ({db_file}): {e}")
    return conn

def init_db():
    """ 初始化数据库，创建表（如果不存在），并自动迁移旧的表结构。 """
    conn = create_connection(DATABASE_FILE)
    if conn is not None:
        try:
            cursor = conn.cursor()

            # 1. 确保表存在 (使用最新的 schema 定义)
            # 这样新创建的数据库就直接是正确的结构。
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
            conn.commit() # 提交创表操作

            # 2. 检查旧的表结构并进行迁移 (如果需要)
            # 这一步是为了兼容已经存在的、没有 'url' 列的旧数据库。
            cursor.execute("PRAGMA table_info(activity_log);")
            columns = [row[1] for row in cursor.fetchall()]
            if 'url' not in columns:
                logging.info("检测到旧版数据库表，缺少 'url' 列。正在进行迁移...")
                try:
                    cursor.execute("ALTER TABLE activity_log ADD COLUMN url TEXT;")
                    conn.commit()
                    logging.info("数据库迁移成功：已成功添加 'url' 列。")
                except sqlite3.Error as e_alter:
                    logging.error(f"数据库迁移失败：添加 'url' 列时出错: {e_alter}")
                    # 如果迁移失败，后续操作可能也会失败，但我们还是继续
            
            # 3. 创建索引（如果不存在）
            create_index_timestamp_sql = "CREATE INDEX IF NOT EXISTS idx_timestamp ON activity_log (timestamp);"
            cursor.execute(create_index_timestamp_sql)
            create_index_app_name_sql = "CREATE INDEX IF NOT EXISTS idx_app_name ON activity_log (app_name);"
            cursor.execute(create_index_app_name_sql)
            create_index_record_type_sql = "CREATE INDEX IF NOT EXISTS idx_record_type ON activity_log (record_type);"
            cursor.execute(create_index_record_type_sql)
            
            conn.commit() # 提交索引创建操作
            logging.info(f"数据库表 'activity_log' 已在 {DATABASE_FILE} 中初始化/验证完毕。")
        except sqlite3.Error as e:
            logging.error(f"创建/验证数据库表失败: {e}")
        finally:
            conn.close()
    else:
        logging.error("未能创建数据库连接，无法初始化数据库。")

def get_mouse_position():
    """获取当前鼠标指针的全局位置"""
    global mouse_controller
    if not mouse_controller: # 确保控制器已初始化
        try:
            mouse_controller = mouse.Controller()
        except Exception as e:
            logging.error(f"初始化鼠标控制器失败: {e}")
            return None
    try:
        return mouse_controller.position
    except Exception as e:
        # 处理 Wayland 等环境下 pynput 可能无法获取位置的问题
        if "DISPLAY environment variable not set" in str(e) or "Wayland" in str(e):
             logging.warning(f"无法获取鼠标位置 (可能在Wayland环境下或无显示服务): {e}")
        else:
            logging.error(f"获取鼠标位置失败: {e}")
        return None

def extract_url_from_text(text: str) -> Optional[str]:
    """
    使用正则表达式从一段文本中提取第一个看起来像URL的字符串。
    """
    if not text:
        return None
    # 正则表达式查找以 http:// 或 https:// 开头的标准URL
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    match = url_pattern.search(text)
    if match:
        url = match.group(0).strip()
        # 移除 OCR 结果中可能出现的尾随标点符号
        if url.endswith(('.', ',', ';', ':')):
            url = url[:-1]
        logging.info(f"通过OCR文本提取到URL: {url}")
        return url
    
    logging.debug("在OCR文本中未通过正则表达式找到URL。")
    return None

def get_url_from_browser(hwnd, app_name):
    """
    使用UI Automation尝试从浏览器窗口获取当前URL。
    此功能依赖 uiautomation 库，可能不稳定，且在不同浏览器/版本上表现不一。
    """
    if not UIAUTOMATION_AVAILABLE or not hwnd:
        return None

    url = None
    try:
        # 将搜索超时设置得较短，以避免在找不到控件时长时间阻塞。
        auto.SetGlobalSearchTimeout(1.0)
        
        window_control = auto.ControlFromHandle(hwnd)

        # 适用于大多数基于Chromium的浏览器 (Chrome, Edge, etc.)
        if app_name in ["Chrome", "Edge", "msedge", "Chromium", "Brave", "Opera", "Cursor"]:
            # 优先查找 Toolbar，地址栏通常在其中
            toolbar = window_control.ToolBarControl()
            if toolbar.Exists(0.1, 0.1):
                address_bar = toolbar.EditControl()
                if address_bar.Exists(0.1, 0.1):
                    url = address_bar.GetValuePattern().Value
            
            # 如果在工具栏中找不到，使用旧的名称查找方法作为回退
            if not url:
                logging.debug(f"在工具栏中未找到地址栏，回退到按名称搜索...")
                address_bar_by_name = window_control.EditControl(Name='Address and search bar')
                if not address_bar_by_name.Exists(0.1, 0.1):
                    address_bar_by_name = window_control.EditControl(Name='地址与搜索栏')
                
                if address_bar_by_name.Exists(0.1, 0.1):
                    url = address_bar_by_name.GetValuePattern().Value

        # 适用于Firefox
        elif app_name == "Firefox":
            doc_control = window_control.DocumentControl(searchDepth=16)
            if doc_control and doc_control.Exists(0.1, 0.1):
                try:
                    url = doc_control.GetValuePattern().Value
                except Exception:
                    pass

        if url:
            url = url.strip()
            # 简单的验证，确保它看起来像一个URL（不包含空格等）
            if ' ' in url or not (url.startswith('http') or '://' in url or '.' in url):
                logging.warning(f"获取到的值 '{url}' 不像一个有效的URL，已忽略。")
                url = None
            else:
                 logging.info(f"成功从 {app_name} 获取URL: {url}")
                 return url
        
        logging.warning(f"未能从 {app_name} (HWND: {hwnd}) 获取到URL。")

    except Exception as e:
        # 减少日志噪音，只在DEBUG模式下显示完整堆栈
        logging.error(f"从浏览器获取URL时发生未知错误: {e}", exc_info=logging.getLogger().level == logging.DEBUG)
    finally:
        # 恢复默认的全局超时设置
        auto.SetGlobalSearchTimeout(auto.TIME_OUT_SECOND)
        
    return None

def capture_screenshot(filename_prefix="screenshot", window_rect=None, app_name="Unknown"):
    """
    捕获屏幕截图。如果提供了window_rect，则捕获该区域。
    对于已知浏览器，会尝试裁剪掉顶部的UI元素（标签栏、地址栏等）。
    返回截图文件的路径。
    """
    try:
        with mss.mss() as sct:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.png"
            filepath = os.path.join(SCREENSHOT_DIR, filename)
            
            sct_img = None
            capture_details = "N/A"

            if window_rect:
                left, top, right, bottom = window_rect

                # -- 新增：浏览器UI裁剪启发式逻辑 --
                browser_apps = ["Chrome", "Firefox", "Edge", "msedge", "Chromium", "Brave", "Opera", "Cursor"]
                if app_name in browser_apps:
                    # 从顶部裁剪一个固定的像素值，以尝试移除标签栏、地址栏和书签栏。
                    # 这个值是一个估计值，可能需要根据屏幕分辨率或浏览器设置进行调整。
                    top_crop_pixels = 130 
                    if (bottom - (top + top_crop_pixels)) > 50: # 确保截图仍有足够的高度
                        top += top_crop_pixels
                        logging.info(f"检测到浏览器 '{app_name}'。自动从截图顶部裁剪 {top_crop_pixels}px。")
                # -- 裁剪逻辑结束 --

                width = right - left
                height = bottom - top
                
                # 确保捕获区域有实际大小 (mss可能会对0或负值报错)
                MIN_CAPTURE_DIMENSION = 1 # 最小为1像素
                if width >= MIN_CAPTURE_DIMENSION and height >= MIN_CAPTURE_DIMENSION:
                    capture_region = {'top': top, 'left': left, 'width': width, 'height': height}
                    try:
                        logging.info(f"尝试截取指定窗口区域: {capture_region}")
                        sct_img = sct.grab(capture_region)
                        capture_details = f"窗口区域: {capture_region}"
                    except mss.exception.ScreenShotError as e_grab:
                        logging.error(f"使用mss.grab()截取窗口区域 {capture_region} 失败: {e_grab}. 将回退到全屏截图。")
                        sct_img = None # 确保sct_img为None以触发回退
                    except Exception as e_grab_other:
                        logging.error(f"截取窗口区域 {capture_region} 时发生意外错误: {e_grab_other}. 将回退到全屏截图。")
                        sct_img = None
                else:
                    logging.warning(f"提供的窗口矩形 {window_rect} 尺寸过小或无效 (宽:{width}, 高:{height})。将回退到全屏截图。")
            
            if sct_img is None: # 如果窗口区域截图失败或未提供window_rect，则全屏截图
                if len(sct.monitors) > 1:
                    monitor_to_capture = sct.monitors[1] # 主显示器
                    logging.info(f"进行全屏截图 (主显示器: {monitor_to_capture})。")
                elif len(sct.monitors) == 1: # 只有一个监视器信息，通常是monitors[0]代表所有监视器合并的虚拟屏幕
                    monitor_to_capture = sct.monitors[0]
                    logging.info(f"进行全屏截图 (sct.monitors[0]: {monitor_to_capture})。")
                else:
                    logging.error("mss未检测到任何显示器，无法截图。")
                    return None
                
                sct_img = sct.grab(monitor_to_capture)
                capture_details = f"全屏 (显示器: {monitor_to_capture})"

            if sct_img:
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img.save(filepath)
                logging.info(f"截图已保存到 {filepath} (截图方式: {capture_details})")
                return filepath
            else:
                logging.error("未能生成sct_img对象，截图失败。")
                return None

    except Exception as e:
        logging.error(f"截图过程中发生严重错误: {e}", exc_info=True)
        return None

def extract_text_from_image(image_path):
    """
    从图像提取文本（OCR）。
    """
    try:
        img = Image.open(image_path)
        # 使用pytesseract进行OCR
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')  # 支持中文和英文
        logging.info(f"从图像提取了 {len(text.split())} 个单词")
        return text
    except Exception as e:
        logging.error(f"从图像提取文本失败 ({image_path}): {e}")
        return ""

def get_active_window_info():
    """
    获取当前活动窗口的信息。
    返回窗口标题, 进程名, 应用名, 页面标题 (如果是浏览器/IDE等), PID, 和窗口矩形。
    """
    window_title = "Unknown"
    process_name = "Unknown"
    app_name = "Unknown"
    page_title = None
    url = None # <--- 新增: 初始化url变量
    pid = None
    window_rect = None # 新增：用于存储窗口矩形 (left, top, right, bottom)

    try:
        active_window_hwnd = None
        if PYWIN32_AVAILABLE:
            active_window_hwnd = win32gui.GetForegroundWindow()
            if active_window_hwnd:
                window_title = win32gui.GetWindowText(active_window_hwnd) if win32gui.GetWindowText(active_window_hwnd) else "Untitled"
                _, pid = win32process.GetWindowThreadProcessId(active_window_hwnd)
                logging.debug(f"pywin32: HWND={active_window_hwnd}, PID={pid}, Window Title='{window_title}'")

                # 尝试获取窗口矩形
                try:
                    if win32gui.IsWindowVisible(active_window_hwnd) and not win32gui.IsIconic(active_window_hwnd):
                        rect = win32gui.GetWindowRect(active_window_hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        
                        # 定义合理的最小窗口尺寸，以过滤掉一些覆盖层或小型工具窗口
                        MIN_VALID_WINDOW_WIDTH = 150  # 可调整
                        MIN_VALID_WINDOW_HEIGHT = 100 # 可调整

                        if width >= MIN_VALID_WINDOW_WIDTH and height >= MIN_VALID_WINDOW_HEIGHT:
                            window_rect = rect
                            logging.debug(f"获取到活动窗口矩形: {window_rect} (宽度: {width}, 高度: {height})")
                        elif width > 0 and height > 0 : # 窗口有效但太小
                            logging.info(f"活动窗口 HWND {active_window_hwnd} 尺寸过小 ({width}x{height})，不用于区域截图。")
                        else: # 无效尺寸
                            logging.warning(f"活动窗口 HWND {active_window_hwnd} 尺寸无效 ({width}x{height})，不用于区域截图。")
                    elif not win32gui.IsWindowVisible(active_window_hwnd):
                        logging.info(f"活动窗口 HWND {active_window_hwnd} 不可见，不获取矩形。")
                    else: # IsIconic (最小化)
                        logging.info(f"活动窗口 HWND {active_window_hwnd} 已最小化，不获取矩形。")
                except Exception as e_rect:
                    logging.error(f"获取窗口 HWND {active_window_hwnd} 的矩形时出错: {e_rect}")
            else:
                logging.warning("win32gui.GetForegroundWindow() 未返回有效的窗口句柄。")
                window_title = "No Active Window (pywin32)"
                # 在这种情况下，无法获取窗口矩形，window_rect 将保持 None
                # return {"title": window_title, ..., "window_rect": None} # 早期返回
        else: # 回退到 pygetwindow
            active_window_gw = gw.getActiveWindow()
            if not active_window_gw:
                logging.warning("gw.getActiveWindow() 未返回活动窗口。")
                window_title = "No Active Window (pygetwindow)"
                # return {"title": window_title, ..., "window_rect": None} # 早期返回
            else:
                window_title = active_window_gw.title if active_window_gw.title else "Untitled"
                # pygetwindow 获取精确PID和可靠的窗口矩形较为困难，通常不直接支持
                logging.warning("pywin32不可用，使用pygetwindow回退。精确的窗口区域截图将不可用，将进行全屏截图。")


        # --- 进程名和应用名提取逻辑 (基本保持不变) ---
        if pid:
            try:
                p = psutil.Process(pid)
                process_name = p.name()
    
                if process_name and process_name != "Unknown":
                    base_name_original_case = process_name.split('.')[0]
                    base_name_lower = base_name_original_case.lower() 
                    
                    if "qq" in window_title.lower() or (process_name and "qq" in process_name.lower()):
                        logging.info(f"QQ_DETECTION_DEBUG: WindowTitle='{window_title}', OriginalProcessName='{process_name}', BaseNameOriginalCase='{base_name_original_case}', BaseNameLower='{base_name_lower}'")
                    
                    if base_name_lower in KNOWN_APP_CASINGS:
                        app_name = KNOWN_APP_CASINGS[base_name_lower]
                        if "qq" in window_title.lower() or (process_name and "qq" in process_name.lower()):
                            logging.info(f"QQ_DETECTION_DEBUG: Matched KNOWN_APP_CASINGS. AppName set to '{app_name}' from key '{base_name_lower}'.")
                    else:
                        app_name = base_name_original_case.capitalize()
                        if "qq" in window_title.lower() or (process_name and "qq" in process_name.lower()):
                            logging.info(f"QQ_DETECTION_DEBUG: No match in KNOWN_APP_CASINGS. AppName set to '{app_name}' by capitalizing '{base_name_original_case}'.")
                else:
                    app_name = "Unknown"
                logging.info(f"PSUTIL_APP_NAME_INFO: PID='{pid}', OriginalProcess='{process_name}', DeterminedAppName='{app_name}'")

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e_psutil:
                logging.warning(f"无法通过PID '{pid}' 获取进程信息 (窗口: '{window_title}'). 错误: {e_psutil}.")
            except Exception as e_psutil_other:
                logging.error(f"使用 psutil.Process(pid={pid}) 时发生意外错误 (窗口: '{window_title}'): {e_psutil_other}")
        elif PYWIN32_AVAILABLE and not pid and active_window_hwnd : # pywin32可用但未能从有效窗口获取pid
            logging.warning(f"pywin32可用，但未能从窗口 '{window_title}' (HWND: {active_window_hwnd}) 获取PID。")
        
        # --- 页面标题提取逻辑 (基本保持不变) ---
        if app_name not in ["Unknown", "System", "No Active Window (pywin32)", "No Active Window (pygetwindow)"]:
            apps_with_page_titles = ["Chrome", "Firefox", "Edge", "Safari", "Chromium", "Brave", "Opera",
                                     "Code", "PyCharm", "Sublime_text", "Notepad++", "Explorer", "msedge", "Cursor"]
            is_target_app_type = app_name in apps_with_page_titles
            if not is_target_app_type and process_name != "Unknown":
                for app_key in apps_with_page_titles:
                    if app_key.lower() in process_name.lower():
                        is_target_app_type = True
                        break
            if is_target_app_type:
                temp_page_title = window_title
                suffix1 = f" - {app_name}"
                if temp_page_title.endswith(suffix1):
                    temp_page_title = temp_page_title[:-len(suffix1)].strip()
                if process_name != "Unknown" and not process_name.lower().startswith(app_name.lower()):
                    process_base_name = process_name.split('.')[0].capitalize()
                    if process_base_name != app_name :
                        suffix2 = f" - {process_base_name}"
                        if temp_page_title.endswith(suffix2):
                             temp_page_title = temp_page_title[:-len(suffix2)].strip()
                if temp_page_title and temp_page_title != window_title and temp_page_title.lower() != app_name.lower():
                    page_title = temp_page_title
                elif temp_page_title and temp_page_title == window_title and app_name == "Explorer": 
                    page_title = window_title

        # --- 新增：URL提取逻辑 ---
        browser_apps = ["Chrome", "Firefox", "Edge", "Safari", "Chromium", "Brave", "Opera", "msedge", "Cursor"]
        if app_name in browser_apps and active_window_hwnd:
            url = get_url_from_browser(active_window_hwnd, app_name)

    except AttributeError as e_attr:
        logging.error(f"获取活动窗口信息时发生 AttributeError: {e_attr}", exc_info=True)
        # 错误不应覆盖已获取的数据。保留已有的 window_title (如果有的话)
    except Exception as e_top:
        logging.error(f"获取活动窗口信息时发生顶层异常: {e_top}", exc_info=True)
        # 同样，不在这里覆盖标题

    mouse_pos = get_mouse_position()
    
    return {
        "title": window_title,
        "process_name": process_name,
        "app_name": app_name,
        "page_title": page_title,
        "url": url, # <--- 新增：将URL添加到返回字典
        "pid": pid,
        "mouse_x": mouse_pos[0] if mouse_pos else None,
        "mouse_y": mouse_pos[1] if mouse_pos else None,
        "window_rect": window_rect # <--- 新增：将窗口矩形添加到返回字典
    }

def save_record(record_data):
    """
    将单条记录保存到SQLite数据库中。
    使用锁来确保线程安全。
    返回新插入记录的ID，如果失败则返回None。
    """
    global record_file_lock
    
    columns = [
        'timestamp', 'record_type', 'triggered_by', 'event_type', 
        'window_title', 'process_name', 'app_name', 'page_title', 'url', 'pid',
        'from_app', 'to_app', 'to_app_title', 
        'screenshot_path', 'ocr_text', 
        'mouse_x', 'mouse_y', 'button', 'pressed'
    ]
    
    data_tuple = (
        record_data.get('timestamp'),
        record_data.get('record_type'),
        record_data.get('triggered_by'),
        record_data.get('event_type'),
        record_data.get('window_title'),
        record_data.get('process_name'),
        record_data.get('app_name'),
        record_data.get('page_title'),
        record_data.get('url'),
        record_data.get('pid'),
        record_data.get('from_app'),
        record_data.get('to_app'),
        record_data.get('to_app_title'),
        record_data.get('screenshot_path'),
        record_data.get('ocr_text'),
        record_data.get('mouse_x'),
        record_data.get('mouse_y'),
        record_data.get('button'),
        1 if record_data.get('pressed') else 0
    )

    sql = f"INSERT INTO activity_log ({', '.join(columns)}) VALUES ({', '.join(['?'] * len(columns))})"
    record_id = None # 初始化 record_id

    try:
        with record_file_lock: 
            conn = create_connection(DATABASE_FILE)
            if conn is None:
                logging.error("保存记录失败：无法连接到数据库。")
                return None # 修改：返回 None
            
            cursor = conn.cursor()
            cursor.execute(sql, data_tuple)
            record_id = cursor.lastrowid # 获取自增ID
            conn.commit()
            logging.info(f"记录已保存到数据库 (ID: {record_id})")
            return record_id # 修改：返回 record_id
    except sqlite3.Error as e:
        logging.error(f"保存记录到数据库失败: {e}. SQL: {sql}, Data: {data_tuple}", exc_info=True)
        return None # 修改：返回 None
    except Exception as e_global: 
        logging.error(f"保存记录时发生意外错误: {e_global}. Data: {record_data}", exc_info=True)
        return None # 修改：返回 None
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def record_screen_activity(triggered_by="timer"):
    """
    捕获屏幕、提取文本、保存记录，并索引到向量数据库。
    """
    global last_active_app_name, last_window_title 
    timestamp = datetime.now().isoformat()
    window_info = get_active_window_info() 
    current_app_name = window_info.get("app_name", "Unknown")
    current_window_title = window_info.get("title", "Unknown")
    current_url = window_info.get("url") # 获取URL
    mouse_x = window_info.get("mouse_x")
    mouse_y = window_info.get("mouse_y")
    pid_from_window_info = window_info.get("pid")
    active_window_rect = window_info.get("window_rect") 
    ocr_text = "" 

    app_changed = current_app_name != last_active_app_name and current_app_name != "Unknown"

    if app_changed:
        event_record = {
            "timestamp": timestamp,
            "event_type": "app_switch", 
            "record_type": "app_switch", 
            "from_app": last_active_app_name if last_active_app_name else "None",
            "to_app": current_app_name,
            "to_app_title": current_window_title, 
            "url": current_url, # 添加URL到切换事件
            "mouse_x": mouse_x,
            "mouse_y": mouse_y,
            "pid": pid_from_window_info, 
            "ocr_text": f"Switched from {last_active_app_name if last_active_app_name else 'Unknown'} to {current_app_name} ({current_window_title})" 
        }
        logging.info(f"检测到应用切换: 从 {last_active_app_name} 到 {current_app_name} ({current_window_title})")
        
        saved_event_id = save_record(event_record) 
        if saved_event_id is not None:
            event_record['id'] = saved_event_id 
            logging.debug(f"DEBUG: Calling index_single_activity_record for event_record with ID: {event_record.get('id')}") # 新增日志
            index_single_activity_record(event_record) 
        
        last_active_app_name = current_app_name
        last_window_title = current_window_title
    elif current_app_name != "Unknown" and last_active_app_name is None : 
        last_active_app_name = current_app_name
        last_window_title = current_window_title
    
    screenshot_path = capture_screenshot(
        filename_prefix="screenshot",
        window_rect=active_window_rect, 
        app_name=current_app_name
    )
    if not screenshot_path:
        logging.error("截图失败，跳过本次记录")
        return
    
    ocr_text = extract_text_from_image(screenshot_path)

    # --- 新增: 从OCR文本中回退提取URL ---
    if not current_url and ocr_text:
        logging.info("UI自动化未能获取URL，尝试从OCR文本中提取...")
        current_url = extract_url_from_text(ocr_text)
    # --- URL回退提取结束 ---
    
    if not ocr_text and triggered_by == "timer": 
        logging.warning(f"OCR (定时器触发) 未识别到有效文本，跳过记录")
        return
    
    activity_content_record = {
        "timestamp": timestamp,
        "record_type": "screen_content", 
        "triggered_by": "app_switch" if app_changed else triggered_by, 
        "window_title": window_info.get("title", "Unknown"), 
        "process_name": window_info.get("process_name", "Unknown"),
        "app_name": window_info.get("app_name", "Unknown"),
        "page_title": window_info.get("page_title"), 
        "url": current_url, # 添加URL到内容记录
        "pid": pid_from_window_info, 
        "screenshot_path": screenshot_path,
        "ocr_text": ocr_text, 
        "mouse_x": mouse_x,
        "mouse_y": mouse_y
    }
    
    if not ocr_text and app_changed:
        logging.warning(f"应用切换到 '{current_app_name}'，但初始屏幕OCR为空。仍记录窗口信息。")
    elif not ocr_text : 
        pass

    saved_content_id = save_record(activity_content_record)
    if saved_content_id is not None:
        activity_content_record['id'] = saved_content_id
        logging.debug(f"DEBUG: Calling index_single_activity_record for activity_content_record with ID: {activity_content_record.get('id')}") # 新增日志
        try:
            logging.info(f"尝试将屏幕内容记录 ({activity_content_record['record_type']}) 索引到向量数据库...")
            index_result = index_single_activity_record(activity_content_record)
            if index_result:
                logging.info(f"屏幕内容记录 ({activity_content_record['record_type']}) 已成功索引")
            else:
                logging.warning(f"屏幕内容记录 ({activity_content_record['record_type']}) 未能成功索引，但已保存")
        except Exception as e:
            logging.error(f"索引屏幕内容记录 ({activity_content_record['record_type']}) 时出错: {e}", exc_info=True)
    else:
        logging.error(f"屏幕内容记录 ({activity_content_record['record_type']}) 未能保存，也未索引")

def process_click_task(task_data):
    """
    在工作线程中处理单个鼠标点击任务（截图, OCR, 保存, 索引）。
    """
    x = task_data["x"]
    y = task_data["y"]
    button_str = task_data["button"]
    timestamp_iso = task_data["timestamp"]

    logging.info(f"工作线程开始处理点击任务: ({x}, {y}), button: {button_str}")

    window_info = get_active_window_info() 
    current_app_name = window_info.get("app_name", "Unknown")
    active_window_rect = window_info.get("window_rect") 
    click_mouse_x = x 
    click_mouse_y = y
    pid_from_window_info = window_info.get("pid")

    screenshot_path = capture_screenshot(
        filename_prefix="mouse_click", 
        window_rect=active_window_rect,
        app_name=current_app_name
    )
    if not screenshot_path:
        logging.error("鼠标点击事件 (工作线程)：截图失败，跳过记录")
        return

    ocr_text = extract_text_from_image(screenshot_path)

    # --- 新增: 从OCR文本中回退提取URL ---
    if not current_url and ocr_text:
        logging.info("UI自动化未能获取URL(点击事件)，尝试从OCR文本中提取...")
        current_url = extract_url_from_text(ocr_text)
    # --- URL回退提取结束 ---

    click_event_record = {
        "timestamp": timestamp_iso, 
        "record_type": "mouse_interaction",
        "triggered_by": "mouse_click",
        "window_title": window_info.get("title", "Unknown"),
        "process_name": window_info.get("process_name", "Unknown"),
        "app_name": window_info.get("app_name", "Unknown"),
        "page_title": window_info.get("page_title"),
        "url": current_url, # 使用可能已通过OCR更新的URL
        "pid": pid_from_window_info, 
        "screenshot_path": screenshot_path,
        "ocr_text": ocr_text if ocr_text else "",
        "mouse_x": click_mouse_x,
        "mouse_y": click_mouse_y,
        "button": button_str, 
        "pressed": True, 
    }

    saved_click_id = save_record(click_event_record) 
    if saved_click_id is not None:
        click_event_record['id'] = saved_click_id 
        logging.debug(f"DEBUG: Calling index_single_activity_record for click_event_record with ID: {click_event_record.get('id')}") # 新增日志
        try:
            logging.info("尝试将鼠标交互记录 (工作线程) 索引到向量数据库...")
            index_result = index_single_activity_record(click_event_record)
            if index_result:
                logging.info("鼠标交互记录 (工作线程) 已成功索引")
            else:
                logging.warning("鼠标交互记录 (工作线程) 未能成功索引，但已保存")
        except Exception as e:
            logging.error(f"索引鼠标交互记录 (工作线程) 时出错: {e}", exc_info=True)
    else:
        logging.error("鼠标交互记录 (工作线程) 未能保存，也未索引")

def click_processing_worker():
    """工作线程函数，从队列中获取并处理鼠标点击任务。"""
    logging.info("鼠标点击处理工作线程已启动。")
    while True:
        try:
            task_data = click_task_queue.get() # 阻塞直到获取任务
            if task_data is None: # 接收到终止信号
                logging.info("鼠标点击处理工作线程收到终止信号，正在退出。")
                click_task_queue.task_done()
                break
            
            process_click_task(task_data)
            click_task_queue.task_done() # 标记任务完成
        except Exception as e:
            logging.error(f"鼠标点击处理工作线程发生错误: {e}", exc_info=True)
            # 即使发生错误，也应标记任务完成，以避免队列阻塞
            if 'task_data' in locals() and task_data is not None: # 确保 task_done 被调用
                 click_task_queue.task_done()

def handle_mouse_click_activity(x, y, button, pressed):
    """处理鼠标点击事件，将任务放入队列。"""
    global last_mouse_click_screenshot_time
    if not pressed: # 只处理按下事件
        return

    current_time = time.time()
    if current_time - last_mouse_click_screenshot_time < MOUSE_CLICK_CAPTURE_INTERVAL_SECONDS:
        # logging.debug("鼠标点击过于频繁，跳过此次截图")
        return
    last_mouse_click_screenshot_time = current_time
    
    # 只记录信息并放入队列，不在此处执行耗时操作
    logging.info(f"鼠标点击事件已捕获: ({x}, {y}), button: {button}. 将任务放入队列。")
    
    task_data = {
        "x": x,
        "y": y,
        "button": str(button),
        "timestamp": datetime.now().isoformat() # 记录事件发生的时间
    }
    click_task_queue.put(task_data)

def start_mouse_listener():
    """启动pynput鼠标监听器。"""
    global mouse_controller
    try:
        mouse_controller = mouse.Controller() # 初始化一次，供get_mouse_position使用
        logging.info("鼠标控制器初始化成功。")
    except Exception as e:
        logging.error(f"启动时初始化鼠标控制器失败 (可能是Wayland/无头环境): {e}")
        # 即使控制器初始化失败，监听器可能仍然可以工作（取决于环境）
        # 或者 get_mouse_position 将持续返回 None

    logging.info("启动鼠标点击监听器...")
    try:
        # 使用 with 语句确保监听器在线程结束时正确停止
        with mouse.Listener(on_click=handle_mouse_click_activity) as listener:
            listener.join()
    except Exception as e:
        # 特别处理在某些Linux环境下（如Wayland或无X服务器）pynput可能无法启动的问题
        if "DISPLAY environment variable not set" in str(e) or \
           "Wayland" in str(e) or \
           "Xlib" in str(e) or \
           "Failed to connect to X server" in str(e): # 常见错误信息
            logging.error(f"无法启动pynput鼠标监听器 (可能是Wayland或无X服务器环境): {e}")
            logging.error("鼠标点击触发的截图功能将不可用。")
        else:
            logging.error(f"鼠标监听器线程中发生未处理的异常: {e}", exc_info=True)

def main():
    """
    主函数：定期捕获屏幕活动，并启动鼠标监听和点击处理工作线程。
    """
    global last_active_app_name, last_window_title
    
    init_db() # <--- 新增：在程序开始时初始化数据库

    last_active_app_name = None
    last_window_title = None
    
    logging.info("开始屏幕活动记录...")

    # 启动鼠标点击处理工作线程
    worker = threading.Thread(target=click_processing_worker, daemon=True)
    worker.start()
    logging.info("鼠标点击处理工作线程已启动。")

    # 启动鼠标监听线程
    mouse_listener_thread = threading.Thread(target=start_mouse_listener, daemon=True)
    mouse_listener_thread.start()
    logging.info("鼠标监听线程已启动。")

    try:
        while True:
            record_screen_activity(triggered_by="timer")
            time.sleep(CAPTURE_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logging.info("屏幕活动记录已停止。正在通知工作线程退出...")
        click_task_queue.put(None) # 发送终止信号给工作线程
        worker.join(timeout=5) # 等待工作线程处理完剩余任务或超时
        mouse_listener_thread.join(timeout=1) # 等待鼠标监听线程退出
        logging.info("所有线程已退出。")
    except Exception as e:
        logging.error(f"屏幕活动记录过程中发生错误: {e}", exc_info=True)
        # 考虑在发生严重错误时也尝试优雅关闭工作线程
        click_task_queue.put(None)
        worker.join(timeout=5)
        mouse_listener_thread.join(timeout=1)

if __name__ == "__main__":
    main()

    # 提示：请确保Tesseract OCR已正确安装并配置
    # 如果在Windows上，您可能需要取消 pytesseract.pytesseract.tesseract_cmd 的注释并设置为您的Tesseract路径
    # 同时，确保您已下载了 `chi_sim.traineddata` 和 `eng.traineddata` 并将其放入Tesseract的 `tessdata` 目录 