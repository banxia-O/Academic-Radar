"""数据源 fetcher 包。

每个 fetcher 暴露统一签名：
    fetch(config: dict, since: datetime, until: datetime) -> list[Item]

约定：
- 不抛异常，内部捕获后返回空列表 + 日志告警（PRD §3 各源独立容错）
- 所有书目元数据均来自 API 原始返回，禁止 LLM 生成（PRD §2.4 反幻觉）
- 每条 Item.fetch_sources 至少包含本 fetcher 的标识
"""
