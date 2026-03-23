---
name: agent-bridge
description: "OpenClaw 多 Agent 间正式通信技能。支持 Agent 发现、消息发送、多轮对话管理、通信历史查询。区别于 sub-agent 的临时任务委派，实现独立 Agent 之间的双向、可追溯通信。"
---

# Agent Bridge - 多 Agent 间通信技能 v2.0

> 💡 **技能版本**: v2.0  
> 📅 **更新时间**: 2026-03-23  
> 👤 **作者**: 小千 👡  
> 🎯 **核心功能**: 实现 OpenClaw 多 Agent 之间的**正式、双向、可追溯**通信

---

## 🎯 技能定位

本技能封装 OpenClaw Gateway 原生的 `sessions_*` 工具集，提供正式的 Agent 间通信能力，**区别于 sub-agent 的"临时任务委派"模式**。

### 与 Sub-agent 的本质区别

| 维度 | Sub-agent (`sessions_spawn`) | Agent Bridge (`sessions_send`) |
|------|------------------------------|--------------------------------|
| **身份** | 同一 Agent 的临时分身 | 独立 Agent 之间的对话 |
| **会话隔离** | 共享 agentDir、auth、workspace | 完全独立的 workspace、agentDir、session store |
| **通信方向** | 单向（父→子，结果 announce 回） | 双向（支持多轮 ping-pong） |
| **人格** | 同一 SOUL.md | 不同 SOUL.md（独立人格） |
| **使用场景** | 临时任务委派、代码生成 | 长期协作、信息同步、任务交接 |

---

## 🆕 v2.0 新特性

- ✅ **实际工具调用**：不再只是生成说明，实际调用 sessions_* 工具
- ✅ **完整错误处理**：定义了错误类型、指数退避重试
- ✅ **消息追踪**：追踪消息状态，确认送达
- ✅ **对话管理重构**：与 sessions_* 工具集成
- ✅ **高级 API**：简化的 ping/notify/ask 方法

---

## 📁 文件结构

```
skills/agent-bridge/
├── SKILL.md                      # 本文件
├── DESIGN.md                     # 设计文档
├── scripts/
│   ├── bridge_core.py            # 核心工具调用层 ★
│   ├── bridge_api.py             # 高级 API 层 ★
│   ├── agent_bridge.py           # CLI 入口
│   ├── conversation_manager.py   # 对话管理器
│   └── message_tracker.py        # 消息追踪器 ★
├── examples/
│   ├── basic_send.py             # 基础发送示例
│   └── multi_turn_conv.py        # 多轮对话示例
└── docs/
    └── ERROR_HANDLING.md         # 错误处理指南
```

---

## 🚀 快速开始

### 前置条件

1. **启用 Agent 间通信**（在 `~/.openclaw/openclaw.json` 中）：
```json
{
  "tools": {
    "agentToAgent": {
      "enabled": true,
      "allow": ["main", "su-er"]
    },
    "sessions": {
      "visibility": "all"
    }
  }
}
```

2. **重启网关**：
```bash
openclaw gateway restart
```

---

## 📖 在 OpenClaw 中使用

### 方式 1：直接使用 sessions_* 工具

```python
# 发送消息并等待回复
result = sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": "你好，素儿，有新任务需要协调",
    "timeoutSeconds": 30
})

# result.status: "ok" | "timeout" | "error"
# result.reply: 素儿的回复内容
```

### 方式 2：使用高级 API（推荐）

```python
from bridge_api import AgentBridge

bridge = AgentBridge(source_agent="main")

# 快速测试通信
is_ok = await bridge.ping("su-er")

# 发送通知（不等待回复）
await bridge.notify("su-er", "有新任务")

# 提问并等待回复
reply = await bridge.ask("su-er", "当前任务进度如何？")

# 开始多轮对话
thread = await bridge.start_conversation("su-er", max_turns=5)
await bridge.continue_conversation(thread.thread_id, "第一个问题")
await bridge.continue_conversation(thread.thread_id, "第二个问题")
await bridge.end_conversation(thread.thread_id)
```

---

## 🔧 核心工具说明

### sessions_send

**用途**：发送消息到另一个 Agent

**参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `sessionKey` | string | 目标会话键，格式 `agent:<agentId>:main` |
| `message` | string | 消息内容 |
| `timeoutSeconds` | number | 超时时间（秒），0 表示即发即弃 |

**返回**：
```json
{
  "runId": "xxx",
  "status": "ok",
  "reply": "回复内容",
  "sessionKey": "agent:su-er:main",
  "delivery": { "status": "pending" }
}
```

### sessions_history

**用途**：获取会话历史

**参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `sessionKey` | string | 会话键 |
| `limit` | number | 限制条数（默认 50） |
| `includeTools` | boolean | 是否包含工具调用 |

### sessions_list

**用途**：列出活跃会话

**参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `activeMinutes` | number | 活跃时间范围（分钟） |
| `kinds` | array | 会话类型过滤 |

---

## 📋 常用场景示例

### 场景 1：任务交接

```python
# 小千将任务交接给素儿
await bridge.notify("su-er", """
📋 任务交接

任务 ID: TASK-2026-0323-001
任务类型：创建新用户 Agent
优先级：高

请确认接收并安排执行计划。
""")
```

### 场景 2：信息查询

```python
# 询问素儿的任务状态
status = await bridge.ask("su-er", "请汇报当前进行中的任务状态")
print(f"素儿回复：{status}")
```

### 场景 3：多轮协作

```python
# 开始多轮对话
thread = await bridge.start_conversation("su-er")

# 第一轮
turn1 = await bridge.continue_conversation(
    thread.thread_id, 
    "有个新用户需要创建 Agent，请提供配置建议"
)

# 第二轮
turn2 = await bridge.continue_conversation(
    thread.thread_id,
    "好的，请按照标准流程执行"
)

# 结束对话
await bridge.end_conversation(thread.thread_id, reason="任务已确认")
```

### 场景 4：批量通知

```python
# 广播消息到多个 Agent
targets = ["su-er", "agent-3", "agent-4"]
results = await bridge.broadcast(targets, "系统将在 10 分钟后维护")

for agent, result in results.items():
    print(f"{agent}: {'✅' if result.status == 'ok' else '❌'}")
```

---

## ⚠️ 错误处理

### 错误类型

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| `AGENT_NOT_FOUND` | 目标 Agent 不存在 | 检查 Agent ID 是否正确 |
| `PERMISSION_DENIED` | 没有通信权限 | 检查白名单配置 |
| `SESSION_NOT_FOUND` | 会话不存在 | 目标 Agent 可能未激活 |
| `TIMEOUT` | 等待回复超时 | 增加超时时间或重试 |
| `NETWORK_ERROR` | 网络错误 | 检查 Gateway 状态 |

### 错误处理示例

```python
from bridge_core import BridgeError, BridgeErrorCode

try:
    reply = await bridge.ask("su-er", "你好")
except BridgeError as e:
    if e.code == BridgeErrorCode.TIMEOUT:
        print("等待超时，请稍后重试")
    elif e.code == BridgeErrorCode.PERMISSION_DENIED:
        print("没有通信权限，请检查配置")
    else:
        print(f"发送失败：{e.message}")
```

---

## 🔧 故障排查

### 问题 1：消息发送失败

**错误**: "agentToAgent is not enabled"

**解决**:
```json
// openclaw.json
{
  "tools": {
    "agentToAgent": {
      "enabled": true  // 确保启用
    }
  }
}
```

### 问题 2：权限被拒绝

**错误**: "Agent 'xxx' is not in allowlist"

**解决**:
```json
{
  "tools": {
    "agentToAgent": {
      "allow": ["main", "su-er", "你的目标Agent"]
    }
  }
}
```

### 问题 3：找不到会话

**错误**: "Session not found: agent:xxx:main"

**解决**:
1. 检查目标 Agent 是否存在：`openclaw agents list --all-agents`
2. 确保目标 Agent 已激活（至少接收过一条消息）
3. 确认 bindings 配置正确

### 问题 4：ping-pong 无限循环

**解决**:
```python
# 在任意一轮回复 REPLY_SKIP 结束对话
await bridge.notify(target_agent, "REPLY_SKIP")
```

---

## 📚 相关文档

| 文档 | 位置 |
|------|------|
| OpenClaw 官方文档 - Session Tools | https://docs.openclaw.ai/concepts/session-tool |
| OpenClaw 官方文档 - Multi-Agent Routing | https://docs.openclaw.ai/concepts/multi-agent |
| 本技能设计文档 | skills/agent-bridge/DESIGN.md |
| 错误处理指南 | skills/agent-bridge/docs/ERROR_HANDLING.md |

---

## 📝 更新日志

### v2.0 (2026-03-23)
- ✅ 新增 bridge_core.py 核心工具调用层
- ✅ 新增 bridge_api.py 高级 API 层
- ✅ 新增 message_tracker.py 消息追踪器
- ✅ 重构 conversation_manager.py 与 sessions_* 工具集成
- ✅ 完整的错误处理和重试机制
- ✅ 支持批量操作（broadcast, batch_ask）

### v1.0 (2026-03-17)
- ✅ 初始版本
- ✅ 基础 CLI 工具
- ✅ 配置检查功能

---

*技能版本：v2.0*  
*最后更新：2026-03-23*  
*维护者：小千 👡*  
*基于：OpenClaw Gateway sessions_* 工具集*
