"""Agent 上下文管理 — token 估算 / 结构化截断 / 滚动压缩。

长任务里工具结果逐轮累积：20 步 × 6000 字符 ≈ 12 万字符，token 成本线性膨胀，
且可能撞上模型上下文窗口。这里解决三件事：

1. ``estimate_tokens`` — 粗估 messages 的 token 数（CJK ≈ 1 token/字，其他 ≈ 4 字符/token）。
   只用于触发压缩的启发式，不追求精确分词。
2. ``truncate_tool_result`` — 按字段结构化截断（替代旧的裸字符切片，
   不再把 JSON 截成非法片段喂回模型）。
3. ``ContextManager`` — 主循环每次工具批次后调用 ``record_batch`` 存下
   人读摘要行；估算 token 超预算时，把最旧的步骤组压缩成摘要。
   消息序列始终保持合法：OpenAI 兼容 API 要求 assistant.tool_calls 与其
   role:tool 回复成组出现，因此压缩时把整组替换为一条无 tool_calls 的
   assistant 摘要消息，而不是只删一半。

摘要批次与消息组天然一一对应：主循环里「有 tool_calls 的一次响应 + 其全部
tool 回复」就是一个组，同时产生一个摘要批次（finish/取消批次也记录）。
"""

from __future__ import annotations

import json
import logging

from nia.utils.config import Config

logger = logging.getLogger(__name__)

# 结构化截断的默认参数
_DEFAULT_LIST_ITEMS = 20


def estimate_tokens(text: str) -> int:
    """粗估一段文本的 token 数。

    中文（CJK 统一表意文字）大约 1 字 ≈ 1 token；拉丁/数字/标点大约 4 字符 ≈ 1 token。
    """
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + (len(text) - cjk) // 4


def estimate_messages_tokens(messages: list) -> int:
    total = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            total += estimate_tokens(content)
        if msg.get("tool_calls"):
            try:
                total += estimate_tokens(json.dumps(msg["tool_calls"], ensure_ascii=False))
            except (TypeError, ValueError):
                pass
        total += 4  # 每条消息的角色/结构开销
    return total


def truncate_tool_result(obj, limit: int | None = None, _depth: int = 0, _str_cap: int | None = None):
    """按字段结构化截断工具结果，返回**始终可被 json.dumps 的对象**。

    策略：字符串按上限截断、列表只保留前 N 项并标注总数、嵌套深度封顶。
    结构化之后仍超限（键极多的退化情况）由调用方对最终字符串兜底。
    """
    limit = limit or 6000
    if _depth > 6:
        return "…(层级过深，已省略)"
    cap = _str_cap if _str_cap is not None else max(200, limit // 6)

    if isinstance(obj, str):
        return obj if len(obj) <= cap else obj[:cap] + f"…(截断，原长 {len(obj)})"
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, (list, tuple)):
        items = [truncate_tool_result(v, limit, _depth + 1, cap) for v in obj[:_DEFAULT_LIST_ITEMS]]
        if len(obj) > _DEFAULT_LIST_ITEMS:
            items.append(f"…(共 {len(obj)} 项，仅显示前 {_DEFAULT_LIST_ITEMS} 项)")
        return items
    if isinstance(obj, dict):
        return {str(k)[:120]: truncate_tool_result(v, limit, _depth + 1, cap) for k, v in obj.items()}
    return str(obj)[:cap]


def summarize_args(args: dict, limit: int = 160) -> str:
    """把工具参数压成一行人读摘要（用于压缩摘要与前端展示）。"""
    try:
        raw = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        raw = str(args)
    return raw if len(raw) <= limit else raw[:limit] + "…"


def summarize_result(result, limit: int = 200) -> str:
    """工具结果的一行人读摘要。"""
    if not isinstance(result, dict):
        return str(result)[:limit]
    if result.get("ok") is False:
        err = result.get("error") or result.get("message") or "失败"
        return f"失败: {str(err)[:limit]}"
    parts: list[str] = []
    for key in ("title", "url", "summary", "chars", "num_links", "finding_count", "note"):
        value = result.get(key)
        if value not in (None, ""):
            text = str(value)
            parts.append(text if len(text) <= 80 else text[:80] + "…")
    pages = result.get("pages")
    if isinstance(pages, list):
        parts.append(f"共 {len(pages)} 页")
    return " | ".join(parts)[:limit] if parts else "完成"


def _scan_groups(messages: list) -> list[tuple[int, int]]:
    """扫描消息序列，找出所有「assistant(tool_calls)+tool 回复」组的 (start, end) 索引。

    消息序列合法性约定：tool 消息必须紧跟在带 tool_calls 的 assistant 消息之后，
    中间不得插入其它角色 —— 本项目的写入路径（agent 主循环）保证这一点。
    """
    groups: list[tuple[int, int]] = []
    i = 0
    n = len(messages)
    while i < n:
        msg = messages[i]
        if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("tool_calls"):
            j = i
            while j + 1 < n and isinstance(messages[j + 1], dict) and messages[j + 1].get("role") == "tool":
                j += 1
            groups.append((i, j))
            i = j + 1
        else:
            i += 1
    return groups


class ContextManager:
    """记录每批工具调用的摘要行，并在超预算时滚动压缩消息历史。"""

    def __init__(self, token_budget: int | None = None, keep_recent_steps: int | None = None):
        self.token_budget = token_budget or Config.AGENT_CONTEXT_TOKEN_BUDGET
        self.keep_recent = keep_recent_steps or Config.AGENT_CONTEXT_KEEP_RECENT_STEPS
        self.batches: list[list[str]] = []  # 与消息组按时间顺序一一对应
        self.compactions = 0

    def record_batch(self, digests: list[str]) -> None:
        """主循环每执行完一批工具调用（含 finish/取消批次）记录一次摘要。"""
        self.batches.append([d[:300] for d in digests])
        if len(self.batches) > 300:  # 摘要自身也不该无界增长
            del self.batches[: len(self.batches) - 300]

    def should_compact(self, messages: list) -> bool:
        return estimate_messages_tokens(messages) > self.token_budget

    def compact(self, messages: list) -> tuple[list, int]:
        """把最旧的步骤组替换为摘要消息，返回 (新消息列表, 估算节省的 token 数)。

        - system 与最初 user 消息永远保留；
        - 最近 keep_recent 个步骤组保留原文（给模型短期记忆）；
        - 更早的组：assistant(tool_calls)+tool… 整组替换为一条摘要 assistant 消息。
        """
        before = estimate_messages_tokens(messages)
        groups = _scan_groups(messages)
        if len(groups) <= self.keep_recent:
            return messages, 0

        old_groups = groups[: len(groups) - self.keep_recent]
        drop: set[int] = set()
        replace: dict[int, str] = {}  # 组起始索引 -> 摘要文本
        for gi, (start, end) in enumerate(old_groups):
            digest = self.batches[gi] if gi < len(self.batches) else []
            text = "；".join(digest) if digest else "（历史步骤，详情略）"
            if len(text) > 500:
                text = text[:500] + "…"
            drop.update(range(start, end + 1))
            replace[start] = f"（第 {gi + 1} 批探索，已压缩）{text}"

        out: list = []
        for i, msg in enumerate(messages):
            if i in replace:
                out.append({"role": "assistant", "content": replace[i]})
            elif i in drop:
                continue
            else:
                out.append(msg)

        # 在开场 user 消息之后插入压缩说明，让模型知道早期历史被概括了
        insert_at = 2 if len(out) > 2 and isinstance(out[1], dict) and out[1].get("role") == "user" else 1
        out.insert(insert_at, {
            "role": "user",
            "content": (
                f"（系统提示：为控制上下文长度，最早的 {len(old_groups)} 批探索记录已压缩为摘要，"
                "仅保留最近步骤的完整内容。历史发现仍完整保存在任务状态中。）"
            ),
        })

        after = estimate_messages_tokens(out)
        saved = max(0, before - after)
        self.compactions += 1
        # 压缩掉的批次不再参与下一次对齐：清掉已消费的摘要
        self.batches = self.batches[len(old_groups):]
        logger.info("context compacted: %d groups -> digest, ~%d tokens freed", len(old_groups), saved)
        return out, saved
