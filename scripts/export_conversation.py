#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 WorkBuddy 会话 jsonl 导出为可读的 workbuddy.md（完整上下文存档）。

用法：python3 export_conversation.py <jsonl路径> <输出md路径>
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

BJ = timezone(timedelta(hours=8))
SRC = sys.argv[1]
OUT = sys.argv[2]
TRUNC = 2500          # 单个内容块截断长度
BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9\-_]{16,}")

# 从 mcp.json 读出真实 token，连同裸 token 一起脱敏（脚本里常以变量形式出现）
def _load_token():
    try:
        cfg = json.load(open(os.path.expanduser("~/.workbuddy/mcp.json")))
        auth = cfg["mcpServers"]["mcd-mcp"]["headers"]["Authorization"]
        return auth.replace("Bearer", "").strip()
    except Exception:
        return None

_RAW_TOKEN = _load_token()
TOKEN_RE = re.compile(re.escape(_RAW_TOKEN)) if _RAW_TOKEN and len(_RAW_TOKEN) >= 12 else None

entries = []
with open(SRC, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass

entries.sort(key=lambda o: o.get("timestamp", 0))

def ts(o):
    return datetime.fromtimestamp(o.get("timestamp", 0) / 1000, BJ).strftime("%H:%M:%S")

def ts_full(o):
    return datetime.fromtimestamp(o.get("timestamp", 0) / 1000, BJ).strftime("%Y-%m-%d %H:%M:%S")

def redact(text):
    if not isinstance(text, str):
        text = str(text)
    text = BEARER_RE.sub("Bearer ***已脱敏***", text)
    if TOKEN_RE:
        text = TOKEN_RE.sub("***已脱敏***", text)
    return text

def clip(text, limit=TRUNC):
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n……（以上已截断，原内容 {len(text)} 字符，完整版见 jsonl 原始记录）"

# 系统提醒去重（同样的 reminder 第二次起只留标记）
seen_reminders = set()
REMINDER_RE = re.compile(r"<system-reminder[^>]*>.*?</system-reminder>", re.S)

def dedup_reminders(text):
    def repl(m):
        block = m.group(0)
        key = re.sub(r"\s+", "", block)[:500]
        if key in seen_reminders:
            return "〈系统提醒：内容与前面重复，略〉"
        seen_reminders.add(key)
        return block
    return REMINDER_RE.sub(repl, text)

# 统计
stats = {}
for o in entries:
    stats[o.get("type", "?")] = stats.get(o.get("type", "?"), 0) + 1

title = next((o.get("aiTitle") for o in entries if o.get("type") == "ai-title"), "（无标题会话）")

# 收集用户消息做目录
INJECT_RE = re.compile(r"<(system-reminder|cb_summary|user-prompt-submit-hook)[^>]*>.*?</\1>", re.S)
TAG_RE = re.compile(r"<[^>]+>")

user_turns = []
for o in entries:
    if o.get("type") == "message" and o.get("role") == "user":
        text = "".join(b.get("text", "") for b in o.get("content", []) if isinstance(b, dict))
        text = dedup_reminders(redact(text)).strip()
        # 预览：剥掉注入块（系统提醒/摘要等）和所有标签，取第一句有效内容
        preview_src = INJECT_RE.sub("", text)
        preview_src = TAG_RE.sub(" ", preview_src)
        preview_src = re.sub(r"\s+", " ", preview_src).strip()
        preview = preview_src[:60] if preview_src else "（自动续跑/无正文）"
        user_turns.append((ts_full(o), preview, len(text)))

lines = []
lines.append("# 麦选 · 对话完整上下文导出")
lines.append("")
lines.append(f"- **会话标题**：{title}")
lines.append(f"- **会话 ID**：{entries[0].get('sessionId', '?') if entries else '?'}")
lines.append(f"- **导出时间**：{datetime.now(BJ).strftime('%Y-%m-%d %H:%M:%S')}（北京时间）")
lines.append(f"- **来源文件**：`{SRC}`")
lines.append(f"- **记录条数**：{len(entries)} 条（{', '.join(f'{k}×{v}' for k, v in sorted(stats.items()))}）")
lines.append("- **说明**：按时间线完整导出全部用户消息、助手消息、工具调用与返回、思考过程；"
             "超长单块内容截断并标注；重复的系统提醒折叠；**Bearer Token 已脱敏**。")
lines.append("")
lines.append("---")
lines.append("")
lines.append("## 📑 用户发言目录")
lines.append("")
for i, (t, preview, _) in enumerate(user_turns, 1):
    lines.append(f"{i}. `{t}` {preview}")
lines.append("")
lines.append("---")
lines.append("")

for o in entries:
    t = o.get("type")
    if t == "message":
        role = o.get("role")
        text = "".join(b.get("text", "") for b in o.get("content", []) if isinstance(b, dict))
        text = dedup_reminders(redact(text))
        if not text.strip():
            continue
        if role == "user":
            lines.append(f"## 👤 用户 · {ts_full(o)}")
        elif role == "assistant":
            lines.append(f"## 🤖 麦选（助手） · {ts_full(o)}")
        else:
            lines.append(f"## [{role}] · {ts_full(o)}")
        lines.append("")
        lines.append(clip(text))
        lines.append("")
    elif t == "reasoning":
        rc = o.get("rawContent") or []
        text = "".join(b.get("text", "") for b in rc if isinstance(b, dict))
        if not text.strip():
            continue
        lines.append(f"> 💭 **思考过程** · {ts_full(o)}（模型内部推理，已截断）")
        lines.append(">")
        for ln in clip(redact(text), 1200).splitlines():
            lines.append("> " + ln)
        lines.append("")
    elif t == "function_call":
        args = o.get("arguments")
        if isinstance(args, (dict, list)):
            args = json.dumps(args, ensure_ascii=False, indent=2)
        lines.append(f"### 🔧 调用工具：`{o.get('name')}` · {ts_full(o)}")
        lines.append("")
        lines.append("```json")
        lines.append(clip(redact(args or ""), 1500))
        lines.append("```")
        lines.append("")
    elif t == "function_call_result":
        out = o.get("output")
        if isinstance(out, dict):
            out = out.get("text", json.dumps(out, ensure_ascii=False))
        elif isinstance(out, list):
            parts = []
            for b in out:
                if isinstance(b, dict):
                    parts.append(b.get("text") or json.dumps(b, ensure_ascii=False))
                else:
                    parts.append(str(b))
            out = "\n".join(parts)
        status = o.get("status", "?")
        lines.append(f"#### ↩️ 工具返回：`{o.get('name')}`（{status}） · {ts_full(o)}")
        lines.append("")
        lines.append("```")
        lines.append(clip(redact(out or "")))
        lines.append("```")
        lines.append("")
    # file-history-snapshot / ai-title / resend-fork-notice 不入正文

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"OK -> {OUT}")
import os
print(f"大小: {os.path.getsize(OUT)/1024:.0f} KB | 行数: {len(lines)} | 用户发言: {len(user_turns)} 条")
