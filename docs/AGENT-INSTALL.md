# Agent 专用安装说明

> 面向 **OpenClaw Agent 维护者** 的安装与接入说明。  
> 如果你只是想快速试用，请先看 [`QUICKSTART.md`](./QUICKSTART.md)。

---

## 1. 适用对象

本说明适用于以下场景：

- 你要把 `agent-bridge` 安装到某个 OpenClaw Agent 的工作区
- 你要让两个或多个 Agent 建立正式通信能力
- 你要把它作为团队 Agent 编排中的基础通信层

---

## 2. 安装位置

推荐目录：

```text
<workspace>/skills/agent-bridge/
```

例如：

```text
C:\Users\Administrator\.openclaw\workspace\skills\agent-bridge
```

安装完成后，确保以下关键文件存在：

- `SKILL.md`
- `README.md`
- `DESIGN.md`
- `scripts/bridge_core.py`
- `scripts/bridge_api.py`
- `scripts/conversation_manager.py`
- `scripts/message_tracker.py`

---

## 3. 网关配置要求

你必须在 `openclaw.json` 中启用 Agent 间通信：

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

### 字段说明

#### `tools.agentToAgent.enabled`
- 必须为 `true`
- 否则 `sessions_send` 的 Agent-to-Agent 路由不会生效

#### `tools.agentToAgent.allow`
- 白名单数组
- 只有在这个数组里的 Agent 才能互相通信

#### `tools.sessions.visibility`
- 推荐为 `all`
- 否则调试、查看历史、跨 Agent 检索会比较受限

---

## 4. 绑定建议

如果你的 Agent 还有渠道分流（如 Feishu / Discord / Telegram），建议确保：

- 主 Agent 有清晰的默认绑定
- 被通信 Agent 至少存在 `main` 会话可接收消息
- 不要把所有 Agent 都只绑定到外部渠道，而不保留可用的内部主会话

建议优先使用：

```text
agent:<agentId>:main
```

这是最稳定的通信会话键。

---

## 5. 安装后的验证步骤

### 验证 1：检查配置

```bash
py skills/agent-bridge/scripts/bridge_core.py config
```

### 验证 2：列出 Agent

```bash
py skills/agent-bridge/scripts/bridge_api.py list
```

### 验证 3：通信测试

```python
sessions_send({
  "sessionKey": "agent:su-er:main",
  "message": "【测试】请回复确认收到",
  "timeoutSeconds": 30
})
```

如果收到回复，说明安装成功。

---

## 6. 推荐接入方式

### 方式 A：在 Agent 会话中直接使用原生工具

适合：
- 简单通信
- 临时测试
- 不需要复杂封装时

```python
sessions_send({
  "sessionKey": "agent:su-er:main",
  "message": "请汇报当前状态",
  "timeoutSeconds": 30
})
```

### 方式 B：通过 `bridge_api.py` 二次封装

适合：
- 需要标准化接口
- 需要重试、状态跟踪、多轮线程管理
- 需要作为更高层技能的依赖

```python
from bridge_api import AgentBridge

bridge = AgentBridge(source_agent="main")
reply = await bridge.ask("su-er", "当前状态如何？")
```

---

## 7. 接入其他技能时的建议

如果你要让其他技能依赖 `agent-bridge`：

### 推荐
- 只依赖 `bridge_api.py` 或 `bridge_core.py`
- 把目标 Agent ID 作为显式参数
- 给超时时间设置合理默认值

### 不推荐
- 在多个技能里各自重复实现 sessions_send 封装
- 把 Agent ID 硬编码在多个文件里
- 无上限地递归转发消息

---

## 8. 典型部署模式

### 模式 1：主 Agent + 专职 Agent

- `main`：总协调
- `su-er`：Agent 管理、人事、建档

这是最适合当前 `agent-bridge` 的结构。

### 模式 2：多 Agent 团队

- `main`：协调与收口
- `planner`：规划
- `coder`：开发
- `reviewer`：审查
- `ops`：运维

此时建议所有可通信 Agent 都加入 allowlist，并统一约定消息格式。

---

## 9. 失败排查

### 问题：`AGENT_NOT_FOUND`
- 检查目标 Agent 是否真的存在于配置中
- 检查 sessionKey 是否写错

### 问题：`PERMISSION_DENIED`
- 检查 `tools.agentToAgent.allow`

### 问题：`SESSION_NOT_FOUND`
- 检查目标 Agent 是否已有可用主会话
- 先让目标 Agent 接收一条消息初始化会话

### 问题：看不到历史
- 检查 `tools.sessions.visibility`

### 问题：对话来回循环
- 显式发送 `REPLY_SKIP`
- 或使用对话线程的结束逻辑

---

## 10. 升级建议

从旧版升级到 v2.0 时，重点确认：

- 新增文件已同步
- `SKILL.md` 与 `README.md` 已更新
- 不要继续依赖旧版 `agent_bridge.py` 的“仅打印说明”行为
- 新逻辑应优先使用 `bridge_api.py` / `bridge_core.py`

---

## 11. 适合作为 GitHub 项目发布吗？

适合，但要明确说明：

- 这是 **OpenClaw Skill / OpenClaw 环境扩展项目**
- 不是通用 SDK
- 需要 OpenClaw 的 `sessions_*` 工具环境支持
- 示例代码应被视为“运行在 Agent 环境中的代码”

因此 GitHub 项目页里必须写清楚环境依赖，避免普通 Python 用户误以为 `pip install` 后即可独立运行。
