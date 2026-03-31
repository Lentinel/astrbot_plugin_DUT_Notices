import asyncio
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from astrbot.api import logger

from sources import SOURCES, SourceConfig
from parsers import filter_title_by_keyword

CHINA_TZ = timezone(timedelta(hours=8))
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
DATE_PATTERN = re.compile(
    r"(?P<year>\d{4})\s*(?:年 |[-/.])\s*(?P<month>\d{1,2})\s*(?:月 |[-/.])\s*(?P<day>\d{1,2})\s*日？"
)


class Notice(TypedDict):
    id: str
    title: str
    link: str
    source: str
    source_key: str
    category: str
    date: str
    pub_date: str
    published_at: datetime


class DutRssService:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    async def fetch_notices(self, source_keys: set[str] | None = None) -> list[Notice]:
        timeout_sec = self._cfg_int("request_timeout_seconds", 20)
        max_items = self._cfg_int("rss_max_items", 50)
        selected_sources = [
            source for source in SOURCES if source_keys is None or source["key"] in source_keys
        ]
        if source_keys is not None and not selected_sources:
            logger.info(f"[DUT RSS] 未找到匹配来源 source_keys={sorted(source_keys)}")

        async with httpx.AsyncClient(
            timeout=timeout_sec,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        ) as client:
            results = await asyncio.gather(
                *(self._fetch_source_notices(client, source) for source in selected_sources),
                return_exceptions=True,
            )

        notices: list[Notice] = []
        for source, result in zip(selected_sources, results):
            if isinstance(result, Exception):
                logger.info(f"[DUT RSS] 抓取来源失败 {source['key']} {source['url']}: {result}")
                continue
            notices.extend(result)

        deduped: dict[str, Notice] = {}
        for item in notices:
            deduped[item["link"]] = item

        ordered = sorted(
            deduped.values(),
            key=lambda item: (item["published_at"], item["source"]),
            reverse=True,
        )
        return ordered[:max_items]

    async def write_rss(self, notices: list[Notice]):
        now_str = datetime.now(CHINA_TZ).strftime("%a, %d %b %Y %H:%M:%S +0800")

        rss = ET.Element("rss", version="2.0")
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = self._cfg_str("rss_title", "DUT 多站点通知聚合")
        ET.SubElement(channel, "link").text = "https://jxyxbzzx.dlut.edu.cn/tzgg/kfqxq.htm"
        ET.SubElement(channel, "description").text = "大连理工大学开发区校区多来源通知聚合"
        ET.SubElement(channel, "lastBuildDate").text = now_str

        for notice in notices:
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = f"[{notice['source']}] {notice['title']}"
            ET.SubElement(item, "link").text = notice["link"]
            ET.SubElement(item, "guid").text = notice["id"]
            ET.SubElement(item, "pubDate").text = notice["pub_date"]
            ET.SubElement(item, "description").text = (
                f"来源：{notice['source']} | 分类：{notice['category']} | 日期：{notice['date']}"
            )

        xml_data = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
        path = self.rss_file_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(xml_data)

        logger.info(f"[DUT RSS] RSS 文件已更新 {path} items={len(notices)}")

    @property
    def rss_file_path(self) -> Path:
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path

            base = get_astrbot_data_path() / "plugin_data" / "astrbot_plugin_DUT_Notices"
        except Exception:
            base = Path("data") / "plugin_data" / "astrbot_plugin_DUT_Notices"
        return base / "dut_notice_rss.xml"

    async def _fetch_source_notices(
        self, client: httpx.AsyncClient, source: SourceConfig
    ) -> list[Notice]:
        # 采购信息网使用专门的 API 抓取方法
        if source.get("category") == "cgbmis":
            return await self._fetch_cgbmis_notices(client, source)

        page_urls = [source["url"], *source.get("extra_urls", [])]
        notices: list[Notice] = []
        seen_links: set[str] = set()

        for page_url in page_urls:
            response = await client.get(page_url, headers=self._request_headers(source, page_url))
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            tags = soup.select(source["selector"])
            if not tags:
                logger.info(
                    f"[DUT RSS] 选择器未命中 {source['key']} {page_url} selector={source['selector']}"
                )
                continue

            for tag in tags:
                if not isinstance(tag, Tag):
                    continue

                href = (tag.get("href") or "").strip()
                if not href:
                    continue

                title = source["parser"](tag).strip()
                if not title:
                    continue

                base_url = source.get("base_url") or page_url
                full_url = urljoin(base_url, href)
                if full_url in seen_links:
                    continue

                published_at = self._extract_published_at(tag, source)
                notices.append(
                    {
                        "id": self._make_notice_id(source["key"], full_url),
                        "title": title,
                        "link": full_url,
                        "source": source["name"],
                        "source_key": source["key"],
                        "category": source["category"],
                        "date": published_at.strftime("%Y-%m-%d"),
                        "pub_date": published_at.strftime("%a, %d %b %Y %H:%M:%S +0800"),
                        "published_at": published_at,
                    }
                )
                seen_links.add(full_url)

        if not notices:
            logger.info(f"[DUT RSS] 来源无有效条目 {source['key']} urls={page_urls}")
        return notices

    async def _fetch_cgbmis_notices(
        self, client: httpx.AsyncClient, source: SourceConfig
    ) -> list[Notice]:
        request_spec = self._build_cgbmis_request(source)
        if request_spec is None:
            logger.info(f"[DUT RSS] cgbmis 来源缺少请求映射：{source.get('key', '')}")
            return []

        parsed = urlparse(source["url"])
        api_url = f"{parsed.scheme}://{parsed.netloc}/sfw_cms/e"
        payload = {
            "window_": "json",
            "request_method_": "ajax",
            "browser_": "notmsie",
            "browser_version_": "1",
            "t_": str(datetime.now(CHINA_TZ).timestamp()),
            **request_spec,
        }

        response = await client.post(
            api_url,
            data=payload,
            headers=self._request_headers(source, api_url),
        )
        response.raise_for_status()

        body = response.json()
        raw_items = body.get("resultset", []) if isinstance(body, dict) else []
        if not isinstance(raw_items, list):
            raw_items = []

        notices: list[Notice] = []
        seen_links: set[str] = set()

        for item in raw_items:
            if not isinstance(item, dict):
                continue

            raw_title = str(item.get("subject") or "").strip()
            if not raw_title:
                continue
            
            # 应用 parser 的关键词过滤逻辑
            parser = source.get("parser")
            if parser is not None:
                # 对 cgbmis JSON 结果应用关键词过滤
                title = filter_title_by_keyword(raw_title, "开发区")
                if not title:
                    continue
            else:
                title = raw_title

            full_url = self._build_cgbmis_link(source, item)
            if not full_url or full_url in seen_links:
                continue

            published_at = self._parse_date(
                str(item.get("beginTime") or item.get("pdate") or "")
            ) or datetime.now(CHINA_TZ)

            notices.append(
                {
                    "id": self._make_notice_id(source["key"], full_url),
                    "title": title,
                    "link": full_url,
                    "source": source["name"],
                    "source_key": source["key"],
                    "category": source["category"],
                    "date": published_at.strftime("%Y-%m-%d"),
                    "pub_date": published_at.strftime("%a, %d %b %Y %H:%M:%S +0800"),
                    "published_at": published_at,
                }
            )
            seen_links.add(full_url)

        if not notices:
            logger.info(
                f"[DUT RSS] cgbmis 来源无有效条目 {source['key']} request={request_spec}"
            )
        return notices

    def _build_cgbmis_request(self, source: SourceConfig) -> dict[str, str] | None:
        request_map: dict[str, dict[str, str]] = {
            "cgbmis_jzcgxy": {
                "page": "cms.psms.publish.query",
                "orgType": "21",
                "type": "ZCXQ,YQXQ,BYXQ,CSXQ",
                "categoryId": "18812",
                "isEnd": "",
                "sort": "begin_time desc",
                "nowDateBefore": "1",
                "limit": "25",
                "start": "0",
            },
            "cgbmis_jzcggg": {
                "page": "cms.psms.publish.query",
                "orgType": "21",
                "type": "ZCXQ,YQXQ,BYXQ,CSXQ",
                "categoryId": "18812",
                "isEnd": "",
                "sort": "begin_time desc",
                "nowDateBefore": "1",
                "limit": "25",
                "start": "0",
            },
            "cgbmis_jzcggg_result": {
                "page": "cms.psms.publish.query",
                "orgType": "21",
                "type": "ZCGG,YQGG,BYGG,CSGG,ZCGS,YQGS,BYGS,CSGS,FBGG",
                "categoryId": "18813",
                "isEnd": "",
                "sort": "begin_time desc",
                "nowDateBefore": "1",
                "limit": "25",
                "start": "0",
            },
            "cgbmis_jzcght": {
                "page": "cms.portalArticle.listAll",
                "sort": "",
                "categoryid": "100649",
                "limit": "25",
                "pic": "false",
                "portalCategoryId": "18814",
                "start": "0",
            },
            "cgbmis_fscggg": {
                "page": "cms.portalArticle.listAll",
                "sort": "",
                "categoryid": "100645",
                "limit": "25",
                "pic": "false",
                "portalCategoryId": "18815",
                "start": "0",
            },
            "cgbmis_fscggg_result": {
                "page": "cms.portalArticle.listAll",
                "sort": "",
                "categoryid": "100646",
                "limit": "25",
                "pic": "false",
                "portalCategoryId": "18816",
                "pdate0": "2025-01-01 00:00:00",
                "start": "0",
            },
        }
        source_key = str(source.get("key") or "")
        return request_map.get(source_key)

    def _build_cgbmis_link(self, source: SourceConfig, item: dict[str, Any]) -> str:
        base_url = source.get("base_url") or source["url"]

        raw_url = str(item.get("url") or "").strip()
        if raw_url:
            return urljoin(base_url, raw_url)

        sync_id = str(item.get("syncId") or "").strip()
        if sync_id:
            return f"http://cgbmis.dlut.edu.cn/provider/#/publish/{sync_id}"

        notice_id = str(item.get("id") or "").strip()
        if notice_id:
            return urljoin(base_url, f"e?page=cms.detail&cid=100522&aid={notice_id}")

        return ""

    def _extract_published_at(self, tag: Tag, source: SourceConfig) -> datetime:
        # 软件学院列表常见"月/日"分离展示，优先从结构化节点读取，避免误匹配页面其他日期。
        if source.get("category") == "ssdut":
            ssdut_date = self._extract_ssdut_date(tag)
            if ssdut_date is not None:
                return ssdut_date

        candidates = [
            tag.get_text(" ", strip=True),
            *self._iter_ancestor_texts(tag, depth=3),
            self._collect_sibling_text(tag),
        ]

        for text in candidates:
            extracted = self._parse_date(text)
            if extracted is not None:
                return extracted

        return datetime.now(CHINA_TZ)

    def _extract_ssdut_date(self, tag: Tag) -> datetime | None:
        item = tag.find_parent(class_=lambda value: isinstance(value, str) and "item" in value)
        if not isinstance(item, Tag):
            item = tag.parent if isinstance(tag.parent, Tag) else None
        if not isinstance(item, Tag):
            return None

        date_node = item.select_one(".date")
        if isinstance(date_node, Tag):
            date_text = date_node.get_text(" ", strip=True)
            full_match = re.search(
                r"(?P<year>\d{4})\s*(?:年 |[-/.])\s*(?P<month>\d{1,2})\s*(?:月 |[-/.]|\s)\s*(?P<day>\d{1,2})",
                date_text,
            )
            if full_match:
                try:
                    return datetime(
                        int(full_match.group("year")),
                        int(full_match.group("month")),
                        int(full_match.group("day")),
                        tzinfo=CHINA_TZ,
                    )
                except ValueError:
                    pass

            # 兼容 year-month 在文本、day 在 <span> 中的场景
            ym_match = re.search(r"(?P<year>\d{4})\s*(?:年 |[-/.])\s*(?P<month>\d{1,2})", date_text)
            day_node = date_node.select_one("span")
            day = self._extract_first_int(day_node.get_text(" ", strip=True) if isinstance(day_node, Tag) else "")
            if ym_match and day is not None:
                try:
                    return datetime(
                        int(ym_match.group("year")),
                        int(ym_match.group("month")),
                        day,
                        tzinfo=CHINA_TZ,
                    )
                except ValueError:
                    pass

        month_node = item.select_one(".month")
        day_node = item.select_one(".day")
        month = self._extract_first_int(month_node.get_text(" ", strip=True) if isinstance(month_node, Tag) else "")
        day = self._extract_first_int(day_node.get_text(" ", strip=True) if isinstance(day_node, Tag) else "")
        if month is None or day is None:
            return None

        return self._resolve_month_day(month, day)

    def _extract_first_int(self, text: str) -> int | None:
        matched = re.search(r"\d{1,2}", text)
        if not matched:
            return None
        try:
            return int(matched.group(0))
        except ValueError:
            return None

    def _resolve_month_day(self, month: int, day: int) -> datetime | None:
        now = datetime.now(CHINA_TZ)
        try:
            candidate = datetime(now.year, month, day, tzinfo=CHINA_TZ)
        except ValueError:
            return None

        # 对仅月日格式做跨年矫正：若日期明显在未来，归到上一年。
        if candidate > now + timedelta(days=31):
            try:
                candidate = datetime(now.year - 1, month, day, tzinfo=CHINA_TZ)
            except ValueError:
                return None
        return candidate

    def _iter_ancestor_texts(self, tag: Tag, depth: int) -> Iterable[str]:
        current = tag.parent
        steps = 0
        while isinstance(current, Tag) and steps < depth:
            text = current.get_text(" ", strip=True)
            if text:
                yield text
            current = current.parent
            steps += 1

    def _collect_sibling_text(self, tag: Tag) -> str:
        texts: list[str] = []
        for sibling in list(tag.previous_siblings)[:2]:
            text = self._node_text(sibling)
            if text:
                texts.append(text)
        for sibling in list(tag.next_siblings)[:2]:
            text = self._node_text(sibling)
            if text:
                texts.append(text)
        return " ".join(texts)

    def _node_text(self, node: object) -> str:
        if isinstance(node, Tag):
            return node.get_text(" ", strip=True)
        return str(node).strip()

    def _parse_date(self, text: str) -> datetime | None:
        if not text:
            return None

        match = DATE_PATTERN.search(text)
        if not match:
            return None

        try:
            year = int(match.group("year"))
            month = int(match.group("month"))
            day = int(match.group("day"))
            return datetime(year, month, day, tzinfo=CHINA_TZ)
        except ValueError:
            return None

    def _make_notice_id(self, source_key: str, link: str) -> str:
        digest = sha1(f"{source_key}|{link}".encode("utf-8")).hexdigest()
        return f"{source_key}:{digest}"

    def _request_headers(self, source: SourceConfig, request_url: str | None = None) -> dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        headers["Referer"] = source.get("base_url") or request_url or source["url"]
        return headers

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            return int(self.config.get(key, default))
        except Exception:
            return default

    def _cfg_str(self, key: str, default: str) -> str:
        value = self.config.get(key, default)
        return str(value) if value is not None else default
