# DiskPulse 开发指南

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.13 |
| GUI 框架 | PySide6 | 6.8 |
| 磁盘信息 | psutil | 7.x |
| 文件删除(回收站) | send2trash | 2.x |
| YAML 解析 | pyyaml | 6.x |
| 开发环境 | Miniconda | `D:\tool\miniconda3\python.exe` |
| 打包工具 | PyInstaller | 6.21 (按需执行) |

### 项目结构

```
DiskPulse/
├── main.py                          # 入口: from app import run; run()
├── app/
│   ├── __init__.py                  # 应用工厂: QApplication + 样式 + 窗口
│   ├── main_window.py               # 主窗口: QSplitter + QStackedWidget
│   ├── i18n.py                      # 翻译管理器(生产版, 被 import)
│   ├── i18n/__init__.py             # 翻译管理器(调试版, 含 print 日志)
│   ├── models/
│   │   ├── file_item.py             # FileItem, FileCategory(enum)
│   │   ├── scan_result.py           # ScanResult
│   │   ├── advisor_item.py          # AdvisorItem
│   │   └── settings.py              # AppSettings(dataclass, JSON 持久化)
│   ├── scanner/
│   │   ├── engine.py                # ScanEngine(QThread) 主扫描线程
│   │   ├── large_file.py            # 大文件筛选(与 engine 内联逻辑重复)
│   │   ├── temp_cleaner.py          # 临时文件扫描(与 engine 内联逻辑重复)
│   │   ├── empty_folder.py          # 空文件夹扫描(与 engine 内联逻辑重复)
│   │   ├── cache_detector.py        # 缓存文件扫描, 环境变量路径解析
│   │   ├── duplicate.py             # 重复文件: 先比大小→再算 MD5
│   │   └── recycler.py              # 回收站: ctypes Windows API
│   ├── advisor/
│   │   ├── engine.py                # AdvisorEngine: 解析 rules.yaml, 三级风险分级
│   │   └── actions.py               # AdvisorActions: 批量删除+日志
│   ├── ui/
│   │   ├── dashboard.py             # DashboardPage: MiniGauge/DiskGauge 环形图
│   │   ├── file_list.py             # FileListPanel: QTreeWidget + 多色标签
│   │   └── advisor_panel.py         # AdvisorPanel: 可展开卡片, 三态复选框
│   ├── utils/
│   │   ├── __init__.py              # resource_path() 打包/开发双模式路径
│   │   ├── file_ops.py              # 删除/回收站/管理员检测
│   │   ├── permissions.py           # 路径权限检查
│   │   └── logger.py                # CleanupLogger 按日轮转日志
│   ├── translations/
│   │   ├── diskpulse_zh_CN.ts/.qm   # 中文翻译
│   │   └── diskpulse_en_US.ts/.qm   # 英文翻译
│   └── resources/
│       └── styles.qss               # 深色主题(526 行 QSS)
├── settings.json                    # 用户配置
├── rules.yaml                       # 清理规则(10 条)
└── .opencode/skills/diskpulse-dev.md
```

## 后端功能模块

### 数据模型 (`app/models/`)

- **FileItem** + **FileCategory(enum)**: 支持 `categories: List[FileCategory]` 多类别标记。同一个文件可以同时属于"大文件"和"旧文件"等多个类别。
- **ScanResult**: 聚合所有扫描结果(`large_files`, `temp_files`, `empty_folders`, `duplicate_groups`, `cache_files`, `old_files`)，提供 `all_items` 展平属性。
- **AdvisorItem**: 建议卡片数据模型(`name`, `description`, `importance(1-3)`, `importance_label`, `hint`, `size_bytes`, `files`)。
- **AppSettings(dataclass)**: JSON 持久化。`load()` 先查 CWD，找不到则回退到打包资源路径，均失败则返回默认值。

### 扫描引擎 (`app/scanner/`)

- **ScanEngine(QThread)**: 主扫描线程，通过信号 `progress(str)`, `finished_signal(ScanResult)` 与 UI 通信。
- 扫描流程: `os.scandir()` 递归遍历 → 收集 `FileItem` 列表 → 分类型分析(大文件/临时文件/空文件夹/旧文件/缓存/重复)。
- **duplicate.py**: 两阶段去重 — 先按文件大小分组 → 再对同组文件计算 MD5 哈希。
- **recycler.py**: 通过 `ctypes.windll.shell32` 调用 Windows API 获取回收站信息/清空回收站。

### 智能建议 (`app/advisor/`)

- **AdvisorEngine**: 解析 `rules.yaml` 的 10 条规则，按重要性(3/2/1)分组。
  - 缓存类规则: 展开 `%ENV%` 环境变量，匹配通配符路径，递归枚举文件。
  - recycler 规则: 调用 `get_recycle_bin_info()`。
  - 旧文件/重复文件: 从 ScanResult 中附加。
- **AdvisorActions**: 批量删除(回收站优先)，通过 `CleanupLogger` 记录操作日志。

### 工具函数 (`app/utils/`)

- **resource_path()**: 关键路径函数。PyInstaller 打包后使用 `sys._MEIPASS`，开发时使用模块相对路径。
- **file_ops.py**: `delete_to_recycle_bin()`(send2trash), `delete_permanently()`(shutil), `is_admin()`(shell32 API), `request_admin()`(ShellExecuteW runas 提权)。

## UI 设计思路

### 布局架构

```
QMainWindow
  └─ QSplitter (水平, 可拖拽 160-300px)
       ├─ Sidebar (导航按钮 + 语言切换 + 管理员提权)
       └─ QStackedWidget
            ├─ [0] DashboardPage  (仪表盘)
            ├─ [1] FileListPanel  (扫描结果)
            └─ [2] AdvisorPanel   (清理建议)
```

### 仪表盘 (`DashboardPage`)

- **MiniGauge**: QPainter 自绘小环形进度条(100-160px)，点击选中后更新大仪表盘。
- **DiskGauge**: 大环形进度条(200-400px)，角度渐变色(绿→黄→红)。
- 数据源: `psutil.disk_usage()` 遍历 A-Z 驱动器。

### 文件列表 (`FileListPanel`)

- **QTreeWidget** 6 列: 复选框/文件名/大小/修改时间/路径/类别。
- **CategoryDelegate(QStyledItemDelegate)**: 类别列绘制多色圆角标签。
- **去重合并**: `_path_to_item` 字典映射，同路径文件合并 `categories` 列表。
- 筛选/排序: QComboBox 控制 `_apply_filter()`，类别列按主类别排序。

### 建议面板 (`AdvisorPanel`)

- **AdvisorCard**: 可展开卡片，顶栏(复选框+描述+大小+展开按钮) + 展开后 QTreeWidget 逐文件勾选。
- **三态复选框**: 主复选框与子项联动(全不选/部分选中/全选)。
- 三级风险: ⭐⭐⭐ 强烈建议(绿) / ⭐⭐ 建议(黄) / ⭐ 谨慎(红)。

### 信号/槽通信

| 发送方 | 信号 | 接收方 | 响应 |
|--------|------|--------|------|
| DashboardPage | `start_scan` | MainWindow | 显示 DriveSelectDialog → 创建 ScanEngine → 开始扫描 |
| ScanEngine | `progress` | MainWindow | 更新状态栏 |
| ScanEngine | `finished_signal(ScanResult)` | MainWindow | 填充 FileListPanel, 刷新 AdvisorPanel |
| FileListPanel | `delete_requested(paths)` | MainWindow | 确认 → 删除 |
| AdvisorPanel | clean button | MainWindow | 获取勾选项 → 确认 → 删除 |
| lang_combo | `currentIndexChanged` | MainWindow | 调用 TranslationManager.load_language() |

## 国际化 (i18n)

- **TranslationManager(QObject)**: 单例模式，`get_translation_manager()` 全局获取。
- 热切换流程: 移除旧 `QTranslator` → 加载新 `.qm` → 安装 → 发送 `LanguageChange` 事件 → 通知观察者回调。
- 所有 UI 组件重写 `changeEvent()` 响应 `LanguageChange` 并调用 `retranslateUi()`。
- 翻译文件: `app/translations/diskpulse_{locale}.ts`(源) / `.qm`(编译)。
- 更新翻译步骤:
  1. 在代码中用 `QCoreApplication.translate("Context", "text")` 或 `self.tr("text")` 包裹文本
  2. 运行 `pyside6-lrelease app/translations/*.ts` 重新编译 `.qm`
  3. qm 文件需通过 `--add-data` 打包

## 资源文件

| 文件 | 作用 |
|------|------|
| `app/resources/styles.qss` | 深色主题全局样式 |
| `app/translations/diskpulse_zh_CN.qm` | 中文翻译(编译后) |
| `app/translations/diskpulse_en_US.qm` | 英文翻译(编译后) |
| `rules.yaml` | 清理规则配置(10 条) |
| `settings.json` | 用户配置与 UI 状态持久化。**读取顺序**：`%APPDATA%\DiskPulse\settings.json` → 仓库/安装目录 → `_MEIPASS`；**写入**：先试仓库/安装目录，不可写则回退 `%APPDATA%\DiskPulse\` |

## 文件操作安全机制

1. 默认移入回收站 (`send2trash`)，可切换永久删除
2. 所有删除操作前弹出确认对话框
3. 操作日志 `logs/cleanup_YYYYMMDD.log`
4. 管理员权限: 启动时检测 `is_admin()`，非管理员提示提权

## 版本更新流程

1. 修改代码
2. 更新 `README.md` 更新日志
3. 更新翻译: `pyside6-lrelease app/translations/*.ts`
4. 测试运行: `python main.py`

## 已知问题 & 注意事项

### 已修复 (审查 + 修复)

- `FileListPanel` 曾把 17 个方法定义两次(副本块 385-550 行)，已删除；`file_list.py` 550 → 325 行。
- `main_window._on_language_changed` 曾有同名双定义，生效版本签名是 `(self, index: int)`，
  而 `i18n` 观察者用字符串 `"en_US"` 调用 → `QComboBox.itemData(str)` 抛 `TypeError`，
  被 `except Exception: pass` 吞掉，**语言实际切不了**。已删除观察者通道，改名为
  `_on_lang_combo_changed`，刷新由 `LanguageChange` 事件驱动。
- `CleanupLogger._setup_logger` 在日志目录不可写时抛 `PermissionError` →
  `MainWindow.__init__` 崩溃（装到 Program Files 时**启动即崩**）。已加降级：
  改用 `NullHandler` 并告警。
- `_save_session` 用 `int(...sortIndicatorOrder())` → PySide6 下抛 `TypeError`，
  **每次关窗必崩**且 `settings.save()` 永不执行（设置静默丢失）。改为取 `.value`。
- `AppSettings.save()` 在只读安装目录抛 `PermissionError`。已改为回退写入
  `%APPDATA%\DiskPulse\settings.json`（`load` 也优先读该位置），两者都不可写时降级告警。
- `FileItem.all_categories` 曾在 `categories` 非空时丢弃 `category` 字段，导致
  "同时是大文件 + 重复文件"的条目丢掉主类别标签。已改为取并集。
- `add_items` 结尾无条件 `self._items.extend(items)`，被去重跳过的条目也计入 →
  统计项数与总大小被放大。已改为只 extend 真正新建的条目。
- `AdvisorEngine._evaluate_rule` 读了 `max_age_days` 却从不使用 → 清理建议会把
  `%TEMP%`/`C:\Windows\Temp` 下**全部**文件算作"可释放空间"。已按 mtime 过滤
  （`max_age_days: 1` = 只纳入超过 1 天未修改的文件；0 = 不过滤）。
- `_evaluate_rule` 曾对同一目录遍历两次（`get_folder_size()` + `rglob()`）。已合并为
  一次 `cache_detector.find_files_shallow()`（只扫一层；缓存目录的文件都在层内）。
- 重复文件与缓存扫描曾在 `ScanEngine` 中完全未接线（README 宣传 6 类，实际只有 4 类）。
  已接通 `find_duplicates()` / `scan_cache_paths()`，新增配置 `enable_duplicate_scan`
  (默认 true) 与 `hash_algorithm`。
  **重复组约定**：组内第一个为保留项，按 mtime 升序（最旧优先），其余为可删除副本
  —— 因为 `AdvisorEngine.analyze()` 用 `group[1:]` 计算可释放空间。缓存扫描的文件
  **不并入** `_all_files`，否则同一文件被登记两次会让重复检测产生假阳性。

### i18n 模块解析（重要，与早期记载相反）

`from app.i18n import ...` 解析到 **`app/i18n/__init__.py`（包）**，不是 `app/i18n.py`。
CPython `FileFinder` 在同一个目录内先找 `<name>/__init__.py` 包，再找 `<name>.py`。
实物证据：`app/i18n/__pycache__/__init__.cpython-31{1,2,3}.pyc` 存在，而全仓
`**/i18n*.pyc` 零命中。

因此 **`app/i18n.py` 是死文件**（133 行，从未被 import；其 `translations` 路径也指向
不存在的 `DiskPulse\translations`）。待清理：删除 `app/i18n.py`。

### 其余死代码 / 死配置（零引用）

- `app/utils/permissions.py` 整模块未被引用
- `app/scanner/large_file.py`、`temp_cleaner.py`、`empty_folder.py`：
  与 `engine.py` 内联逻辑重复
- `ScanEngine.progress_value` / `file_found` 信号、`_seen_inodes`
- `main_window._restart_application`；`AdvisorActions`（`main_window` 直接调
  `delete_paths`，绕过了它，连带审计日志从未记录）
- `rules.yaml` 的 `pattern` / `min_size_mb` / `max_access_days` 字段无代码读取
- `AppSettings.use_recycle_bin` / `confirm_before_delete` / `exclude_paths` 无代码读取
  （删除始终走回收站，确认框始终弹）
- `file_item.hash` / `group_id` 字段从未赋值

### 打包注意事项
- 使用 conda Python: `D:\tool\miniconda3\python.exe`
- 需加 `Library\bin` 到 PATH 以解决 DLL 依赖: `$env:Path = "D:\tool\miniconda3\Library\bin;$env:Path"`
- `--add-data` 必须包含: `styles.qss`, `*.qm`, `rules.yaml`, `settings.json`
- 运行时通过 `app/utils/__init__.py:resource_path()` 使用 `sys._MEIPASS` 访问资源
