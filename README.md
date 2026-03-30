# astrbot_plugin_DUT_Notices

抓取大连理工大学多个通知站点，生成聚合 RSS 文件，并把新增通知主动推送到已订阅会话。

## 功能

- 支持多个来源的通知抓取
- 定时轮询检测新增通知
- 生成标准 RSS 2.0 文件
- 向已订阅会话主动推送新增通知
- 支持管理员配置推送目标会话

## 当前支持来源

### 开发区校区
- 教学运行保障中心开发区校区教学事务综合室

### 教务处
- 教务处部院信息
- 教务处教学文件
- 教务处其他文件
- 教务处重要通告

### 软件学院
- 软件学院 - 学生活动
- 软件学院 - 学工通知
- 软件学院 - 国际通知
- 软件学院 - 国际交流
- 软件学院 - 学术报告
- 软件学院 - 创新实践
- 软件学院 - 研究生招生
- 软件学院 - 研究生通知
- 软件学院 - 本科生通知

### 集成电路学院 (ic.dlut.edu.cn)
- 集成电路学院 - 学院通知
- 集成电路学院 - 学院公示
- 集成电路学院 - 学术动态
- 集成电路学院 - 科学研究
- 集成电路学院 - 本科生通知
- 集成电路学院 - 研究生通知

### 采购信息网（仅开发区校区相关内容） (cgbmis.dlut.edu.cn)
- 采购信息网 - 集中采购意向
- 采购信息网 - 集中采购公告
- 采购信息网 - 集中采购结果
- 采购信息网 - 集中采购合同
- 采购信息网 - 分散采购公告
- 采购信息网 - 分散采购结果

## 依赖

- `httpx`
- `beautifulsoup4`

安装方式：在插件目录执行依赖安装，或由 AstrBot 插件依赖管理自动安装 `requirements.txt`。

## 指令

### 用户指令
- `/dut_notice help`: 查看插件帮助
- `/dut_notice subscribe`: 订阅当前会话
- `/dut_notice unsubscribe`: 取消订阅当前会话
- `/dut_notice sources`: 查看支持的来源与当前会话订阅状态
- `/dut_notice subscribe_source <来源 key|来源名>`: 订阅单个来源
- `/dut_notice unsubscribe_source <来源 key|来源名>`: 取消订阅单个来源
- `/dut_notice check`: 立即检查一次并推送增量
- `/dut_notice latest`: 查看最近 5 条聚合通知
- `/dut_notice latest_source <来源 key|来源名>`: 查看单个来源最近 5 条通知
- `/dut_notice latest_campus`: 查看教学运行保障中心最近 5 条通知
- `/dut_notice latest_teach`: 查看教务处网站最近 5 条通知
- `/dut_notice latest_ss`: 查看软件学院网站最近 5 条通知
- `/dut_notice latest_ic`: 查看集成电路学院网站最近 5 条通知
- `/dut_notice latest_cgbmis`: 查看采购信息网最近 5 条通知（仅标题含"开发区"）
- `/dut_notice rss`: 查看聚合 RSS 文件路径

### 管理员指令
- `/dut_notice add_push_target`: 添加当前会话为推送目标
- `/dut_notice remove_push_target`: 移除当前会话的推送目标
- `/dut_notice list_push_targets`: 列出所有推送目标会话

## 使用示例

- 查看帮助：`/dut_notice help`
- 查看所有来源：`/dut_notice sources`
- 订阅全部来源：`/dut_notice subscribe`
- 订阅软件学院本科生通知：`/dut_notice subscribe_source ss_bkstz`
- 订阅集成电路学院学院通知：`/dut_notice subscribe_source ic_xytz`
- 查看教务处部院信息最新通知：`/dut_notice latest_source teach_byxx`
- 查看教学运行保障中心最新通知：`/dut_notice latest_campus`
- 查看教务处网站最新通知：`/dut_notice latest_teach`
- 查看软件学院网站最新通知：`/dut_notice latest_ss`
- 查看集成电路学院网站最新通知：`/dut_notice latest_ic`
- 查看采购信息网最新通知：`/dut_notice latest_cgbmis`
- 手动触发一次检查：`/dut_notice check`
- 添加推送目标：`/dut_notice add_push_target`

## 配置项

配置文件 Schema 位于 `_conf_schema.json`，支持在 AstrBot WebUI 可视化配置:

- `rss_title`: 聚合 RSS 标题
- `rss_max_items`: RSS 保留条数
- `poll_interval_minutes`: 轮询间隔（分钟）
- `request_timeout_seconds`: 请求超时（秒）
- `push_targets`: 主动推送目标会话 ID 列表（unified_msg_origin）

## 数据存储

- 订阅会话与已推送通知 ID: AstrBot KV 存储
- RSS 文件：`data/plugin_data/astrbot_plugin_DUT_Notices/dlut_notice_rss.xml`

## 说明

- 首次运行会建立通知基线，不会推送历史消息。
- 推送消息与 RSS 条目会携带来源名称，便于区分通知站点。
- 支持"全局订阅"和"按来源订阅"并存；同一会话不会收到重复推送。
- 若学校页面结构发生变化，可能需要同步调整 `sources.py` 中的选择器。
