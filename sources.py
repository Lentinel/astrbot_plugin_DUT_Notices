import re
from collections.abc import Callable
from typing import TypedDict

from bs4 import Tag

from parsers import parse_h2_child, parse_text_content, parse_title_attr, parse_title_with_keyword

Parser = Callable[[Tag], str]


class SourceConfig(TypedDict, total=False):
    key: str
    name: str
    url: str
    selector: str
    parser: Parser
    category: str
    base_url: str


SOURCES: list[SourceConfig] = [
    {
        "key": "campus_jxyxbzzx",
        "name": "教学运行保障中心开发区校区教学事务综合室",
        "url": "https://jxyxbzzx.dlut.edu.cn/tzgg/kfqxq.htm",
        "selector": "div.l_text-wrapper_3 a[href*='/info/']",
        "parser": parse_text_content,
        "category": "campus",
        "base_url": "https://jxyxbzzx.dlut.edu.cn/",
    },
    {
        "key": "teach_byxx",
        "name": "教务处部院信息",
        "url": "https://teach.dlut.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1206",
        "selector": ".list a[href*='wbnewsid=']",
        "parser": parse_title_attr,
        "category": "teaching",
        "base_url": "https://teach.dlut.edu.cn/",
    },
    {
        "key": "teach_zytg",
        "name": "教务处重要通告",
        "url": "https://teach.dlut.edu.cn/zhongyaotonggao/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1016",
        "selector": ".list a[href*='wbnewsid=']",
        "parser": parse_title_attr,
        "category": "teaching",
        "base_url": "https://teach.dlut.edu.cn/",
    },
    {
        "key": "teach_jxwj",
        "name": "教务处教学文件",
        "url": "https://teach.dlut.edu.cn/jiaoxuewenjian/list.jsp?totalpage=68&PAGENUM=3&urltype=tree.TreeTempUrl&wbtreeid=1082",
        "selector": ".list a[href*='wbnewsid=']",
        "parser": parse_title_attr,
        "category": "teaching",
        "base_url": "https://teach.dlut.edu.cn/",
    },
    {
        "key": "teach_qtwj",
        "name": "教务处其他文件",
        "url": "https://teach.dlut.edu.cn/qitawenjian/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1081",
        "selector": ".list a[href*='wbnewsid=']",
        "parser": parse_title_attr,
        "category": "teaching",
        "base_url": "https://teach.dlut.edu.cn/",
    },
    {
        "key": "ss_xshd",
        "name": "软件学院 - 学生活动",
        "url": "https://ss.dlut.edu.cn/xsgz/xshd.htm",
        "selector": ".list04 .item a",
        "parser": parse_h2_child,
        "category": "ssdut",
    },
    {
        "key": "ss_xsgz",
        "name": "软件学院 - 学工通知",
        "url": "https://ss.dlut.edu.cn/xsgz/tzgg.htm",
        "selector": ".list04 .item a",
        "parser": parse_h2_child,
        "category": "ssdut",
    },
    {
        "key": "ss_gjtz",
        "name": "软件学院 - 国际通知",
        "url": "https://ss.dlut.edu.cn/gjhzjl/tzgg.htm",
        "selector": ".list04 .item a",
        "parser": parse_h2_child,
        "category": "ssdut",
    },
    {
        "key": "ss_gjjl",
        "name": "软件学院 - 国际交流",
        "url": "https://ss.dlut.edu.cn/gjhzjl/gjjl.htm",
        "selector": ".list04 .item a",
        "parser": parse_h2_child,
        "category": "ssdut",
    },
    {
        "key": "ss_xsbg",
        "name": "软件学院 - 学术报告",
        "url": "https://ss.dlut.edu.cn/kxyj/xsbg.htm",
        "selector": ".list04 .item a",
        "parser": parse_h2_child,
        "category": "ssdut",
    },
    {
        "key": "ss_cxsj",
        "name": "软件学院 - 创新实践",
        "url": "https://ss.dlut.edu.cn/rcpy/cxsj/hdtz.htm",
        "selector": ".list04 .item a",
        "parser": parse_h2_child,
        "category": "ssdut",
    },
    {
        "key": "ss_yjszs",
        "name": "软件学院 - 研究生招生",
        "url": "https://ss.dlut.edu.cn/rcpy/yjspy/yjszs.htm",
        "selector": ".list04 .item a",
        "parser": parse_h2_child,
        "category": "ssdut",
    },
    {
        "key": "ss_yjstz",
        "name": "软件学院 - 研究生通知",
        "url": "https://ss.dlut.edu.cn/rcpy/yjspy/yjstz.htm",
        "selector": ".list04 .item a",
        "parser": parse_h2_child,
        "category": "ssdut",
    },
    {
        "key": "ss_bkstz",
        "name": "软件学院 - 本科生通知",
        "url": "https://ss.dlut.edu.cn/rcpy/bkspy/bkstz.htm",
        "selector": ".list04 .item a",
        "parser": parse_h2_child,
        "category": "ssdut",
    },
    # 集成电路学院 (ic.dlut.edu.cn)
    {
        "key": "ic_xytz",
        "name": "集成电路学院 - 学院通知",
        "url": "https://ic.dlut.edu.cn/xytz.htm",
        "selector": ".ny_newsListRow ul li a",
        "parser": parse_text_content,
        "category": "ic",
        "base_url": "https://ic.dlut.edu.cn/",
    },
    {
        "key": "ic_xygs",
        "name": "集成电路学院 - 学院公示",
        "url": "https://ic.dlut.edu.cn/xygs.htm",
        "selector": ".ny_newsListRow ul li a",
        "parser": parse_text_content,
        "category": "ic",
        "base_url": "https://ic.dlut.edu.cn/",
    },
    {
        "key": "ic_xsdt",
        "name": "集成电路学院 - 学术动态",
        "url": "https://ic.dlut.edu.cn/xsdt.htm",
        "selector": ".ny_newsListRow ul li a",
        "parser": parse_text_content,
        "category": "ic",
        "base_url": "https://ic.dlut.edu.cn/",
    },
    {
        "key": "ic_kxyj",
        "name": "集成电路学院 - 科学研究",
        "url": "https://ic.dlut.edu.cn/xkyky/kydt.htm",
        "selector": ".ny_newsListRow ul li a",
        "parser": parse_text_content,
        "category": "ic",
        "base_url": "https://ic.dlut.edu.cn/",
    },
    {
        "key": "ic_bkstz",
        "name": "集成电路学院 - 本科生通知",
        "url": "https://ic.dlut.edu.cn/rcpy/bkspy/bksjx.htm",
        "selector": ".ny_newsListRow ul li a",
        "parser": parse_text_content,
        "category": "ic",
        "base_url": "https://ic.dlut.edu.cn/",
    },
    {
        "key": "ic_yjstz",
        "name": "集成电路学院 - 研究生通知",
        "url": "https://ic.dlut.edu.cn/rcpy/yjspy/yjsjx.htm",
        "selector": ".ny_newsListRow ul li a",
        "parser": parse_text_content,
        "category": "ic",
        "base_url": "https://ic.dlut.edu.cn/",
    },
    # 采购信息网 (cgbmis.dlut.edu.cn) - 仅标题含"开发区"的内容
    {
        "key": "cgbmis_jzcgxy",
        "name": "采购信息网 - 集中采购意向",
        "url": "http://cgbmis.dlut.edu.cn/sfw_cms/e?page=cms.psms.gglist&orgType=21&df=0",
        "selector": ".textlist-big li a",
        "parser": lambda tag: parse_title_with_keyword(tag, "开发区"),
        "category": "cgbmis",
        "base_url": "http://cgbmis.dlut.edu.cn/",
    },
    {
        "key": "cgbmis_jzcggg",
        "name": "采购信息网 - 集中采购公告",
        "url": "http://cgbmis.dlut.edu.cn/sfw_cms/e?page=cms.psms.gglist&orgType=21&df=1",
        "selector": ".textlist-big li a",
        "parser": lambda tag: parse_title_with_keyword(tag, "开发区"),
        "category": "cgbmis",
        "base_url": "http://cgbmis.dlut.edu.cn/",
    },
    {
        "key": "cgbmis_jzcggg_result",
        "name": "采购信息网 - 集中采购结果",
        "url": "http://cgbmis.dlut.edu.cn/sfw_cms/e?page=cms.psms.gglist&orgType=21&df=2",
        "selector": ".textlist-big li a",
        "parser": lambda tag: parse_title_with_keyword(tag, "开发区"),
        "category": "cgbmis",
        "base_url": "http://cgbmis.dlut.edu.cn/",
    },
    {
        "key": "cgbmis_jzcght",
        "name": "采购信息网 - 集中采购合同",
        "url": "http://cgbmis.dlut.edu.cn/sfw_cms/e?page=cms.psms.gglist&orgType=21&df=3&cid=100649",
        "selector": ".textlist-big li a",
        "parser": lambda tag: parse_title_with_keyword(tag, "开发区"),
        "category": "cgbmis",
        "base_url": "http://cgbmis.dlut.edu.cn/",
    },
    {
        "key": "cgbmis_fscggg",
        "name": "采购信息网 - 分散采购公告",
        "url": "http://cgbmis.dlut.edu.cn/sfw_cms/e?page=cms.psms.gglist&orgType=22&df=4&cid=100644",
        "selector": ".textlist-big li a",
        "parser": lambda tag: parse_title_with_keyword(tag, "开发区"),
        "category": "cgbmis",
        "base_url": "http://cgbmis.dlut.edu.cn/",
    },
    {
        "key": "cgbmis_fscggg_result",
        "name": "采购信息网 - 分散采购结果",
        "url": "http://cgbmis.dlut.edu.cn/sfw_cms/e?page=cms.psms.gglist&orgType=22&df=5&cid=100644",
        "selector": ".textlist-big li a",
        "parser": lambda tag: parse_title_with_keyword(tag, "开发区"),
        "category": "cgbmis",
        "base_url": "http://cgbmis.dlut.edu.cn/",
    },
]

SOURCES_BY_KEY = {source["key"]: source for source in SOURCES}


def resolve_source(query: str) -> SourceConfig | None:
    normalized_query = _normalize_query(query)
    if not normalized_query:
        return None

    exact = SOURCES_BY_KEY.get(query.strip())
    if exact is not None:
        return exact

    matches = [
        source
        for source in SOURCES
        if normalized_query in {
            _normalize_query(source["key"]),
            _normalize_query(source["name"]),
        }
        or normalized_query in _normalize_query(source["key"])
        or normalized_query in _normalize_query(source["name"])
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def format_source_lines(subscribed_keys: set[str] | None = None) -> list[str]:
    subscribed_keys = subscribed_keys or set()
    lines: list[str] = []
    for source in SOURCES:
        status = " [已单独订阅]" if source["key"] in subscribed_keys else ""
        lines.append(f"- {source['key']}: {source['name']}{status}")
    return lines


def _normalize_query(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", text).casefold()
