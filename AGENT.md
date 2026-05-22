# AGENT.md — Academic Radar 接入指南（写给 Agent 看）

> 本文是写给 **LLM Agent** 阅读的操作手册。如果你（Agent）被指派接入或运维这个插件，请按本文步骤执行，不要绕过文件边界规则。
>
> 完整设计意图见 `academic-radar-prd-v2.md`，本指南只覆盖"怎么用"，不覆盖"为什么"。

---

## 0. TL;DR — 你最常做的三件事

1. **首次接入**：引导用户给出研究方向 → 写入 `academic_radar_config.yaml` → 装 cron → 跑一次 `python3 radar_main.py` 验通
2. **关键词变更**：用户提到"加个新关键词 / 屏蔽某类文章" → **只改** `academic_radar_config.yaml`，不动代码
3. **推送渠道切换**：改 `academic_radar_config.yaml` 里的 `push:` 段

90% 的运维任务只动一个文件：`academic_radar_config.yaml`。

---

## 1. 安装

### 推荐路径

| 场景 | 路径 | 理由 |
|------|------|------|
| 用户本机长期运行 | `~/academic-radar/` | 家目录稳定，cron 易写 |
| 服务器 / VPS | `/opt/academic-radar/` | 服务级标准位置 |
| Agent 容器内 | `/app/academic-radar/` | 容器内常规挂载点 |
| 临时测试 | `~/tmp/academic-radar/` | 用完即弃 |

**禁止**装在系统目录（`/usr/`、`/etc/`、`/var/`）或随时会被清理的 `/tmp/`。

### 安装步骤

```bash
git clone <repo-url> ~/academic-radar
cd ~/academic-radar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

依赖检查：Python ≥ 3.9（`zoneinfo` 是 3.9+ 内置模块，低版本需 `backports.zoneinfo`）。

---

## 2. 引导用户提供关键词（最关键的一步）

用户通常不会一次性给出结构化的关键词。**你需要主动提问，然后映射到 config 字段。**

### 2.1 推荐对话脚本

按以下顺序逐项问，**不要一次问完**（用户会答得很笼统）：

```
1. "你的研究方向是什么？用1-2句话描述，越具体越好。"
   → 写入 config.research_focus

2. "在这个方向里，哪些英文关键词组合最能精准命中你想看的论文？
    举例：'FLASH radiotherapy'、'immune checkpoint inhibitor radiation'。
    多个关键词组合用空格连接代表 AND，每行一个独立 topic。"
   → 写入 config.topics.en

3. "有需要追踪的中文关键词吗？（公众号、中文期刊、会议摘要等）"
   → 写入 config.topics.zh（可以为空）

4. "有哪些作者或机构你特别关注？姓在前名缩写在后，如 'Smith A'。"
   → 写入 config.authors（可以为空）

5. "有哪些类型的论文要直接排除？比如兽医、儿科、综述等。"
   → 写入 config.exclude

6. "推送到哪里？微信群机器人 webhook / Telegram / Slack / 邮件？"
   → 写入 config.push 整段

7. **LLM 模型自查 + 让用户选**（你来主导，**不要直接让用户填 key**）
   → 先自查环境里**已配好 API key** 的 LLM provider（env / 框架 registry / 本地服务）
   → 把可用 provider + 推荐模型 + 价格档位列给用户选（详细步骤 §2.4）
   → 用户选完后写入 `config.llm`
```

### 2.2 关键词质量校准

用户给的关键词通常**太宽或太窄**，你要做这件事：

- **太宽**（如 "cancer"）：警告用户"这会命中几千篇/天，建议加修饰词，如 'cancer radiotherapy immunotherapy'"
- **太窄**（如完整论文标题）：警告用户"这只会命中那一篇，建议拆成核心 2-3 个词"
- **拼写不规范**：自动纠正（如 "PD1" → "PD-1"，"FLASH RT" → "FLASH radiotherapy"），但**改完后告诉用户改了什么**

### 2.3 关键词命中机制（你要心里有数）

`processors/keyword_filter.py` 做的是**子串匹配**（不是分词不是正则）：
- `"FLASH radiotherapy"` 命中 `"FLASH radiotherapy in cancer"` ✅
- `"FLASH radiotherapy"` **不** 命中 `"radiotherapy with FLASH"`（顺序敏感）❌
- 命中 `topics.en` **或** `authors` **任一即通过**；命中 `exclude` **任一即丢弃**

如果用户希望 OR 关系，让他们写成多行（一行一个 topic）。

### 2.4 LLM 模型自查（步骤 7 展开）

**先自查，再问用户**——用户大概率不知道自己机器上有哪些 API key。

#### 自查顺序

1. **环境变量**（覆盖 90% 场景）
   ```bash
   env | grep -iE "_API_KEY|_API_TOKEN" | sed 's/=.*/=<set>/' | sort
   ```
   常见命名：`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`DEEPSEEK_API_KEY`、`MOONSHOT_API_KEY`、`DASHSCOPE_API_KEY`（通义）、`ZHIPUAI_API_KEY`（智谱）、`GROQ_API_KEY`、`MISTRAL_API_KEY`

2. **Agent 框架自带的 model registry**（看运行环境）
   - Claude Code: `~/.claude/settings.json` 的 `env` / `apiKeyHelper`
   - Hermes / LangChain / 自建: 看框架自己的 model providers 配置
   - LlamaIndex / 项目本地: 看 `.env`

3. **本地 OpenAI 兼容服务**
   ```bash
   curl -fsS http://localhost:11434/v1/models 2>/dev/null && echo "→ Ollama 在 11434"
   curl -fsS http://localhost:8000/v1/models  2>/dev/null && echo "→ vLLM 在 8000"
   ```

4. **全没找到 → 直接告诉用户**：
   > "这台机器没找到现成的 LLM API key。你需要先去申请一个（OpenAI / DeepSeek / 月之暗面 / 智谱 任选一家），拿到 key 再回来我帮你填。"

   **不要**编 endpoint，**不要**写假 key 进 config。

#### 呈现选项给用户（不要泄漏 key 本身）

```
我自查到这台机器可用的 LLM provider：

1. OpenAI（OPENAI_API_KEY 已设置）
   推荐：gpt-4o-mini，约 ¥0.x/天
2. DeepSeek（DEEPSEEK_API_KEY 已设置）
   推荐：deepseek-chat，约 ¥0.0x/天（最便宜）
3. Ollama 本地（qwen2.5:7b）
   免费，跑本机 GPU/CPU

评分任务很简单，建议选 2 或 3（详见 §5 决策树）。用哪个？
```

#### 写入 config

用户选完后，**只改** `academic_radar_config.yaml` 的 `llm:` 段。常见 `base_url`：

| Provider | base_url |
|----------|----------|
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Moonshot (Kimi) | `https://api.moonshot.cn/v1` |
| 通义 DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 BigModel | `https://open.bigmodel.cn/api/paas/v4` |
| Groq | `https://api.groq.com/openai/v1` |
| Ollama 本地 | `http://localhost:11434/v1` |
| vLLM 本地 | `http://localhost:8000/v1` |

写完跑一个 smoke test 确认 key 真能用：

```bash
python3 -c "
from openai import OpenAI; import yaml
cfg = yaml.safe_load(open('academic_radar_config.yaml'))['llm']
r = OpenAI(base_url=cfg['base_url'], api_key=cfg['api_key']).chat.completions.create(
    model=cfg['model'], messages=[{'role':'user','content':'reply with just OK'}], max_tokens=5)
print(r.choices[0].message.content)
"
```

输出非 "OK" 或报错 → 回到自查步骤 4，让用户换一个 provider。**不要**带着错的 key 装 cron。

#### Key 安全提示

- `radar_main.load_config()` 用 `yaml.safe_load`，**不展开 env 变量**——key 必须明文写进 yaml（写 `${OPENAI_API_KEY}` 会当字面字符串）
- 让用户对 config 文件加权限：`chmod 600 academic_radar_config.yaml`
- `.gitignore` **没有**忽略这个 yaml（PRD 把它当模板需要版本化）。如果用户 repo 是公开的，建议执行：
  ```bash
  git update-index --assume-unchanged academic_radar_config.yaml
  ```
- 如果用户强烈要求从 env 读 key：这是 §3 黄色等级改动（要改 `radar_main.load_config()`），改完跑一遍 §8 反幻觉自查

---

## 3. 文件修改边界（务必遵守）

| 等级 | 文件 | 你能做什么 |
|------|------|------------|
| 🟢 **自由编辑** | `academic_radar_config.yaml` | 关键词、作者、排除词、推送渠道、API key、运行模式、时区——全部用户可见配置都在这里。**99% 的用户需求都改这一个文件**。 |
| 🟡 **谨慎编辑** | `processors/llm_scorer.py` 的 `build_prompt()` | 评分 prompt 模板。改的时候**必须保留反幻觉约束**（见下节）。改完跑一次 `python3 radar_main.py` 校验。 |
| 🟡 **谨慎编辑** | `output/formatter.py` 的 `format_item()` | 推送展示格式。可以加字段、改 emoji，但**不能凭空生成 item 没有的字段**。 |
| 🔴 **不要动** | `fetchers/*.py` | 数据源 API 契约。除非用户明确要求"加一个新数据源"或"某个 API 升级了"，否则不要碰。改坏一个 fetcher 会让该源全部失败。 |
| 🔴 **不要动** | `models.py` | 流水线数据 schema。所有模块共享。改一个字段名等于改 N 处。 |
| 🔴 **不要动** | `processors/doi_validator.py` | 反幻觉防线之一。`TRUSTED_SOURCES` 白名单错改一处会让所有 DOI 标错状态。 |
| 🔴 **不要动** | `processors/dedup.py` | 多源合并逻辑。改 `SOURCE_PRIORITY` 会改变主条目选取。 |
| 🔴 **绝对不要动** | `radar_main.py` 的流水线顺序 | 顺序错了反幻觉就破了（DOI 验证必须在 LLM 评分之后、推送之前）。 |
| ⚫ **运行时生成，不要手改** | `state/last_success_ts`、`data/radar/*.json` | 时间戳和存档。手改会导致下次抓取窗口错乱或推送重复。 |

### 反幻觉红线（PRD §附录 B）

改 `llm_scorer.py` 的 prompt 时，**这几条必须保留**：

```
1. LLM 只输出 score (1-5整数) 和 summary（基于摘要原文）
2. 严禁生成或改写 title / author / DOI / 期刊
3. summary 中不允许添加摘要未出现的数据或结论
```

如果用户要求"让 LLM 帮我补充论文背景"——**拒绝并解释**：会引入幽灵引用风险，违反 PRD 设计。

---

## 4. Cron 设置

### 4.1 日常模式（PRD §2.1 默认）

每天 08:00 和 20:00 各跑一次：

```cron
0 8,20 * * * cd ~/academic-radar && /usr/bin/python3 radar_main.py >> ~/academic-radar/run.log 2>&1
```

### 4.2 会议模式（开会期间临时启用）

每 4 小时一次：

```cron
0 */4 * * * cd ~/academic-radar && /usr/bin/python3 radar_main.py >> ~/academic-radar/run.log 2>&1
```

同时把 `academic_radar_config.yaml` 里的 `mode: daily` 改成 `mode: conference`（影响推送底部的"下次抓取"提示文本）。

### 4.3 时区处理

cron 跑在系统时区，但脚本内部按 `config.timezone` 计算时间窗口。**改了 config.timezone 不需要改 cron**——脚本会自己处理。

### 4.4 安装 cron 的标准流程

```bash
# 查看当前 crontab
crontab -l

# 编辑（追加，不要覆盖用户已有任务）
(crontab -l 2>/dev/null; echo "0 8,20 * * * cd ~/academic-radar && /usr/bin/python3 radar_main.py >> ~/academic-radar/run.log 2>&1") | crontab -

# 验证
crontab -l | grep academic-radar
```

⚠️ 用 venv 时把 `/usr/bin/python3` 换成 `~/academic-radar/.venv/bin/python3`。

### 4.5 Agent 自带调度器

如果运行环境是 Hermes / AutoGPT / 自建 Agent 框架，用框架的定时器（如 Hermes 的 `scheduler.add_job(cron="0 8,20 * * *")`）调用 `radar_main.run_once()` 即可，**不要混用 cron + Agent scheduler**。

---

## 5. LLM 配置

在 `academic_radar_config.yaml` 的 `llm:` 段：

```yaml
llm:
  base_url: "https://api.openai.com/v1"   # 或任何 OpenAI 兼容端点
  api_key: "sk-..."
  model: "gpt-4o-mini"                     # 评分任务建议用小模型省钱
  timeout: 30
```

### 模型选择决策树

| 用户预算 | 推荐模型 | 备注 |
|---------|---------|------|
| 紧（每天 < 1￥） | `gpt-4o-mini` / `claude-haiku-4-5` / 任何 7B-32B 的国产模型 | 评分任务很简单，小模型够用 |
| 中等 | `gpt-4o` / `claude-sonnet-4-6` | 摘要质量更好 |
| 富裕 | `claude-opus-4-7` | 没必要，溢出 |

**这是评分任务，不是创作任务**——再小的模型只要能输出合规 JSON 就够用。

---

## 6. 运行 & 验证

### 6.1 首次跑通

```bash
cd ~/academic-radar
python3 radar_main.py
```

应该看到：

```
INFO Window: 2026-05-20T08:00:00+08:00 → 2026-05-22T08:00:00+08:00
INFO pubmed: 23 items
INFO semantic_scholar: 15 items
...
INFO Total fetched: 89
INFO After keyword filter: 18
INFO After LLM scoring: 9 (errors: 0)
INFO After dedup: 7
INFO Archived to data/radar/2026-05-22_0800.json
INFO Done. output=7 push=OK
```

### 6.2 没收到推送怎么排查

按这个顺序看：

```bash
# 1. 看推送是否成功
tail -50 run.log | grep -E "push|Push"

# 2. 看本次抓到/筛掉多少
ls -lt data/radar/*.json | head -1 | awk '{print $9}' | xargs jq '.stats'

# 3. 看是不是关键词太严
jq '.items | length' data/radar/$(ls -t data/radar/*.json | head -1 | xargs basename)

# 4. 看 LLM 是否有评分异常
ls data/radar/errors/

# 5. 看上次成功时间（如果太旧说明 cron 没跑）
cat state/last_success_ts
```

### 6.3 用户说"今天没收到"

```
A. 先看 data/radar/ 里今天有没有新 JSON 文件
   有 → 跑过了，可能是推送渠道挂了（看 run.log）
   没 → cron 没跑（看 systemctl status cron 或 crontab -l）

B. 看 JSON 里 final_output 是否 = 0
   是 → "今日无新增"是预期行为（PRD §2.4 Step 6 明确规定不凑数）
   否 → 推送链路问题
```

---

## 7. 常见用户请求 → 标准动作映射

| 用户说 | 你做什么 |
|--------|---------|
| "加一个关键词 XXX" | 改 `config.topics.en` 或 `topics.zh`，append 一行 |
| "屏蔽 XXX 类文章" | 改 `config.exclude`，append 一行 |
| "关注一下 XXX 教授" | 改 `config.authors`，append `"Last F"` 格式 |
| "换成 Telegram 推送" | 改 `config.push.channel: telegram`，填 bot_token + chat_id |
| "暂时停掉 RSS 不要看了" | 改 `config.sources.rss: false`（不要删 `rss_feeds`） |
| "推送太多了" | 改 `config.output.max_items` 从 15 调到 10 |
| "学会议期间想多看几次" | 改 `config.mode: conference` + 改 cron 到 `0 */4 * * *` |
| "PubMed 这两天没数据" | **先查 `data/radar/*.json` 的 stats.pubmed_searched**，再判断是真没数据还是 API 失败 |
| "推送的某条论文是假的" | **立即排查** —— 这是反幻觉防线被破。看该条的 `fetch_sources` 和 `abstract_source`，必要时打开存档 JSON 看 `raw` 字段 |
| "我换电脑了，怎么迁移" | 把整个目录 rsync 走（包括 `state/`），重新装 cron |

---

## 8. 反幻觉自查（每次改动后必跑）

如果你改了 `llm_scorer.py` 的 prompt 或 `formatter.py` 的展示逻辑，**必须**做这两件事：

1. 跑一次 `python3 radar_main.py`，看最新 archive JSON：
   ```bash
   jq '.items[] | {title, doi, abstract_source, fetch_sources, doi_verify_method}' data/radar/$(ls -t data/radar/*.json | head -1 | xargs basename)
   ```
   每条都必须有 `fetch_sources` 和 `abstract_source`，否则反幻觉链路断了。

2. 抽查一条推送出去的论文，**手动**用 DOI 去 doi.org / PubMed 验证标题、作者一致。

发现不一致 → 回退到上一个 commit，**不要尝试 hotfix**。

---

## 9. 你不应该做的事

- ❌ 不要让 LLM 调用 search / web tool 去"补充"论文信息——所有元数据只能来自 fetchers
- ❌ 不要把 `state/last_success_ts` 提交到 git（已在 .gitignore）
- ❌ 不要把用户的 API key 写进代码或提交到 git——只能写在 `academic_radar_config.yaml` 里且该文件不应公开
- ❌ 不要"为了让推送好看"在 formatter 里硬编码任何论文相关字段
- ❌ 不要在没有用户明确同意的情况下改 `radar_main.py` 的流水线顺序
- ❌ 不要为了"修 bug"删 `errors/` 目录下的日志——那是排查反幻觉问题的关键证据

---

## 10. 升级 / 维护

- 加新数据源：在 `fetchers/` 加一个新文件，签名 `fetch(config, since, until) -> list[Item]`，在 `radar_main.fetch_all()` 注册，在 `dedup.SOURCE_PRIORITY` 排位置
- 加新推送渠道：在 `output/pusher.py` 的 `dispatch` 表加一行
- 改存档 schema：同步改 `models.Item` 和 `radar_main.archive()`，**老的 JSON 文件别尝试迁移**

遇到拿不准的，**先问用户，不要擅自改**。
