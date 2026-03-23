#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bridge API - OpenClaw 多 Agent 通信高级 API

职责：
1. 提供简化的 API 接口
2. 封装常用操作模式
3. 提供便捷方法

使用方式：
    from bridge_api import AgentBridge
    
    bridge = AgentBridge()
    
    # 快速测试通信
    is_ok = await bridge.ping("su-er")
    
    # 发送通知
    await bridge.notify("su-er", "有新任务")
    
    # 提问并等待回复
    reply = await bridge.ask("su-er", "当前状态如何？")

作者：小千 👡
版本：v2.0
日期：2026-03-23
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from bridge_core import BridgeCore, BridgeError, BridgeErrorCode, SendResult
from conversation_manager import ConversationManager, ConversationThread, ConversationTurn
from message_tracker import MessageTracker


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class ConversationResult:
    """对话结果"""
    thread_id: str
    target_agent: str
    turn_count: int
    status: str
    messages: List[Dict[str, str]]  # [{role: "user"|"assistant", content: "..."}]
    last_reply: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# 高级 API 入口
# ============================================================================

class AgentBridge:
    """高级 API 入口"""
    
    def __init__(
        self,
        source_agent: str = "main",
        default_timeout: int = 30,
        max_retries: int = 3
    ):
        """
        初始化 Agent Bridge
        
        Args:
            source_agent: 发起方 Agent ID
            default_timeout: 默认超时时间（秒）
            max_retries: 默认重试次数
        """
        self.source_agent = source_agent
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        
        # 核心组件
        self.core = BridgeCore()
        self.tracker = MessageTracker()
        self.conversations = ConversationManager(
            core=self.core,
            tracker=self.tracker,
            default_timeout=default_timeout
        )
    
    def set_tools(self, sessions_send, sessions_history, sessions_list) -> None:
        """
        设置底层工具（由 OpenClaw 环境注入）
        
        Args:
            sessions_send: sessions_send 工具函数
            sessions_history: sessions_history 工具函数
            sessions_list: sessions_list 工具函数
        """
        self.core.set_tools(sessions_send, sessions_history, sessions_list)
    
    # ========== Agent 发现 ==========
    
    def list_agents(self) -> List[Dict]:
        """列出所有可用 Agent"""
        agents = self.core.list_agents()
        return [
            {
                "id": a.id,
                "name": a.name,
                "emoji": a.emoji,
                "is_allowed": a.is_allowed,
                "workspace": a.workspace,
                "model": a.model
            }
            for a in agents
        ]
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取指定 Agent 信息"""
        agent = self.core.get_agent_info(agent_id)
        if agent:
            return {
                "id": agent.id,
                "name": agent.name,
                "emoji": agent.emoji,
                "is_allowed": agent.is_allowed
            }
        return None
    
    # ========== 快速通信 ==========
    
    async def ping(self, target_agent: str, timeout: int = 10) -> bool:
        """
        快速测试与目标 Agent 的通信
        
        Args:
            target_agent: 目标 Agent ID
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否通信成功
        """
        try:
            result = await self.core.send_with_retry(
                target_agent=target_agent,
                message="[PING] 通信测试",
                timeout_seconds=timeout,
                max_retries=1
            )
            return result.status == "ok"
        except BridgeError:
            return False
    
    async def notify(self, target_agent: str, message: str) -> bool:
        """
        发送通知（不等待回复）
        
        Args:
            target_agent: 目标 Agent ID
            message: 消息内容
            
        Returns:
            bool: 是否发送成功
        """
        try:
            result = await self.core.send(
                target_agent=target_agent,
                message=message,
                timeout_seconds=0  # 即发即弃
            )
            return result.status == "ok"
        except BridgeError:
            return False
    
    async def ask(
        self,
        target_agent: str,
        question: str,
        timeout: int = None
    ) -> str:
        """
        提问并等待回复
        
        Args:
            target_agent: 目标 Agent ID
            question: 问题内容
            timeout: 超时时间（秒）
            
        Returns:
            str: 回复内容
            
        Raises:
            BridgeError: 超时或发送失败时抛出
        """
        timeout = timeout or self.default_timeout
        result = await self.core.send_with_retry(
            target_agent=target_agent,
            message=question,
            timeout_seconds=timeout,
            max_retries=self.max_retries
        )
        
        if result.status == "timeout":
            raise BridgeError(
                BridgeErrorCode.TIMEOUT,
                f"等待 {target_agent} 回复超时"
            )
        
        return result.reply or ""
    
    async def send(
        self,
        target_agent: str,
        message: str,
        timeout: int = None
    ) -> SendResult:
        """
        发送消息（底层接口）
        
        Args:
            target_agent: 目标 Agent ID
            message: 消息内容
            timeout: 超时时间（秒）
            
        Returns:
            SendResult: 发送结果
        """
        return await self.core.send_with_retry(
            target_agent=target_agent,
            message=message,
            timeout_seconds=timeout or self.default_timeout,
            max_retries=self.max_retries
        )
    
    # ========== 对话管理 ==========
    
    async def start_conversation(
        self,
        target_agent: str,
        max_turns: int = 10,
        opening_message: str = None
    ) -> ConversationThread:
        """
        开始对话
        
        Args:
            target_agent: 目标 Agent ID
            max_turns: 最大轮次
            opening_message: 开场消息（可选）
            
        Returns:
            ConversationThread: 对话线程
        """
        thread = await self.conversations.start(
            source_agent=self.source_agent,
            target_agent=target_agent,
            max_turns=max_turns
        )
        
        if opening_message:
            await self.conversations.send_turn(thread.thread_id, opening_message)
        
        return thread
    
    async def continue_conversation(
        self,
        thread_id: str,
        message: str,
        timeout: int = None
    ) -> ConversationTurn:
        """
        继续对话
        
        Args:
            thread_id: 线程 ID
            message: 消息内容
            timeout: 超时时间（秒）
            
        Returns:
            ConversationTurn: 这一轮对话的结果
        """
        return await self.conversations.send_turn(thread_id, message, timeout=timeout)
    
    async def end_conversation(
        self,
        thread_id: str,
        reason: str = None,
        send_notification: bool = False
    ) -> None:
        """
        结束对话
        
        Args:
            thread_id: 线程 ID
            reason: 结束原因
            send_notification: 是否发送结束通知
        """
        await self.conversations.end(thread_id, reason, send_notification)
    
    def get_conversation(self, thread_id: str) -> Optional[ConversationThread]:
        """获取对话线程"""
        return self.conversations.get_thread(thread_id)
    
    def list_active_conversations(self) -> List[ConversationThread]:
        """列出所有活跃对话"""
        return self.conversations.list_active_threads()
    
    # ========== 批量操作 ==========
    
    async def broadcast(
        self,
        target_agents: List[str],
        message: str
    ) -> Dict[str, SendResult]:
        """
        广播消息到多个 Agent
        
        Args:
            target_agents: 目标 Agent 列表
            message: 消息内容
            
        Returns:
            Dict[str, SendResult]: 各 Agent 的发送结果
        """
        tasks = {
            agent: self.core.send(agent, message, timeout_seconds=0)
            for agent in target_agents
        }
        
        results = {}
        for agent, task in tasks.items():
            try:
                results[agent] = await task
            except BridgeError as e:
                results[agent] = SendResult(
                    run_id="",
                    status="error",
                    error=e
                )
        
        return results
    
    async def batch_ask(
        self,
        questions: Dict[str, str],
        timeout: int = None
    ) -> Dict[str, str]:
        """
        向多个 Agent 提问
        
        Args:
            questions: {agent_id: question} 映射
            timeout: 超时时间（秒）
            
        Returns:
            Dict[str, str]: {agent_id: reply} 映射
        """
        tasks = {
            agent: self.ask(agent, question, timeout)
            for agent, question in questions.items()
        }
        
        results = {}
        for agent, task in tasks.items():
            try:
                results[agent] = await task
            except BridgeError as e:
                results[agent] = f"[错误: {e.message}]"
        
        return results
    
    # ========== 历史查询 ==========
    
    async def get_history(
        self,
        target_agent: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        获取与目标 Agent 的通信历史
        
        Args:
            target_agent: 目标 Agent ID
            limit: 限制条数
            
        Returns:
            List[Dict]: 消息列表
        """
        session_key = f"agent:{target_agent}:main"
        messages = await self.core.get_history(session_key, limit)
        
        return [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
                "sender": m.sender,
                "is_inter_session": m.provenance is not None
            }
            for m in messages
        ]
    
    # ========== 统计信息 ==========
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        tracker_stats = self.tracker.get_stats()
        active_threads = self.list_active_conversations()
        
        return {
            "source_agent": self.source_agent,
            "tracker": tracker_stats,
            "active_conversations": len(active_threads),
            "allowed_agents": self.core.get_allowed_agents()
        }


# ============================================================================
# 便捷函数
# ============================================================================

# 全局实例（懒加载）
_bridge_instance: Optional[AgentBridge] = None

def get_bridge() -> AgentBridge:
    """获取全局 Bridge 实例"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = AgentBridge()
    return _bridge_instance


async def ping(agent_id: str) -> bool:
    """快速 ping"""
    return await get_bridge().ping(agent_id)


async def notify(agent_id: str, message: str) -> bool:
    """快速通知"""
    return await get_bridge().notify(agent_id, message)


async def ask(agent_id: str, question: str, timeout: int = 30) -> str:
    """快速提问"""
    return await get_bridge().ask(agent_id, question, timeout)


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    """CLI 测试入口"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Bridge API - Agent Bridge 高级 API')
    parser.add_argument('command', choices=['list', 'ping', 'notify', 'ask', 'stats', 'test'])
    parser.add_argument('--target', '-t', help='目标 Agent ID')
    parser.add_argument('--message', '-m', help='消息内容')
    parser.add_argument('--timeout', type=int, default=30, help='超时时间')
    
    args = parser.parse_args()
    
    bridge = AgentBridge()
    
    if args.command == 'list':
        agents = bridge.list_agents()
        print("\n📡 可用 Agent 列表：\n")
        for a in agents:
            status = "✅" if a["is_allowed"] else "❌"
            print(f"  {status} {a['emoji']} {a['name']} ({a['id']})")
        print()
    
    elif args.command == 'ping':
        if not args.target:
            print("❌ 请指定 --target 参数")
            return
        
        print(f"\n🏓 Ping {args.target}...")
        result = asyncio.run(bridge.ping(args.target, args.timeout))
        print(f"  {'✅ 通信正常' if result else '❌ 通信失败'}\n")
    
    elif args.command == 'notify':
        if not args.target or not args.message:
            print("❌ 请指定 --target 和 --message 参数")
            return
        
        print(f"\n📤 发送通知到 {args.target}...")
        result = asyncio.run(bridge.notify(args.target, args.message))
        print(f"  {'✅ 发送成功' if result else '❌ 发送失败'}\n")
    
    elif args.command == 'ask':
        if not args.target or not args.message:
            print("❌ 请指定 --target 和 --message 参数")
            return
        
        print(f"\n❓ 向 {args.target} 提问...")
        try:
            reply = asyncio.run(bridge.ask(args.target, args.message, args.timeout))
            print(f"\n📝 回复：\n{reply}\n")
        except BridgeError as e:
            print(f"\n❌ 错误：{e}\n")
    
    elif args.command == 'stats':
        stats = bridge.get_stats()
        print("\n📊 统计信息：")
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        print()
    
    elif args.command == 'test':
        print("\n🧪 测试 Agent Bridge API...")
        
        # 列出 Agent
        agents = bridge.list_agents()
        print(f"  ✅ 发现 {len(agents)} 个 Agent")
        
        # 统计
        stats = bridge.get_stats()
        print(f"  ✅ 统计：{stats['active_conversations']} 个活跃对话")
        
        print("\n  注意：CLI 模式下需要实际 OpenClaw 环境才能发送消息\n")


if __name__ == '__main__':
    main()
