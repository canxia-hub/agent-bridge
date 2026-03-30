---
name: agent-bridge
description: "OpenClaw 多 Agent 间正式通信技能。提供通信纪律指导、身份识别协议、对话控制规范。技能只提供指导，Agent 使用 OpenClaw 内置工具执行通信。"
version: "4.1"
---

# Agent Bridge - 多 Agent 间通信技能

> 💡 **技能版本**: v4.1  
> 📅 **更新时间**: 2026-03-31  
> 👤 **维护者**: 小千 👡  
> 🎯 **核心原则**: 技能只提供指导，Agent 使用 OpenClaw 内置工具执行通信

---

## 🔒 前置规则：AGENTS.md 必备通信规范

**重要**：本技能要求在 AGENTS.md 中写入以下精简通信规范，确保 Agent 每次启动时自动加载核心规则。

### 标准模板（必须写入 AGENTS.md）

将以下精简内容添加到 AGENTS.md：

```xml
<agent_communication_discipline>
  <purpose>Agent 间通信核心纪律 — 详细规则见 agent-bridge 技能</purpose>
  
  <basic_rules>
    <rule>用户消息用 message 工具回复，Agent 消息用 sessions_send 回复，绝不混淆。</rule>
    <rule>sessionKey 格式：agent:&lt;id&gt;:main，禁止用 label 寻址。</rule>
    <rule>多轮对话最多 5 轮，发起方负责发送 [END] 结束。</rule>
    <rule>每次发送/回复消息只能执行一次 sessions_send，禁止重复发送。</rule>
    <rule>收到消息后，只调用一次 sessions_send 回复，禁止重试。</rule>
    <rule>禁止在 thinking 中"调试"通信问题后重复发送。</rule>
  </basic_rules>
  
  <communication_flow>
    发送消息时携带消息头：
    [MSG_ID:msg:&lt;sender&gt;:&lt;timestamp&gt;:&lt;random&gt;]
    [FROM:AGENT:&lt;sender&gt;]
    [TO:AGENT:&lt;receiver&gt;]
    [TASK_TYPE:NOTIFY|QUERY|DELEGATE|COLLABORATE]
    
    收到消息时：验证 FROM 与来源一致 → 检查 MSG_ID 是否重复 → 处理消息 → 发送一次回复（只一次）。
  </communication_flow>
  
  <silent_wait>
    DELEGATE 类型：timeoutSeconds=0，发送后静默等待。
    接收方：处理完成后必须主动回复，携带 [TASK_STATUS] 和 [TASK_RESULT]。
    发送方：维护 pending_tasks 列表，超时未收到回复则通知用户。
  </silent_wait>
  
  <timeout_reference>
    NOTIFY=0（即发即弃）
    QUERY=30（等待回复）
    DELEGATE=0（静默等待，对方主动回复）
    COLLABORATE=60（多轮对话）
  </timeout_reference>
</agent_communication_discipline>
```

**设计原则**：AGENTS.md 只包含核心纪律骨架，详细规则（熔断保护、幂等性、错误处理等）由本技能提供指导。

### 实施步骤

1. **检查 AGENTS.md**：确认是否存在 `<agent_communication_discipline>` 章节
2. **添加或更新**：将上述模板写入 AGENTS.md
3. **位置建议**：放在 `<agent_communication_guide>` 章节之后
4. **所有 Agent**：确保每个独立 Agent 的 AGENTS.md 都包含此规范

---

## 📢 群发消息指导

### 群发场景

当需要向多个 Agent 同时发送消息时（如广播通知、任务分配），必须遵循以下规则：

### 规则 1：禁止并行发送

**问题**：并行向多个 Agent 发送消息会导致响应超时，因为每个 Agent 处理时间不同。

**错误做法**：
```python
# ❌ 错误：并行发送，会导致超时
for agent in ["su-er", "tuan", "intel-analyst"]:
    sessions_send({
        "sessionKey": f"agent:{agent}:main",
        "message": "...",
        "timeoutSeconds": 30
    })  # 累计等待时间可能超过 90 秒
```

**正确做法**：串行发送，使用 NOTIFY 类型（timeoutSeconds=0）
```python
# ✅ 正确：串行发送，即发即弃
for agent in ["su-er", "tuan", "intel-analyst"]:
    sessions_send({
        "sessionKey": f"agent:{agent}:main",
        "message": "[TASK_TYPE:NOTIFY]\n...",
        "timeoutSeconds": 0  # 即发即弃，不等待回复
    })
```

### 规则 2：群发使用 NOTIFY 类型

群发消息应使用 `TASK_TYPE:NOTIFY`，`timeoutSeconds=0`：

```
特点：
- 即发即弃，不等待回复
- 发送后立即继续处理其他任务
- 避免累积超时

接收方行为：
- 收到后处理消息
- 如需回复，主动使用 sessions_send 回复
- 回复时携带 [TASK_TYPE:NOTIFY] 和 [TASK_STATUS]
```

### 规则 3：静默等待机制

**场景**：发送 DELEGATE 类型任务后，需要等待结果。

**发送方规则**：
```python
# 发送 DELEGATE 任务
sessions_send({
    "sessionKey": "agent:tuan:main",
    "message": "[TASK_TYPE:DELEGATE]\n...",
    "timeoutSeconds": 0  # 静默等待，不在此处阻塞
})

# 发送后：
# 1. 记录到 pending_tasks 列表
# 2. 继续处理其他事务
# 3. 不轮询、不重复发送
# 4. 等待接收方主动回复
```

**接收方规则**：
```python
# 处理完成后主动回复
sessions_send({
    "sessionKey": "agent:main:main",
    "message": """[TASK_TYPE:NOTIFY]
[TASK_ID:原任务ID]
[TASK_STATUS:COMPLETED]
[TASK_RESULT:SUCCESS]
---
任务已完成，结果：...""",
    "timeoutSeconds": 0
})
```

### 规则 4：禁止的行为

| 禁止行为 | 原因 | 正确做法 |
|---|---|---|
| 群发时使用 timeoutSeconds > 0 | 累积超时 | 使用 timeoutSeconds=0 |
| 发送后立即轮询检查 | 浪费资源 | 静默等待对方主动回复 |
| 超时后立即重发 | 可能造成重复处理 | 记录 pending，等待对方回复 |
| 同一任务多次发送 | 消息堆积 | 每个任务只发送一次 |
| 并行向多 Agent 发送 | 响应不可控 | 串行发送或使用 NOTIFY |

### 规则 5：超时处理

**如果发送方超时未收到回复**：

1. **检查 pending_tasks**：确认任务是否已记录
2. **不要立即重发**：接收方可能仍在处理
3. **等待合理时间**：根据任务复杂度设置等待时间
4. **主动询问**：超过预期时间后，发送 QUERY 类型询问状态
5. **上报用户**：如果多次询问无响应，通知用户

```python
# 超时处理流程
def handle_timeout(task_id, target_agent):
    # 1. 检查是否在 pending_tasks 中
    if task_id not in pending_tasks:
        return  # 任务可能已完成，忽略
    
    # 2. 不要重发，而是询问状态
    sessions_send({
        "sessionKey": f"agent:{target_agent}:main",
        "message": f"[TASK_TYPE:QUERY]\n询问任务 {task_id} 的处理状态",
        "timeoutSeconds": 30
    })
    
    # 3. 如果再次超时，通知用户
    # ...
```

### 群发消息模板

```
[MSG_ID:msg:main:20260330T210000:bcast001]
[FROM:AGENT:main]
[TO:AGENT:{receiver}]
[TASK_TYPE:NOTIFY]
[TIMESTAMP:2026-03-30T21:00:00+08:00]
[BROADCAST:true]
---
【群发通知】

通知内容...

（此消息为群发，无需回复确认）
```

---

## ⚠️ 核心原则

**本技能不包含任何实际调用工具的代码。**

本技能提供：
- ✅ 通信纪律规范
- ✅ 身份识别协议
- ✅ 对话控制规则
- ✅ 消息格式模板
- ✅ 错误处理指导

Agent 应使用 OpenClaw 内置工具执行通信：
- `sessions_send` - 发送消息
- `sessions_history` - 查询历史
- `sessions_list` - 列出会话

---

## 🔇 静默规则：什么时候不要发送消息

> ⚠️ **重要**：不发送消息和发送消息一样重要。错误的回复可能造成死循环。

### 规则 1：任务完成后保持静默

**场景**：任务已明确完成，收到确认消息后。

**行为**：保持静默，不再回复。

```
❌ 错误做法：
收到：[TASK_STATUS:COMPLETED]
回复：收到完成确认！  ← 不必要

✅ 正确做法：
收到：[TASK_STATUS:COMPLETED]
行为：静默，不回复
```

**原因**：
- 任务已闭环，回复会开启新循环
- 对方收到确认后也会回复 → 死循环

### 规则 2：收到重复消息保持静默

**场景**：收到的消息 MSG_ID 已在缓存中（5 分钟内处理过）。

**行为**：静默拒绝，不回复。

```
❌ 错误做法：
收到重复 MSG_ID → 回复"已处理过"  ← 会触发对方回复

✅ 正确做法：
收到重复 MSG_ID → 静默跳过，不回复
```

**判断方法**：
1. 检查 MSG_ID 是否在 `processed_msg_ids` 缓存中
2. 检查消息时间戳是否在合理窗口内
3. 检查是否是队列中的历史消息（已处理过的任务）

### 规则 3：确认类消息不回复

**场景**：收到纯粹的确认消息（ACK、已完成通知等）。

**行为**：静默，除非需要继续推进任务。

```
需要静默的消息类型：
- [TASK_STATUS:COMPLETED] + 无后续动作
- [TASK_STATUS:ACK_RECEIVED]
- [TASK_RESULT:已交付]
- 纯通知类消息（无问题、无请求）
```

```
❌ 错误做法：
收到：任务已完成！
回复：好的收到！  ← 不必要

✅ 正确做法：
收到：任务已完成！
行为：静默，记录到日志
```

### 规则 4：检测死循环并熔断

**场景**：短时间内收到同一 Agent 多条相似消息。

**行为**：停止回复，上报用户。

```
死循环信号：
- 同一 MSG_ID 重复出现
- 同一任务多次确认
- 短时间内收到 3+ 条相似内容消息

熔断行为：
1. 停止回复
2. 记录异常到日志
3. 必要时通知用户
```

### 规则 5：用户明确要求静默

**场景**：用户明确指示"不要回复其他消息"。

**行为**：严格遵守，忽略所有 Agent 消息。

```
用户指令示例：
- "不要再回复了"
- "忽略其他消息"
- "完成后不要回复"

执行：
- 不回复任何 Agent 消息
- 继续处理用户的新指令
```

### 静默规则速查表

| 场景 | 行为 | 原因 |
|------|------|------|
| 任务已完成确认 | 🔇 静默 | 避免开启新循环 |
| 重复 MSG_ID | 🔇 静默 | 已处理，回复会死循环 |
| 纯 ACK 消息 | 🔇 静默 | 无需继续对话 |
| 收到 [END] 标记 | 🔇 静默 | 对话已结束 |
| 历史队列消息 | 🔇 静默 | 任务已归档 |
| 用户要求静默 | 🔇 静默 | 用户指令优先 |
| 需要推进任务 | ✅ 回复 | 继续工作流 |
| 收到新任务 | ✅ 回复 | 开始处理 |
| 收到问题 | ✅ 回复 | 提供答案 |

### 实现示例

```python
# 消息处理逻辑
def handle_inter_session_message(msg):
    msg_id = extract_msg_id(msg)
    
    # 1. 检查是否是重复消息
    if msg_id in processed_msg_ids:
        return  # 静默跳过，不回复
    
    # 2. 检查是否是任务完成确认
    if is_task_completion_ack(msg):
        log(f"任务完成: {msg_id}")
        return  # 静默，不回复
    
    # 3. 检查是否是历史队列消息
    if is_stale_message(msg):
        return  # 静默跳过
    
    # 4. 检查用户是否要求静默
    if user_requested_silence:
        return  # 遵守用户指令
    
    # 5. 检查是否需要回复
    if requires_response(msg):
        # 只发送一次回复
        send_single_response(msg)
    
    # 记录已处理
    processed_msg_ids.add(msg_id)
```

---

## 🎯 七大通信挑战与解决方案

### 1. 身份清晰问题

**问题**：Agent 间收发身份信息不清晰，容易混淆。

**解决方案**：标准化消息头协议

```
所有 Agent 间消息必须携带消息头：

[MSG_ID:msg:main:20260330T120000:abc123]
[FROM:AGENT:main]
[TO:AGENT:su-er]
[TASK_TYPE:DELEGATE]
[TIMESTAMP:2026-03-30T12:00:00+08:00]
---
<消息正文>
```

### 2. 身份验证问题

**问题**：如何确保 Agent 准确识别对方身份，防止伪造。

**解决方案**：身份注册表 + 身份验证协议

```
1. 身份注册表：agents/INDEX.md 作为权威来源
2. 接收消息时验证 FROM 与 sessionKey 来源一致
3. sessionKey 格式由 Gateway 控制，不可伪造
```

### 3. 用户 Agent 混淆问题

**问题**：Agent 可能混淆用户身份与 Agent 身份。

**解决方案**：身份类型区分 + 渠道隔离

| 身份类型 | 标识格式 | 回复渠道 |
|---|---|---|
| 用户 | `feishu:user:ou_xxx` | `message` 工具 |
| Agent | `agent:su-er:main` | `sessions_send` 工具 |

**铁律**：
- 用户消息 → 通过原渠道回复（message 工具）
- Agent 消息 → 通过 sessions_send 回复
- **永远不要把 Agent 消息回复给用户渠道**
- **永远不要把用户消息回复给 Agent 渠道**

### 4. 对话死循环问题

**问题**：Agent 互相对话陷入无限循环。

**解决方案**：轮次限制 + 结束标记

```yaml
对话限制：
  max_turns: 5          # 最大轮次
  turn_timeout: 60      # 单轮超时（秒）
  total_timeout: 300    # 总超时（秒）

结束标记：
  [END] - 正常结束
  [TIMEOUT] - 超时结束
  [ERROR] - 错误结束
```

**责任分配**：
- 发起方：监控轮次，在接近上限时主动发送 [END]
- 响应方：收到 [END] 后停止发送

### 5. 消息堆积问题

**问题**：Agent 重复发送消息导致大量消息堆积。

**解决方案**：消息 ID + 去重机制

```
消息 ID 格式：msg:<agentId>:<timestamp>:<random>
示例：msg:main:20260330T120000:abc123

去重规则：
- 维护已处理消息 ID 缓存
- 缓存窗口：5 分钟
- 收到重复 ID 时跳过处理

重试限制：
- NOTIFY 类型：不重试
- 其他类型：最多重试 2 次
```

### 6. 静默等待问题

**问题**：复杂任务需要发送方静默等待，接收方主动回复。

**解决方案**：任务类型驱动 + 等待协议

| 任务类型 | timeoutSeconds | 发送方行为 | 接收方行为 |
|---|---|---|---|
| `NOTIFY` | 0 | 即发即弃 | 收到即结束 |
| `QUERY` | 30 | 等待回复 | 回复后结束 |
| `DELEGATE` | 0 | **静默等待** | **完成后主动回复** |
| `COLLABORATE` | 60 | 多轮等待 | 每轮回复 |

**DELEGATE 类型流程**：
```
1. 发送方：timeoutSeconds=0，发送后继续处理其他事情
2. 发送方：记录到 pending_tasks 列表
3. 接收方：收到后确认
4. 接收方：处理完成后主动 sessions_send 回复
5. 发送方：收到回复，从 pending_tasks 移除
```

### 7. 异常 Agent 问题

**问题**：某 Agent 频繁出错重复发送消息。

**解决方案**：熔断器 + 用户告警

```yaml
熔断器配置：
  failure_threshold: 3      # 连续 3 次失败触发
  open_timeout: 300         # 熔断 5 分钟
  auto_recover: true        # 自动恢复

熔断响应：
  - 拒绝回复
  - 返回 [CIRCUIT_BREAKER:OPEN]
  - 向用户发送告警
```

---

## 📋 消息格式模板

### 通知消息（NOTIFY）

```
[MSG_ID:{msg_id}]
[FROM:AGENT:{sender}]
[TO:AGENT:{receiver}]
[TASK_TYPE:NOTIFY]
[TIMESTAMP:{timestamp}]
---
{content}
```

**使用场景**：单向通知，无需回复
**timeoutSeconds**：0

### 问答消息（QUERY）

```
[MSG_ID:{msg_id}]
[FROM:AGENT:{sender}]
[TO:AGENT:{receiver}]
[TASK_TYPE:QUERY]
[TIMESTAMP:{timestamp}]
[EXPIRES:{expires}]
---
{question}
```

**使用场景**：简单问答，等待回复
**timeoutSeconds**：30

### 任务委派消息（DELEGATE）

```
[MSG_ID:{msg_id}]
[FROM:AGENT:{sender}]
[TO:AGENT:{receiver}]
[TASK_TYPE:DELEGATE]
[TASK_ID:{task_id}]
[TIMESTAMP:{timestamp}]
[EXPIRES:{expires}]
---
任务描述：{description}

期望结果：{expected_result}

截止时间：{deadline}
```

**使用场景**：委派任务，静默等待结果
**timeoutSeconds**：0（发送后静默等待）
**接收方必须**：完成后主动回复

### 协作消息（COLLABORATE）

```
[MSG_ID:{msg_id}]
[FROM:AGENT:{sender}]
[TO:AGENT:{receiver}]
[TASK_TYPE:COLLABORATE]
[TASK_ID:{task_id}]
[TIMESTAMP:{timestamp}]
[TURN:{current_turn}/{max_turns}]
---
{content}
```

**使用场景**：多轮协作对话
**timeoutSeconds**：60
**max_turns**：5

### 任务结果消息

```
[MSG_ID:{msg_id}]
[FROM:AGENT:{sender}]
[TO:AGENT:{receiver}]
[TASK_TYPE:NOTIFY]
[TASK_ID:{original_task_id}]
[TASK_STATUS:COMPLETED]
[TASK_RESULT:SUCCESS]
[TIMESTAMP:{timestamp}]
---
任务结果：{result}

详细说明：{details}
```

**使用场景**：DELEGATE 任务完成后回复

---

## 🔧 工具使用指导

### sessions_send 正确用法

```python
# ✅ 正确：使用完整 sessionKey
sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": "...",
    "timeoutSeconds": 30
})

# ❌ 错误：使用 label 参数
sessions_send({
    "label": "su-er",  # label 不是用于 Agent 寻址！
    "message": "..."
})

# ❌ 错误：格式不完整
sessions_send({
    "sessionKey": "su-er",  # 缺少 "agent:" 前缀
    "message": "..."
})
```

### sessionKey 格式规范

```
格式：agent:<agentId>:main

示例：
- agent:main:main      → 小千的主会话
- agent:su-er:main     → 素儿的主会话
- agent:tuan:main      → 湍的主会话
```

### timeoutSeconds 选择指南

| 场景 | 推荐值 | 说明 |
|---|---|---|
| 简单通知 | 0 | 即发即弃 |
| 简单问答 | 30 | 等待回复 |
| 任务委派 | 0 | 静默等待对方主动回复 |
| 复杂协作 | 60-300 | 根据复杂度调整 |

---

## 📊 Agent 目录

| Agent ID | 名称 | 会话键 | 职责 |
|---|---|---|---|
| main | 小千 | `agent:main:main` | 主线程、总协调、最终交付 |
| su-er | 素儿 | `agent:su-er:main` | 人事主管、Agent 创建与管理 |
| tuan | 湍 | `agent:tuan:main` | 多媒体创意总监 |
| intel-analyst | 情报分析师 | `agent:intel-analyst:main` | 情报分析、风险评估 |

**完整目录**：`agents/INDEX.md`

---

## ⚠️ 常见错误

### 错误 1：使用 label 参数

```python
# ❌ 错误
sessions_send({"label": "tuan", "message": "..."})

# ✅ 正确
sessions_send({"sessionKey": "agent:tuan:main", "message": "..."})
```

### 错误 2：混淆用户和 Agent

```python
# ❌ 错误：把 Agent 消息回复给用户渠道
# 收到 agent:su-er:main 的消息
# 却使用 message 工具回复到用户渠道

# ✅ 正确：Agent 消息回复给 Agent 渠道
sessions_send({
    "sessionKey": "agent:su-er:main",
    "message": "..."
})
```

### 错误 3：无限对话

```python
# ❌ 错误：没有轮次限制，无限继续
while True:
    reply = sessions_send({...})
    # 没有结束条件

# ✅ 正确：设置轮次限制
max_turns = 5
for turn in range(max_turns):
    reply = sessions_send({
        "message": f"[TURN:{turn+1}/{max_turns}]\n{content}"
    })
    if should_end(reply):
        sessions_send({"message": "[END]"})
        break
```

### 错误 4：重复发送

```python
# ❌ 错误：没有消息 ID，无法去重
sessions_send({"message": "处理这个任务"})
sessions_send({"message": "处理这个任务"})  # 重复

# ✅ 正确：携带唯一消息 ID
msg_id = "msg:main:20260330T120000:abc123"
sessions_send({
    "message": f"[MSG_ID:{msg_id}]\n处理这个任务"
})
```

---

## 📚 相关文档

| 文档 | 位置 |
|---|---|
| 通信纪律设计 | `docs/agent-bridge-discipline-design-v4-2026-03-30.md` |
| 通信机制研究 | `docs/openclaw-agent-communication-mechanism-research-2026-03-30.md` |
| Agent 目录 | `agents/INDEX.md` |
| 运行契约 | `AGENTS.md` → `agent_communication_discipline` 章节 |

---

## 🧪 自检清单

发送消息前检查：
- [ ] sessionKey 格式正确（`agent:<id>:main`）
- [ ] 消息包含消息头（MSG_ID, FROM, TO, TIMESTAMP）
- [ ] timeoutSeconds 与任务类型匹配
- [ ] 多轮对话设置 TURN 字段

接收消息后检查：
- [ ] 验证 FROM 与来源一致
- [ ] 检查 MSG_ID 是否重复
- [ ] 检查消息是否过期
- [ ] 区分用户和 Agent 身份

---

*技能版本: v4.1*  
*维护者: 小千 👡*  
*更新时间: 2026-03-31*
