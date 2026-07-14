#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n 热切换翻译系统
使用 Qt 内置 QTranslator 系统 + LanguageChange 事件实现无重启语言切换
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Callable, List as ListType
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication, QEvent, QObject, Signal, QSettings, QCoreApplication
from PySide6.QtWidgets import QWidget, QApplication


class TranslationManager(QObject):
    """翻译管理器，负责加载/切换语言"""
    
    language_changed = Signal(str)
    
    def __init__(self, app=None):
        super().__init__()
        self._app = app
        self._translator = QTranslator()
        self._current_locale = "zh_CN"  # 默认中文
        # QM 文件在 app/translations 目录
        self._translations_dir = Path(__file__).parent.parent / "translations"
        self._observers: ListType[Callable] = []  # 观察者模式
        self._settings = QSettings("DiskPulse", "DiskPulse")
        
    def set_app(self, app):
        self._app = app
        
    def add_observer(self, callback: Callable):
        """注册观察者，语言切换时回调"""
        if callback not in self._observers:
            self._observers.append(callback)
            
    def remove_observer(self, callback: Callable):
        if callback in self._observers:
            self._observers.remove(callback)
            
    def available_languages(self) -> Dict[str, str]:
        """返回可用语言 {代码: 显示名}"""
        return {
            "zh_CN": "中文 (简体)",
            "en_US": "English",
        }
    
    def current_language(self) -> str:
        return self._current_locale
    
    def current_language_name(self) -> str:
        return self.available_languages().get(self._current_locale, self._current_locale)
    
    def load_language(self, locale_code: str) -> bool:
        """加载指定语言并触发热切换"""
        if locale_code not in self.available_languages():
            return False
            
        if locale_code == self._current_locale:
            return True
            
        # 移除旧翻译
        if self._app:
            self._app.removeTranslator(self._translator)
            
        # 加载新翻译
        qm_file = self._translations_dir / f"diskpulse_{locale_code}.qm"
        print(f"Loading translation from: {qm_file}, exists: {qm_file.exists()}")
        if qm_file.exists():
            success = self._translator.load(str(qm_file))
            print(f"Load result: {success}")
            if success:
                if self._app:
                    self._app.installTranslator(self._translator)
                self._current_locale = locale_code
                self._settings.setValue("language", locale_code)
                self._settings.sync()
                self._notify_language_changed()
                return True
                
        # 如果没有 qm 文件，尝试加载系统默认
        if locale_code == "zh_CN":
            self._current_locale = locale_code
            if self._app:
                self._app.removeTranslator(self._translator)
            self._notify_language_changed()
            return True
            
        return False
    
    def _notify_language_changed(self):
        """通知所有观察者并发送 LanguageChange 事件"""
        # 1. 通知注册的观察者
        for callback in self._observers:
            try:
                callback(self._current_locale)
            except Exception:
                pass
                
        # 2. 发送 Qt LanguageChange 事件给所有顶层窗口
        if self._app:
            for widget in self._app.topLevelWidgets():
                event = QEvent(QEvent.Type.LanguageChange)
                QCoreApplication.postEvent(widget, event)
                
    def auto_detect_language(self) -> str:
        """自动检测系统语言"""
        system_locale = QLocale.system().name()  # 如 "zh_CN", "en_US"
        if system_locale in self.available_languages():
            return system_locale
        # 回退到英语
        return "en_US"
    
    def initialize(self):
        """初始化：加载保存的语言或自动检测"""
        locale = self._settings.value("language", "zh_CN")
        self.load_language(locale)
        
    def save_language_preference(self, locale_code: str):
        """保存语言偏好到设置"""
        self._settings.setValue("language", locale_code)
        self._settings.sync()

    def tr(self, context: str, text: str) -> str:
        """翻译函数"""
        return QCoreApplication.translate(context, text)


# 全局单例
_translation_manager: Optional[TranslationManager] = None


def get_translation_manager(app: QApplication = None) -> TranslationManager:
    global _translation_manager
    if _translation_manager is None:
        _translation_manager = TranslationManager(app)
    elif app and _translation_manager._app is None:
        _translation_manager.set_app(app)
    return _translation_manager


def tr(context: str, text: str) -> str:
    """全局翻译函数，供非 QObject 类使用"""
    return get_translation_manager().tr(context, text)