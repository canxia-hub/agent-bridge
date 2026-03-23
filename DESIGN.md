# Agent Bridge 技能设计文档

> 💡 **技能名称**: `agent-bridge`  
> 🎯 **核心功能**: 实现 OpenClaw 多 Agent 之间的正式通信  
> 📅 **设计时间**: 2026-03-17  
> 👤 **设计者**: 小千 👡

---

## 🎯 技能定位

本技能封装 OpenClaw Gateway 原生的 `sessions_*` 工具集，提供**正式的、双向的、可追溯的**Agent 间通信能力，区别于 sub-agent 的"临时任务委派"模式。

### 与 Sub-agent 的本质区别

| 维度 | Sub-agent (`sessions_spawn`) | Agent Bridge (`sessions_send`) |
|------|------------------------------|--------------------------------|
| **身份** | 同一 Agent 的临时分身 | 独立 Agent 之间的对话 |
| **会话隔离** | 共享 agentDir、auth、workspace | 完全独立的 workspace、agentDir、session store |
| **通信方向** | 单向（父→子，结果 announce 回） | 双向（支持多轮 ping-pong） |
| **人格** | 同一 SOUL.md | 不同 SOUL.md（独立人格） |
| **使用场景** | 临时任务委派、代码生成 | 长期协作、信息同步、任务交接 |

---

## 🛠️ 核心功能模块

### 模块 1：Agent 发现与状态查询

**功能**: 列出所有可用 Agent 及其运行状态

```typescript
interface AgentDiscovery {
  /** 列出所有已配置的 Agent */
  listAgents(): Promise<AgentInfo[]>;
  
  /** 查询指定 Agent 的活跃会话 */
  getActiveSessions(agentId: string, activeMinutes?: number): Promise<SessionInfo[]>;
  
  /** 检查 Agent 间通信权限 */
  checkCommunicationPermission(fromAgent: string, toAgent: string): Promise<boolean>;
}

interface AgentInfo {
  id: string;
  name: string;
  emoji?: string;
  workspace: string;
  model: string;
  status: 'active' | 'idle' | 'offline';
  lastActiveAt?: string;
}
```

**封装的工具**:
- `sessions_list` - 查询会话列表
- `agents_list` - 查询可用 Agent 列表

---

### 模块 2：消息发送与接收

**功能**: 向指定 Agent 发送消息，支持同步/异步模式

```typescript
interface MessageSender {
  /**
   * 发送消息到另一个 Agent
   * @param targetAgentId 目标 Agent ID
   * @param message 消息内容
   * @param options 发送选项
   */
  send(
    targetAgentId: string,
    message: string,
    options?: SendOptions
  ): Promise<SendResult>;
  
  /**
   * 发送消息并等待回复（支持多轮对话）
   * @param targetAgentId 目标 Agent ID
   * @param message 消息内容
   * @param maxTurns 最大对话轮次（默认 5）
   */
  sendAndWait(
    targetAgentId: string,
    message: string,
    maxTurns?: number,
    timeoutSeconds?: number
  ): Promise<ConversationResult>;
}

interface SendOptions {
  /** 超时时间（秒），0=即发即弃 */
  timeoutSeconds?: number;
  /** 会话键，不指定则使用 targetAgent 的 main session */
  sessionKey?: string;
  /** 是否等待回复 */
  waitForReply?: boolean;
  /** 对话上下文（用于多轮对话） */
  context?: Message[];
}

interface SendResult {
  runId: string;
  status: 'accepted' | 'ok' | 'timeout' | 'error';
  reply?: string;
  error?: string;
}

interface ConversationResult {
  runId: string;
  turns: number;
  messages: Message[];
  status: 'completed' | 'timeout' | 'error';
}
```

**封装的工具**:
- `sessions_send` - 发送消息到另一个会话
- `sessions_history` - 读取对话历史

---

### 模块 3：对话上下文管理

**功能**: 维护 Agent 间对话的上下文，支持多轮交流

```typescript
interface ConversationManager {
  /**
   * 开始一个新的对话线程
   */
  startConversation(targetAgentId: string): Promise<ConversationThread>;
  
  /**
   * 继续现有对话
   */
  continueConversation(threadId: string, message: string): Promise<ConversationTurn>;
  
  /**
   * 结束对话
   */
  endConversation(threadId: string): Promise<void>;
  
  /**
   * 获取对话历史
   */
  getConversationHistory(threadId: string, limit?: number): Promise<Message[]>;
}

interface ConversationThread {
  threadId: string;
  targetAgentId: string;
  createdAt: string;
  lastActivityAt: string;
  turnCount: number;
  status: 'active' | 'closed';
}

interface ConversationTurn {
  turnNumber: number;
  fromAgent: string;
  toAgent: string;
  message: string;
  timestamp: string;
  reply?: string;
}
```

**数据存储**:
- 对话线程元数据存储在 LanceDB（category=entity）
- 对话历史记录存储在 LanceDB（category=reflection）

---

### 模块 4：权限与安全控制

**功能**: 验证 Agent 间通信权限，防止未授权访问

```typescript
interface SecurityPolicy {
  /** 检查发送方是否被允许通信 */
  canSend(fromAgent: string, toAgent: string): Promise<boolean>;
  
  /** 获取 Agent 的通信白名单 */
  getAllowlist(agentId: string): Promise<string[]>;
  
  /** 记录通信日志（用于审计） */
  logCommunication(fromAgent: string, toAgent: string, action: string): Promise<void>;
}
```

**配置依赖**:
```json5
// ~/.openclaw/openclaw.json
{
  "tools": {
    "agentToAgent": {
      "enabled": true,  // 必须启用
      "allow": ["main", "su-er"]  // 白名单
    }
  }
}
```

---

## 📋 技能命令设计

### 命令 1：`/agent-bridge list`
列出所有可用 Agent 及其状态

**输出示例**:
```
📡 可用 Agent 列表：

┌─────────┬──────────┬─────────┬─────────────────────────────┐
│ Agent   │ 状态     │ 最后活跃 │ 工作区                    │
├─────────┼──────────┼─────────┼─────────────────────────────┤
│ main    │ ✅ 活跃  │ 刚刚    │ ~/.openclaw/workspace      │
│ su-er   │ ⏸️ 空闲  │ 2 小时前 │ ~/.openclaw/workspace-su-er│
└─────────┴──────────┴─────────┴─────────────────────────────┘

💡 提示：使用 /agent-bridge send <agent> <消息> 发送消息
```

### 命令 2：`/agent-bridge send <agent-id> <消息>`
向指定 Agent 发送消息

**用法**:
```
/agent-bridge send su-er 你好，素儿，有新任务要协调
/agent-bridge send su-er --wait 你好，请处理一下这个任务
```

**参数**:
- `agent-id` (必填): 目标 Agent ID
- `消息` (必填): 消息内容
- `--wait`: 等待回复（默认等待 30 秒）
- `--timeout <秒数>`: 自定义超时时间

### 命令 3：`/agent-bridge conversation <agent-id>`
开始/继续与指定 Agent 的对话

**用法**:
```
/agent-bridge conversation su-er
```

**交互模式**:
```
🗨️ 与 素儿 的对话已开始（线程：conv_su-er_20260317_1526）

小千 → 素儿：你好，素儿，有个新用户需要创建 Agent
素儿 → 小千：收到，请提供用户信息和 Agent 配置要求

[输入消息继续对话，或输入 /end 结束对话]
```

### 命令 4：`/agent-bridge history <agent-id>`
查看与指定 Agent 的通信历史

**用法**:
```
/agent-bridge history su-er
/agent-bridge history su-er --limit 20
```

### 命令 5：`/agent-bridge config`
查看/修改 Agent 间通信配置

**用法**:
```
/agent-bridge config show
/agent-bridge config set allowlist main,su-er
```

---

## 🔧 技能文件结构

```
skills/agent-bridge/
├── SKILL.md                 # 技能说明文档
├── scripts/
│   ├── agent_bridge.py      # 主脚本（Python 封装）
│   └── conversation_manager.py  # 对话管理器
├── docs/
│   ├── USAGE.md             # 使用指南
│   └── CONFIG.md            # 配置说明
└── examples/
    ├── basic_send.py        # 基础发送示例
    └── multi_turn_conv.py   # 多轮对话示例
```

---

## ⚙️ 所需 Gateway 配置

### 1. 启用 Agent 间通信

```json5
// ~/.openclaw/openclaw.json
{
  "tools": {
    "agentToAgent": {
      "enabled": true,
      "allow": ["main", "su-er"]
    },
    "sessions": {
      "visibility": "agent"  // 允许看到同 Agent 下的所有会话
    }
  }
}
```

### 2. 配置 Bindings（可选，用于飞书路由）

```json5
{
  "bindings": [
    {
      "agentId": "main",
      "match": {
        "channel": "feishu",
        "peer": { "kind": "direct", "id": "ou_天夔訫" }
      }
    },
    {
      "agentId": "su-er",
      "match": {
        "channel": "feishu",
        "peer": { "kind": "group", "id": "oc_Agent 管理群" }
      }
    }
  ]
}
```

---

## 🧪 测试计划

### 测试 1：基础通信
```bash
# 从小千发送消息到素儿
/agent-bridge send su-er 测试消息

# 预期：素儿收到消息并回复
```

### 测试 2：多轮对话
```bash
# 开始对话线程
/agent-bridge conversation su-er

# 预期：可以连续多轮交流，上下文保持
```

### 测试 3：权限验证
```bash
# 尝试从未授权的 Agent 发送
# 预期：被拒绝，返回权限错误
```

---

## 📝 实施步骤

1. ✅ 设计文档确认（当前步骤）
2. ⏳ 创建技能目录结构
3. ⏳ 编写主脚本 `agent_bridge.py`
4. ⏳ 编写对话管理器 `conversation_manager.py`
5. ⏳ 编写 SKILL.md 使用文档
6. ⏳ 配置 Gateway（`tools.agentToAgent.enabled: true`）
7. ⏳ 测试基础通信功能
8. ⏳ 测试多轮对话功能
9. ⏳ 编写示例和文档

---

## ⚠️ 注意事项

1. **必须启用 `tools.agentToAgent.enabled: true`**，否则 sessions_send 会被拦截
2. **必须配置 `allow` 白名单**，明确哪些 Agent 可以互相通信
3. **每个 Agent 需要独立的 auth-profiles.json**，凭证不共享
4. **ping-pong 轮次限制** 默认 5 轮，可在配置中调整
5. **会话可见性** 需要设置为 `agent` 或 `all` 才能跨 Agent 查询

---

*设计文档版本：v1.0*  
*设计者：小千 👡*  
*审核状态：待阿訫确认*
