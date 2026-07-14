import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.models.advisor_item import AdvisorItem
from app.models.scan_result import ScanResult
from app.scanner.cache_detector import scan_cache_paths, resolve_env_path
from app.scanner.recycler import get_recycle_bin_info
from app.utils.file_ops import get_folder_size


from app.utils import resource_path


class AdvisorEngine:
    def __init__(self, rules_path: str = ""):
        if not rules_path:
            rules_path = resource_path("rules.yaml")
        self.rules = self._load_rules(rules_path)

    def _load_rules(self, path: str) -> List[Dict[str, Any]]:
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("rules", [])
        except (FileNotFoundError, yaml.YAMLError):
            return []

    def analyze(self, scan_result: Optional[ScanResult] = None) -> dict:
        grouped = {3: [], 2: [], 1: []}

        for rule in self.rules:
            item = self._evaluate_rule(rule, scan_result)
            if item and item.file_count > 0:
                grouped[item.importance].append(item)

        if scan_result:
            dup_groups = scan_result.duplicate_groups
            if dup_groups:
                total_size = 0
                total_count = 0
                files = []
                for group in dup_groups:
                    for f in group[1:]:
                        total_size += f.size
                        total_count += 1
                        files.append(f.path)
                if total_count > 0:
                    grouped[2].append(AdvisorItem(
                        name="duplicate_files",
                        description="重复文件",
                        importance=2,
                        importance_label="建议检查清理",
                        hint="这些文件内容完全相同，可能只是备份副本。请确认保留位置后再删除",
                        size_bytes=total_size,
                        file_count=total_count,
                        files=files,
                    ))

            if scan_result.old_files:
                total_size = sum(f.size for f in scan_result.old_files)
                grouped[2].append(AdvisorItem(
                    name="old_large_files",
                    description="超过 90 天未访问的大文件",
                    importance=2,
                    importance_label="建议检查清理",
                    hint="这些文件长期未使用，可能是不再需要的旧文件，请确认后再删除",
                    size_bytes=total_size,
                    file_count=len(scan_result.old_files),
                    files=[f.path for f in scan_result.old_files],
                ))

        return {
            "strongly_recommended": grouped[3],
            "suggested": grouped[2],
            "caution": grouped[1],
        }

    def _evaluate_rule(self, rule: dict, scan_result: Optional[ScanResult]) -> Optional[AdvisorItem]:
        name = rule.get("name", "")
        description = rule.get("description", "")
        importance = rule.get("importance", 1)
        importance_label = rule.get("importance_label", "")
        hint = rule.get("hint", "")
        paths = rule.get("paths", [])
        max_age_days = rule.get("max_age_days", 0)

        if name == "recycler":
            info = get_recycle_bin_info()
            count = info.get("item_count", 0)
            size = info.get("total_size", 0)
            if count > 0:
                return AdvisorItem(
                    name=name,
                    description=description,
                    importance=importance,
                    importance_label=importance_label,
                    hint=hint,
                    size_bytes=size,
                    file_count=count,
                    files=[],
                )
            return None

        if not paths:
            return None

        all_files = []
        total_size = 0
        for pattern in paths:
            resolved = resolve_env_path(pattern)
            for rp in resolved:
                if rp.is_file():
                    s = rp.stat().st_size
                    all_files.append(rp)
                    total_size += s
                elif rp.is_dir():
                    total_size += get_folder_size(rp)
                    try:
                        for f in rp.rglob("*"):
                            if f.is_file():
                                all_files.append(f)
                    except (PermissionError, OSError):
                        continue

        if all_files:
            return AdvisorItem(
                name=name,
                description=description,
                importance=importance,
                importance_label=importance_label,
                hint=hint,
                size_bytes=total_size,
                file_count=len(all_files),
                files=all_files,
            )
        return None
