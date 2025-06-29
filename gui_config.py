#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI 配置管理器
管理桌面应用的设置和偏好
"""

import json
import os
from typing import Dict, Any, Optional

class GUIConfig:
    """GUI配置管理器"""
    
    def __init__(self, config_file: str = "gui_settings.json"):
        self.config_file = config_file
        self._settings = self._load_settings()
        
    def _load_settings(self) -> Dict[str, Any]:
        """加载设置文件"""
        default_settings = {
            "window": {
                "width": 1000,
                "height": 900,
                "x": 100,
                "y": 100,
                "maximized": False
            },
            "ui": {
                "theme": "modern",
                "font_size": 12,
                "auto_refresh": True,
                "refresh_interval": 30,
                "show_tray_icon": True,
                "minimize_to_tray": True
            },
            "paths": {
                "data_directory": "",
                "screenshot_directory": "screen_recordings",
                "database_directory": "chroma_db_activity"
            },
            "api": {
                "siliconflow_key": "",
                "default_model": "Qwen/Qwen2.5-VL-72B-Instruct",
                "api_url": "https://api.siliconflow.cn/v1/chat/completions",
                "temperature": 0.7,
                "max_tokens": 2000
            },
            "data": {
                "max_records_display": 100,
                "auto_load_on_startup": True,
                "data_retention_days": 30
            },
            "capture": {
                "auto_start": True,
                "capture_interval": 60,
                "enable_ocr": True,
                "enable_url_detection": True
            },
            "notifications": {
                "enable_notifications": True,
                "show_startup_message": True,
                "show_error_notifications": True
            }
        }
        
        if not os.path.exists(self.config_file):
            # 创建默认配置文件
            self._settings = default_settings
            self.save_settings()
            return default_settings
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                # 合并默认设置和加载的设置
                return self._merge_settings(default_settings, loaded_settings)
        except (json.JSONDecodeError, FileNotFoundError):
            return default_settings
            
    def _merge_settings(self, default: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """递归合并设置"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_settings(result[key], value)
            else:
                result[key] = value
        return result
        
    def save_settings(self) -> bool:
        """保存设置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存设置失败: {e}")
            return False
            
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取设置值，支持点分隔的路径"""
        keys = key_path.split('.')
        value = self._settings
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
                
        return value
        
    def set(self, key_path: str, value: Any) -> None:
        """设置值，支持点分隔的路径"""
        keys = key_path.split('.')
        target = self._settings
        
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
            
        target[keys[-1]] = value
        
    def get_window_geometry(self) -> Dict[str, int]:
        """获取窗口几何信息"""
        return {
            'width': self.get('window.width', 1200),
            'height': self.get('window.height', 800),
            'x': self.get('window.x', 100),
            'y': self.get('window.y', 100),
            'maximized': self.get('window.maximized', False)
        }
        
    def save_window_geometry(self, width: int, height: int, x: int, y: int, maximized: bool = False) -> None:
        """保存窗口几何信息"""
        self.set('window.width', width)
        self.set('window.height', height)
        self.set('window.x', x)
        self.set('window.y', y)
        self.set('window.maximized', maximized)
        self.save_settings()
        
    def get_ui_settings(self) -> Dict[str, Any]:
        """获取UI设置"""
        return {
            'theme': self.get('ui.theme', 'modern'),
            'font_size': self.get('ui.font_size', 12),
            'auto_refresh': self.get('ui.auto_refresh', True),
            'refresh_interval': self.get('ui.refresh_interval', 30),
            'show_tray_icon': self.get('ui.show_tray_icon', True),
            'minimize_to_tray': self.get('ui.minimize_to_tray', True)
        }
        
    def get_data_settings(self) -> Dict[str, Any]:
        """获取数据设置"""
        return {
            'max_records_display': self.get('data.max_records_display', 100),
            'auto_load_on_startup': self.get('data.auto_load_on_startup', True),
            'data_retention_days': self.get('data.data_retention_days', 30)
        }
        
    def get_capture_settings(self) -> Dict[str, Any]:
        """获取捕获设置"""
        return {
            'auto_start': self.get('capture.auto_start', True),
            'capture_interval': self.get('capture.capture_interval', 60),
            'enable_ocr': self.get('capture.enable_ocr', True),
            'enable_url_detection': self.get('capture.enable_url_detection', True)
        }
        
    def get_notification_settings(self) -> Dict[str, Any]:
        """获取通知设置"""
        return {
            'enable_notifications': self.get('notifications.enable_notifications', True),
            'show_startup_message': self.get('notifications.show_startup_message', True),
            'show_error_notifications': self.get('notifications.show_error_notifications', True)
        }
        
    def get_path_settings(self) -> Dict[str, Any]:
        """获取路径设置"""
        return {
            'data_directory': self.get('paths.data_directory', ''),
            'screenshot_directory': self.get('paths.screenshot_directory', 'screen_recordings'),
            'database_directory': self.get('paths.database_directory', 'chroma_db_activity')
        }
        
    def get_api_settings(self) -> Dict[str, Any]:
        """获取API设置"""
        return {
            'siliconflow_key': self.get('api.siliconflow_key', ''),
            'default_model': self.get('api.default_model', 'Qwen/Qwen2.5-VL-72B-Instruct'),
            'api_url': self.get('api.api_url', 'https://api.siliconflow.cn/v1/chat/completions'),
            'temperature': self.get('api.temperature', 0.7),
            'max_tokens': self.get('api.max_tokens', 2000)
        }

# 全局配置实例
gui_config = GUIConfig() 