# Academic-Radar

> **如果你是 AI Agent 在阅读本仓库**：请优先阅读 [`AGENT.md`](./AGENT.md)——那是写给你的操作手册（安装、引导用户、文件修改边界、cron、反幻觉自查）。本 README 给人类用户看。

一个**给临床医生 / 医学方向科研人员 / 研究生**的学术信息雷达插件。按你设定的频率（每天 / 每周 / 每月，或开会期间每几小时）定时从 PubMed、Semantic Scholar、OpenAlex、bioRxiv、medRxiv、arXiv、X（推特）、RSS 抓取你研究方向相关的论文，LLM 打分筛选去重后，推送到你的微信、Telegram、Slack 或邮箱。

适合"我想每天花 3 分钟扫一眼领域新进展，但不想被微信群和订阅源里 90% 的噪音淹没"的人。

---

## 你只需要做这两件事

**第一步**：把这个仓库的链接发给你的 AI Agent（Claude Code / Hermes / 其他支持工具调用 + 能改本地文件的 Agent），说一句"帮我装上 Academic-Radar"。

**第二步**：Agent 会问你两个问题，照实回答：

1. **你的研究方向是什么？** 用一两句话讲清楚就行。
   > 例："放疗联合免疫治疗，重点关注 FLASH 放疗、远隔效应、cGAS-STING 通路。"

2. **检索结果推到哪里？** 微信群机器人 / Telegram Bot / Slack / 邮箱，任选其一。

Agent 还会问你**想多久检索一次**（每天 / 每 3 天 / 每周 / 每 2 周 / 每月，或自定义；开会期间也能临时切到每几小时一次）——按你领域的出文节奏选就行。

完事了。Agent 会自己装依赖、自查你机器上已经配好的 LLM API key（让你挑一个最便宜的）、引导你把关键词说得更具体（拼写/精度/排除词会校准）、装定时任务、跑一次验证。

**下次检索时**（取决于你设的频率：下一天 / 下周 / 下月）就能收到第一份报告。

---

## 推送渠道：你要准备的东西

至少备一个：

| 渠道 | 你需要拿到 |
|------|-----------|
| **微信群机器人** | 企业微信 / 钉钉群里"添加机器人 → 自定义机器人"，复制 webhook URL |
| **微信个人号机器人** | 个人号 bot（OpenClaw / WeChaty / 你自己写的都行），让 bot 暴露一个 HTTP 接收端口，把 URL 给 Agent。**不需要企业号也能用** |
| **Telegram** | 找 [@BotFather](https://t.me/BotFather) 创建 Bot 拿 Token，把 Bot 拉进你的对话/群拿 Chat ID |
| **Slack** | Workspace 里建一个 Incoming Webhook，复制 URL |
| **邮箱** | SMTP 服务器地址 + 账号 + 密码（Gmail / QQ 邮箱 / 自建邮箱都行） |

> 如果你用的 Agent **自己有邮箱**（某些云端集成版本会给 Agent 配独立邮箱），可以让 Agent 用自己的邮箱接收，再转给你。不过最省事的还是微信类机器人——手机直接收，免费，不用切应用。

---

## 报告长什么样

```
📡 学术雷达 05-22 08:00
抓取范围：05-21 20:00 ~ 05-22 08:00
PubMed: 23 | S2: 15 | OpenAlex: 31 | bioRxiv: 8 | arXiv: 6 | X: 47 | RSS: 5
命中: 7 条

———

1. ✅Published | 相关性:5
标题: FLASH Proton Therapy Combined with Anti-PD-1 in Recurrent Glioblastoma
作者: Smith A, Johnson B, et al.
期刊: Journal of Clinical Oncology, 2026
DOI: 10.1200/JCO.2026.xxxxx
引用: 12 (S2)
核心发现: xxxxx
来源: PubMed + X(@DrRadOnc 讨论)

2. 📄Preprint | 相关性:4
标题: xxxxx
作者: xxx
来源: medRxiv, 2026-05-20
链接: https://medrxiv.org/xxx
核心发现: xxx
正式发表: 未检出

———
关键词版本: 05-20 更新
下次抓取: 20:00
```

每条都带发表状态标识（✅ 正式发表 / 📄 预印本 / 🎤 会议摘要 / ❓ 未验证）和数据来源标注。**所有书目信息都从 API 拉的真实数据，不是 LLM 编的**。

---

## 它在背后做什么

```
7 个数据源 → 关键词初筛（脚本层，省 token）→ 跨周期去重（剔除上次已推过的）
  → LLM 1-5 分相关性评分 → DOI 验证 + 发表状态识别 → 跨源去重合并 → 排序 → 推送 + 存档
```

**数据源**：

- PubMed（3600 万+ 条，生物医学金标准）
- Semantic Scholar（2 亿+，引文网络 + AI 摘要）
- OpenAlex（4.7 亿+，覆盖最广）
- bioRxiv / medRxiv（生物医学预印本第一时间）
- arXiv（物理 / 医学物理 / 定量生物学预印本，FLASH、剂量学等方向常首发于此）
- X（学术圈讨论 / 会议实况）
- RSS（你自定义的期刊订阅 / 公众号）

**反幻觉设计**：标题、作者、DOI 全部来自 API 原始返回，LLM 只负责"打分 + 基于摘要总结"，严禁生成任何书目信息——你不会收到"幽灵引用"。如果哪天你怀疑某条是假的，每条的 `fetch_sources` 和 `abstract_source` 字段可以一路追溯到原始 API。

**不重复打扰**：每次只推**上次之后新出现**的文章。检索窗口随上次成功时间滑动，再叠加一层跨周期去重——比对近 30 天已推送过的 DOI / 标题，命中就跳过。所以即使某篇文章卡在窗口边界、或预印本延迟几天才被索引，也不会被反复推给你。

**容错**：单个数据源挂了不阻塞其他源，最多某次少几条。漏跑（机器关机）会自动补抓上次成功之后的窗口（上限为检索周期的 3 倍），不会断档。

完整设计见 [`academic-radar-prd-v2.md`](./academic-radar-prd-v2.md)。

---

## 日常维护：跟 Agent 说一句话就行

| 你想做什么 | 跟 Agent 说 |
|------------|-------------|
| 加新关键词 | "帮我加上 'BNCT' 关键词" |
| 屏蔽某类文章 | "把综述类排除掉" |
| 关注某个新作者 | "追踪一下 XX 教授" |
| 换推送渠道 | "改成发到我的 Telegram" |
| 推送太多了 | "每次最多 10 条" |
| 换检索频率 | "改成每周检索一次就行" |
| 开会期间想多看 | "开会这几天切到每 4 小时一次" |
| 暂时关掉某个源 | "暂时不看 X 平台了" |
| 今天怎么没收到 | "查一下今天的抓取日志" |
| 想换更便宜的模型 | "换成 DeepSeek 跑评分" |

Agent 会改对应的配置文件（`academic_radar_config.yaml`），你不需要碰任何代码。

---

## 你需要的环境（给好奇的人）

| 项 | 说明 |
|----|------|
| AI Agent | 支持工具调用 + 能改本地文件，例如 Claude Code（CLI / 桌面 / Web）、Hermes、自建 Agent |
| Python | ≥ 3.9 |
| 一台常开的机器 | 跑定时任务用，本机 / VPS / 云主机都行。笔记本经常关机也没事——下次开机会自动补抓上次成功之后的窗口 |
| LLM API Key | OpenAI / DeepSeek / Kimi / 智谱 / 通义 / 本地 Ollama 都行。**评分任务很简单，最便宜的模型就够**——Agent 会自查你机器上已有哪些，让你选 |
| 推送渠道凭证 | 见上文表格，至少备一个 |

第一次跟 Agent 对话装好之后，平均 **5-10 分钟搞定**。之后就是定时跑、定时收报告。

---

## 进阶 / 自己动手改

- 完整产品需求文档：[`academic-radar-prd-v2.md`](./academic-radar-prd-v2.md)
- Agent 运维手册：[`AGENT.md`](./AGENT.md)（含反幻觉自查、文件修改边界、prompt 调整规则）
- 配置文件：[`academic_radar_config.yaml`](./academic_radar_config.yaml)（直接手改也行）
- 跑一次验证：`python3 radar_main.py`
- 存档位置：`data/radar/YYYY-MM-DD_HHmm.json`（保留最近 30 天）

---

## License

见 [LICENSE](./LICENSE)。
