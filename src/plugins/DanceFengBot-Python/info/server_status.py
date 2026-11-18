"""服务器状态采集与文本格式化（``#status`` 命令使用）。

统计服务器运行的系统、CPU / 内存占用、软件与 Python 版本、项目运行时长
以及当前时间。

优先使用 ``psutil``（若运行环境已安装）；未安装时：

* Windows：通过 ``ctypes`` 调用 ``GlobalMemoryStatusEx`` / ``GetSystemTimes`` /
  ``GetProcessTimes``；
* Linux：读取 ``/proc/stat`` 与 ``/proc/meminfo``；

因此不需要新增第三方依赖，缺少数据时对应项显示「不可用」。
"""

from __future__ import annotations

import ctypes
import os
import platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

try:  # Python 3.11+ 内置
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 低版本 Python 兜底
    tomllib = None  # type: ignore[assignment]

try:  # 可选依赖：装了就用，没装走系统原生实现
    import psutil  # type: ignore
except Exception:  # noqa: BLE001
    psutil = None

# 插件加载时刻：没有 psutil 时用它近似「项目启动时间」
_PLUGIN_LOADED_AT = time.time()

# FILETIME 从 1601-01-01 起算（100ns 为单位），与 Unix epoch 相差的秒数
_FILETIME_EPOCH_DELTA = 116_444_736_000

_PROJECT_ROOT: Path | None = None


# ---------------------------------------------------------------- Windows 原生实现
class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _FileTime(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_ulong),
        ("dwHighDateTime", ctypes.c_ulong),
    ]


def _filetime_value(value: _FileTime) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _windows_memory() -> tuple[int, int] | None:
    """返回 ``(已用字节, 总字节)``。"""
    if os.name != "nt":
        return None
    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        total = int(status.ullTotalPhys)
        return total - int(status.ullAvailPhys), total
    except Exception:  # noqa: BLE001
        return None


def _windows_cpu_times() -> tuple[int, int] | None:
    """返回 ``(忙时 tick, 总 tick)``；``GetSystemTimes`` 的 kernel 已包含 idle。"""
    if os.name != "nt":
        return None
    try:
        idle = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        ok = ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        )
        if not ok:
            return None
        idle_value = _filetime_value(idle)
        total = _filetime_value(kernel) + _filetime_value(user)
        return total - idle_value, total
    except Exception:  # noqa: BLE001
        return None


def _windows_process_start() -> float | None:
    """当前进程的启动时间（Unix 秒）。"""
    if os.name != "nt":
        return None
    try:
        creation = _FileTime()
        exit_time = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        )
        if not ok:
            return None
        return _filetime_value(creation) / 10_000_000 - _FILETIME_EPOCH_DELTA
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- Linux 原生实现
def parse_proc_stat(line: str) -> tuple[int, int] | None:
    """解析 ``/proc/stat`` 的 ``cpu ...`` 行，返回 ``(忙时 tick, 总 tick)``。"""

    parts = line.split()
    if len(parts) < 5 or parts[0] != "cpu":
        return None
    try:
        values = [int(value) for value in parts[1:]]
    except ValueError:
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return total - idle, total


def parse_meminfo(text: str) -> tuple[int, int] | None:
    """解析 ``/proc/meminfo``，返回 ``(已用字节, 总字节)``。"""
    info: dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        fields = rest.split()
        if not key.strip() or not fields:
            continue
        try:
            info[key.strip()] = int(fields[0]) * 1024
        except ValueError:
            continue
    total = info.get("MemTotal")
    available = info.get("MemAvailable", info.get("MemFree"))
    if not total or available is None or available > total:
        return None
    return total - available, total


def _linux_cpu_times() -> tuple[int, int] | None:
    try:
        with open("/proc/stat", encoding="utf-8") as fp:
            line = fp.readline()
    except OSError:
        return None
    return parse_proc_stat(line)


def _linux_memory() -> tuple[int, int] | None:
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_meminfo(text)


# ---------------------------------------------------------------- 通用采集
def cpu_percent(interval: float = 0.3) -> float | None:
    """采样系统 CPU 使用率（0~100），失败返回 ``None``。"""
    if psutil is not None:
        try:
            return float(psutil.cpu_percent(interval=interval))
        except Exception:  # noqa: BLE001
            pass

    sampler = None
    if os.name == "nt":
        sampler = _windows_cpu_times
    elif sys.platform.startswith("linux"):
        sampler = _linux_cpu_times
    if sampler is None:
        return None

    first = sampler()
    if first is None:
        return None
    time.sleep(interval)
    second = sampler()
    if second is None:
        return None

    busy = second[0] - first[0]
    total = second[1] - first[1]
    if total <= 0:
        return None
    return max(0.0, min(100.0, busy * 100.0 / total))


def memory_usage() -> tuple[int, int] | None:
    """返回 ``(已用字节, 总字节)``，失败返回 ``None``。"""
    if psutil is not None:
        try:
            memory = psutil.virtual_memory()
            return int(memory.total - memory.available), int(memory.total)
        except Exception:  # noqa: BLE001
            pass
    if os.name == "nt":
        return _windows_memory()
    if sys.platform.startswith("linux"):
        return _linux_memory()
    return None


def process_uptime_seconds() -> float:
    """当前进程（项目）已运行的秒数。"""
    if psutil is not None:
        try:
            return max(0.0, time.time() - psutil.Process().create_time())
        except Exception:  # noqa: BLE001
            pass
    if os.name == "nt":
        started = _windows_process_start()
        if started is not None:
            return max(0.0, time.time() - started)
    return max(0.0, time.time() - _PLUGIN_LOADED_AT)


def _find_project_root() -> Path | None:
    """从当前文件向上查找 ``pyproject.toml``，定位项目根目录。"""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").is_file():
            _PROJECT_ROOT = parent
            return parent
    return None


def software_version() -> str:
    """读取 ``pyproject.toml`` 中的项目版本。"""
    root = _find_project_root()
    if root is None or tomllib is None:
        return "未知"
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return "未知"
    project = data.get("project") or {}
    return str(project.get("version") or "未知")


def system_description() -> str:
    """系统描述，如 ``Windows 10.0.26100（AMD64）`` / ``Linux 5.15.0（x86_64）``。"""
    machine = platform.machine()
    if os.name == "nt":
        release = platform.version() or platform.release() or "Windows"
        system = f"Windows {release}"
    elif sys.platform.startswith("linux"):
        system = f"Linux {platform.release()}".strip()
    else:
        system = platform.platform()
    if machine:
        system += f"（{machine}）"
    return system


def format_bytes(num_bytes: int) -> str:
    """把字节数格式化为易读的 MB / GB。"""
    gb = num_bytes / (1024**3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    return f"{num_bytes / (1024**2):.0f} MB"


def format_duration(seconds: float) -> str:
    """把秒数格式化为 ``3 天 04:05:06`` / ``04:05:06``。"""
    total = int(max(0.0, seconds))
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days} 天 {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@dataclass(frozen=True)
class ServerStatus:
    """一次服务器状态采样结果。"""

    system: str
    cpu_percent: float | None
    cpu_count: int
    memory_used: int | None
    memory_total: int | None
    version: str
    python_version: str
    uptime_seconds: float
    now: datetime

    def format(self) -> str:
        if self.cpu_percent is None:
            cpu_text = "不可用"
        else:
            cpu_text = f"{self.cpu_percent:.1f}%"
            if self.cpu_count > 0:
                cpu_text += f"（{self.cpu_count} 核）"

        if self.memory_used is None or not self.memory_total:
            memory_text = "不可用"
        else:
            percent = self.memory_used * 100.0 / self.memory_total
            memory_text = (
                f"{percent:.1f}%（{format_bytes(self.memory_used)}"
                f" / {format_bytes(self.memory_total)}）"
            )

        offset = self.now.astimezone().utcoffset() or timedelta(0)
        total_minutes = int(offset.total_seconds() // 60)
        sign = "+" if total_minutes >= 0 else "-"
        total_minutes = abs(total_minutes)
        offset_text = f"UTC{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"

        return "\n".join(
            [
                "🖥 服务器状态",
                f"系统：{self.system}",
                f"CPU：{cpu_text}",
                f"内存：{memory_text}",
                f"版本：DanceFengBot-Python {self.version}",
                f"Python：{self.python_version}",
                f"运行时长：{format_duration(self.uptime_seconds)}",
                f"当前时间：{self.now:%Y-%m-%d %H:%M:%S}（{offset_text}）",
            ]
        )


def collect_status() -> ServerStatus:
    """采集一次服务器状态（CPU 采样会阻塞约 0.3 秒，调用方应放入线程）。"""
    used, total = memory_usage() or (None, None)
    return ServerStatus(
        system=system_description(),
        cpu_percent=cpu_percent(),
        cpu_count=os.cpu_count() or 0,
        memory_used=used,
        memory_total=total,
        version=software_version(),
        python_version=platform.python_version(),
        uptime_seconds=process_uptime_seconds(),
        now=datetime.now(),
    )
