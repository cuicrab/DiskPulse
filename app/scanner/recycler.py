import ctypes
import os
from pathlib import Path
from typing import List
from datetime import datetime
from app.models.file_item import FileItem, FileCategory


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("i64Size", ctypes.c_ulonglong),
        ("i64NumItems", ctypes.c_ulonglong),
    ]


def get_recycle_bin_info() -> dict:
    try:
        rbi = SHQUERYRBINFO()
        rbi.cbSize = ctypes.sizeof(rbi)
        ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(rbi))
        return {
            "item_count": rbi.i64NumItems,
            "total_size": rbi.i64Size,
        }
    except Exception:
        return {"item_count": 0, "total_size": 0}


def empty_recycle_bin() -> bool:
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0)
        return True
    except Exception:
        return False
