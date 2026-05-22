# PRD: Academic Radar — 学术雷达插件（开源版）

## 1. 产品概述

一个学术信息自动检索、过滤、验证、推送插件，面向 LLM Agent 框架。定时从多个学术数据库和社交平台抓取与用户研究方向相关的学术内容，经过相关性评分、来源验证、去重后，推送结构化消息。

**目标用户**：临床医生/研究生/科研人员，需要低噪音、高相关性的学术信息流。

**运行环境**：任意支持定时任务和 LLM 调用的 Agent 框架（如 Hermes、AutoGPT、自建 Agent 等）。底座模型不限（支持 OpenAI API 兼容格式即可）。

**推送渠道**：可配置。支持微信（通过 webhook）、Telegram Bot、Slack、邮件等，推送模块为独立接口。

## 2. 核心需求

### 2.1 定时触发

- 通过 cron 或 Agent 内置调度触发，脚本层不消耗 LLM token
- 日常模式：每天 08:00 / 20:00（时区可配置）
- 会议模式：每 4 小时一次，手动开启/关闭（通过配置文件切换）
- 每次运行记录时间戳到本地文件 `last_success_ts`
- 下次抓取起点 = max(上次成功时间, 当前时间 - 48h)

### 2.2 信息抓取

#### 🔴 Tier 1：学术数据库 API（主动检索，可信源）

**PubMed E-utilities（已发表文献，主力源）**

- 接口：NCBI E-utilities API（免费，无需 API key 可低频使用，注册 key 可提至 10 req/s）
- 端点：`esearch.fcgi` + `efetch.fcgi`
- 按 MeSH 词 + 自由词 + 时间窗口检索
- 返回结构化数据：PMID、DOI、标题、作者、期刊、摘要、MeSH 标签
- PMID/DOI 天然可信，来自 MEDLINE 索引，无需二次验证
- 覆盖：3600 万+ 条生物医学引文

**Semantic Scholar Graph API（引文网络分析）**

- 接口：Semantic Scholar Academic Graph API（免费，无需 API key，可申请提速）
- 端点：`https://api.semanticscholar.org/graph/v1/paper/search`
- 返回：标题、作者、摘要、AI 生成 TLDR、引用数、influential citation count、DOI、PMID、ArXiv ID
- 价值：引文影响力分析、相关论文推荐、跨数据库 ID 映射
- 限制：100 请求 / 5 分钟（无 key），需做请求节流
- 覆盖：2 亿+ 跨学科论文

**OpenAlex API（广覆盖元数据补充）**

- 接口：完全免费，无需 API key（加 mailto 参数进入 polite pool 可提速）
- 端点：`https://api.openalex.org/works`
- 返回：标题、作者、机构隶属、引用数、DOI、开放获取链接、概念标签
- 价值：覆盖面最广（4.7 亿+ 作品），含非英文文献、数据集、预印本；可补充 PubMed 未收录的内容
- 限制：10 万请求 / 天
- 用途：作为 PubMed 的补充层，尤其用于追踪特定作者/机构的发表动态

**bioRxiv / medRxiv API（预印本）**

- 接口：bioRxiv API（免费，无需认证）
- 端点：`https://api.biorxiv.org/details/[server]/[interval]`
- 按日期范围批量拉取，返回 DOI、标题、作者、摘要、发布日期
- 可检查是否已有正式发表版本（API 返回 `published` DOI 字段）

**Crossref REST API（DOI 验证与元数据标准化）**

- 接口：完全免费开放
- 端点：`https://api.crossref.org/works/{DOI}`
- 用途：对非 PubMed 来源的 DOI 进行存在性验证和元数据标准化
- 替代直接 HTTP 访问 `doi.org`，返回结构化 JSON（期刊、出版日期、引用数、license 信息等）
- 支持 polite pool（加 mailto 参数）

**检索策略**

- PubMed：MeSH 词 + 自由词组合检索，MeSH 提高精确率，自由词补充新术语召回
- Semantic Scholar：关键词检索 + fieldsOfStudy 过滤（Medicine, Biology）
- OpenAlex：concept/topic 过滤 + 作者/机构追踪
- bioRxiv/medRxiv：按日期范围全量拉取后本地关键词过滤（API 不支持复杂检索）
- 去重顺序：PubMed > Semantic Scholar > OpenAlex > bioRxiv，按 DOI 合并，保留信息最全的版本

#### 🟡 Tier 2：社交信号层（补充，非主力）

**X 平台**

- 使用 LLM 原生搜索能力或 X API v2
- 价值定位：发现学术评论、争议观点、会议实时讨论，而非发现文献本身
- 抓取字段：推文原文、作者 handle、发布时间、引用论文链接
- 与 Tier 1 匹配：X 上讨论的论文如已被 Tier 1 抓到，合并为同一条目附加 X 讨论链接

#### 🟢 Tier 3：辅助源（可选）

**RSS 订阅（公众号 / 博客 / 期刊 Alert）**

- 通过 RSSHub 或其他 RSS 转换工具订阅目标信息源
- cron 运行时拉取新条目
- 公众号、博客等为二手信息源，所有条目需追溯原始学术来源

**手动输入**

- 用户转发链接给 Agent → 读取全文 → 纳入当次处理

### 2.3 关键词配置

独立配置文件 `academic_radar_config.yaml`，用户可随时修改，不动插件代码。

```yaml
# ===== 研究方向关键词 =====
# 命中至少一个才进入评分流程
topics:
  en:
    - "radiotherapy immunotherapy"
    - "immune checkpoint inhibitor radiation"
    - "FLASH radiotherapy"
    - "cGAS-STING radiation"
    - "abscopal effect"
    # 按需添加
  zh:
    - "放疗 免疫治疗"
    - "FLASH放疗"
    - "免疫原性细胞死亡"
    # 按需添加

# ===== 追踪作者/机构 =====
# 命中即保留，不需同时命中 topic
authors:
  - "Last F"          # 按需替换为目标作者
  # - "机构名称"      # 也可追踪机构

# ===== 排除词 =====
exclude:
  - "veterinary"
  - "dental"
  - "pediatric"

# ===== 运行模式 =====
mode: daily         # daily / conference

# ===== 时区 =====
timezone: "Asia/Shanghai"

# ===== 数据源开关 =====
sources:
  pubmed: true
  semantic_scholar: true
  openalex: true
  biorxiv: true
  medrxiv: true
  x_search: true
  rss: true

# ===== API 配置 =====
api_keys:
  pubmed_api_key: ""          # 可选，填写后提高请求频率
  semantic_scholar_key: ""    # 可选，填写后提高请求频率
  openalex_mailto: ""         # 填写邮箱进入 polite pool
  crossref_mailto: ""         # 同上

# ===== RSS 订阅 =====
rss_feeds: []
  # - name: "期刊名称"
  #   url: "https://..."

# ===== 推送渠道 =====
push:
  channel: "webhook"          # webhook / telegram / slack / email
  webhook_url: ""
  # telegram_bot_token: ""
  # telegram_chat_id: ""
```

### 2.4 处理流程

#### Step 1: 数据汇聚与初筛

- 从各 Tier 1 源拉取原始数据
- 按 topics 关键词初筛（至少命中一个），或命中 authors 列表
- 排除 exclude 关键词命中的条目
- 初筛在脚本层完成，不消耗 LLM token

#### Step 2: LLM 相关性评分

对初筛通过的条目，LLM 基于标题 + 摘要评分 1-5：

| 分数 | 含义 | 处理 |
|------|------|------|
| 5 | 研究方向核心文献 | 保留，优先展示 |
| 4 | 同领域重要进展 | 保留 |
| 3 | 相邻领域，有参考价值 | 保留 |
| 2 | 仅关键词匹配，实际关联弱 | 丢弃 |
| 1 | 不相关 | 丢弃 |

评分 prompt 应包含用户研究方向的简要描述（从配置文件读取），而非仅依赖关键词。

#### Step 3: 来源验证与发表状态识别

**发表状态分类：**

| 状态 | 标识 | 判断依据 | 验证动作 |
|------|------|----------|----------|
| Published | ✅ | 有 DOI 且来自正式期刊 | Tier 1 API 源的 DOI 天然可信；Tier 2/3 来源的 DOI 通过 Crossref API 验证 |
| Preprint | 📄 | 来自 bioRxiv/medRxiv/arXiv | 记录预印本链接，通过 bioRxiv API 检查是否已有正式发表版 |
| Conference | 🎤 | 会议摘要（ASCO/ASTRO/ESMO 等） | 记录 Abstract 编号 |
| Unverified | ❓ | 仅社交平台讨论，无法追溯原始文献 | 标注，不丢弃 |

**DOI 验证规则（仅对 Tier 2/3 来源执行）：**

- 优先使用 Crossref API（`https://api.crossref.org/works/{DOI}`）验证，返回结构化元数据
- Crossref 查不到时，回退 `https://doi.org/{DOI}` HTTP HEAD 请求，200 = 存在
- 验证超时不阻塞流程，标注 "⚠️DOI 待验证" 后继续

**反幻觉设计原则：**

- LLM 不生成任何引用信息（标题、作者、DOI 均来自 API 原始返回），仅负责评分和摘要
- 摘要文本从 API 拉取的 abstract 生成，不允许 LLM 凭空补充未在 abstract 中出现的数据
- 每条输出必须携带 fetch_source 字段标注数据来源 API
- 若 LLM 评分返回格式异常，该条目进入 errors 日志，不进入推送

#### Step 4: 去重与合并

- 有 DOI 的按 DOI 去重，优先保留 PubMed 版本（元数据最规范）
- 有 PMID 的按 PMID 去重
- 无 DOI/PMID 的按标题相似度去重（阈值 ≥80%，可用 Levenshtein 或 Jaccard）
- 同一研究的多源信息合并为一条（如 PubMed 元数据 + Semantic Scholar 引用数 + X 讨论链接）

#### Step 5: 排序

1. 发表状态优先级：Published > Preprint > Conference > Unverified
2. 同状态内按相关性评分降序
3. 同分按时间倒序

#### Step 6: 输出

- 条目数范围：0-15
- 无相关内容时输出 "今日无新增"，不凑数
- 超过 15 条时截断，标注 "另有 N 条未展示，回复 '更多' 查看"

### 2.5 输出格式

纯文本推送格式（适配微信等不支持 markdown 的平台）：

```
📡 学术雷达 05-22 08:00
抓取范围：05-21 20:00 ~ 05-22 08:00
PubMed: 23 | S2: 15 | OpenAlex: 31 | bioRxiv: 8 | X: 47 | RSS: 5
命中: 7 条

———

1. ✅Published | 相关性:5
标题: FLASH Proton Therapy Combined with Anti-PD-1 in Recurrent Glioblastoma
作者: Smith A, Johnson B, et al.
期刊: Journal of Clinical Oncology, 2026
DOI: 10.1200/JCO.2026.xxxxx
引用: 12 (S2) | IF: 45.3
核心发现: xxxxxxxx
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

### 2.6 存档

每次推送结果存本地 JSON：

```json
{
  "fetch_time": "2026-05-22T08:00:00+08:00",
  "time_window": {
    "from": "2026-05-21T20:00:00+08:00",
    "to": "2026-05-22T08:00:00+08:00"
  },
  "config_version": "2026-05-20",
  "stats": {
    "pubmed_searched": 23,
    "semantic_scholar_searched": 15,
    "openalex_searched": 31,
    "biorxiv_searched": 8,
    "x_searched": 47,
    "rss_processed": 5,
    "manual_processed": 0,
    "after_keyword_filter": 18,
    "after_llm_scoring": 9,
    "after_dedup": 7,
    "final_output": 7
  },
  "items": [
    {
      "id": "doi:10.1200/...",
      "title": "...",
      "authors": ["Smith A", "Johnson B"],
      "source_journal": "JCO",
      "doi": "10.1200/...",
      "pmid": "39876543",
      "doi_verified": true,
      "doi_verify_method": "pubmed_native",
      "status": "published",
      "relevance_score": 5,
      "summary": "...",
      "abstract_source": "pubmed_api",
      "citation_count": 12,
      "citation_source": "semantic_scholar",
      "x_links": ["https://x.com/..."],
      "fetch_sources": ["pubmed", "semantic_scholar", "x"],
      "fetched_at": "2026-05-22T08:01:23+08:00"
    }
  ],
  "errors": []
}
```

存储路径：`data/radar/YYYY-MM-DD_HHmm.json`
保留最近 30 天，超期自动清理。

## 3. 异常处理

| 场景 | 处理 |
|------|------|
| PubMed API 失败 | 重试 1 次（间隔 5s），仍失败则跳过并标注 "⚠️PubMed 抓取失败" |
| Semantic Scholar API 限流 | 降速重试（指数退避），仍失败则跳过 |
| OpenAlex API 失败 | 跳过，标注 |
| bioRxiv API 失败 | 重试 1 次，仍失败则跳过并标注 |
| X 搜索失败 | 跳过 X 源，标注 "⚠️X 抓取失败"，不阻塞其他源 |
| RSS 拉取失败 | 跳过 RSS 源，标注 |
| Crossref DOI 验证超时 | 标注 "⚠️DOI 待验证"，不阻塞 |
| LLM 返回格式异常 | 记录原始返回到 `data/radar/errors/`，跳过该条目 |
| 全部源失败 | 推送 "🔧 雷达故障，全部数据源不可用，请检查日志" |
| 配置文件缺失/格式错误 | 推送告警，使用上一次有效配置（缓存于 `state/last_valid_config.yaml`） |

**核心原则：各源独立容错，单一源失败不阻塞整体流程。**

## 4. 文件结构

```
academic-radar/
├── academic_radar_config.yaml      # 关键词/数据源/推送配置（用户可编辑）
├── radar_main.py                   # 主入口，调度各模块
├── fetchers/
│   ├── pubmed_fetcher.py           # PubMed E-utilities 检索
│   ├── semantic_scholar_fetcher.py # Semantic Scholar Graph API
│   ├── openalex_fetcher.py         # OpenAlex API
│   ├── biorxiv_fetcher.py          # bioRxiv/medRxiv API
│   ├── x_fetcher.py                # X 平台检索（可选）
│   └── rss_fetcher.py              # RSS 拉取
├── processors/
│   ├── keyword_filter.py           # 关键词初筛（脚本层，不消耗 token）
│   ├── llm_scorer.py               # LLM 相关性评分
│   ├── doi_validator.py            # DOI 验证（Crossref + 回退 doi.org）
│   ├── dedup.py                    # 去重与多源合并
│   └── sorter.py                   # 排序
├── output/
│   ├── formatter.py                # 输出格式化（纯文本/markdown 可切换）
│   └── pusher.py                   # 推送接口（webhook/telegram/slack/email）
├── state/
│   ├── last_success_ts             # 上次成功时间戳
│   └── last_valid_config.yaml      # 上次有效配置缓存
├── data/
│   └── radar/                      # 推送存档 JSON
│       └── errors/                 # 异常日志
├── requirements.txt
├── README.md
└── LICENSE
```

## 5. 验收标准

1. 关键词配置文件修改后，下次 cron 运行自动生效，无需重启
2. PubMed / Semantic Scholar / OpenAlex / bioRxiv API 检索返回结果可正常解析
3. 推送的每条已发表文献 DOI 可点击跳转到原文
4. 推送中不出现无来源的内容（每条必须标注 fetch_source 和发表状态）
5. **反幻觉验证：推送中的标题、作者、DOI 均可追溯到 API 原始返回，LLM 不生成任何书目信息**
6. 连续 3 天运行无重复推送同一篇文献
7. 任一数据源失败不影响其他源处理
8. 存档 JSON 结构稳定，可被下游脚本读取（周报生成等）
9. 数据源可通过配置文件开关，不需改代码

## 6. 后续迭代（不在本期范围）

- Zotero 自动导入
- 周报 / 月报汇总模式
- 引文网络可视化
- 全文自动下载（Unpaywall / OA 链接）
- Google Scholar 检索（无稳定公开 API，需 Scraper）
- 多用户配置支持
- Web UI 管理界面

## 附录 A: 数据源对比

| 数据源 | 覆盖量 | 费用 | API Key | 医学覆盖 | 主要价值 |
|--------|--------|------|---------|----------|----------|
| PubMed | 3600 万+ | 免费 | 可选 | ⭐⭐⭐⭐⭐ | 生物医学金标准 |
| Semantic Scholar | 2 亿+ | 免费 | 可选 | ⭐⭐⭐⭐ | 引文分析、TLDR |
| OpenAlex | 4.7 亿+ | 免费 | 不需要 | ⭐⭐⭐⭐ | 最广覆盖、机构追踪 |
| bioRxiv/medRxiv | 持续增长 | 免费 | 不需要 | ⭐⭐⭐⭐ | 预印本第一时间 |
| Crossref | 1.5 亿+ | 免费 | 不需要 | — | DOI 验证与元数据 |
| X 平台 | — | 取决于接入方式 | 取决于接入方式 | — | 学术讨论、会议实况 |

## 附录 B: 反幻觉架构设计

学术检索场景中 LLM 幻觉的主要风险：

1. **幽灵引用（Ghost Reference）**：生成不存在的论文标题、作者、DOI
2. **引用不忠（Citation Unfaithfulness）**：引用真实论文但声明内容与论文不符
3. **数据编造**：在摘要总结中添加原文未提及的数据或结论

**本插件的防御策略：**

- **LLM 职责边界**：LLM 只做两件事——① 生成检索 query ② 对 API 返回的真实数据评分。所有书目元数据（标题、作者、DOI、摘要）均来自 API 原始返回，不经 LLM 生成或改写。
- **核心发现摘要**：基于 API 返回的 abstract 原文生成，prompt 明确约束 "仅基于以下摘要内容总结，不添加摘要中未出现的信息"。
- **可溯源性**：每条输出携带 `fetch_sources` 和 `abstract_source` 字段，可追溯数据的完整链路。
- **DOI 双重验证**：Tier 1 来源天然可信，Tier 2/3 来源通过 Crossref API 结构化验证。
- **格式校验**：LLM 返回的评分结果做 schema 校验，异常条目进入 error 日志而非推送。
