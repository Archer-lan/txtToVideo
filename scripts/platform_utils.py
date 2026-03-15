"""跨平台工具模块

集中管理所有平台相关的差异逻辑，为各阶段脚本提供统一的跨平台接口。
"""

import os
import platform
import shutil
import signal
import threading
from pathlib import Path


def is_windows() -> bool:
    """检测当前是否为 Windows 平台"""
    return platform.system() == "Windows"


def find_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件路径"""
    path = shutil.which("ffmpeg")
    if path:
        return path
    if is_windows():
        for candidate in [
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        ]:
            if os.path.isfile(candidate):
                return candidate
    return "ffmpeg"


def find_ffprobe() -> str:
    """查找 ffprobe 可执行文件路径"""
    path = shutil.which("ffprobe")
    if path:
        return path
    # 尝试从 ffmpeg 同目录找
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path != "ffmpeg":
        ffprobe_candidate = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe.exe" if is_windows() else "ffprobe")
        if os.path.isfile(ffprobe_candidate):
            return ffprobe_candidate
    return "ffprobe"


FFMPEG = find_ffmpeg()
FFPROBE = find_ffprobe()


def get_default_font_path() -> str:
    """根据平台返回默认中文字体路径

    Returns:
        Windows: C:/Windows/Fonts/msyh.ttc (微软雅黑)
        macOS:   /System/Library/Fonts/Helvetica.ttc
        Linux:   /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc
    """
    system = platform.system()
    if system == "Windows":
        return "C:/Windows/Fonts/msyh.ttc"
    elif system == "Darwin":
        return "/System/Library/Fonts/Helvetica.ttc"
    else:
        return "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"


def get_ffmpeg_subtitle_path(srt_path: Path) -> str:
    """将 SRT 路径转换为 FFmpeg subtitles 滤镜可接受的格式

    Windows: 将反斜杠替换为正斜杠，转义盘符冒号为 \\:
    POSIX:   双重反斜杠转义、冒号转义、单引号转义（保持现有逻辑）

    Args:
        srt_path: SRT 字幕文件路径

    Returns:
        FFmpeg subtitles 滤镜可接受的转义路径字符串
    """
    resolved = str(srt_path.resolve())

    if is_windows():
        # Windows: 反斜杠替换为正斜杠，然后转义冒号
        result = resolved.replace("\\", "/")
        # 转义盘符冒号 (如 C: -> C\\:)，以及路径中其他冒号
        result = result.replace(":", "\\\\:")
        # 转义单引号
        result = result.replace("'", "'\\''")
        return result
    else:
        # POSIX: 保持现有转义逻辑
        result = (
            resolved
            .replace("\\", "\\\\\\\\")
            .replace(":", "\\\\:")
            .replace("'", "'\\''")
        )
        return result


def run_with_timeout(func, args=(), kwargs=None, timeout_seconds=300):
    """跨平台超时执行

    Unix 上使用 signal.SIGALRM 保持现有行为，Windows 上使用 threading 方案。

    Args:
        func: 要执行的可调用对象
        args: 传递给 func 的位置参数
        kwargs: 传递给 func 的关键字参数
        timeout_seconds: 超时秒数，默认 300 秒

    Returns:
        func 的返回值

    Raises:
        TimeoutError: 当执行超过 timeout_seconds 时
    """
    kwargs = kwargs or {}

    if is_windows():
        # Windows: 使用 threading.Thread + thread.join(timeout)
        result = [None]
        exception = [None]

        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            raise TimeoutError(f"操作超时 ({timeout_seconds}s)")

        if exception[0]:
            raise exception[0]

        return result[0]
    else:
        # Unix: 使用 signal.SIGALRM 保持现有行为
        def _timeout_handler(signum, frame):
            raise TimeoutError(f"操作超时 ({timeout_seconds}s)")

        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout_seconds)
        try:
            result = func(*args, **kwargs)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

        return result
