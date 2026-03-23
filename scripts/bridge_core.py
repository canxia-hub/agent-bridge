#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bridge Core - OpenClaw 多 Agent 通信核心层

职责：
1. 封装 sessions_send/sessions_history/sessions_list 工具调用
2. 提供统一的错误处理和重试机制
3. 管理 Agent 间通信配置

使用方式：
    from bridge_core import BridgeCore, BridgeError
    
    core = BridgeCore()
    result = await core.send("su-er", "你好")
    print(result.reply)

作者：小千 👡
版本：v2.0
日期：2026-03-23
"""

import json
import os
import sys
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

# ============================================================================
# 常量定义
# ============================================================================

STATE_DIR = os.path.expanduser("~/.openclaw")
CONFIG_PATH = os.path.join(STATE_DIR, "openclaw.json")

# 默认配置
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0
DEFAULT_CHECK_INTERVAL = 2.0

# ============================================================================
# 错误类型定义
# ============================================================================

class BridgeErrorCode(Enum):
    """错误代码枚举"""
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class BridgeError(Exception):
    """Agent 间通信错误"""
    
    ERROR_MESSAGES = {
        BridgeErrorCode.AGENT_NOT_FOUND: "目标 Agent 不存在",
        BridgeErrorCode.PERMISSION_DENIED: "没有通信权限",
        BridgeErrorCode.SESSION_NOT_FOUND: "会话不存在",
        BridgeErrorCode.TIMEOUT: "等待回复超时",
        BridgeErrorCode.NETWORK_ERROR: "网络错误",
        BridgeErrorCode.CONFIG_ERROR: "配置错误",
        BridgeErrorCode.UNKNOWN_ERROR: "未知错误",
    }
    
    def __init__(self, code: BridgeErrorCode, message: str = None, details: Dict = None):
        self.code = code
        self.message = message or self.ERROR_MESSAGES.get(code, "未知错误")
        self.details = details or {}
        super().__init__(f"[{code.value}] {self.message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "code": self.code.value,
            "message": self.message,
            "details": self.details
        }

# ============================================================================
# 数据结构定义
# ============================================================================

@dataclass
class SendResult:
    """发送结果"""
    run_id: str
    status: str  # "ok" | "timeout" | "error"
    reply: Optional[str] = None
    session_key: str = ""
    delivery_status: str = "pending"  # "pending" | "delivered" | "failed"
    error: Optional[BridgeError] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SendResult':
        """从字典创建"""
        return cls(
            run_id=data.get("runId", ""),
            status=data.get("status", "error"),
            reply=data.get("reply"),
            session_key=data.get("sessionKey", ""),
            delivery_status=data.get("delivery", {}).get("status", "pending"),
            error=None
        )

@dataclass
class AgentInfo:
    """Agent 信息"""
    id: str
    name: str
    emoji: str
    workspace: str
    model: str
    is_allowed: bool
    is_active: bool = False
    
    @classmethod
    def from_config(cls, agent_config: Dict, is_allowed: bool) -> 'AgentInfo':
        """从配置创建"""
        identity = agent_config.get('identity', {})
        return cls(
            id=agent_config.get('id', 'unknown'),
            name=identity.get('name', agent_config.get('id', 'unknown')),
            emoji=identity.get('emoji', ''),
            workspace=agent_config.get('workspace', ''),
            model=agent_config.get('model', ''),
            is_allowed=is_allowed
        )

@dataclass
class MessageInfo:
    """消息信息"""
    role: str
    content: str
    timestamp: float
    sender: Optional[str] = None
    provenance: Optional[Dict] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MessageInfo':
        """从字典创建"""
        content = ""
        if isinstance(data.get('content'), list):
            for item in data['content']:
                if item.get('type') == 'text':
                    content = item.get('text', '')
                    break
        else:
            content = data.get('content', '')
        
        return cls(
            role=data.get('role', ''),
            content=content,
            timestamp=data.get('timestamp', 0),
            sender=data.get('senderLabel'),
            provenance=data.get('provenance')
        )

# ============================================================================
# 核心通信类
# ============================================================================

class BridgeCore:
    """核心通信类"""
    
    def __init__(self, config_path: str = None):
        """
        初始化核心通信层
        
        Args:
            config_path: openclaw.json 路径，默认 ~/.openclaw/openclaw.json
        """
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        self._validate_config()
        
        # 工具调用钩子（在 OpenClaw 环境中会被设置为实际工具）
        self._sessions_send: Optional[Callable] = None
        self._sessions_history: Optional[Callable] = None
        self._sessions_list: Optional[Callable] = None
    
    def set_tools(self, sessions_send: Callable, sessions_history: Callable, 
                  sessions_list: Callable) -> None:
        """
        设置工具调用函数（由 OpenClaw 环境注入）
        
        Args:
            sessions_send: sessions_send 工具函数
            sessions_history: sessions_history 工具函数
            sessions_list: sessions_list 工具函数
        """
        self._sessions_send = sessions_send
        self._sessions_history = sessions_history
        self._sessions_list = sessions_list
    
    # ========== 配置管理 ==========
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise BridgeError(
                BridgeErrorCode.CONFIG_ERROR,
                f"配置文件不存在：{self.config_path}"
            )
        except json.JSONDecodeError as e:
            raise BridgeError(
                BridgeErrorCode.CONFIG_ERROR,
                f"配置文件解析失败：{e}"
            )
    
    def _validate_config(self) -> None:
        """验证配置"""
        tools = self.config.get('tools', {})
        agent_to_agent = tools.get('agentToAgent', {})
        
        if not agent_to_agent.get('enabled', False):
            raise BridgeError(
                BridgeErrorCode.CONFIG_ERROR,
                "Agent 间通信未启用，请在 openclaw.json 中设置 tools.agentToAgent.enabled = true"
            )
    
    def reload_config(self) -> None:
        """重新加载配置"""
        self.config = self._load_config()
        self._validate_config()
    
    # ========== Agent 发现 ==========
    
    def list_agents(self) -> List[AgentInfo]:
        """列出所有可用 Agent 及其通信权限"""
        agents_config = self.config.get('agents', {}).get('list', [])
        allowed = self.config.get('tools', {}).get('agentToAgent', {}).get('allow', [])
        
        agents = []
        for agent_config in agents_config:
            agent_id = agent_config.get('id', '')
            is_allowed = agent_id in allowed
            agents.append(AgentInfo.from_config(agent_config, is_allowed))
        
        return agents
    
    def get_agent_info(self, agent_id: str) -> Optional[AgentInfo]:
        """获取指定 Agent 信息"""
        agents = self.list_agents()
        for agent in agents:
            if agent.id == agent_id:
                return agent
        return None
    
    def check_permission(self, from_agent: str, to_agent: str) -> bool:
        """检查通信权限"""
        allowed = self.config.get('tools', {}).get('agentToAgent', {}).get('allow', [])
        return from_agent in allowed and to_agent in allowed
    
    def get_allowed_agents(self) -> List[str]:
        """获取允许通信的 Agent 白名单"""
        return self.config.get('tools', {}).get('agentToAgent', {}).get('allow', [])
    
    # ========== 消息发送 ==========
    
    def _build_session_key(self, target_agent: str, session_type: str = "main") -> str:
        """构建会话键"""
        return f"agent:{target_agent}:{session_type}"
    
    async def send(
        self,
        target_agent: str,
        message: str,
        timeout_seconds: int = DEFAULT_TIMEOUT,
        session_key: str = None
    ) -> SendResult:
        """
        发送消息到目标 Agent
        
        Args:
            target_agent: 目标 Agent ID
            message: 消息内容
            timeout_seconds: 超时时间（秒），0 表示即发即弃
            session_key: 自定义会话键，默认使用 main 会话
            
        Returns:
            SendResult: 发送结果
            
        Raises:
            BridgeError: 发送失败时抛出
        """
        # 验证 Agent 存在
        if not self.get_agent_info(target_agent):
            raise BridgeError(
                BridgeErrorCode.AGENT_NOT_FOUND,
                f"Agent '{target_agent}' 不存在",
                {"available_agents": [a.id for a in self.list_agents()]}
            )
        
        # 构建会话键
        if not session_key:
            session_key = self._build_session_key(target_agent)
        
        # 构建调用参数
        params = {
            "sessionKey": session_key,
            "message": message,
            "timeoutSeconds": timeout_seconds
        }
        
        # 调用工具
        try:
            if self._sessions_send:
                # 在 OpenClaw 环境中，使用注入的工具
                result = await self._sessions_send(**params)
            else:
                # CLI 模式：返回调用说明
                result = self._generate_send_instruction(params)
            
            return SendResult.from_dict(result)
            
        except Exception as e:
            if isinstance(e, BridgeError):
                raise
            raise BridgeError(
                BridgeErrorCode.NETWORK_ERROR,
                f"消息发送失败：{str(e)}",
                {"params": params}
            )
    
    def _generate_send_instruction(self, params: Dict) -> Dict:
        """生成调用说明（CLI 模式）"""
        return {
            "runId": "cli-mode",
            "status": "ok",
            "sessionKey": params["sessionKey"],
            "reply": None,
            "delivery": {"status": "pending", "mode": "announce"},
            "_instruction": {
                "tool": "sessions_send",
                "params": params,
                "note": "CLI 模式：请在 OpenClaw 会话中执行此工具调用"
            }
        }
    
    async def send_with_retry(
        self,
        target_agent: str,
        message: str,
        timeout_seconds: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY
    ) -> SendResult:
        """
        带重试的消息发送
        
        Args:
            target_agent: 目标 Agent ID
            message: 消息内容
            timeout_seconds: 超时时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒），指数退避
            
        Returns:
            SendResult: 发送结果
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = await self.send(target_agent, message, timeout_seconds)
                if result.status == "ok":
                    return result
                elif result.status == "timeout":
                    last_error = BridgeError(
                        BridgeErrorCode.TIMEOUT,
                        f"等待回复超时（尝试 {attempt + 1}/{max_retries}）"
                    )
            except BridgeError as e:
                last_error = e
                if e.code in [BridgeErrorCode.AGENT_NOT_FOUND, BridgeErrorCode.PERMISSION_DENIED]:
                    # 这些错误不应重试
                    raise
            
            # 指数退避
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))
        
        raise last_error or BridgeError(BridgeErrorCode.UNKNOWN_ERROR, "发送失败")
    
    # ========== 历史查询 ==========
    
    async def get_history(
        self,
        session_key: str,
        limit: int = 20,
        include_tools: bool = False
    ) -> List[MessageInfo]:
        """
        获取会话历史
        
        Args:
            session_key: 会话键
            limit: 限制条数
            include_tools: 是否包含工具调用
            
        Returns:
            List[MessageInfo]: 消息列表
        """
        params = {
            "sessionKey": session_key,
            "limit": limit,
            "includeTools": include_tools
        }
        
        try:
            if self._sessions_history:
                result = await self._sessions_history(**params)
                messages = result.get("messages", [])
                return [MessageInfo.from_dict(m) for m in messages]
            else:
                # CLI 模式
                return self._generate_history_instruction(params)
                
        except Exception as e:
            raise BridgeError(
                BridgeErrorCode.NETWORK_ERROR,
                f"历史查询失败：{str(e)}"
            )
    
    def _generate_history_instruction(self, params: Dict) -> List[MessageInfo]:
        """生成历史查询说明（CLI 模式）"""
        print(f"📋 调用方式：")
        print(f'sessions_history({json.dumps(params, ensure_ascii=False, indent=2)})')
        return []
    
    # ========== 会话管理 ==========
    
    async def list_sessions(
        self,
        agent_id: str = None,
        active_minutes: int = 60
    ) -> List[Dict]:
        """
        列出活跃会话
        
        Args:
            agent_id: 过滤指定 Agent 的会话
            active_minutes: 活跃时间范围（分钟）
            
        Returns:
            List[Dict]: 会话列表
        """
        params = {
            "activeMinutes": active_minutes
        }
        
        try:
            if self._sessions_list:
                result = await self._sessions_list(**params)
                sessions = result.get("sessions", [])
                
                if agent_id:
                    sessions = [s for s in sessions if agent_id in s.get("key", "")]
                
                return sessions
            else:
                # CLI 模式
                return self._generate_list_instruction(params)
                
        except Exception as e:
            raise BridgeError(
                BridgeErrorCode.NETWORK_ERROR,
                f"会话列表查询失败：{str(e)}"
            )
    
    def _generate_list_instruction(self, params: Dict) -> List[Dict]:
        """生成会话列表查询说明（CLI 模式）"""
        print(f"📋 调用方式：")
        print(f'sessions_list({json.dumps(params, ensure_ascii=False, indent=2)})')
        return []


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    """CLI 测试入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bridge Core - OpenClaw 多 Agent 通信核心层')
    parser.add_argument('command', choices=['list', 'config', 'test'], help='命令')
    parser.add_argument('--target', help='目标 Agent ID')
    parser.add_argument('--message', help='消息内容')
    
    args = parser.parse_args()
    
    try:
        core = BridgeCore()
        
        if args.command == 'list':
            agents = core.list_agents()
            print("\n📡 可用 Agent 列表：\n")
            for agent in agents:
                status = "✅" if agent.is_allowed else "❌"
                print(f"  {status} {agent.emoji} {agent.name} ({agent.id})")
            print()
            
        elif args.command == 'config':
            print("\n⚙️  配置信息：")
            print(f"  配置文件：{core.config_path}")
            print(f"  白名单：{core.get_allowed_agents()}")
            print()
            
        elif args.command == 'test':
            if not args.target:
                print("❌ 请指定 --target 参数")
                sys.exit(1)
            
            print(f"\n🧪 测试发送到 {args.target}...")
            result = core._generate_send_instruction({
                "sessionKey": f"agent:{args.target}:main",
                "message": args.message or "测试消息",
                "timeoutSeconds": 30
            })
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
    except BridgeError as e:
        print(f"\n❌ 错误：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
