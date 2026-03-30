import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.event.filter import PermissionType
from astrbot.api.star import Context, Star, register


def _load_local_module(module_name: str):
    module_path = Path(__file__).resolve().with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Cannot load local plugin module: {module_name}")

    sys.modules.pop(module_name, None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


for _module_name in (
    "parsers",
    "sources",
    "rss_service",
    "command_utils",
    "subscription_store",
):
    _load_local_module(_module_name)

from command_utils import extract_command_args, format_latest_lines
from rss_service import DutRssService, Notice
from sources import SourceConfig, format_source_lines, resolve_source
from subscription_store import SubscriptionStore


@register("astrbot_plugin_DUT_Notices", "Lentinel", "抓取 DUT 多站点通知并推送到订阅会话", "1.2.6")
class DutNoticePlugin(Star):
    def __init__(self, context: Context, config: dict[str, Any] | None = None):
        super().__init__(context)
        self.config = config or {}
        self._poll_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._rss_service = DutRssService(self.config)
        self._subscription_store = SubscriptionStore(self.get_kv_data, self.put_kv_data)

    async def initialize(self):
        self._stop_event.clear()
        self._poll_task = asyncio.create_task(self._polling_loop())
        logger.info("[DUT RSS] 插件初始化完成，多源轮询任务已启动。")

    async def terminate(self):
        self._stop_event.set()
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("[DUT RSS] 插件已停止。")

    @filter.command_group("dut_notice")
    def dut_notice_group(self):
        pass

    @dut_notice_group.command("help")
    async def help(self, event: AstrMessageEvent):
        """查看插件使用说明。"""
        yield event.plain_result(self._help_text())

    @dut_notice_group.command("sources")
    async def sources(self, event: AstrMessageEvent):
        """查看当前支持的来源及订阅状态。"""
        global_enabled = event.unified_msg_origin in await self._subscription_store.get_global_sessions()
        source_subscriptions = await self._subscription_store.get_source_subscriptions()
        subscribed_keys = set(source_subscriptions.get(event.unified_msg_origin, []))

        lines = ["可用来源:"]
        lines.extend(format_source_lines(subscribed_keys))
        if global_enabled:
            lines.append("")
            lines.append("当前会话已开启全局订阅，所有来源的新通知都会推送。")
        elif subscribed_keys:
            lines.append("")
            lines.append('当前会话仅会收到标记为"已单独订阅"的来源推送。')
        else:
            lines.append("")
            lines.append("当前会话尚未订阅任何来源。")
        yield event.plain_result("\n".join(lines))

    @dut_notice_group.command("subscribe")
    async def subscribe(self, event: AstrMessageEvent):
        """订阅当前会话的全部来源新通知推送。"""
        umo = event.unified_msg_origin
        sessions = await self._subscription_store.get_global_sessions()
        if umo not in sessions:
            sessions.append(umo)
            await self._subscription_store.save_global_sessions(sessions)
        yield event.plain_result("已订阅全部 DUT 来源通知推送。")

    @dut_notice_group.command("unsubscribe")
    async def unsubscribe(self, event: AstrMessageEvent):
        """取消订阅当前会话的全部来源新通知推送。"""
        umo = event.unified_msg_origin
        sessions = await self._subscription_store.get_global_sessions()
        if umo in sessions:
            sessions.remove(umo)
            await self._subscription_store.save_global_sessions(sessions)
            yield event.plain_result("已取消全部 DUT 来源通知推送。")
            return
        source_subscriptions = await self._subscription_store.get_source_subscriptions()
        if umo in source_subscriptions:
            del source_subscriptions[umo]
            await self._subscription_store.save_source_subscriptions(source_subscriptions)
        yield event.plain_result("已取消全部 DUT 来源通知推送。")

    @dut_notice_group.command("subscribe_source")
    async def subscribe_source(self, event: AstrMessageEvent):
        """订阅指定来源的新通知推送。"""
        umo = event.unified_msg_origin
        error = f"参数错误，请使用 /dut_notice subscribe_source <来源 key|来源名>"
        source = self._resolve_source_from_event(event, error)
        if source is None:
            yield event.plain_result(error)
            return

        source_subscriptions = await self._subscription_store.get_source_subscriptions()
        if umo not in source_subscriptions:
            source_subscriptions[umo] = []
        if source["key"] not in source_subscriptions[umo]:
            source_subscriptions[umo].append(source["key"])
            await self._subscription_store.save_source_subscriptions(source_subscriptions)
        yield event.plain_result(f"已订阅 {source['name']} 来源通知推送。")

    @dut_notice_group.command("unsubscribe_source")
    async def unsubscribe_source(self, event: AstrMessageEvent):
        """取消订阅指定来源的新通知推送。"""
        umo = event.unified_msg_origin
        error = f"参数错误，请使用 /dut_notice unsubscribe_source <来源 key|来源名>"
        source = self._resolve_source_from_event(event, error)
        if source is None:
            yield event.plain_result(error)
            return

        source_subscriptions = await self._subscription_store.get_source_subscriptions()
        if umo in source_subscriptions and source["key"] in source_subscriptions[umo]:
            source_subscriptions[umo].remove(source["key"])
            if not source_subscriptions[umo]:
                del source_subscriptions[umo]
            await self._subscription_store.save_source_subscriptions(source_subscriptions)
        yield event.plain_result(f"已取消订阅 {source['name']} 来源通知推送。")

    @dut_notice_group.command("check")
    async def check_now(self, event: AstrMessageEvent):
        """立即检查一次并推送增量通知。"""
        count = await self._run_check(push=True)
        yield event.plain_result(f"已检查更新，共发现 {count} 条新通知。")

    @dut_notice_group.command("add_push_target")
    @filter.permission_type(PermissionType.ADMIN)
    async def add_push_target(self, event: AstrMessageEvent):
        """添加当前会话为推送目标（仅管理员可用）。"""
        umo = event.unified_msg_origin
        push_targets = self.config.get("push_targets", [])
        if not isinstance(push_targets, list):
            push_targets = []
        if umo not in push_targets:
            push_targets.append(umo)
            self.config["push_targets"] = push_targets
            self.config.save_config()
            yield event.plain_result(f"已添加推送目标：{umo}")
        else:
            yield event.plain_result(f"当前会话已是推送目标：{umo}")

    @dut_notice_group.command("remove_push_target")
    @filter.permission_type(PermissionType.ADMIN)
    async def remove_push_target(self, event: AstrMessageEvent):
        """移除当前会话的推送目标（仅管理员可用）。"""
        umo = event.unified_msg_origin
        push_targets = self.config.get("push_targets", [])
        if not isinstance(push_targets, list):
            push_targets = []
        if umo in push_targets:
            push_targets.remove(umo)
            self.config["push_targets"] = push_targets
            self.config.save_config()
            yield event.plain_result(f"已移除推送目标：{umo}")
        else:
            yield event.plain_result(f"当前会话不是推送目标：{umo}")

    @dut_notice_group.command("list_push_targets")
    @filter.permission_type(PermissionType.ADMIN)
    async def list_push_targets(self, event: AstrMessageEvent):
        """列出所有推送目标会话（仅管理员可用）。"""
        push_targets = self.config.get("push_targets", [])
        if not isinstance(push_targets, list) or not push_targets:
            yield event.plain_result("当前没有配置的推送目标。")
            return
        lines = ["推送目标会话:"]
        for target in push_targets:
            lines.append(f"- {target}")
        yield event.plain_result("\n".join(lines))

    @dut_notice_group.command("rss")
    async def show_rss_info(self, event: AstrMessageEvent):
        """查看 RSS 文件路径。"""
        path = self._rss_service.rss_file_path
        yield event.plain_result(f"RSS 文件路径：{path}")

    @dut_notice_group.command("latest")
    async def latest(self, event: AstrMessageEvent):
        """查看最近 5 条聚合通知。"""
        notices = await self._rss_service.fetch_notices()
        yield event.plain_result(format_latest_lines("最近通知", notices[:5]))

    @dut_notice_group.command("latest_source")
    async def latest_source(self, event: AstrMessageEvent):
        """查看指定来源最近 5 条通知。"""
        error = f"参数错误，请使用 /dut_notice latest_source <来源 key|来源名>"
        source = self._resolve_source_from_event(event, error)
        if source is None:
            logger.info(f"[DUT RSS] latest_source 未解析到来源：{error}")
            yield event.plain_result(error)
            return

        logger.info(f"[DUT RSS] latest_source 开始抓取 source_key={source['key']} source_name={source['name']}")
        notices = await self._rss_service.fetch_notices(source_keys={source["key"]})
        logger.info(f"[DUT RSS] latest_source 抓取完成 source_key={source['key']} count={len(notices)}")
        if not notices:
            yield event.plain_result(f"{source['name']} 暂无通知。")
            return
        yield event.plain_result(format_latest_lines(f"{source['name']} 最近通知", notices[:5]))

    @dut_notice_group.command("latest_campus")
    async def latest_campus(self, event: AstrMessageEvent):
        """查看教学运行保障中心开发区校区教学事务综合室最近 5 条通知。"""
        notices = await self._rss_service.fetch_notices(source_keys={"campus_jxyxbzzx"})
        if not notices:
            yield event.plain_result("教学运行保障中心开发区校区教学事务综合室暂无通知。")
            return
        yield event.plain_result(format_latest_lines("教学运行保障中心开发区校区教学事务综合室最近通知", notices[:5]))

    @dut_notice_group.command("latest_teach")
    async def latest_teach(self, event: AstrMessageEvent):
        """查看教务处网站最近 5 条通知。"""
        source_keys = {"teach_byxx", "teach_zytg", "teach_jxwj", "teach_qtwj"}
        notices = await self._rss_service.fetch_notices(source_keys=source_keys)
        if not notices:
            yield event.plain_result("教务处网站暂无通知。")
            return
        yield event.plain_result(format_latest_lines("教务处网站最近通知", notices[:5]))

    @dut_notice_group.command("latest_ss")
    async def latest_ss(self, event: AstrMessageEvent):
        """查看软件学院网站最近 5 条通知。"""
        source_keys = {"ss_xshd", "ss_xsgz", "ss_gjtz", "ss_gjjl", "ss_xsbg", "ss_cxsj", "ss_yjszs", "ss_yjstz", "ss_bkstz"}
        notices = await self._rss_service.fetch_notices(source_keys=source_keys)
        if not notices:
            yield event.plain_result("软件学院网站暂无通知。")
            return
        yield event.plain_result(format_latest_lines("软件学院网站最近通知", notices[:5]))

    @dut_notice_group.command("latest_ic")
    async def latest_ic(self, event: AstrMessageEvent):
        """查看集成电路学院网站最近 5 条通知。"""
        source_keys = {"ic_xytz", "ic_xygs", "ic_xsdt", "ic_kxyj", "ic_bkstz", "ic_yjstz"}
        notices = await self._rss_service.fetch_notices(source_keys=source_keys)
        if not notices:
            yield event.plain_result("集成电路学院网站暂无通知。")
            return
        yield event.plain_result(format_latest_lines("集成电路学院网站最近通知", notices[:5]))

    @dut_notice_group.command("latest_cgbmis")
    async def latest_cgbmis(self, event: AstrMessageEvent):
        """查看采购信息网最近 5 条通知（仅标题含"开发区"）。"""
        source_keys = {"cgbmis_jzcgxy", "cgbmis_jzcggg", "cgbmis_jzcggg_result", "cgbmis_jzcght", "cgbmis_fscggg", "cgbmis_fscggg_result"}
        notices = await self._rss_service.fetch_notices(source_keys=source_keys)
        if not notices:
            yield event.plain_result("采购信息网暂无通知。")
            return
        yield event.plain_result(format_latest_lines("采购信息网最近通知（仅标题含\"开发区\"）", notices[:5]))

    async def _polling_loop(self):
        interval_minutes = self._cfg_int("poll_interval_minutes", 5)
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval_minutes * 60)
                break
            except asyncio.TimeoutError:
                pass
            try:
                await self._run_check(push=True)
            except Exception as exc:
                logger.error(f"[DUT RSS] 轮询检查失败：{exc}")

    async def _run_check(self, push: bool) -> int:
        notices = await self._rss_service.fetch_notices()
        if not notices:
            return 0

        await self._rss_service.write_rss(notices)

        if not push:
            return len(notices)

        await self._push_new_items(notices)
        return len(notices)

    async def _refresh_rss_only(self):
        notices = await self._rss_service.fetch_notices()
        if notices:
            await self._rss_service.write_rss(notices)

    async def _push_new_items(self, items: list[Notice]):
        global_sessions = set(await self._subscription_store.get_global_sessions())
        source_subscriptions = await self._subscription_store.get_source_subscriptions()
        push_targets = set(self.config.get("push_targets", []))

        for item in items:
            recipients = set(global_sessions)
            recipients.update(
                session
                for session, source_keys in source_subscriptions.items()
                if item["source_key"] in source_keys
            )
            # 添加配置的推送目标
            recipients.update(push_targets)

            for umo in recipients:
                text = (
                    f"[DUT 新通知][{item['source']}] {item['title']}\n"
                    f"{item['date']}\n"
                    f"{item['link']}"
                )
                try:
                    await self.context.send_message(umo, MessageChain().plain(text))
                except Exception as exc:
                    logger.warning(f"[DUT RSS] 向会话推送失败 {umo}: {exc}")

    def _resolve_source_from_event(
        self, event: AstrMessageEvent, error_hint: str
    ) -> SourceConfig | None:
        text = extract_command_args(event, "").strip()
        if not text:
            return None
        source = resolve_source(text)
        if source is None:
            logger.info(f"[DUT RSS] 未找到匹配的来源，输入：{text}，可用来源：{[s['key'] for s in SOURCES]}")
        return source

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            return int(self.config.get(key, default))
        except (ValueError, TypeError):
            return default

    def _help_text(self) -> str:
        lines = [
            "DUT RSS 插件使用说明",
            "",
            "用户指令:",
            "- /dut_notice help: 查看本帮助",
            "- /dut_notice sources: 查看支持的来源",
            "- /dut_notice subscribe: 订阅全部来源",
            "- /dut_notice unsubscribe: 取消订阅全部来源",
            "- /dut_notice subscribe_source <来源 key|来源名>: 订阅单个来源",
            "- /dut_notice unsubscribe_source <来源 key|来源名>: 取消订阅单个来源",
            "- /dut_notice check: 立即检查更新",
            "- /dut_notice latest: 查看最近 5 条聚合通知",
            "- /dut_notice latest_source <来源 key|来源名>: 查看单个来源最近 5 条通知",
            "- /dut_notice latest_campus: 查看教学运行保障中心最近 5 条通知",
            "- /dut_notice latest_teach: 查看教务处网站最近 5 条通知",
            "- /dut_notice latest_ss: 查看软件学院网站最近 5 条通知",
            "- /dut_notice latest_ic: 查看集成电路学院网站最近 5 条通知",
            "- /dut_notice latest_cgbmis: 查看采购信息网最近 5 条通知（仅标题含\"开发区\"）",
            "- /dut_notice rss: 查看 RSS 文件路径",
            "",
            "管理员指令:",
            "- /dut_notice add_push_target: 添加当前会话为推送目标",
            "- /dut_notice remove_push_target: 移除当前会话的推送目标",
            "- /dut_notice list_push_targets: 列出所有推送目标",
            "",
            "配置项:",
            "- rss_title: RSS 标题",
            "- rss_max_items: RSS 最大条目数",
            "- poll_interval_minutes: 轮询间隔（分钟）",
            "- request_timeout_seconds: 请求超时（秒）",
            "- push_targets: 推送目标会话列表",
        ]
        return "\n".join(lines)
