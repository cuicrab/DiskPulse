"""
i18n 热切换翻译系统
使用 Qt 的 LanguageChange 事件机制实现无重启语言切换
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Callable
from PySide6.QtCore import QCoreApplication, QTranslator, QLocale, QEvent, QObject, Signal, QSettings
from PySide6.QtWidgets import QWidget, QApplication


class TranslationManager(QObject):
    """翻译管理器 - 支持热切换"""
    
    language_changed = Signal(str)  # locale_code
    
    def __init__(self, app: QApplication = None):
        super().__init__()
        self._app = app
        self._translator = QTranslator()
        self._current_locale = "zh_CN"
        self._translations_dir = Path(__file__).parent.parent / "translations"
        self._observers: List[Callable] = []  # 观察者模式
        self._settings = QSettings("DiskPulse", "DiskPulse")
        
    def set_app(self, app: QApplication):
        self._app = app
        
    def add_observer(self, callback: Callable):
        """注册观察者，语言切换时回调"""
        if callback not in self._observers:
            self._observers.append(callback)
            
    def remove_observer(self, callback: Callable):
        if callback in self._observers:
            self._observers.remove(callback)
            
    def available_languages(self) -> Dict[str, str]:
        return {
            "zh_CN": "中文 (简体)",
            "en_US": "English",
        }
    
    def current_language(self) -> str:
        return self._current_locale
    
    def current_language_name(self) -> str:
        return self.available_languages().get(self._current_locale, self._current_locale)
    
    def load_language(self, locale_code: str) -> bool:
        """加载语言并触发热切换"""
        if locale_code not in self.available_languages():
            return False
            
        if locale_code == self._current_locale:
            return True
            
        # 移除旧翻译
        if self._app:
            self._app.removeTranslator(self._translator)
            
        # 加载新翻译
        qm_file = self._translations_dir / f"diskpulse_{locale_code}.qm"
        if not qm_file.exists():
            if locale_code == "zh_CN":
                self._current_locale = locale_code
                self._notify_language_changed()
                return True
            return False
            
        success = self._translator.load(str(qm_file))
        if not success:
            return False
            
        if self._app:
            self._app.installTranslator(self._translator)
            
        self._current_locale = locale_code
        self._settings.setValue("language", locale_code)
        self._settings.sync()
        
        # 触发热切换 - 发送 LanguageChange 事件给所有顶层窗口
        self._notify_language_changed()
        
        return True
    
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
        system_locale = QLocale.system().name()
        if system_locale in self.available_languages():
            return system_locale
        return "en_US"
    
    def initialize(self):
        """初始化：加载保存的语言或自动检测"""
        locale = self._settings.value("language", "zh_CN")
        self.load_language(locale)
        
    def tr(self, context: str, text: str) -> str:
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
    """全局翻译函数"""
    return get_translation_manager().tr(context, text)