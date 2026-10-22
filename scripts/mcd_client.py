#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mcd-mcp 最小 JSON-RPC 客户端（麦选实测同款调用逻辑）。

用法：
    python3 mcd_client.py <工具名> ['<JSON 参数>']
    python3 mcd_client.py --list-tools
    python3 mcd_client.py now-time-info

说明：
- token 自动从 ~/.workbuddy/mcp.json 的 mcpServers.mcd-mcp.headers.Authorization 读取，不硬编码。
- 官方 MCP 地址 https://mcp.mcd.cn，需先 initialize 拿 Mcp-Session-Id，再 tools/call。
- 坑位①：真实数据在返回体的 result.structuredContent（标准 JSON），result.content[].text 只是说明包装。
- 坑位②：calculate-price 的价格单位是「分」，展示要 ÷100。
- 仅依赖 Python 标准库。
"""
import json
import os
import sys
import urllib.request

MCP_JSON = os.path.expanduser("~/.workbuddy/mcp.json")
BASE_URL = "https://mcp.mcd.cn"


def load_auth():
    with open(MCP_JSON, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["mcpServers"]["mcd-mcp"]["headers"]["Authorization"]


class McdClient:
    def __init__(self):
        self.auth = load_auth()
        self.session_id = None
        self._req_id = 0

    def _rpc(self, method, params=None):
        self._req_id += 1
        payload = {"jsonrpc": "2.0", "id": self._req_id, "method": method}
        if params is not None:
            payload["params"] = params
        req = urllib.request.Request(BASE_URL, data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Authorization", self.auth)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        if self.session_id:
            req.add_header("Mcp-Session-Id", self.session_id)
        with urllib.request.urlopen(req, timeout=60) as resp:
            self.session_id = resp.headers.get("Mcp-Session-Id", self.session_id)
            body = resp.read().decode("utf-8").strip()
            if not body:
                return {}  # 通知（notifications/*）无返回体
            return json.loads(body)

    def ensure_session(self):
        if self.session_id:
            return
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "maixuan-scripts", "version": "1.0"},
        })
        self._rpc("notifications/initialized")

    def call_tool(self, name, arguments=None):
        """调用工具，返回 structuredContent（真实数据）。"""
        self.ensure_session()
        resp = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        result = resp.get("result", {})
        if "structuredContent" in result:
            return result["structuredContent"]
        # 没有 structuredContent 时把原文返回，便于排查
        return result

    def list_tools(self):
        self.ensure_session()
        return self._rpc("tools/list").get("result", {}).get("tools", [])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    client = McdClient()
    if sys.argv[1] == "--list-tools":
        tools = client.list_tools()
        print(f"共 {len(tools)} 个工具：")
        for t in tools:
            print(" -", t.get("name"))
        return
    name = sys.argv[1]
    arguments = {}
    if len(sys.argv) >= 3:
        arguments = json.loads(sys.argv[2])
    sc = client.call_tool(name, arguments)
    print(json.dumps(sc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
