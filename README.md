# Agent Bridge

OpenClaw 多 Agent 正式通信技能。

`agent-bridge` 用于在 **独立 Agent** 之间建立正式、双向、可追溯的通信链路。它不是 sub-agent 的临时任务分身方案，而是面向长期协作、任务交接、状态同步与多轮会话管理的通信层。

## 适用场景

- 主 Agent 与专职 Agent 的正式协作
- 多 Agent 团队中的任务交接与状态汇报
- 跨会话的长期对话线程管理
- 需要保留通信历史、上下文与可追溯性的场景

## 核心特性

- 基于 OpenClaw 原生 `sessions_*` 工具集
- 支持 `send / ask / notify / broadcast`
- 支持多轮对话与线程管理
- 完整错误处理与指数退避重试
- 消息状态追踪（pending / delivered / replied / timeout）
- 适用于双 Agent 也适用于未来 3+ Agent 协作扩展

## 项目结构

```text
agent-bridge/
├── SKILL.md
├── README.md
├── DESIGN.md
├── LICENSE
├── docs/
│   ├── QUICKSTART.md
│   └── AGENT-INSTALL.md
├── examples/
│   ├── basic_send.py
│   └── multi_turn_conv.py
└── scripts/
    ├── agent_bridge.py
    ├── bridge_api.py
    ├── bridge_core.py
    ├── conversation_manager.py
    └── message_tracker.py
```

## 快速开始

### 1. 前置配置

确保 `openclaw.json` 中启用了 Agent 间通信：

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

### 2. 基础调用

```python
from bridge_api import AgentBridge

bridge = AgentBridge(source_agent="main")
reply = await bridge.ask("su-er", "当前状态如何？")
print(reply)
```

### 3. 多轮对话

```python
thread = await bridge.start_conversation("su-er", max_turns=5)
await bridge.continue_conversation(thread.thread_id, "你好，素儿")
await bridge.continue_conversation(thread.thread_id, "请汇报当前任务")
await bridge.end_conversation(thread.thread_id)
```

## 文档

- 技能规范说明：[`SKILL.md`](./SKILL.md)
- 快速上手：[`docs/QUICKSTART.md`](./docs/QUICKSTART.md)
- Agent 专用安装说明：[`docs/AGENT-INSTALL.md`](./docs/AGENT-INSTALL.md)
- 设计文档：[`DESIGN.md`](./DESIGN.md)

## 注意事项

### 1. 这不是 Sub-agent 替代品

如果你的需求是“临时委派一个分身做脏活累活”，请使用 `sessions_spawn`。  
如果你的需求是“让两个独立 Agent 正式对话并留痕”，才使用 `agent-bridge`。

### 2. 必须启用白名单

没有加入 `tools.agentToAgent.allow` 的 Agent，无法进行通信。

### 3. 会话可见性需要放开

建议配置：

```json
{
  "tools": {
    "sessions": {
      "visibility": "all"
    }
  }
}
```

否则你可能无法正常查看跨 Agent 会话历史。

### 4. 注意结束 ping-pong

多轮对话结束时，建议显式发送 `REPLY_SKIP` 或主动关闭线程，避免不必要的往返回复。

### 5. 这是 OpenClaw 技能，不是通用 Python 库

`scripts/` 中的代码虽然是 Python，但它的核心价值依赖 OpenClaw 的 `sessions_send / sessions_history / sessions_list` 环境。脱离 OpenClaw，功能会退化为说明模式或无法真正通信。

## 版本

### v2.0.0

- 新增 `bridge_core.py`
- 新增 `bridge_api.py`
- 新增 `message_tracker.py`
- 重构 `conversation_manager.py`
- 增强错误处理、重试机制、消息状态管理
- 补充示例与文档

## License

MIT-0. See [`LICENSE`](./LICENSE).
