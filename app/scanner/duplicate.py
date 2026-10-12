import hashlib
import time
from typing import List, Dict, Callable, Optional
from pathlib import Path
from collections import defaultdict
from app.models.file_item import FileItem, FileCategory

# 只做"候选筛选"的快速哈希前缀大小；不同内容的文件通常在前 64KB 就区分开了
QUICK_HASH_PREFIX = 64 * 1024
# 每读这么多字节检查一次是否被要求取消
_CANCEL_CHECK_BYTES = 4 * 1024 * 1024


class HashScanCancelled(Exception):
    """哈希查重被调用方要求中止（用户取消扫描，或超出时间预算）。"""


def _new_hash(algorithm: str):
    try:
        return hashlib.new(algorithm)
    except (ValueError, TypeError):
        return hashlib.md5()


def hash_file(path: Path, algorithm: str = "md5", chunk_size: int = 1024 * 1024,
              limit: int = 0, should_stop: Optional[Callable[[], bool]] = None) -> str:
    """计算文件哈希。

    limit > 0 时只读取前 limit 字节（用于快速候选筛选）。
    should_stop 每读取约 4MB 调用一次，返回 True 时抛 HashScanCancelled。
    """
    h = _new_hash(algorithm)
    read = 0
    since_check = 0
    try:
        with open(str(path), "rb") as f:
            while True:
                if limit and read >= limit:
                    break
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                if limit and read + len(chunk) > limit:
                    chunk = chunk[:limit - read]
                h.update(chunk)
                read += len(chunk)
                since_check += len(chunk)
                if should_stop is not None and since_check >= _CANCEL_CHECK_BYTES:
                    since_check = 0
                    if should_stop():
                        raise HashScanCancelled()
        return h.hexdigest()
    except (PermissionError, OSError):
        return ""


def find_duplicates(files: List[FileItem],
                    algorithm: str = "md5",
                    min_size: int = 8 * 1024 * 1024,
                    time_budget_seconds: float = 60.0,
                    should_stop: Optional[Callable[[], bool]] = None,
                    on_progress: Optional[Callable[[str], None]] = None,
                    ) -> tuple:
    """按内容哈希查找重复文件，返回 (重复组列表, 是否因时间预算/取消而提前结束)。

    为避免在整盘扫描时无休止地读盘，本函数有三重限制：
      * min_size：小于该字节数的文件不参与（小文件数量极多、收益低）
      * time_budget_seconds：超过预算即停止，返回已确认的结果
      * should_stop：调用方取消（用户停止/关窗）时立即中止

    采用两阶段哈希：先比大小，再用 64KB 前缀哈希筛掉绝大多数内容不同的文件，
    只对前缀相同的候选读全文。
    """
    deadline = time.monotonic() + time_budget_seconds if time_budget_seconds > 0 else None

    # 1) 按大小分组（同尺寸才可能是重复）
    size_map: Dict[int, List[FileItem]] = defaultdict(list)
    seen_paths = set()
    for f in files:
        key = str(f.path)
        if f.size >= max(min_size, 1) and key not in seen_paths:
            seen_paths.add(key)
            size_map[f.size].append(f)

    candidates_by_size = {s: g for s, g in size_map.items() if len(g) >= 2}
    total_candidates = sum(len(g) for g in candidates_by_size.values())

    result: List[List[FileItem]] = []
    if not candidates_by_size:
        return result, False

    def stop_requested() -> bool:
        if should_stop is not None and should_stop():
            return True
        return deadline is not None and time.monotonic() > deadline

    processed = 0
    timed_out = False

    def report(prefix: str):
        if on_progress and total_candidates:
            on_progress(f"{prefix}（{processed}/{total_candidates}，已找到 {len(result)} 组）")

    report("正在比对重复文件")
    try:
        for size, group in candidates_by_size.items():
            if stop_requested():
                timed_out = True
                break

            # 阶段一：前缀哈希筛选
            quick_map: Dict[str, List[FileItem]] = defaultdict(list)
            for f in group:
                if stop_requested():
                    timed_out = True
                    break
                quick = hash_file(f.path, algorithm=algorithm,
                                  limit=QUICK_HASH_PREFIX, should_stop=stop_requested)
                processed += 1
                if quick:
                    quick_map[quick].append(f)
            if timed_out:
                break
            report("正在比对重复文件")

            # 阶段二：只对前缀相同的候选读全文
            for quick_candidates in quick_map.values():
                if len(quick_candidates) < 2:
                    continue
                full_map: Dict[str, List[FileItem]] = defaultdict(list)
                for f in quick_candidates:
                    if stop_requested():
                        timed_out = True
                        break
                    full = hash_file(f.path, algorithm=algorithm, should_stop=stop_requested)
                    if full:
                        full_map[full].append(f)
                if timed_out:
                    break
                for dup_group in full_map.values():
                    if len(dup_group) >= 2:
                        for f in dup_group:
                            f.category = FileCategory.DUPLICATE
                        # 约定：组内第一个为保留的"原文件"，其余为判定删除的重复副本。
                        # 按修改时间升序（最旧优先），使可释放空间与建议删除集合稳定可复现。
                        result.append(sorted(dup_group, key=lambda x: (x.modified_time, str(x.path))))
                report("正在比对重复文件")
            if timed_out:
                break
    except HashScanCancelled:
        return result, True

    if on_progress:
        if timed_out:
            on_progress(f"重复文件比对已提前结束（达到时间上限，已确认 {len(result)} 组，"
                        f"比对 {processed}/{total_candidates} 个候选）")
        else:
            on_progress(f"重复文件比对完成，共 {len(result)} 组")
    return result, timed_out
