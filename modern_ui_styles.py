#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
现代化UI样式库 - 浅色风格 + 简约玻璃效果
"""

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
import qtawesome as qta
import math

class ModernStyles:
    """现代化样式定义"""
    
    # 颜色主题 - 浅色风格
    COLORS = {
        # 主色调 - 浅色主题
        'primary_bg': '#f8f9fa',
        'secondary_bg': '#ffffff', 
        'tertiary_bg': '#f1f3f4',
        
        # 玻璃效果 - 浅色版本
        'glass_bg': 'rgba(255, 255, 255, 0.8)',
        'glass_border': 'rgba(0, 0, 0, 0.1)',
        'glass_shadow': 'rgba(0, 0, 0, 0.1)',
        
        # 文字颜色
        'text_primary': '#1a1a1a',
        'text_secondary': '#6c757d',
        'text_accent': '#007bff',
        
        # 强调色 - 现代化配色
        'accent_blue': '#007bff',
        'accent_green': '#28a745',
        'accent_orange': '#fd7e14',
        'accent_purple': '#6f42c1',
        'accent_pink': '#e83e8c',
        'accent_red': '#dc3545',
        'accent_yellow': '#ffc107',
        'accent_cyan': '#17a2b8',
        
        # 渐变色 - 浅色背景
        'gradient_primary': 'qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #ffffff, stop: 1 #f8f9fa)',
        'gradient_accent': 'qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #007bff, stop: 1 #0056b3)',
        'gradient_warm': 'qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #fd7e14, stop: 1 #e83e8c)',
        'gradient_sidebar': 'qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #ffffff, stop: 1 #f1f3f4)',
    }
    
    @staticmethod
    def get_main_window_style():
        """主窗口样式"""
        return f"""
            QMainWindow {{
                background: {ModernStyles.COLORS['gradient_primary']};
                border: none;
                border-radius: 25px;
            }}
        """
    
    @staticmethod 
    def get_glass_card_style():
        """玻璃卡片样式"""
        return f"""
            QWidget {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 20px;
            }}
        """
    
    @staticmethod
    def get_sidebar_style():
        """侧边栏样式"""
        return f"""
            QWidget {{
                background: {ModernStyles.COLORS['gradient_sidebar']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 25px;
            }}
        """
    
    @staticmethod
    def get_modern_button_style():
        """现代化按钮样式"""
        return f"""
            QPushButton {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 15px;
                color: {ModernStyles.COLORS['text_primary']};
                font-weight: 600;
                font-size: 14px;
                padding: 12px 20px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: rgba(0, 123, 255, 0.1);
                border: 2px solid {ModernStyles.COLORS['text_accent']};
            }}
            QPushButton:pressed {{
                background: rgba(0, 123, 255, 0.05);
            }}
            QPushButton:checked {{
                background: {ModernStyles.COLORS['gradient_accent']};
                color: white;
                font-weight: bold;
                border: 2px solid {ModernStyles.COLORS['accent_blue']};
            }}
        """
    
    @staticmethod
    def get_table_style():
        """表格样式 - 现代化设计"""
        return f"""
            QTableWidget {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 20px;
                color: {ModernStyles.COLORS['text_primary']};
                gridline-color: rgba(0, 0, 0, 0.08);
                font-size: 14px;
                selection-background-color: transparent;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 15px 12px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.05);
                border-right: none;
                background: transparent;
            }}
            QTableWidget::item:selected {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, 
                    stop: 0 rgba(0, 123, 255, 0.12), 
                    stop: 1 rgba(0, 123, 255, 0.03));
                color: {ModernStyles.COLORS['text_primary']};
                border-left: 2px solid {ModernStyles.COLORS['accent_blue']};
            }}
            QTableWidget::item:hover {{
                background: rgba(0, 123, 255, 0.06);
            }}
            QHeaderView::section {{
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, 
                    stop: 0 rgba(248, 249, 250, 0.9), 
                    stop: 1 rgba(241, 243, 244, 0.9));
                color: {ModernStyles.COLORS['text_primary']};
                padding: 18px 12px;
                border: none;
                font-weight: 600;
                font-size: 14px;
                border-bottom: 2px solid rgba(0, 0, 0, 0.1);
            }}
            QHeaderView::section:first {{
                border-top-left-radius: 20px;
            }}
            QHeaderView::section:last {{
                border-top-right-radius: 20px;
            }}
            QScrollBar:vertical {{
                background: rgba(248, 249, 250, 0.8);
                width: 10px;
                border-radius: 5px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(0, 123, 255, 0.6),
                    stop: 1 rgba(0, 123, 255, 0.4));
                border-radius: 5px;
                min-height: 30px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(0, 123, 255, 0.8),
                    stop: 1 rgba(0, 123, 255, 0.6));
            }}
            QScrollBar::handle:vertical:pressed {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(0, 123, 255, 0.9),
                    stop: 1 rgba(0, 123, 255, 0.7));
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """

class GlassCard(QWidget):
    """玻璃卡片组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制玻璃背景
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 20, 20)
        
        # 背景渐变 - 浅色版本
        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        gradient.setColorAt(0, QColor(255, 255, 255, 200))
        gradient.setColorAt(1, QColor(248, 249, 250, 180))
        
        painter.fillPath(path, gradient)
        
        # 边框 - 浅色版本
        pen = QPen(QColor(0, 0, 0, 25))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

class ProgressRing(QWidget):
    """圆形进度环"""
    def __init__(self, value=0, max_value=100, color="#4fc3f7", parent=None):
        super().__init__(parent)
        self.value = value
        self.max_value = max_value
        self.color = QColor(color)
        self.setFixedSize(80, 80)
        
    def setValue(self, value):
        self.value = max(0, min(value, self.max_value))
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect().adjusted(10, 10, -10, -10)
        
        # 背景圆环
        pen = QPen(QColor(255, 255, 255, 30))
        pen.setWidth(6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(rect)
        
        # 进度圆环
        if self.value > 0:
            pen.setColor(self.color)
            pen.setWidth(8)
            painter.setPen(pen)
            
            angle = int(360 * (self.value / self.max_value))
            painter.drawArc(rect, 90 * 16, -angle * 16)

class ProgressBar(QWidget):
    """现代化进度条"""
    def __init__(self, value=0, max_value=100, color="#007aff", parent=None):
        super().__init__(parent)
        self.value = value
        self.max_value = max_value
        self.color = QColor(color)
        self.setFixedHeight(8)
        self.setMinimumWidth(100)
        
    def setValue(self, value):
        self.value = max(0, min(value, self.max_value))
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # 背景条
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(rect), 4, 4)
        painter.fillPath(bg_path, QColor(255, 255, 255, 30))
        
        # 进度条
        if self.value > 0:
            progress_width = int(rect.width() * (self.value / self.max_value))
            progress_rect = QRectF(0, 0, progress_width, rect.height())
            
            progress_path = QPainterPath()
            progress_path.addRoundedRect(progress_rect, 4, 4)
            painter.fillPath(progress_path, self.color)

class AppUsageCard(QWidget):
    """应用使用卡片 - 去掉背景框"""
    def __init__(self, app_name, usage_time, icon_name=None, color="#007aff", percentage=0, parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self.usage_time = usage_time
        self.color = color
        self.percentage = percentage
        self.setFixedHeight(90)
        self.setStyleSheet("background: transparent; border: none;")
        self.setup_ui(icon_name)
        
    def setup_ui(self, icon_name):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(20)
        
        # 左侧：应用图标（圆形背景）
        icon_container = QWidget()
        icon_container.setFixedSize(50, 50)
        icon_container.setStyleSheet(f"""
            QWidget {{
                background: {self.color};
                border-radius: 25px;
                border: 2px solid rgba(255, 255, 255, 0.1);
            }}
        """)
        
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        
        icon_label = QLabel()
        if icon_name:
            icon = qta.icon(icon_name, color='white')
            pixmap = icon.pixmap(24, 24)
            icon_label.setPixmap(pixmap)
        else:
            # 使用应用名称首字母
            icon_label.setText(self.app_name[0].upper())
            icon_label.setStyleSheet(f"""
                QLabel {{
                    background: transparent;
                    border: none;
                    color: white;
                    font-size: 18px;
                    font-weight: bold;
                }}
            """)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon_label)
        
        layout.addWidget(icon_container)
        
        # 中间：应用信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        # 应用名称
        name_label = QLabel(self.app_name)
        name_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 16px;
                font-weight: 600;
            }}
        """)
        info_layout.addWidget(name_label)
        
        # 使用时长
        time_label = QLabel(self.usage_time)
        time_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_secondary']};
                font-size: 14px;
                font-weight: 500;
            }}
        """)
        info_layout.addWidget(time_label)
        
        layout.addLayout(info_layout)
        
        # 右侧：进度条和百分比 - 占据更多空间
        right_layout = QVBoxLayout()
        right_layout.setSpacing(8)
        
        # 百分比标签
        percent_label = QLabel(f"{self.percentage}%")
        percent_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        percent_label.setAlignment(Qt.AlignRight)
        right_layout.addWidget(percent_label)
        
        # 进度条容器，让进度条从左边开始，跨越更多空间
        progress_container = QWidget()
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(0)
        
        # 进度条 - 增加宽度，从左边开始
        progress = ProgressBar(color=self.color)
        progress.setValue(self.percentage)
        progress.setMinimumWidth(250)  # 进一步增加最小宽度
        progress_layout.addWidget(progress)
        
        right_layout.addWidget(progress_container)
        layout.addLayout(right_layout)

class ModernScrollArea(QScrollArea):
    """现代化滚动区域"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(248, 249, 250, 0.8);
                width: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(0, 123, 255, 0.6),
                    stop: 1 rgba(0, 123, 255, 0.4));
                border-radius: 5px;
                min-height: 30px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(0, 123, 255, 0.8),
                    stop: 1 rgba(0, 123, 255, 0.6));
            }
            QScrollBar::handle:vertical:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 rgba(0, 123, 255, 0.9),
                    stop: 1 rgba(0, 123, 255, 0.7));
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                background: rgba(248, 249, 250, 0.8);
                height: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 rgba(0, 123, 255, 0.6),
                    stop: 1 rgba(0, 123, 255, 0.4));
                border-radius: 5px;
                min-width: 30px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 rgba(0, 123, 255, 0.8),
                    stop: 1 rgba(0, 123, 255, 0.6));
            }
            QScrollBar::handle:horizontal:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 rgba(0, 123, 255, 0.9),
                    stop: 1 rgba(0, 123, 255, 0.7));
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)

class ChatBubble(QWidget):
    """聊天气泡 - 带头像"""
    def __init__(self, message, is_user=False, parent=None):
        super().__init__(parent)
        self.message = message
        self.is_user = is_user
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        if self.is_user:
            layout.addStretch()
            
        # 创建头像
        avatar = self.create_avatar()
        
        # 消息气泡
        bubble = QLabel(self.message)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(400)
        
        if self.is_user:
            bubble.setStyleSheet(f"""
                QLabel {{
                    background: {ModernStyles.COLORS['gradient_accent']};
                    color: white;
                    padding: 12px 16px;
                    border-radius: 18px;
                    font-size: 14px;
                    border-top-right-radius: 5px;
                }}
            """)
            # 用户头像在右侧
            layout.addWidget(bubble)
            layout.addWidget(avatar)
        else:
            bubble.setStyleSheet(f"""
                QLabel {{
                    background: {ModernStyles.COLORS['glass_bg']};
                    color: {ModernStyles.COLORS['text_primary']};
                    border: 1px solid {ModernStyles.COLORS['glass_border']};
                    padding: 12px 16px;
                    border-radius: 18px;
                    font-size: 14px;
                    border-top-left-radius: 5px;
                }}
            """)
            # AI头像在左侧
            layout.addWidget(avatar)
            layout.addWidget(bubble)
            
        if not self.is_user:
            layout.addStretch()
    
    def create_avatar(self):
        """创建头像"""
        avatar = QLabel()
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignCenter)
        
        if self.is_user:
            # 用户头像 - 简约的用户图标
            avatar.setStyleSheet(f"""
                QLabel {{
                    background: {ModernStyles.COLORS['gradient_accent']};
                    border-radius: 18px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                }}
            """)
            avatar.setText("👤")
        else:
            # AI头像 - 机器人图标
            avatar.setStyleSheet(f"""
                QLabel {{
                    background: {ModernStyles.COLORS['gradient_warm']};
                    border-radius: 18px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                }}
            """)
            avatar.setText("🤖")
            
        return avatar

class ModernButton(QPushButton):
    """现代化按钮"""
    def __init__(self, text="", icon=None, style="primary", parent=None):
        super().__init__(text, parent)
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(20, 20))
        self.style_type = style
        self.setup_style()
        
    def setup_style(self):
        if self.style_type == "primary":
            self.setStyleSheet(f"""
                ModernButton {{
                    background: {ModernStyles.COLORS['gradient_accent']};
                    border: none;
                    border-radius: 12px;
                    color: white;
                    font-weight: 600;
                    font-size: 14px;
                    padding: 12px 24px;
                }}
                                 ModernButton:hover {{
                     background: {ModernStyles.COLORS['gradient_warm']};
                     border: 2px solid rgba(255, 255, 255, 0.3);
                 }}
                 ModernButton:pressed {{
                     background: {ModernStyles.COLORS['gradient_accent']};
                 }}
            """)
        elif self.style_type == "glass":
            self.setStyleSheet(ModernStyles.get_modern_button_style())

class StatsCard(QWidget):
    """统计卡片 - 去掉背景框"""
    def __init__(self, title, value, icon=None, color="#4fc3f7", parent=None):
        super().__init__(parent)
        self.title = title
        self.value = value
        self.color = color
        self.setFixedHeight(120)
        self.setStyleSheet("background: transparent; border: none;")
        self.setup_ui(icon)
        
    def setup_ui(self, icon):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # 图标和标题行
        header_layout = QHBoxLayout()
        
        if icon:
            icon_label = QLabel()
            icon_pixmap = icon.pixmap(24, 24)
            icon_label.setPixmap(icon_pixmap)
            icon_label.setStyleSheet("background: transparent; border: none;")
            header_layout.addWidget(icon_label)
            
        title_label = QLabel(self.title)
        title_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_secondary']};
                font-size: 14px;
                font-weight: 500;
            }}
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 数值
        value_label = QLabel(self.value)
        value_label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                border: none;
                color: {ModernStyles.COLORS['text_primary']};
                font-size: 28px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(value_label)
        
        layout.addStretch()

class ModernTabWidget(QWidget):
    """现代化标签页组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = []
        self.current_index = 0
        self.setup_ui()
        
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(20)
        
        # 标签按钮容器
        self.tab_container = QWidget()
        self.tab_container.setFixedHeight(50)
        self.tab_container.setStyleSheet("background: transparent; border: none;")
        self.tab_layout = QHBoxLayout(self.tab_container)
        self.tab_layout.setContentsMargins(10, 5, 10, 5)
        self.tab_layout.setSpacing(10)
        
        self.layout.addWidget(self.tab_container)
        
    def addTab(self, title):
        """添加标签页，不再需要widget"""
        # 创建标签按钮
        button = QPushButton(title)
        button.setCheckable(True)
        button.setStyleSheet(f"""
            QPushButton {{
                background: {ModernStyles.COLORS['glass_bg']};
                border: 1px solid {ModernStyles.COLORS['glass_border']};
                border-radius: 15px;
                color: {ModernStyles.COLORS['text_secondary']};
                font-weight: 500;
                font-size: 14px;
                padding: 10px 25px;
                min-width: 80px;
                max-height: 35px;
            }}
            QPushButton:checked {{
                background: {ModernStyles.COLORS['gradient_accent']};
                color: white;
                font-weight: 600;
                border: 1px solid {ModernStyles.COLORS['accent_blue']};
            }}
            QPushButton:hover {{
                background: rgba(0, 123, 255, 0.1);
                border: 1px solid {ModernStyles.COLORS['accent_blue']};
            }}
        """)
        
        index = len(self.tabs)
        button.clicked.connect(lambda: self.setCurrentIndex(index))
        
        self.tabs.append({"button": button, "title": title})
        self.tab_layout.addWidget(button)
        
        if index == 0:
            button.setChecked(True)
            
    def setCurrentIndex(self, index):
        """切换到指定标签页"""
        if 0 <= index < len(self.tabs):
            # 更新按钮状态
            for i, tab in enumerate(self.tabs):
                tab["button"].setChecked(i == index)
                
            # 不再需要切换内容
            self.current_index = index 