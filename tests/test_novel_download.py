"""
小说下载模块测试

包含 property-based 测试和单元测试。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, strategies as st, assume

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import __init__  # noqa: F401

# 动态导入 00_download_novel 模块
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "download_novel",
    Path(__file__).resolve().parent.parent / "scripts" / "00_download_novel.py",
)
download_novel_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(download_novel_mod)

is_url_or_file = download_novel_mod.is_url_or_file
parse_chapter_range = download_novel_mod.parse_chapter_range
PlatformRouter = download_novel_mod.PlatformRouter
PlatformInfo = download_novel_mod.PlatformInfo
ChapterRange = download_novel_mod.ChapterRange
DownloadResult = download_novel_mod.DownloadResult
UnsupportedPlatformError = download_novel_mod.UnsupportedPlatformError
download_novel = download_novel_mod.download_novel


# ============================================================
# Property-Based Tests: is_url_or_file
# ============================================================

class TestIsUrlOrFilePBT:
    """is_url_or_file 的 property-based 测试"""

    @given(st.text(min_size=1))
    def test_always_returns_valid_type(self, s):
        """任意非空字符串，返回值必为三者之一"""
        result = is_url_or_file(s)
        assert result in ("url", "book_id", "file")

    @given(st.sampled_from(["http://", "https://"]), st.text(min_size=1))
    def test_url_prefix_returns_url(self, prefix, rest):
        """以 http:// 或 https:// 开头的字符串返回 "url" """
        result = is_url_or_file(prefix + rest)
        assert result == "url"

    @given(st.integers(min_value=0, max_value=10**18))
    def test_pure_digits_returns_book_id(self, n):
        """纯数字字符串返回 "book_id" """
        result = is_url_or_file(str(n))
        assert result == "book_id"

    @given(st.text(min_size=1))
    def test_non_url_non_digit_returns_file(self, s):
        """非 URL 非纯数字的字符串返回 "file" """
        s = s.strip()
        assume(len(s) > 0)
        assume(not s.startswith("http://") and not s.startswith("https://"))
        assume(not s.isdigit())
        result = is_url_or_file(s)
        assert result == "file"


# ============================================================
# Property-Based Tests: detect_platform
# ============================================================

class TestDetectPlatformPBT:
    """detect_platform 的 property-based 测试"""

    @given(st.integers(min_value=1, max_value=10**18))
    def test_fanqie_url_returns_correct_platform(self, book_id):
        """番茄小说 URL 返回 fanqie 平台"""
        url = f"https://fanqienovel.com/page/{book_id}"
        router = PlatformRouter()
        info = router.detect_platform(url)
        assert info.platform_name == "fanqie"
        assert info.downloader_type == "fanqie"
        assert info.book_id == str(book_id)

    @given(st.integers(min_value=1, max_value=10**18))
    def test_qidian_url_returns_correct_platform(self, book_id):
        """起点中文网 URL 返回 qidian 平台"""
        url = f"https://book.qidian.com/info/{book_id}"
        router = PlatformRouter()
        info = router.detect_platform(url)
        assert info.platform_name == "qidian"
        assert info.downloader_type == "novel-downloader"
        assert info.book_id == str(book_id)

    @given(st.integers(min_value=1, max_value=10**18))
    def test_pure_digit_defaults_to_fanqie(self, book_id):
        """纯数字 ID 默认路由到番茄小说"""
        router = PlatformRouter()
        info = router.detect_platform(str(book_id))
        assert info.platform_name == "fanqie"
        assert info.book_id == str(book_id)

    def test_unknown_url_raises_error(self):
        """未知 URL 抛出 UnsupportedPlatformError"""
        router = PlatformRouter()
        with pytest.raises(UnsupportedPlatformError):
            router.detect_platform("https://unknown-site.com/book/123")

    @given(st.integers(min_value=1, max_value=10**18))
    def test_changdunovel_url_returns_fanqie(self, book_id):
        """changdunovel URL 也路由到 fanqie"""
        url = f"https://changdunovel.com/page/{book_id}"
        router = PlatformRouter()
        info = router.detect_platform(url)
        assert info.platform_name == "fanqie"
        assert info.book_id == str(book_id)


# ============================================================
# Property-Based Tests: parse_chapter_range
# ============================================================

class TestParseChapterRangePBT:
    """parse_chapter_range 的 property-based 测试"""

    @given(st.integers(min_value=1, max_value=10000), st.integers(min_value=1, max_value=10000))
    def test_start_end_roundtrip(self, start, end):
        """格式化后解析结果与原始值一致"""
        assume(start <= end)
        result = parse_chapter_range(f"{start}-{end}")
        assert result is not None
        assert result.start == start
        assert result.end == end

    @given(st.integers(min_value=1, max_value=10000))
    def test_start_only(self, start):
        """只有起始章节"""
        result = parse_chapter_range(f"{start}-")
        assert result is not None
        assert result.start == start
        assert result.end is None

    @given(st.integers(min_value=1, max_value=10000))
    def test_end_only(self, end):
        """只有结束章节"""
        result = parse_chapter_range(f"-{end}")
        assert result is not None
        assert result.start is None
        assert result.end == end

    def test_none_returns_none(self):
        """None 输入返回 None"""
        assert parse_chapter_range(None) is None

    def test_empty_returns_none(self):
        """空字符串返回 None"""
        assert parse_chapter_range("") is None

    @given(st.integers(min_value=1, max_value=10000))
    def test_single_number(self, n):
        """单个数字视为只下载该章"""
        result = parse_chapter_range(str(n))
        assert result is not None
        assert result.start == n
        assert result.end == n


# ============================================================
# Unit Tests: download_novel 流程编排
# ============================================================

class TestDownloadNovelUnit:
    """download_novel 入口函数的单元测试"""

    def test_download_novel_flow(self, tmp_path):
        """测试正常下载流程编排"""
        output_dir = tmp_path / "input"
        output_file = output_dir / "test_novel.txt"

        mock_result = DownloadResult(
            output_path=output_file,
            title="测试小说",
            chapter_count=5,
            total_chars=10000,
        )

        with patch.object(PlatformRouter, "detect_platform") as mock_detect, \
             patch.object(PlatformRouter, "get_downloader") as mock_get_dl:

            mock_detect.return_value = PlatformInfo(
                platform_name="fanqie",
                downloader_type="fanqie",
                book_id="123456",
                original_source="123456",
            )

            mock_downloader = MagicMock()
            mock_downloader.validate_source.return_value = True
            mock_downloader.download.return_value = mock_result
            mock_get_dl.return_value = mock_downloader

            # 创建假的输出文件
            output_dir.mkdir(parents=True)
            output_file.write_text("测试内容", encoding="utf-8")

            result = download_novel(
                source="123456",
                output_dir=output_dir,
                config={"timeout": 10, "retry": 0},
            )

            assert result.title == "测试小说"
            assert result.chapter_count == 5
            mock_detect.assert_called_once()
            mock_downloader.validate_source.assert_called_once_with("123456")
            mock_downloader.download.assert_called_once()

    def test_download_novel_invalid_source(self, tmp_path):
        """测试书籍验证失败"""
        with patch.object(PlatformRouter, "detect_platform") as mock_detect, \
             patch.object(PlatformRouter, "get_downloader") as mock_get_dl:

            mock_detect.return_value = PlatformInfo(
                platform_name="fanqie",
                downloader_type="fanqie",
                book_id="999",
                original_source="999",
            )

            mock_downloader = MagicMock()
            mock_downloader.validate_source.return_value = False
            mock_get_dl.return_value = mock_downloader

            with pytest.raises(ValueError, match="无法访问书籍"):
                download_novel(
                    source="999",
                    output_dir=tmp_path,
                    config={},
                )

    def test_download_novel_unsupported_platform(self, tmp_path):
        """测试不支持的平台"""
        with pytest.raises(UnsupportedPlatformError):
            download_novel(
                source="https://unknown-site.com/book/123",
                output_dir=tmp_path,
                config={},
            )


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_local_file_classified_as_file(self):
        """本地文件路径被正确分类"""
        assert is_url_or_file("input/chapter01.txt") == "file"
        assert is_url_or_file("./my_novel.txt") == "file"
        assert is_url_or_file("/absolute/path/novel.md") == "file"

    def test_url_classified_as_url(self):
        """URL 被正确分类"""
        assert is_url_or_file("https://fanqienovel.com/page/123") == "url"
        assert is_url_or_file("http://book.qidian.com/info/456") == "url"

    def test_book_id_classified_as_book_id(self):
        """纯数字被正确分类为 book_id"""
        assert is_url_or_file("7143038691944959011") == "book_id"
        assert is_url_or_file("123456") == "book_id"
