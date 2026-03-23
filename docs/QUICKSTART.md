# Agent Bridge 快速使用指南

> 📖 **适用对象**: OpenClaw 用户、多 Agent 协作者  
> ⏱️ **阅读时间**: 5 分钟  
> 🎯 **目标**: 快速上手 Agent 间通信功能

---

## 🚀 5 分钟快速开始

### Step 1: 确认配置（1 分钟）

运行以下命令检查配置是否正确：

```bash
py skills/agent-bridge/scripts/agent_bridge.py config
```

**预期输出**:
```
⚙️  Agent 间通信配置
==================================================

启用状态：✅ 已启用
通信白名单：main, su-er
会话可见性：all
```

如果显示 `❌ 未启用`，需要修改 `~/.openclaw/openclaw.json`：

```json5
{
  "tools": {
    "agentToAgent": {
      "enabled": true,
      "allow": ["main", "su-er"]
    }
  }
}
```

然后重启网关：`openclaw gateway restart`

---

### Step 2: 查看可用 Agent（30 秒）

```bash
py skills/agent-bridge/scripts/agent_bridge.py list
```

**预期输出**:
```
📡 可用 Agent 列表：

Agent ID     名称              工作区                                      通信权限  
--------------------------------------------------------------------------------
main         👡 千残狎           ~/.openclaw/workspace-main               ✅        
su-er        🐙 素儿            ...\.openclaw\workspace-su-er            ✅        
```

---

### Step 3: 发送第一条消息（2 分钟）

#### 方式 A：使用命令行工具

```bash
# 即发即弃
py skills/agent-bridge/scripts/agent_bridge.py send su-er "你好，素儿！"

# 等待回复
py skills/agent-bridge/scripts/agent_bridge.py send su-er "你好，素儿！" --wait
```

#### 方式 B：在 OpenClaw 中直接调用工具

```python
# 在 OpenClaw 会话中执行
sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": "你好，素儿！测试 Agent 间通信",
    "timeoutSeconds": 30
})
```

**预期结果**:
```
✅ 收到回复：收到，小千！通信测试成功~
```

---

### Step 4: 查看通信历史（1 分钟）

```bash
py skills/agent-bridge/scripts/agent_bridge.py history su-er
```

**输出示例**:
```
📜 与 su-er 的通信历史
==================================================
会话键：agent:su-er:main
限制条数：20

📋 调用方式：

    sessions_history({
        "sessionKey": "agent:su-er:main",
        "limit": 20,
        "includeTools": false
    })
```

---

## 📋 常用场景速查

### 场景 1：任务委派

```python
sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": """
📋 任务委派

任务：创建财务小助手 Agent
优先级：高
截止：明天

请确认接收并安排执行计划。
""",
    "timeoutSeconds": 60
})
```

---

### 场景 2：多轮对话

```python
# 第 1 轮
turn1 = sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": "你好，素儿，有个问题想请教",
    "timeoutSeconds": 30
})

# 第 2 轮（基于回复继续）
turn2 = sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": f"明白了，{turn1.get('reply')}。那具体应该怎么做？",
    "timeoutSeconds": 30
})

# 结束对话
sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": "好的，我明白了！感谢解答~ REPLY_SKIP",
    "timeoutSeconds": 0
})
```

---

### 场景 3：状态查询

```python
# 查询素儿的当前任务状态
status = sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": "请汇报当前进行中的任务状态",
    "timeoutSeconds": 30
})
```

---

### 场景 4：协作决策

```python
# 发起决策讨论
decision = sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": """
🗳️ 决策请求

议题：是否为新人 Agent 配置 Docker 沙箱？

选项 A：配置沙箱（更安全，资源消耗大）
选项 B：不配置沙箱（性能好，风险高）

请给出你的建议。
""",
    "timeoutSeconds": 60
})
```

---

## ⚠️ 常见问题

### Q1: 消息发送失败，提示 "agentToAgent is not enabled"

**解决**:
```json5
// openclaw.json
{
  "tools": {
    "agentToAgent": {
      "enabled": true  // 确保启用
    }
  }
}
```
然后重启网关。

---

### Q2: 提示 "Agent 'xxx' is not in allowlist"

**解决**:
```json5
{
  "tools": {
    "agentToAgent": {
      "allow": ["main", "su-er", "目标 Agent"]  // 添加目标 Agent
    }
  }
}
```

---

### Q3: 等待回复超时

**可能原因**:
- 目标 Agent 未激活（至少接收过一条消息）
- 目标 Agent 的 bindings 配置不正确
- 网络问题

**解决**:
1. 检查目标 Agent 是否存在：`openclaw agents list`
2. 检查 bindings 配置
3. 增加超时时间：`timeoutSeconds: 60`

---

### Q4: 如何结束多轮对话？

**方法**: 回复特殊标记 `REPLY_SKIP`

```python
sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": "好的，我明白了！REPLY_SKIP",  # 添加 REPLY_SKIP
    "timeoutSeconds": 0
})
```

---

## 📚 进阶学习

| 主题 | 文档 |
|------|------|
| 完整技能说明 | [SKILL.md](../SKILL.md) |
| 设计文档 | [DESIGN.md](../DESIGN.md) |
| 基础发送示例 | [examples/basic_send.py](../examples/basic_send.py) |
| 多轮对话示例 | [examples/multi_turn_conv.py](../examples/multi_turn_conv.py) |
| 对话管理器 | [scripts/conversation_manager.py](../scripts/conversation_manager.py) |

---

## 💡 最佳实践

1. **明确消息目的** - 在消息开头说明意图（通知/询问/委派）
2. **结构化内容** - 使用标题、列表等格式化长消息
3. **设置合理超时** - 简单消息 30 秒，复杂任务 60 秒+
4. **及时结束对话** - 使用 `REPLY_SKIP` 避免无限 ping-pong
5. **定期审查历史** - 使用 `history` 命令查看通信记录

---

*最后更新：2026-03-17*  
*维护者：小千 👡*
