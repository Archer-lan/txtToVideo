#!/usr/bin/env python3
"""
阶段 0: 小说下载

根据用户输入的 URL 或书籍 ID，自动识别平台并下载小说文本到 input/ 目录。
支持番茄小说、起点中文网、笔趣阁等平台。
"""

import json
import logging
import platform
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 番茄小说字体反混淆映射表
# ============================================================
# 番茄小说使用自定义 woff2 字体将 PUA (Private Use Area) Unicode
# 码点映射到真实汉字，以下映射表用于解码。
# 来源: fanqienovel-downloader 项目 (MIT License)

_FANQIE_CODE = [[58344, 58715], [58345, 58716]]
_FANQIE_CHARSET = json.loads(
    '[["D","在","主","特","家","军","然","表","场","4","要","只","v","和","?","6","别","还","g","现","儿","岁","?","?","此","象","月","3","出","战","工","相","o","男","直","失","世","F","都","平","文","什","V","O","将","真","T","那","当","?","会","立","些","u","是","十","张","学","气","大","爱","两","命","全","后","东","性","通","被","1","它","乐","接","而","感","车","山","公","了","常","以","何","可","话","先","p","i","叫","轻","M","士","w","着","变","尔","快","l","个","说","少","色","里","安","花","远","7","难","师","放","t","报","认","面","道","S","?","克","地","度","I","好","机","U","民","写","把","万","同","水","新","没","书","电","吃","像","斯","5","为","y","白","几","日","教","看","但","第","加","候","作","上","拉","住","有","法","r","事","应","位","利","你","声","身","国","问","马","女","他","Y","比","父","x","A","H","N","s","X","边","美","对","所","金","活","回","意","到","z","从","j","知","又","内","因","点","Q","三","定","8","R","b","正","或","夫","向","德","听","更","?","得","告","并","本","q","过","记","L","让","打","f","人","就","者","去","原","满","体","做","经","K","走","如","孩","c","G","给","使","物","?","最","笑","部","?","员","等","受","k","行","一","条","果","动","光","门","头","见","往","自","解","成","处","天","能","于","名","其","发","总","母","的","死","手","入","路","进","心","来","h","时","力","多","开","已","许","d","至","由","很","界","n","小","与","Z","想","代","么","分","生","口","再","妈","望","次","西","风","种","带","J","?","实","情","才","这","?","E","我","神","格","长","觉","间","年","眼","无","不","亲","关","结","0","友","信","下","却","重","己","老","2","音","字","m","呢","明","之","前","高","P","B","目","太","e","9","起","稜","她","也","W","用","方","子","英","每","理","便","四","数","期","中","C","外","样","a","海","们","任"],["s","?","作","口","在","他","能","并","B","士","4","U","克","才","正","们","字","声","高","全","尔","活","者","动","其","主","报","多","望","放","h","w","次","年","?","中","3","特","于","十","入","要","男","同","G","面","分","方","K","什","再","教","本","己","结","1","等","世","N","?","说","g","u","期","Z","外","美","M","行","给","9","文","将","两","许","张","友","0","英","应","向","像","此","白","安","少","何","打","气","常","定","间","花","见","孩","它","直","风","数","使","道","第","水","已","女","山","解","d","P","的","通","关","性","叫","儿","L","妈","问","回","神","来","S","","四","望","前","国","些","O","v","l","A","心","平","自","无","军","光","代","是","好","却","c","得","种","就","意","先","立","z","子","过","Y","j","表","","么","所","接","了","名","金","受","J","满","眼","没","部","那","m","每","车","度","可","R","斯","经","现","门","明","V","如","走","命","y","6","E","战","很","上","f","月","西","7","长","夫","想","话","变","海","机","x","到","W","一","成","生","信","笑","但","父","开","内","东","马","日","小","而","后","带","以","三","几","为","认","X","死","员","目","位","之","学","远","人","音","呢","我","q","乐","象","重","对","个","被","别","F","也","书","稜","D","写","还","因","家","发","时","i","或","住","德","当","o","l","比","觉","然","吃","去","公","a","老","亲","情","体","太","b","万","C","电","理","?","失","力","更","拉","物","着","原","她","工","实","色","感","记","看","出","相","路","大","你","候","2","和","?","与","p","样","新","只","便","最","不","进","T","r","做","格","母","总","爱","身","师","轻","知","往","加","从","?","天","e","H","?","听","场","由","快","边","让","把","任","8","条","头","事","至","起","点","真","手","这","难","都","界","用","法","n","处","下","又","Q","告","地","5","k","t","岁","有","会","果","利","民"]]'
)


def decode_fanqie_text(text: str) -> str:
    """
    解码番茄小说字体混淆文本。

    番茄小说使用 PUA Unicode 码点替换真实汉字，
    此函数将 PUA 码点还原为对应的真实字符。
    两种编码模式 (mode 0/1) 会依次尝试。
    """
    result = []
    for ch in text:
        code = ord(ch)
        decoded = False
        for mode in range(2):
            start, end = _FANQIE_CODE[mode]
            if start <= code <= end:
                bias = code - start
                if bias < len(_FANQIE_CHARSET[mode]):
                    mapped = _FANQIE_CHARSET[mode][bias]
                    if mapped and mapped != '?':
                        result.append(mapped)
                        decoded = True
                        break
        if not decoded:
            result.append(ch)
    return ''.join(result)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class PlatformInfo:
    """平台信息"""
    platform_name: str       # 平台名称: "fanqie", "qidian", "biquge", ...
    downloader_type: str     # 下载器类型: "novel-downloader" | "fanqie"
    book_id: str             # 从 URL 中提取的书籍 ID
    original_source: str     # 用户原始输入


@dataclass
class DownloadResult:
    """下载结果"""
    output_path: Path        # 输出文件路径
    title: str               # 书名
    chapter_count: int       # 下载章节数
    total_chars: int         # 总字数


@dataclass
class ChapterRange:
    """章节范围"""
    start: Optional[int] = None  # 起始章节号（含），None 表示从头
    end: Optional[int] = None    # 结束章节号（含），None 表示到末尾


class UnsupportedPlatformError(Exception):
    """无法识别的 URL 格式"""
    pass


class DownloaderNotInstalledError(Exception):
    """下载器依赖未安装"""
    pass


# ============================================================
# 抽象基类
# ============================================================

class BaseDownloader(ABC):
    """下载器抽象基类"""

    @abstractmethod
    def download(
        self,
        book_id: str,
        output_dir: Path,
        chapter_range: Optional[ChapterRange] = None,
    ) -> DownloadResult:
        """下载小说并保存为 TXT"""
        ...

    @abstractmethod
    def validate_source(self, book_id: str) -> bool:
        """验证书籍 ID 是否有效"""
        ...


# ============================================================
# 工具函数
# ============================================================

def is_url_or_file(input_str: str) -> str:
    """
    判断用户输入是 URL、书籍 ID 还是本地文件路径

    Returns:
        "url" | "book_id" | "file"
    """
    s = input_str.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return "url"
    if s.isdigit():
        return "book_id"
    return "file"


def parse_chapter_range(chapters_str: Optional[str]) -> Optional[ChapterRange]:
    """
    解析章节范围字符串

    支持格式: "1-10", "5-", "-20", None
    """
    if chapters_str is None:
        return None

    chapters_str = chapters_str.strip()
    if not chapters_str:
        return None

    if "-" not in chapters_str:
        # 单个数字，视为只下载该章
        n = int(chapters_str)
        return ChapterRange(start=n, end=n)

    parts = chapters_str.split("-", 1)
    start = int(parts[0]) if parts[0].strip() else None
    end = int(parts[1]) if parts[1].strip() else None
    return ChapterRange(start=start, end=end)


# ============================================================
# 平台路由器
# ============================================================

# 平台 URL 模式映射: platform_name -> [(regex_pattern, ...)]
PLATFORM_PATTERNS: Dict[str, List[str]] = {
    "fanqie": [
        r"fanqienovel\.com/page/(\d+)",
        r"changdunovel\.com/page/(\d+)",
    ],
    "qidian": [
        r"book\.qidian\.com/info/(\d+)",
        r"m\.qidian\.com/book/(\d+)",
    ],
    "biquge": [
        r"biquge\.\w+/book/(\d+)",
        r"xbiquge\.\w+/book/(\d+)",
    ],
}

# 平台 → 下载器类型映射
DOWNLOADER_MAP: Dict[str, str] = {
    "fanqie": "fanqie",
    "qidian": "novel-downloader",
    "biquge": "novel-downloader",
}

SUPPORTED_PLATFORMS = list(PLATFORM_PATTERNS.keys())


class PlatformRouter:
    """根据 URL/ID 路由到对应下载器"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def detect_platform(self, source: str) -> PlatformInfo:
        """识别输入来源所属平台"""
        source = source.strip()

        # 纯数字 → 默认当作番茄小说 ID
        if source.isdigit():
            return PlatformInfo(
                platform_name="fanqie",
                downloader_type="fanqie",
                book_id=source,
                original_source=source,
            )

        # URL 匹配
        for platform, patterns in PLATFORM_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, source)
                if match:
                    book_id = match.group(1)
                    return PlatformInfo(
                        platform_name=platform,
                        downloader_type=DOWNLOADER_MAP[platform],
                        book_id=book_id,
                        original_source=source,
                    )

        raise UnsupportedPlatformError(
            f"无法识别的 URL: {source}\n支持的平台: {', '.join(SUPPORTED_PLATFORMS)}"
        )

    def get_downloader(self, platform_info: PlatformInfo) -> BaseDownloader:
        """根据平台信息返回对应下载器实例"""
        if platform_info.downloader_type == "fanqie":
            return FanqieDownloaderAdapter(self.config.get("fanqie", {}))
        else:
            return NovelDownloaderAdapter(self.config)


# ============================================================
# 下载器适配器
# ============================================================

class NovelDownloaderAdapter(BaseDownloader):
    """适配 novel-downloader (pip install novel-downloader)"""

    def __init__(self, config: dict):
        self.config = config
        self._check_installed()

    def _check_installed(self):
        try:
            import novel_downloader  # noqa: F401
        except ImportError:
            raise DownloaderNotInstalledError(
                "novel-downloader 未安装，请执行: pip install novel-downloader"
            )

    def download(
        self,
        book_id: str,
        output_dir: Path,
        chapter_range: Optional[ChapterRange] = None,
    ) -> DownloadResult:
        import asyncio
        import sys
        from novel_downloader.plugins import registrar
        from novel_downloader.schemas import BookConfig, ClientConfig

        # 从 config 中获取站点信息，默认 qidian
        site = self.config.get("site", "qidian")
        interval = self.config.get("request_interval", 0.5)

        book = BookConfig(book_id=book_id)
        cfg = ClientConfig(request_interval=interval)
        client = registrar.get_client(site, cfg)

        async def _do_download():
            async with client:
                await client.download(book)
            # 导出为 txt
            client.export(book, formats=["txt"])

        # Windows 上 ProactorEventLoop 与部分异步库不兼容，切换到 SelectorEventLoop
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(_do_download())

        # 查找导出的 txt 文件
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # novel-downloader 默认导出到当前目录，需要移动到 output_dir
        # 查找最新生成的 txt 文件
        import glob
        txt_files = sorted(glob.glob("*.txt"), key=lambda f: Path(f).stat().st_mtime, reverse=True)

        if not txt_files:
            raise FileNotFoundError("下载完成但未找到导出的 TXT 文件")

        src = Path(txt_files[0])
        dst = output_dir / src.name
        src.rename(dst)

        content = dst.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        # 粗略估算章节数（以"第X章"开头的行）
        chapter_count = sum(1 for line in lines if re.match(r"^第.+章", line.strip()))
        if chapter_count == 0:
            chapter_count = 1

        title = src.stem
        return DownloadResult(
            output_path=dst,
            title=title,
            chapter_count=chapter_count,
            total_chars=len(content),
        )

    def validate_source(self, book_id: str) -> bool:
        """验证书籍 ID 格式（基本校验）"""
        return bool(book_id and book_id.strip())


def _get_user_agent() -> str:
    """根据平台返回对应的 User-Agent 字符串"""
    if platform.system() == "Windows":
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    else:
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )


class FanqieDownloaderAdapter(BaseDownloader):
    """适配番茄小说下载（通过 fanqienovel.com API 抓取）"""

    FANQIE_DIR_URL = "https://fanqienovel.com/api/reader/directory/detail"
    FANQIE_READER_URL = "https://fanqienovel.com/reader/"
    HEADERS = {
        "User-Agent": _get_user_agent(),
    }

    def __init__(self, config: dict):
        self.config = config

    def _get_chapter_content(self, item_id: str) -> str:
        """通过第三方 API 获取章节正文（无字体混淆）"""
        import requests

        # 使用第三方 API，返回干净的 HTML 内容
        api_url = f"http://yuefanqie.jingluo.love/content?item_id={item_id}"
        try:
            resp = requests.get(api_url, timeout=self.config.get("timeout", 30))
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == 0 and data.get("data", {}).get("content"):
                html_content = data["data"]["content"]
                # 清理 HTML 标签，提取纯文本
                text = re.sub(r"<header>.*?</header>", "", html_content, flags=re.DOTALL)
                text = re.sub(r"<footer>.*?</footer>", "", text, flags=re.DOTALL)
                paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", text, re.DOTALL)
                if paragraphs:
                    lines = []
                    for p in paragraphs:
                        clean = re.sub(r"<[^>]+>", "", p)
                        clean = clean.replace("&nbsp;", " ").replace("&lt;", "<")
                        clean = clean.replace("&gt;", ">").replace("&amp;", "&")
                        clean = clean.strip()
                        if clean:
                            lines.append(clean)
                    if lines:
                        return "\n".join(lines)

                # 如果没有 <p> 标签，直接清理所有 HTML
                clean = re.sub(r"<[^>]+>", "\n", html_content)
                clean = re.sub(r"\n{2,}", "\n", clean).strip()
                if clean:
                    return clean
        except Exception as e:
            logger.warning(f"第三方 API 获取失败 (item_id={item_id}): {e}，回退到直接抓取")

        # 回退：直接从番茄小说阅读页抓取（可能有乱码）
        return self._get_chapter_content_fallback(item_id)
    def _get_chapter_content_fallback(self, item_id: str) -> str:
        """回退方案：直接从阅读页 HTML 提取并解码字体混淆"""
        import requests

        resp = requests.get(
            f"{self.FANQIE_READER_URL}{item_id}",
            headers=self.HEADERS,
            timeout=self.config.get("timeout", 30),
        )
        resp.raise_for_status()
        html = resp.text

        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
        if not paragraphs:
            match = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
            if match:
                return decode_fanqie_text(match.group(1))
            return "[内容获取失败]"

        lines = []
        for p in paragraphs:
            text = re.sub(r"<[^>]+>", "", p)
            text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
            text = text.replace("&amp;", "&").replace("&#x27;", "'").strip()
            if text:
                lines.append(decode_fanqie_text(text))

        return "\n".join(lines)

    def download(
        self,
        book_id: str,
        output_dir: Path,
        chapter_range: Optional[ChapterRange] = None,
    ) -> DownloadResult:
        import requests
        import time

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 获取目录
        logger.info(f"获取番茄小说目录: book_id={book_id}")
        resp = requests.get(
            self.FANQIE_DIR_URL,
            params={"bookId": book_id},
            headers=self.HEADERS,
            timeout=self.config.get("timeout", 30),
        )
        resp.raise_for_status()
        data = resp.json()

        dir_data = data.get("data", {})
        all_item_ids = dir_data.get("allItemIds", [])

        if not all_item_ids:
            raise ValueError(f"书籍 {book_id} 没有可下载的章节")

        # 从 chapterListWithVolume 获取章节标题映射
        chapter_titles = {}
        for volume in dir_data.get("chapterListWithVolume", []):
            # volume 是一个 list of chapter dicts
            if isinstance(volume, list):
                for ch in volume:
                    chapter_titles[str(ch.get("itemId", ""))] = ch.get("title", "")
            elif isinstance(volume, dict):
                for ch in volume.get("chapterList", []):
                    chapter_titles[str(ch.get("itemId", ""))] = ch.get("title", "")

        # 从页面获取书名
        title = f"fanqie_{book_id}"
        try:
            page_resp = requests.get(
                f"https://fanqienovel.com/page/{book_id}",
                headers=self.HEADERS,
                timeout=10,
            )
            match = re.search(r"<title>([^<]+)</title>", page_resp.text)
            if match:
                raw_title = match.group(1)
                # 清理常见后缀
                for suffix in ["完整版在线免费阅读", "在线免费阅读", "免费阅读",
                               "_番茄小说", "-番茄小说", "番茄小说官网",
                               "小说官网"]:
                    raw_title = raw_title.replace(suffix, "")
                # 处理 "书名_书名xxx" 格式，取下划线前的部分
                if "_" in raw_title:
                    parts = raw_title.split("_")
                    # 如果第一部分是第二部分的子串，只保留第一部分
                    if len(parts) >= 2 and parts[0] in parts[1]:
                        raw_title = parts[0]
                raw_title = raw_title.strip(" -_|")
                if raw_title:
                    title = raw_title
        except Exception:
            pass

        # 应用章节范围
        total_chapters = len(all_item_ids)
        start_idx = (chapter_range.start - 1) if (chapter_range and chapter_range.start) else 0
        end_idx = chapter_range.end if (chapter_range and chapter_range.end) else total_chapters

        if end_idx > total_chapters:
            logger.warning(f"指定的结束章节 {end_idx} 超过实际章节数 {total_chapters}，将下载到最后一章")
            end_idx = total_chapters

        selected_ids = all_item_ids[start_idx:end_idx]
        logger.info(f"下载章节 {start_idx + 1}-{end_idx} / {total_chapters}")

        # 逐章下载内容
        lines = [f"《{title}》\n"]
        for i, item_id in enumerate(selected_ids):
            ch_title = chapter_titles.get(str(item_id), f"第{start_idx + i + 1}章")
            logger.info(f"  [{i+1}/{len(selected_ids)}] {ch_title}")

            try:
                content = self._get_chapter_content(str(item_id))
            except Exception as e:
                logger.warning(f"章节 {ch_title} 下载失败: {e}")
                content = "[内容获取失败]"

            lines.append(f"\n{ch_title}\n\n{content}\n")

            # 请求间隔，避免被限流
            if i < len(selected_ids) - 1:
                time.sleep(0.5)

        # 写入文件
        output_path = output_dir / f"{title}.txt"
        full_text = "\n".join(lines)
        output_path.write_text(full_text, encoding="utf-8")

        return DownloadResult(
            output_path=output_path,
            title=title,
            chapter_count=len(selected_ids),
            total_chars=len(full_text),
        )

    def validate_source(self, book_id: str) -> bool:
        """验证番茄小说书籍 ID 是否有效"""
        try:
            import requests
            resp = requests.get(
                self.FANQIE_DIR_URL,
                params={"bookId": book_id},
                headers=self.HEADERS,
                timeout=10,
            )
            data = resp.json()
            return bool(data.get("data", {}).get("allItemIds"))
        except Exception:
            return False


# ============================================================
# 阶段 0 入口函数
# ============================================================

def download_novel(
    source: str,
    output_dir: Path,
    config: dict,
    chapter_range: Optional[ChapterRange] = None,
) -> DownloadResult:
    """
    阶段 0 主入口：根据 source 自动路由并下载小说

    Args:
        source: URL 或书籍 ID
        output_dir: 输出目录
        config: pipeline.yaml 中的 download 配置段
        chapter_range: 可选章节范围

    Returns:
        DownloadResult 包含输出文件路径
    """
    from scripts.platform_utils import run_with_timeout

    config = config or {}
    timeout = config.get("timeout", 300)
    max_retries = config.get("retry", 2)

    # Step 1: 路由到对应平台
    router = PlatformRouter(config)
    platform_info = router.detect_platform(source)
    logger.info(f"识别平台: {platform_info.platform_name} (book_id={platform_info.book_id})")

    # Step 2: 获取下载器
    downloader = router.get_downloader(platform_info)

    # Step 3: 验证书籍可访问
    if not downloader.validate_source(platform_info.book_id):
        raise ValueError(f"无法访问书籍: {platform_info.book_id}")

    # Step 4: 带超时和重试的下载
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = run_with_timeout(
                downloader.download,
                kwargs={
                    "book_id": platform_info.book_id,
                    "output_dir": output_dir,
                    "chapter_range": chapter_range,
                },
                timeout_seconds=timeout,
            )

            # Step 5: 验证输出
            if not result.output_path.exists():
                raise FileNotFoundError(f"下载文件不存在: {result.output_path}")
            if result.output_path.stat().st_size == 0:
                raise ValueError(f"下载文件为空: {result.output_path}")

            logger.info(
                f"下载完成: {result.title}, "
                f"{result.chapter_count} 章, {result.total_chars} 字"
            )
            return result

        except TimeoutError:
            last_error = TimeoutError(f"下载超时 ({timeout}s)")
            logger.warning(f"下载超时 (尝试 {attempt + 1}/{max_retries + 1})")
        except Exception as e:
            last_error = e
            logger.warning(f"下载失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}")

    raise RuntimeError(f"下载失败，已重试 {max_retries} 次: {last_error}")
