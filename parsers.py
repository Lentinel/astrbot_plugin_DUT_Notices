from bs4 import Tag


def parse_title_attr(tag: Tag) -> str:
    return (tag.get("title") or tag.get_text(" ", strip=True)).strip()


def parse_h2_child(tag: Tag) -> str:
    h2 = tag.find("h2")
    if isinstance(h2, Tag):
        return h2.get_text(" ", strip=True)
    return tag.get_text(" ", strip=True)


def parse_text_content(tag: Tag) -> str:
    return tag.get_text(" ", strip=True)


def parse_title_with_keyword(tag: Tag, keyword: str = "开发区") -> str:
    """解析标题，仅当标题包含指定关键词时返回标题，否则返回空字符串。"""
    title = (tag.get("title") or tag.get_text(" ", strip=True)).strip()
    if keyword in title:
        return title
    return ""
