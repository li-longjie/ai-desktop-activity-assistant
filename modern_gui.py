#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 桌面活动助手 - 现代化iOS风格界面
具有拟态玻璃效果和现代化设计
"""

import sys
import os
import asyncio
import threading
import subprocess
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import json

# 设置环境变量来避免DPI警告
if hasattr(sys, 'platform') and sys.platform == 'win32':
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import qtawesome as qta

# 导入现有的核心模块
from activity_retriever import ActivityRetriever, load_and_index_activity_data, get_all_activity_records, get_application_usage_summary
from llm_service import LLMService
from screen_capture import init_db, record_screen_activity
from gui_config import gui_config

# 导入现代化样式库
from modern_ui_styles import *

class AsyncRunner(QObject):
    """异步任务运行器"""
    finished = Signal(object)
    error = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.loop = None
        
    def run_async(self, coro):
        """在新线程中运行异步协程"""
        def run():
            try:
                if self.loop is None:
                    self.loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self.loop)
                
                result = self.loop.run_until_complete(coro)
                self.finished.emit(result)
            except Exception as e:
                self.error.emit(str(e))
        
        thread = threading.Thread(target=run)
        thread.daemon = True
        thread.start()

class ModernChatWidget(GlassCard):
    """现代化聊天界面组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.activity_retriever = None
        self.async_runner = AsyncRunner()
        self.async_runner.finished.connect(self.on_query_finished)
        self.async_runner.error.connect(self.on_query_error)
        self.setup_ui()
        self.setup_retriever()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 标题区域 - 去掉背景框，直接显示
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.robot', color='#007bff').pixmap(28, 28))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("AI 智能助手")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 22px;
                font-weight: bold;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        # 清除按钮
        clear_btn = ModernButton("清除对话", qta.icon('fa5s.trash-alt', color='#dc3545'), "glass")
        clear_btn.clicked.connect(self.clear_history)
        title_layout.addWidget(clear_btn)
        
        layout.addLayout(title_layout)
        
        # 聊天记录区域
        self.chat_scroll = ModernScrollArea()
        self.chat_content = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(15)
        
        self.chat_scroll.setWidget(self.chat_content)
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setMinimumHeight(400)
        layout.addWidget(self.chat_scroll)
        
        # 输入区域 - 去掉背景框，直接使用布局
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(20, 15, 20, 15)
        input_layout.setSpacing(15)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("询问您的活动记录，例如：昨天我用VSCode工作了多长时间？")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(248, 249, 250, 0.8);
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 15px;
                padding: 12px 16px;
                font-size: 14px;
                color: {ModernStyles.COLORS['text_primary']};
            }}
            QLineEdit:focus {{
                border-color: {ModernStyles.COLORS['accent_blue']};
                background: rgba(255, 255, 255, 0.9);
                border-width: 2px;
            }}
            QLineEdit::placeholder {{
                color: {ModernStyles.COLORS['text_secondary']};
            }}
        """)
        self.input_field.returnPressed.connect(self.send_message)
        
        self.send_button = ModernButton("发送", qta.icon('fa5s.paper-plane', color='white'), "primary")
        self.send_button.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        layout.addLayout(input_layout)
        
    def setup_retriever(self):
        """初始化活动检索器"""
        try:
            llm_service = LLMService()
            self.activity_retriever = ActivityRetriever(llm_service=llm_service)
            self.add_message("🤖 AI助手已就绪！您可以询问任何关于您活动记录的问题。", False)
        except Exception as e:
            self.add_message(f"❌ AI功能初始化失败: {e}\n\n您仍然可以使用其他功能查看活动记录和统计数据。", False, is_error=True)
            self.input_field.setEnabled(False)
            self.send_button.setEnabled(False)
            
    def add_message(self, message, is_user=False, is_error=False):
        """添加消息到聊天区域"""
        if is_error:
            bubble = QLabel(message)
            bubble.setWordWrap(True)
            bubble.setStyleSheet(f"""
                QLabel {{
                    background: rgba(220, 53, 69, 0.1);
                    border: 1px solid rgba(220, 53, 69, 0.3);
                    color: {ModernStyles.COLORS['accent_red']};
                    padding: 15px;
                    border-radius: 15px;
                    font-size: 14px;
                }}
            """)
            self.chat_layout.addWidget(bubble)
        else:
            chat_bubble = ChatBubble(message, is_user)
            self.chat_layout.addWidget(chat_bubble)
        
        # 滚动到底部
        QTimer.singleShot(100, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))
        
    def send_message(self):
        """发送消息"""
        if not self.activity_retriever:
            return
            
        question = self.input_field.text().strip()
        if not question:
            return
            
        # 添加用户消息
        self.add_message(question, True)
        self.input_field.clear()
        
        # 禁用输入
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        self.send_button.setText("思考中...")
        
        # 异步查询
        self.async_runner.run_async(self.activity_retriever.retrieve_and_answer(question))
        
    def on_query_finished(self, result):
        """查询完成"""
        if isinstance(result, tuple) and len(result) == 2:
            answer, screenshots = result
            self.add_message(answer, False)
        else:
            self.add_message(str(result), False)
        
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.send_button.setText("发送")
        
    def on_query_error(self, error):
        """查询错误"""
        self.add_message(f"抱歉，处理您的问题时出现了错误：{error}", False, is_error=True)
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.send_button.setText("发送")
        
    def clear_history(self):
        """清除聊天历史"""
        for i in reversed(range(self.chat_layout.count())):
            widget = self.chat_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.add_message("🤖 对话历史已清除，我们重新开始吧！", False)

class ModernStatsWidget(GlassCard):
    """现代化统计页面 - iOS风格"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.async_runner = AsyncRunner()
        self.async_runner.finished.connect(self.on_stats_loaded)
        self.async_runner.error.connect(self.on_stats_error)
        self.setup_ui()
        QTimer.singleShot(500, self.load_today_stats)
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)
        
        # 标题区域 - 去掉背景框
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.chart-line', color='#28a745').pixmap(32, 32))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("屏幕使用时长")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 24px;
                font-weight: bold;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 时间段选择器
        self.tab_widget = ModernTabWidget()
        self.tab_widget.addTab("今天")
        self.tab_widget.addTab("昨天")
        self.tab_widget.addTab("本周")
        self.tab_widget.addTab("本月")
        
        # 连接切换事件
        for i, tab in enumerate(self.tab_widget.tabs):
            tab["button"].clicked.connect(lambda checked, index=i: self.on_period_changed(index))
            
        layout.addWidget(self.tab_widget)
        
        # 总计卡片
        self.total_card = StatsCard(
            "总使用时长", 
            "0小时 0分钟",
            qta.icon('fa5s.clock', color='#30d158'),
            "#30d158"
        )
        layout.addWidget(self.total_card)
        
        # 应用使用列表
        self.app_scroll = ModernScrollArea()
        self.app_container = QWidget()
        self.app_layout = QVBoxLayout(self.app_container)
        self.app_layout.setSpacing(10)
        self.app_layout.setAlignment(Qt.AlignTop)
        
        self.app_scroll.setWidget(self.app_container)
        self.app_scroll.setWidgetResizable(True)
        layout.addWidget(self.app_scroll)
        

    def on_period_changed(self, index):
        """时间段改变"""
        periods = ["today", "yesterday", "week", "month"]
        if index < len(periods):
            self.load_stats(periods[index])
            
    def load_today_stats(self):
        """加载今天的统计"""
        self.load_stats("today")
        
    def load_stats(self, period="today"):
        """加载统计数据"""
        try:
            # 计算时间范围
            end_time = datetime.now()
            if period == "today":
                start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "yesterday":
                start_time = (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                start_time = datetime.now() - timedelta(days=7)
            elif period == "month":
                start_time = datetime.now() - timedelta(days=30)
            else:
                start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 异步调用统计函数
            import asyncio
            async def get_stats():
                return await get_application_usage_summary(start_time, end_time)
            
            # 在新的事件循环中运行
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(get_stats())
                loop.close()
                
                # 转换数据格式
                if "usage" in result:
                    stats_data = []
                    for app_name, duration in result["usage"].items():
                        stats_data.append({
                            "app_name": app_name,
                            "total_time_seconds": int(duration.total_seconds())
                        })
                    # 按使用时长排序
                    stats_data.sort(key=lambda x: x["total_time_seconds"], reverse=True)
                    self.on_stats_loaded(stats_data)
                else:
                    print(f"统计数据格式错误: {result}")
                    
            except Exception as e:
                print(f"异步调用失败: {e}")
                # 回退到空数据
                self.on_stats_loaded([])
                
        except Exception as e:
            print(f"加载统计数据失败: {e}")
            self.on_stats_loaded([])
        
    def on_stats_loaded(self, stats_data):
        """统计数据加载完成"""
        if not stats_data:
            return
            
        # 清除现有的应用卡片
        for i in reversed(range(self.app_layout.count())):
            widget = self.app_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
                
        # 计算总时长
        total_seconds = sum(app.get('total_time_seconds', 0) for app in stats_data)
        total_hours = total_seconds // 3600
        total_minutes = (total_seconds % 3600) // 60
        
        # 更新总计卡片
        # 查找并更新总时长显示
        for child in self.total_card.findChildren(QLabel):
            # 查找显示时间的标签（不是标题）
            if "小时" in child.text() or "分钟" in child.text() or child.text() == "0小时 0分钟":
                child.setText(f"{total_hours}小时 {total_minutes}分钟")
                break
            # 如果没有找到时间标签，查找可能的数值标签
            elif child.text().replace(" ", "").replace("小时", "").replace("分钟", "").isdigit() or child.text() == "0":
                child.setText(f"{total_hours}小时 {total_minutes}分钟")
                break
        
        # 应用图标映射
        app_icons = {
            'Chrome': 'fa5b.chrome',
            'Firefox': 'fa5b.firefox-browser', 
            'Edge': 'fa5b.edge',
            'VSCode': 'fa5s.code',
            'Code': 'fa5s.code',
            'Python': 'fa5b.python',
            'Explorer': 'fa5s.folder-open',
            'Notepad': 'fa5s.edit',
            'Calculator': 'fa5s.calculator',
        }
        
        # 应用颜色映射 - iOS风格
        app_colors = [
            '#007aff', '#30d158', '#ff9500', '#af52de', '#ff2d92',
            '#ff3b30', '#ffcc00', '#32d74b', '#64d2ff', '#bf5af2'
        ]
        
        # 创建应用使用卡片
        for i, app_data in enumerate(stats_data[:10]):  # 显示前10个应用
            app_name = app_data.get('app_name', 'Unknown')
            seconds = app_data.get('total_time_seconds', 0)
            
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            
            if hours > 0:
                time_str = f"{hours}小时 {minutes}分钟"
            else:
                time_str = f"{minutes}分钟"
                
            # 获取图标和颜色
            icon_name = None
            for key, icon in app_icons.items():
                if key.lower() in app_name.lower():
                    icon_name = icon
                    break
                    
            color = app_colors[i % len(app_colors)]
            
            # 计算百分比
            if total_seconds > 0:
                percentage = int((seconds / total_seconds) * 100)
            else:
                percentage = 0
                    
            # 创建应用卡片
            app_card = AppUsageCard(app_name, time_str, icon_name, color, percentage)
            self.app_layout.addWidget(app_card)
            
    def on_stats_error(self, error):
        """统计数据加载错误"""
        print(f"加载统计数据失败: {error}")

class ModernRecordsWidget(GlassCard):
    """现代化记录页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 确保背景正确显示
        self.setStyleSheet(f"""
            ModernRecordsWidget {{
                background: {ModernStyles.COLORS['primary_bg']};
                border: none;
            }}
        """)
        self.setup_ui()
        QTimer.singleShot(500, self.load_records)
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)
        
        # 标题区域
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.history', color='#64ffda').pixmap(32, 32))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("活动记录")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 24px;
                font-weight: bold;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        # 刷新按钮 - 修复图标显示
        refresh_btn = ModernButton("刷新", qta.icon('fa5s.sync-alt', color='#007bff'), "glass")
        refresh_btn.clicked.connect(self.load_records)
        title_layout.addWidget(refresh_btn)
        
        layout.addLayout(title_layout)
        
        # 记录表格容器
        table_container = GlassCard()
        table_container.setStyleSheet(f"""
            GlassCard {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 20px;
            }}
        """)
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        
        # 记录表格
        self.table = QTableWidget()
        self.table.setStyleSheet(ModernStyles.get_table_style())
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(True)
        
        # 设置列
        columns = ["时间", "应用", "窗口标题", "类型", "OCR文本"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # 设置列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 时间列
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 应用列
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # 窗口标题列
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 类型列
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # OCR文本列
        
        # 设置行高
        self.table.verticalHeader().setDefaultSectionSize(45)
        
        # 连接双击事件
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        table_layout.addWidget(self.table)
        layout.addWidget(table_container)
        
    def on_cell_double_clicked(self, row, column):
        """处理单元格双击事件"""
        if column == 4:  # OCR文本列
            self.show_full_ocr_content(row)
    
    def show_full_ocr_content(self, row):
        """显示完整的OCR内容和相关信息"""
        try:
            # 获取当前记录的完整信息
            records = get_all_activity_records(limit=50)
            if row >= len(records):
                return
                
            record = records[row]
            
            # 创建对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("活动详情")
            dialog.setModal(True)
            dialog.resize(800, 600)
            
            # 设置对话框样式
            dialog.setStyleSheet(f"""
                QDialog {{
                    background: {ModernStyles.COLORS['primary_bg']};
                    border-radius: 15px;
                }}
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(30, 30, 30, 30)
            layout.setSpacing(20)
            
            # 标题
            title_label = QLabel("📋 活动记录详情")
            title_label.setStyleSheet(f"""
                QLabel {{
                    color: {ModernStyles.COLORS['text_primary']};
                    font-size: 20px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
            """)
            layout.addWidget(title_label)
            
            # 基本信息卡片
            info_card = GlassCard()
            info_layout = QVBoxLayout(info_card)
            info_layout.setContentsMargins(20, 20, 20, 20)
            info_layout.setSpacing(10)
            
            # 时间信息
            timestamp = record.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    time_str = timestamp
            else:
                time_str = "未知"
            
            info_text = f"""
            <p><strong>🕐 时间:</strong> {time_str}</p>
            <p><strong>📱 应用:</strong> {record.get('app_name', '未知')}</p>
            <p><strong>🪟 窗口标题:</strong> {record.get('window_title', '无')}</p>
            <p><strong>📄 类型:</strong> {record.get('record_type', '未知')}</p>
            """
            
            # 添加URL信息（如果有）
            url = record.get('url', '')
            if url:
                # 限制URL显示长度
                display_url = url if len(url) <= 80 else url[:80] + "..."
                info_text += f'<p><strong>🔗 URL:</strong> <a href="{url}" style="color: #007bff; text-decoration: none;">{display_url}</a></p>'
            
            info_label = QLabel(info_text)
            info_label.setOpenExternalLinks(True)  # 允许点击链接
            info_label.setWordWrap(True)
            info_label.setStyleSheet(f"""
                QLabel {{
                    color: {ModernStyles.COLORS['text_primary']};
                    font-size: 14px;
                    line-height: 1.5;
                    background: transparent;
                    border: none;
                }}
                QLabel a {{
                    color: #007bff;
                    text-decoration: none;
                }}
                QLabel a:hover {{
                    color: #0056b3;
                    text-decoration: underline;
                }}
            """)
            info_layout.addWidget(info_label)
            layout.addWidget(info_card)
            
            # OCR文本内容
            ocr_label = QLabel("📝 OCR识别内容:")
            ocr_label.setStyleSheet(f"""
                QLabel {{
                    color: {ModernStyles.COLORS['text_primary']};
                    font-size: 16px;
                    font-weight: 600;
                    margin-top: 10px;
                }}
            """)
            layout.addWidget(ocr_label)
            
            # OCR文本显示区域
            ocr_text_edit = QTextEdit()
            ocr_text = record.get('ocr_text', '无OCR内容')
            ocr_text_edit.setPlainText(ocr_text)
            ocr_text_edit.setReadOnly(True)
            ocr_text_edit.setStyleSheet(f"""
                QTextEdit {{
                    background: {ModernStyles.COLORS['glass_bg']};
                    border: 1px solid {ModernStyles.COLORS['glass_border']};
                    border-radius: 10px;
                    color: {ModernStyles.COLORS['text_primary']};
                    font-size: 13px;
                    padding: 15px;
                    line-height: 1.4;
                }}
            """)
            layout.addWidget(ocr_text_edit)
            
            # 按钮区域
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            
            # 复制按钮
            copy_btn = ModernButton("📋 复制OCR内容", qta.icon('fa5s.copy', color='#007bff'), "glass")
            copy_btn.clicked.connect(lambda: self.copy_to_clipboard(ocr_text))
            button_layout.addWidget(copy_btn)
            
            # 关闭按钮
            close_btn = ModernButton("关闭", qta.icon('fa5s.times', color='#dc3545'), "glass")
            close_btn.clicked.connect(dialog.accept)
            button_layout.addWidget(close_btn)
            
            layout.addLayout(button_layout)
            
            # 显示对话框
            dialog.exec()
            
        except Exception as e:
            print(f"显示OCR详情失败: {e}")
    
    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            print("OCR内容已复制到剪贴板")
        except Exception as e:
            print(f"复制失败: {e}")

    def load_records(self, silent=False):
        """加载记录数据"""
        try:
            # 清空现有数据
            self.table.setRowCount(0)
            
            # 重新加载数据
            records = get_all_activity_records(limit=50)
            self.table.setRowCount(len(records))
            
            if not silent:
                print(f"📋 加载了 {len(records)} 条记录")  # 调试信息
            
            # 应用图标映射
            app_icons = {
                'chrome': 'fa5b.chrome',
                'firefox': 'fa5b.firefox-browser',
                'edge': 'fa5b.edge',
                'vscode': 'fa5s.code',
                'code': 'fa5s.code',
                'cursor': 'fa5s.code',
                'python': 'fa5b.python',
                'explorer': 'fa5s.folder-open',
                'notepad': 'fa5s.edit',
                'calculator': 'fa5s.calculator',
                'cmd': 'fa5s.terminal',
                'powershell': 'fa5s.terminal',
            }
            
            # 类型颜色映射
            type_colors = {
                'screen_content': '#28a745',
                'window_change': '#17a2b8',
                'app_usage': '#fd7e14',
                'default': '#6c757d'
            }
            
            for row, record in enumerate(records):
                # 时间列
                timestamp = record.get('timestamp', '')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime('%H:%M:%S')
                    except:
                        time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                else:
                    time_str = "未知"
                
                time_item = QTableWidgetItem(time_str)
                time_item.setTextAlignment(Qt.AlignCenter)
                time_item.setForeground(QColor('#6c757d'))
                self.table.setItem(row, 0, time_item)
                
                # 应用列
                app_name = record.get('app_name', 'Unknown')
                
                # 查找应用图标，添加到应用名称前
                icon_text = ""
                for key, icon in app_icons.items():
                    if key.lower() in app_name.lower():
                        icon_text = "📱 " if key == 'python' else "💻 " if key in ['cursor', 'vscode', 'code'] else "🌐 " if key in ['chrome', 'firefox', 'edge'] else "📁 " if key == 'explorer' else "⚡ "
                        break
                
                app_item = QTableWidgetItem(f"{icon_text}{app_name}")
                app_item.setForeground(QColor(ModernStyles.COLORS['text_primary']))
                self.table.setItem(row, 1, app_item)
                
                # 窗口标题列
                window_title = record.get('window_title', '')
                if len(window_title) > 60:
                    window_title = window_title[:60] + "..."
                
                title_item = QTableWidgetItem(window_title)
                title_item.setToolTip(record.get('window_title', ''))  # 完整标题作为工具提示
                self.table.setItem(row, 2, title_item)
                
                # 类型列 - 添加颜色标识
                record_type = record.get('record_type', '')
                type_color = type_colors.get(record_type, type_colors['default'])
                
                # 添加圆点前缀表示类型
                type_indicator = "🟢" if record_type == 'screen_content' else "🔵" if record_type == 'window_change' else "🟠" if record_type == 'app_usage' else "⚪"
                
                type_item = QTableWidgetItem(f"{type_indicator} {record_type}")
                type_item.setForeground(QColor(type_color))
                self.table.setItem(row, 3, type_item)
                
                # OCR文本列
                ocr_text = record.get('ocr_text', '')
                if len(ocr_text) > 100:
                    ocr_text = ocr_text[:100] + "..."
                
                ocr_item = QTableWidgetItem(ocr_text)
                
                # 构建工具提示，包含完整OCR文本和URL信息
                tooltip_parts = []
                
                # 添加完整OCR文本
                full_ocr = record.get('ocr_text', '')
                if full_ocr:
                    tooltip_parts.append(f"OCR内容:\n{full_ocr}")
                
                # 添加URL信息（如果有）
                url = record.get('url', '')
                if url:
                    tooltip_parts.append(f"\n🔗 网页URL:\n{url}")
                
                # 添加双击提示
                tooltip_parts.append("\n💡 双击此单元格查看完整详情")
                
                tooltip_text = "\n".join(tooltip_parts) if tooltip_parts else "无内容"
                ocr_item.setToolTip(tooltip_text)
                ocr_item.setForeground(QColor('#6c757d'))
                self.table.setItem(row, 4, ocr_item)
            
            # 强制刷新表格显示
            self.table.viewport().repaint()
            self.table.viewport().update()
                
        except Exception as e:
            print(f"加载记录失败: {e}")

class ModernAboutWidget(GlassCard):
    """关于应用页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(30)
        
        # 标题区域
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.info-circle', color='#007aff').pixmap(32, 32))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("关于应用")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 24px;
                font-weight: bold;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 应用信息卡片
        info_card = GlassCard()
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(30, 30, 30, 30)
        info_layout.setSpacing(20)
        
        # 应用Logo和名称
        logo_layout = QHBoxLayout()
        logo_icon = QLabel()
        logo_icon.setPixmap(qta.icon('fa5s.desktop', color='#007aff').pixmap(64, 64))
        logo_icon.setStyleSheet("background: transparent; border: none;")
        logo_layout.addWidget(logo_icon)
        
        app_info_layout = QVBoxLayout()
        app_name = QLabel("屏幕智能助手")
        app_name.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 28px;
                font-weight: bold;
            }}
        """)
        
        app_version = QLabel("版本 v1.0")
        app_version.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_secondary']};
                font-size: 16px;
                margin-top: 5px;
            }}
        """)
        
        app_info_layout.addWidget(app_name)
        app_info_layout.addWidget(app_version)
        app_info_layout.addStretch()
        
        logo_layout.addLayout(app_info_layout)
        logo_layout.addStretch()
        info_layout.addLayout(logo_layout)
        
        # 描述信息
        description = QLabel("基于AI的智能桌面活动记录分析系统")
        description.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: 500;
                margin: 20px 0;
            }}
        """)
        info_layout.addWidget(description)
        
        # 功能特性
        features_title = QLabel("🚀 主要功能")
        features_title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: 600;
                margin-top: 20px;
                margin-bottom: 10px;
            }}
        """)
        info_layout.addWidget(features_title)
        
        features_text = """
        <div style='color: #6c757d; font-size: 14px; line-height: 1.8;'>
        <p style='margin: 8px 0;'>📸 <strong>自动屏幕截图和OCR文本识别</strong><br/>
        &nbsp;&nbsp;&nbsp;&nbsp;智能捕获屏幕内容，提取文本信息</p>
        
        <p style='margin: 8px 0;'>🤖 <strong>AI驱动的自然语言查询</strong><br/>
        &nbsp;&nbsp;&nbsp;&nbsp;使用自然语言查询您的活动历史</p>
        
        <p style='margin: 8px 0;'>📊 <strong>应用使用时长统计</strong><br/>
        &nbsp;&nbsp;&nbsp;&nbsp;详细的使用时间分析和可视化</p>
        
        <p style='margin: 8px 0;'>🔗 <strong>网页URL自动识别</strong><br/>
        &nbsp;&nbsp;&nbsp;&nbsp;自动记录浏览器访问的网页地址</p>
        
        <p style='margin: 8px 0;'>🔍 <strong>智能活动记录搜索</strong><br/>
        &nbsp;&nbsp;&nbsp;&nbsp;快速检索和查看详细活动信息</p>
        </div>
        """
        
        features_label = QLabel(features_text)
        features_label.setWordWrap(True)
        features_label.setStyleSheet("background: transparent; border: none;")
        info_layout.addWidget(features_label)
        
        # 技术信息
        tech_title = QLabel("⚙️ 技术信息")
        tech_title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: 600;
                margin-top: 20px;
                margin-bottom: 10px;
            }}
        """)
        info_layout.addWidget(tech_title)
        
        tech_text = """
        <div style='color: #6c757d; font-size: 14px; line-height: 1.6;'>
        <p style='margin: 5px 0;'><strong>界面框架:</strong> PySide6 (Qt6)</p>
        <p style='margin: 5px 0;'><strong>OCR引擎:</strong> Tesseract-OCR</p>
        <p style='margin: 5px 0;'><strong>AI模型:</strong> 支持多种LLM API</p>
        <p style='margin: 5px 0;'><strong>数据存储:</strong> SQLite + ChromaDB</p>
        <p style='margin: 5px 0;'><strong>开发语言:</strong> Python 3.8+</p>
        </div>
        """
        
        tech_label = QLabel(tech_text)
        tech_label.setWordWrap(True)
        tech_label.setStyleSheet("background: transparent; border: none;")
        info_layout.addWidget(tech_label)
        
        layout.addWidget(info_card)
        layout.addStretch()

class ModernSettingsWidget(GlassCard):
    """现代化设置页面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: rgba(248, 249, 250, 0.8);
                width: 8px;
                border-radius: 4px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {ModernStyles.COLORS['accent_blue']};
                border-radius: 4px;
                min-height: 20px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 123, 255, 0.8);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)
        
        # 滚动内容容器
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(30, 30, 30, 30)
        scroll_layout.setSpacing(30)
        
        # 标题
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.cogs', color='#007aff').pixmap(32, 32))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("设置")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 24px;
                font-weight: bold;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        scroll_layout.addLayout(title_layout)
        
        # 设置卡片
        self.create_refresh_settings(scroll_layout)
        self.create_path_settings(scroll_layout)
        self.create_api_settings(scroll_layout)
        self.create_data_settings(scroll_layout)
        self.create_screen_settings(scroll_layout)
        
        scroll_layout.addStretch()
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
    def create_refresh_settings(self, parent_layout):
        """创建刷新设置"""
        card = GlassCard()
        card.setFixedHeight(150)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)
        
        # 标题
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.sync-alt', color='#007aff').pixmap(24, 24))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("自动刷新设置")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: 600;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 开关和间隔设置
        controls_layout = QHBoxLayout()
        
        self.auto_refresh_cb = QCheckBox("启用自动刷新")
        self.auto_refresh_cb.setChecked(gui_config.get('ui.auto_refresh', True))
        self.auto_refresh_cb.setStyleSheet(f"""
            QCheckBox {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 14px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid rgba(255, 255, 255, 0.3);
            }}
            QCheckBox::indicator:checked {{
                background: {ModernStyles.COLORS['gradient_accent']};
                border-color: #64ffda;
            }}
        """)
        controls_layout.addWidget(self.auto_refresh_cb)
        
        interval_label = QLabel("间隔:")
        interval_label.setStyleSheet("background: transparent; border: none; color: #1a1a1a; font-size: 16px; font-weight: 500;")
        controls_layout.addWidget(interval_label)
        
        # 创建完全对称的间隔控制器
        interval_container = QWidget()
        interval_layout = QHBoxLayout(interval_container)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.setSpacing(0)
        
        # 减少按钮
        self.decrease_btn = QPushButton("-")
        self.decrease_btn.setFixedSize(32, 32)
        self.decrease_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-top-left-radius: 16px;
                border-bottom-left-radius: 16px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-right: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {ModernStyles.COLORS['accent_blue']};
                color: white;
            }}
        """)
        
        # 数值显示区域（组合输入框和单位）
        self.interval_value = gui_config.get('ui.refresh_interval', 30)
        value_container = QWidget()
        value_container.setFixedSize(70, 32)
        value_container.setStyleSheet(f"""
            QWidget {{
                background: {ModernStyles.COLORS['glass_bg']};
                border-top: 1px solid {ModernStyles.COLORS['glass_border']};
                border-bottom: 1px solid {ModernStyles.COLORS['glass_border']};
            }}
        """)
        
        value_layout = QHBoxLayout(value_container)
        value_layout.setContentsMargins(2, 0, 2, 0)
        value_layout.setSpacing(2)
        
        self.interval_input = QLineEdit(str(self.interval_value))
        self.interval_input.setFixedSize(35, 28)
        self.interval_input.setAlignment(Qt.AlignCenter)
        self.interval_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #1a1a1a;
                font-size: 14px;
                font-weight: 600;
            }
        """)
        self.interval_input.editingFinished.connect(self.on_interval_changed)
        
        seconds_label = QLabel("秒")
        seconds_label.setFixedSize(25, 28)
        seconds_label.setAlignment(Qt.AlignCenter)
        seconds_label.setStyleSheet("background: transparent; border: none; color: #6c757d; font-size: 12px;")
        
        value_layout.addWidget(self.interval_input)
        value_layout.addWidget(seconds_label)
        
        # 增加按钮
        self.increase_btn = QPushButton("+")
        self.increase_btn.setFixedSize(32, 32)
        self.increase_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 16px;
                border-bottom-right-radius: 16px;
                border-left: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {ModernStyles.COLORS['accent_blue']};
                color: white;
            }}
        """)
        
        # 连接事件
        self.decrease_btn.clicked.connect(self.decrease_interval)
        self.increase_btn.clicked.connect(self.increase_interval)
        
        interval_layout.addWidget(self.decrease_btn)
        interval_layout.addWidget(value_container)
        interval_layout.addWidget(self.increase_btn)
        
        controls_layout.addWidget(interval_container)
        
        controls_layout.addStretch()
        
        # 立即刷新按钮
        refresh_btn = ModernButton("立即刷新", qta.icon('fa5s.sync-alt', color='white'))
        refresh_btn.clicked.connect(self.manual_refresh)
        controls_layout.addWidget(refresh_btn)
        
        layout.addLayout(controls_layout)
        parent_layout.addWidget(card)
        
    def create_path_settings(self, parent_layout):
        """创建路径设置"""
        card = GlassCard()
        card.setFixedHeight(180)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)
        
        # 标题
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.folder', color='#007aff').pixmap(24, 24))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("保存路径设置")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: 600;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 数据目录设置
        data_dir_layout = QHBoxLayout()
        data_dir_label = QLabel("数据库保存位置:")
        data_dir_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 14px;
                font-weight: 500;
                min-width: 120px;
            }}
        """)
        data_dir_layout.addWidget(data_dir_label)
        
        current_data_dir = gui_config.get('paths.data_directory', '当前目录')
        if not current_data_dir:
            current_data_dir = '当前目录'
        
        self.data_dir_display = QLabel(current_data_dir)
        self.data_dir_display.setStyleSheet(f"""
            QLabel {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 8px;
                padding: 8px 12px;
                color: {ModernStyles.COLORS['text_secondary']};
                font-size: 14px;
            }}
        """)
        data_dir_layout.addWidget(self.data_dir_display, 1)
        
        select_data_btn = QPushButton("浏览")
        select_data_btn.setFixedSize(60, 32)
        select_data_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ModernStyles.COLORS['accent_blue']};
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(0, 123, 255, 0.8);
            }}
        """)
        select_data_btn.clicked.connect(self.select_data_directory)
        data_dir_layout.addWidget(select_data_btn)
        
        layout.addLayout(data_dir_layout)
        
        # 截图目录设置
        screenshot_dir_layout = QHBoxLayout()
        screenshot_dir_label = QLabel("截图保存路径:")
        screenshot_dir_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 14px;
                font-weight: 500;
                min-width: 120px;
            }}
        """)
        screenshot_dir_layout.addWidget(screenshot_dir_label)
        
        current_screenshot_dir = gui_config.get('paths.screenshot_directory', 'screen_recordings')
        self.screenshot_dir_display = QLabel(current_screenshot_dir)
        self.screenshot_dir_display.setStyleSheet(f"""
            QLabel {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 8px;
                padding: 8px 12px;
                color: {ModernStyles.COLORS['text_secondary']};
                font-size: 14px;
            }}
        """)
        screenshot_dir_layout.addWidget(self.screenshot_dir_display, 1)
        
        select_screenshot_btn = QPushButton("浏览")
        select_screenshot_btn.setFixedSize(60, 32)
        select_screenshot_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ModernStyles.COLORS['accent_blue']};
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(0, 123, 255, 0.8);
            }}
        """)
        select_screenshot_btn.clicked.connect(self.select_screenshot_directory)
        screenshot_dir_layout.addWidget(select_screenshot_btn)
        
        layout.addLayout(screenshot_dir_layout)
        
        parent_layout.addWidget(card)
        
    def create_api_settings(self, parent_layout):
        """创建API设置"""
        card = GlassCard()
        card.setFixedHeight(280)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)
        
        # 标题
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.code', color='#1f1f1f').pixmap(24, 24))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("硅基流动API设置")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: 600;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # API密钥输入
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API密钥:")
        api_key_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 14px;
                font-weight: 500;
                min-width: 80px;
            }}
        """)
        api_key_layout.addWidget(api_key_label)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("请输入硅基流动API密钥")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        # 先尝试从gui_config读取，如果为空则从config.py读取
        api_key_from_gui = gui_config.get('api.siliconflow_key', '')
        if not api_key_from_gui:
            try:
                from config import APIConfig
                api_key_from_gui = APIConfig.QWEN_API_KEY or APIConfig.DEEPSEEK_API_KEY or ''
                # 如果从config.py读取到了密钥，保存到gui_config中
                if api_key_from_gui:
                    gui_config.set('api.siliconflow_key', api_key_from_gui)
                    gui_config.save_settings()
            except ImportError:
                pass
        
        self.api_key_input.setText(api_key_from_gui)
        self.api_key_input.setStyleSheet(f"""
            QLineEdit {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 8px;
                padding: 8px 12px;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {ModernStyles.COLORS['accent_blue']};
            }}
        """)
        api_key_layout.addWidget(self.api_key_input)
        
        # 显示/隐藏密钥按钮
        toggle_btn = QPushButton("👁")
        toggle_btn.setFixedSize(32, 32)
        toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 8px;
                color: {ModernStyles.COLORS['text_secondary']};
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {ModernStyles.COLORS['accent_blue']};
                color: white;
            }}
        """)
        toggle_btn.clicked.connect(self.toggle_api_key_visibility)
        api_key_layout.addWidget(toggle_btn)
        
        layout.addLayout(api_key_layout)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_label = QLabel("默认模型:")
        model_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 14px;
                font-weight: 500;
                min-width: 80px;
            }}
        """)
        model_layout.addWidget(model_label)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "Qwen/Qwen2.5-VL-72B-Instruct",
            "deepseek-ai/DeepSeek-V3",
            "Qwen/Qwen2.5-72B-Instruct",
            "meta-llama/Llama-3.1-70B-Instruct"
        ])
        # 先尝试从gui_config读取模型，如果为空则从config.py读取
        current_model = gui_config.get('api.default_model', '')
        if not current_model:
            try:
                from config import APIConfig
                current_model = APIConfig.QWEN_MODEL or APIConfig.DEEPSEEK_MODEL or 'Qwen/Qwen2.5-VL-72B-Instruct'
                # 如果从config.py读取到了模型，保存到gui_config中
                if current_model:
                    gui_config.set('api.default_model', current_model)
                    gui_config.save_settings()
            except ImportError:
                current_model = 'Qwen/Qwen2.5-VL-72B-Instruct'
        
        # 如果在下拉框中找到该模型，则选中它
        index = self.model_combo.findText(current_model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        else:
            # 如果没找到，添加到下拉框并选中
            self.model_combo.addItem(current_model)
            self.model_combo.setCurrentText(current_model)
        
        self.model_combo.setStyleSheet(f"""
            QComboBox {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 8px;
                padding: 8px 12px;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 14px;
            }}
            QComboBox:focus {{
                border: 2px solid {ModernStyles.COLORS['accent_blue']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
        """)
        model_layout.addWidget(self.model_combo)
        
        layout.addLayout(model_layout)
        
        # 按钮布局
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        save_btn = ModernButton("保存设置", qta.icon('fa5s.save', color='white'))
        save_btn.clicked.connect(self.save_api_settings)
        buttons_layout.addWidget(save_btn)
        
        test_btn = ModernButton("测试连接", qta.icon('fa5s.plug', color='#007aff'), "glass")
        test_btn.clicked.connect(self.test_api_connection)
        buttons_layout.addWidget(test_btn)
        
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
        parent_layout.addWidget(card)
        
    def create_data_settings(self, parent_layout):
        """创建数据设置"""
        card = GlassCard()
        card.setFixedHeight(120)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)
        
        # 标题
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.database', color='#007aff').pixmap(24, 24))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("数据管理")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: 600;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 按钮布局
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        load_btn = ModernButton("重新加载数据", qta.icon('fa5s.database', color='white'))
        load_btn.clicked.connect(self.load_data)
        buttons_layout.addWidget(load_btn)
        
        clear_btn = ModernButton("清空数据", qta.icon('fa5s.trash', color='#ff3b30'), "glass")
        clear_btn.clicked.connect(self.clear_data)
        clear_btn.setStyleSheet(f"""
            ModernButton {{
                background: rgba(255, 59, 48, 0.1);
                border: 1px solid rgba(255, 59, 48, 0.3);
                border-radius: 12px;
                color: #ff3b30;
                font-weight: 600;
                font-size: 14px;
                padding: 12px 24px;
            }}
            ModernButton:hover {{
                background: rgba(255, 59, 48, 0.2);
                border: 1px solid rgba(255, 59, 48, 0.5);
            }}
        """)
        buttons_layout.addWidget(clear_btn)
        
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
        parent_layout.addWidget(card)
        
    def create_screen_settings(self, parent_layout):
        """创建屏幕录制设置"""
        card = GlassCard()
        card.setFixedHeight(180)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)
        
        # 标题
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon('fa5s.video', color='#007aff').pixmap(24, 24))
        title_icon.setStyleSheet("background: transparent; border: none;")
        title_layout.addWidget(title_icon)
        
        title = QLabel("屏幕录制")
        title.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: 600;
                margin-left: 10px;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        
        # 录制控制按钮行
        recording_controls = QHBoxLayout()
        recording_controls.setSpacing(15)
        
        # 开始录制按钮
        self.start_recording_btn = ModernButton("启动录制", qta.icon('fa5s.play', color='#30d158'), "glass")
        self.start_recording_btn.clicked.connect(self.start_recording)
        recording_controls.addWidget(self.start_recording_btn)
        
        # 停止录制按钮
        self.stop_recording_btn = ModernButton("停止录制", qta.icon('fa5s.stop', color='#ff3b30'), "glass")
        self.stop_recording_btn.clicked.connect(self.stop_recording)
        self.stop_recording_btn.setEnabled(False)  # 初始状态禁用
        recording_controls.addWidget(self.stop_recording_btn)
        
        recording_controls.addStretch()
        
        layout.addLayout(recording_controls)
        
        # 录制状态显示
        self.recording_status = QLabel("📴 屏幕录制未激活")
        self.recording_status.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_secondary']};
                font-size: 14px;
                padding: 10px;
            }}
        """)
        layout.addWidget(self.recording_status)
        
        # 根据配置初始化录制状态
        self.init_recording_state()
        
        parent_layout.addWidget(card)
    
    def init_recording_state(self):
        """初始化录制状态"""
        auto_start = gui_config.get('capture.auto_start', True)
        if auto_start:
            self.start_recording_btn.setEnabled(False)
            self.stop_recording_btn.setEnabled(True)
            self.recording_status.setText("🔴 屏幕录制已激活")
            self.recording_status.setStyleSheet(f"""
                QLabel {{
                    background: transparent;
                    border: none;
                    color: {ModernStyles.COLORS['accent_green']};
                    font-size: 14px;
                    padding: 10px;
                }}
            """)
        else:
            self.start_recording_btn.setEnabled(True)
            self.stop_recording_btn.setEnabled(False)
            self.recording_status.setText("📴 屏幕录制未激活")
            self.recording_status.setStyleSheet(f"""
                QLabel {{
                    background: transparent;
                    border: none;
                    color: {ModernStyles.COLORS['text_secondary']};
                    font-size: 14px;
                    padding: 10px;
                }}
            """)
        
    def decrease_interval(self):
        """减少间隔"""
        if self.interval_value > 10:
            self.interval_value -= 10
            self.interval_input.setText(str(self.interval_value))
            gui_config.set('ui.refresh_interval', self.interval_value)
            gui_config.save_settings()
            
    def increase_interval(self):
        """增加间隔"""
        if self.interval_value < 300:
            self.interval_value += 10
            self.interval_input.setText(str(self.interval_value))
            gui_config.set('ui.refresh_interval', self.interval_value)
            gui_config.save_settings()
            
    def on_interval_changed(self):
        """手动输入间隔改变"""
        try:
            value = int(self.interval_input.text())
            if 10 <= value <= 300:
                self.interval_value = value
                gui_config.set('ui.refresh_interval', self.interval_value)
                gui_config.save_settings()
            else:
                # 如果超出范围，恢复原值
                self.interval_input.setText(str(self.interval_value))
                QMessageBox.warning(self, "提示", "间隔时间必须在10-300秒之间")
        except ValueError:
            # 如果输入无效，恢复原值
            self.interval_input.setText(str(self.interval_value))
            QMessageBox.warning(self, "提示", "请输入有效的数字")

    def manual_refresh(self):
        """手动刷新"""
        try:
            main_window = self.get_main_window()
            if main_window and hasattr(main_window, 'auto_refresh_data'):
                main_window.auto_refresh_data()
                QMessageBox.information(self, "成功", "数据已刷新！")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"刷新失败: {e}")
            
    def load_data(self):
        """加载数据"""
        try:
            count = load_and_index_activity_data()
            QMessageBox.information(self, "成功", f"已加载 {count} 条新记录到向量数据库")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载数据失败: {e}")
            
    def clear_data(self):
        """清空数据"""
        reply = QMessageBox.question(
            self, "确认", 
            "确定要清空所有数据吗？此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, "提示", "数据清空功能待实现")
            
    def start_recording(self):
        """开始屏幕录制"""
        try:
            # 保存录制状态到配置
            gui_config.set('capture.auto_start', True)
            gui_config.save_settings()
            
            # 获取主窗口并启动录制服务
            main_window = self.get_main_window()
            if main_window and hasattr(main_window, 'setup_screen_recording'):
                main_window.setup_screen_recording()
            
            # 更新UI状态
            self.start_recording_btn.setEnabled(False)
            self.stop_recording_btn.setEnabled(True)
            self.recording_status.setText("🔴 屏幕录制已激活")
            self.recording_status.setStyleSheet(f"""
                QLabel {{
                    background: transparent;
                    border: none;
                    color: {ModernStyles.COLORS['accent_green']};
                    font-size: 14px;
                    padding: 10px;
                }}
            """)
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"启动录制失败: {e}")
            
    def stop_recording(self):
        """停止屏幕录制"""
        try:
            # 保存录制状态到配置
            gui_config.set('capture.auto_start', False)
            gui_config.save_settings()
            
            # 获取主窗口并停止录制服务
            main_window = self.get_main_window()
            if main_window and hasattr(main_window, 'stop_screen_recording'):
                main_window.stop_screen_recording()
            
            # 更新UI状态
            self.start_recording_btn.setEnabled(True)
            self.stop_recording_btn.setEnabled(False)
            self.recording_status.setText("📴 屏幕录制未激活")
            self.recording_status.setStyleSheet(f"""
                QLabel {{
                    color: {ModernStyles.COLORS['text_secondary']};
                    font-size: 14px;
                    padding: 10px;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 10px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }}
            """)
            
            QMessageBox.information(self, "成功", "屏幕录制已停止")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"停止录制失败: {e}")
            
    def get_main_window(self):
        """获取主窗口引用"""
        widget = self
        while widget is not None:
            if isinstance(widget, QMainWindow):
                return widget
            widget = widget.parent()
        return None
        
    def select_data_directory(self):
        """选择数据目录"""
        from PySide6.QtWidgets import QFileDialog
        
        current_dir = gui_config.get('paths.data_directory', os.getcwd())
        if not current_dir:
            current_dir = os.getcwd()
            
        directory = QFileDialog.getExistingDirectory(
            self, 
            "选择数据存储目录", 
            current_dir
        )
        
        if directory:
            gui_config.set('paths.data_directory', directory)
            gui_config.save_settings()
            self.data_dir_display.setText(directory)
            QMessageBox.information(self, "成功", f"数据目录已设置为:\n{directory}")
            
    def select_screenshot_directory(self):
        """选择截图目录"""
        from PySide6.QtWidgets import QFileDialog
        
        current_dir = gui_config.get('paths.screenshot_directory', 'screen_recordings')
        if not os.path.isabs(current_dir):
            current_dir = os.path.join(os.getcwd(), current_dir)
            
        directory = QFileDialog.getExistingDirectory(
            self, 
            "选择截图保存目录", 
            current_dir
        )
        
        if directory:
            gui_config.set('paths.screenshot_directory', directory)
            gui_config.save_settings()
            self.screenshot_dir_display.setText(directory)
            QMessageBox.information(self, "成功", f"截图目录已设置为:\n{directory}")
            
    def select_api_key_file(self):
        """选择API密钥文件"""
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择API密钥文件",
            "",
            "环境变量文件 (*.env);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 简单解析.env格式的文件
                api_keys = {}
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        api_keys[key.strip()] = value.strip().strip('"\'')
                
                # 保存API密钥配置
                gui_config.set('api.keys', api_keys)
                gui_config.set('api.key_file_path', file_path)
                gui_config.save_settings()
                
                QMessageBox.information(
                    self, "成功", 
                    f"API密钥文件已加载:\n{file_path}\n\n找到 {len(api_keys)} 个配置项"
                )
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取API密钥文件失败:\n{e}")
                
    def clear_api_key(self):
        """清空API密钥"""
        reply = QMessageBox.question(
            self, "确认", 
            "确定要清空所有API密钥配置吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            gui_config.set('api.keys', {})
            gui_config.set('api.key_file_path', '')
            gui_config.save_settings()
            QMessageBox.information(self, "成功", "API密钥配置已清空")
            
    def toggle_api_key_visibility(self):
        """切换API密钥可见性"""
        if self.api_key_input.echoMode() == QLineEdit.Password:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            
    def save_api_settings(self):
        """保存API设置"""
        api_key = self.api_key_input.text().strip()
        model = self.model_combo.currentText()
        
        if not api_key:
            QMessageBox.warning(self, "警告", "请输入API密钥")
            return
            
        # 保存设置
        gui_config.set('api.siliconflow_key', api_key)
        gui_config.set('api.default_model', model)
        gui_config.save_settings()
        
        # 更新config.py中的配置
        try:
            from config import APIConfig
            APIConfig.QWEN_API_KEY = api_key
            APIConfig.DEEPSEEK_API_KEY = api_key
            APIConfig.QWEN_MODEL = model
            APIConfig.DEEPSEEK_MODEL = model
        except ImportError:
            pass
            
        QMessageBox.information(self, "成功", "API设置已保存")
        
    def test_api_connection(self):
        """测试API连接"""
        api_key = self.api_key_input.text().strip()
        model = self.model_combo.currentText()
        
        if not api_key:
            QMessageBox.warning(self, "警告", "请先输入API密钥")
            return
            
        # 创建测试对话框
        test_dialog = QDialog(self)
        test_dialog.setWindowTitle("测试API连接")
        test_dialog.setFixedSize(400, 200)
        test_dialog.setStyleSheet(f"""
            QDialog {{
                background: {ModernStyles.COLORS['primary_bg']};
                border-radius: 15px;
            }}
        """)
        
        layout = QVBoxLayout(test_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 状态标签
        status_label = QLabel("正在测试API连接...")
        status_label.setStyleSheet(f"""
            QLabel {{
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 14px;
                font-weight: 500;
            }}
        """)
        layout.addWidget(status_label)
        
        # 进度条
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 0)  # 无限进度条
        progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 8px;
                background: {ModernStyles.COLORS['glass_bg']};
                text-align: center;
                color: {ModernStyles.COLORS['text_primary']};
            }}
            QProgressBar::chunk {{
                background: {ModernStyles.COLORS['accent_blue']};
                border-radius: 7px;
            }}
        """)
        layout.addWidget(progress_bar)
        
        # 关闭按钮
        close_btn = ModernButton("关闭", qta.icon('fa5s.times', color='white'), "glass")
        close_btn.clicked.connect(test_dialog.close)
        close_btn.setEnabled(False)
        layout.addWidget(close_btn)
        
        test_dialog.show()
        
        # 异步测试API
        def test_api():
            try:
                import requests
                import json
                
                url = "https://api.siliconflow.cn/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 10
                }
                
                response = requests.post(url, headers=headers, json=data, timeout=10)
                
                if response.status_code == 200:
                    status_label.setText("✅ API连接测试成功！")
                    progress_bar.setRange(0, 1)
                    progress_bar.setValue(1)
                else:
                    status_label.setText(f"❌ API连接失败: {response.status_code}")
                    progress_bar.setRange(0, 1)
                    progress_bar.setValue(0)
                    
            except Exception as e:
                status_label.setText(f"❌ 连接错误: {str(e)}")
                progress_bar.setRange(0, 1)
                progress_bar.setValue(0)
                
            close_btn.setEnabled(True)
            
        # 在单独线程中运行测试
        import threading
        threading.Thread(target=test_api, daemon=True).start()

class ModernMainWindow(QMainWindow):
    """现代化主窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("屏幕智能助手")
        self.setWindowIcon(qta.icon('fa5s.desktop'))
        
        # 设置标准窗口样式，支持调整大小
        self.setWindowFlags(Qt.Window)
        # 设置最小窗口大小
        self.setMinimumSize(1000, 700)
        
        # 加载窗口几何信息
        geometry = gui_config.get_window_geometry()
        self.resize(geometry['width'], geometry['height'])
        self.move(geometry['x'], geometry['y'])
        if geometry['maximized']:
            self.showMaximized()
        
        # 设置窗口样式
        self.setStyleSheet(ModernStyles.get_main_window_style() + f"""
            QToolTip {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 8px;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 12px;
                padding: 8px 12px;
                max-width: 400px;
            }}
        """)
        
        # 移除了自定义拖拽功能，使用系统标题栏
        
        self.setup_ui()
        self.setup_tray()
        
        # 初始化数据库
        init_db()
        
        # 设置自动刷新
        self.setup_auto_refresh()
        
        # 根据设置决定是否启动屏幕录制
        if gui_config.get('capture.auto_start', True):
            self.setup_screen_recording()
        
    # 移除了自定义拖拽事件，使用系统标题栏处理窗口移动
        
    def setup_ui(self):
        """设置UI"""
        central_widget = QWidget()
        central_widget.setStyleSheet("background: transparent;")
        self.setCentralWidget(central_widget)
        
        # 主布局直接包含内容，不添加标题栏
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 内容区域
        content_widget = QWidget()
        content_widget.setStyleSheet(f"""
            QWidget {{
                background: {ModernStyles.COLORS['primary_bg']};
                border: none;
            }}
        """)
        
        # 内容区域的主布局
        content_main_layout = QVBoxLayout(content_widget)
        content_main_layout.setSpacing(0)
        content_main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 移除了自定义控制按钮，使用系统标题栏
        
        # 主内容区域
        main_content_widget = QWidget()
        content_layout = QHBoxLayout(main_content_widget)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 10, 20, 20)
        
        # 创建侧边栏
        sidebar = self.create_sidebar()
        content_layout.addWidget(sidebar)
        
        # 创建内容区域
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"""
            QStackedWidget {{
                background: {ModernStyles.COLORS['primary_bg']};
                border: none;
                border-radius: 20px;
            }}
        """)
        
        # 添加页面 - AI对话为默认首页
        self.chat_widget = ModernChatWidget()
        self.stats_widget = ModernStatsWidget()
        self.records_widget = ModernRecordsWidget()
        self.settings_widget = ModernSettingsWidget()
        self.about_widget = ModernAboutWidget()
        
        self.content_stack.addWidget(self.chat_widget)
        self.content_stack.addWidget(self.stats_widget)
        self.content_stack.addWidget(self.records_widget)
        self.content_stack.addWidget(self.settings_widget)
        self.content_stack.addWidget(self.about_widget)
        
        content_layout.addWidget(self.content_stack, 1)
        content_main_layout.addWidget(main_content_widget)
        main_layout.addWidget(content_widget)
        
    # 移除了苹果风格控制按钮相关方法，使用系统标题栏
        
    # 移除了自定义标题栏相关方法，使用系统标题栏
        
    # 移除了自定义最大化切换方法，使用系统标题栏
        
    def create_sidebar(self):
        """创建侧边栏"""
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet(ModernStyles.get_sidebar_style())
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 30, 20, 30)
        layout.setSpacing(15)
        
        # Logo区域 - 去掉背景框，直接显示
        logo_layout = QHBoxLayout()
        logo_icon = QLabel()
        logo_icon.setPixmap(qta.icon('fa5s.desktop', color='#007bff').pixmap(32, 32))
        logo_icon.setStyleSheet("background: transparent; border: none;")
        logo_layout.addWidget(logo_icon)
        
        logo_text = QLabel("屏幕智能助手")
        logo_text.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 18px;
                font-weight: bold;
                margin-left: 10px;
            }}
        """)
        logo_layout.addWidget(logo_text)
        layout.addLayout(logo_layout)
        
        # 分割线
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("QFrame { color: rgba(255, 255, 255, 0.2); }")
        layout.addWidget(divider)
        
        # 导航按钮
        self.nav_buttons = []
        nav_items = [
            ("AI对话", qta.icon('fa5s.comments', color='#007bff'), 0),
            ("使用统计", qta.icon('fa5s.chart-bar', color='#28a745'), 1),
            ("活动记录", qta.icon('fa5s.list', color='#fd7e14'), 2),
            ("设置", qta.icon('fa5s.cogs', color='#6c757d'), 3),
            ("关于", qta.icon('fa5s.info-circle', color='#007aff'), 4)
        ]
        
        for text, icon, index in nav_items:
            button = self.create_nav_button(text, icon, index)
            self.nav_buttons.append(button)
            layout.addWidget(button)
            
        layout.addStretch()
        
        # 状态信息 - 去掉背景框
        status_layout = QHBoxLayout()
        status_container = QWidget()
        status_container.setLayout(status_layout)
        status_container.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }
        """)
        status_layout.setContentsMargins(10, 10, 10, 10)
        status_layout.setSpacing(8)
        
        # 状态指示灯
        status_dot = QLabel("●")
        status_dot.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['accent_green']};
                font-size: 20px;
                font-weight: bold;
            }}
        """)
        
        # 状态文字
        status_text = QLabel("就绪")
        status_text.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['accent_green']};
                font-size: 16px;
                font-weight: 600;
            }}
        """)
        
        status_layout.addWidget(status_dot)
        status_layout.addWidget(status_text)
        status_layout.addStretch()
        layout.addWidget(status_container)
        
        return sidebar
        
    def create_nav_button(self, text, icon, index):
        """创建导航按钮"""
        button = QPushButton(text)
        button.setIcon(icon)
        button.setIconSize(QSize(24, 24))
        button.setCheckable(True)
        button.setStyleSheet(ModernStyles.get_modern_button_style())
        
        button.clicked.connect(lambda: self.switch_page(index))
        
        if index == 0:  # 默认选中第一个
            button.setChecked(True)
            
        return button
        
    def switch_page(self, index):
        """切换页面"""
        self.content_stack.setCurrentIndex(index)
        
        # 更新按钮状态
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
            
    def setup_tray(self):
        """设置系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
            
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(qta.icon('fa5s.desktop'))
        
        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示主窗口")
        show_action.triggered.connect(self.show_and_raise)
        
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(QApplication.quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
        
    def tray_icon_activated(self, reason):
        """托盘图标激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_and_raise()
            
    def show_and_raise(self):
        """显示并激活窗口"""
        self.show()
        self.raise_()
        self.activateWindow()
        if self.isMinimized():
            self.showNormal()
            
    def setup_auto_refresh(self):
        """设置自动刷新"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh_data)
        
        if gui_config.get('ui.auto_refresh', True):
            interval = gui_config.get('ui.refresh_interval', 30) * 1000
            self.refresh_timer.start(interval)
            
    def setup_screen_recording(self):
        """设置屏幕录制"""
        import threading
        
        self.recording_running = True  # 控制录制状态
        
        def run_screen_recording():
            """在后台线程运行屏幕录制"""
            try:
                import time
                from screen_capture import record_screen_activity
                
                print("🎬 屏幕录制服务已启动")
                
                # 主录制循环
                while hasattr(self, 'recording_running') and self.recording_running:
                    try:
                        record_screen_activity(triggered_by="timer")
                        time.sleep(30)  # 每30秒记录一次（更频繁）
                    except Exception as e:
                        print(f"屏幕录制错误: {e}")
                        time.sleep(60)
                        
                print("🛑 屏幕录制服务已停止")
                        
            except Exception as e:
                print(f"屏幕录制服务启动失败: {e}")
        
        # 在后台线程启动屏幕录制
        self.recording_thread = threading.Thread(target=run_screen_recording, daemon=True)
        self.recording_thread.start()
    
    def stop_screen_recording(self):
        """停止屏幕录制"""
        if hasattr(self, 'recording_running'):
            self.recording_running = False
            print("🔄 正在停止屏幕录制服务...")
            
    def auto_refresh_data(self):
        """自动刷新数据"""
        try:
            # 只有当有新数据时才刷新
            count = load_and_index_activity_data()
            
            if count > 0:
                print(f"🔄 自动刷新：发现 {count} 条新记录，正在更新界面...")
                
                # 只在有新数据时才刷新界面
                self.stats_widget.load_today_stats()
                self.records_widget.load_records(silent=True)  # 静默加载，避免重复日志
                
                # 强制刷新当前显示的界面
                self.repaint()
                QApplication.processEvents()
            else:
                # 静默检查，不输出日志
                pass
                
        except Exception as e:
            print(f"❌ 自动刷新失败: {e}")
            
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("屏幕智能助手")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Screen Assistant")
    app.setWindowIcon(qta.icon('fa5s.desktop'))
    
    window = ModernMainWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main()) 