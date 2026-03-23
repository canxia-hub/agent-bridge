#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversation Manager - 对话管理器 v2.0

职责：
1. 创建和管理对话线程
2. 维护对话上下文
3. 与 sessions_* 工具集成

主要改动（v2.0）：
- 与 bridge_core 集成，实际调用 sessions_* 工具
- 支持异步操作
- 完整的错误处理
- 消息追踪集成

作者：小千 👡
版本：v2.0
日期：2026-03-23
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from bridge_core import BridgeCore, BridgeError, BridgeErrorCode
from message_tracker import MessageTracker, MessageStatus


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class ConversationTurn:
    """对话轮次"""
    turn_number: int
    from_agent: str
    to_agent: str
    message: str
    reply: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    run_id: Optional[str] = None
    status: str = "pending"  # pending | completed | failed
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "turn_number": self.turn_number,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message": self.message,
            "reply": self.reply,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "status": self.status,
            "error": self.error
        }


@dataclass
class ConversationThread:
    """对话线程"""
    thread_id: str
    source_agent: str
    target_agent: str
    session_key: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_activity_at: str = field(default_factory=lambda: datetime.now().isoformat())
    turn_count: int = 0
    max_turns: int = 10
    status: str = "active"  # active | closed | error
    turns: List[ConversationTurn] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "thread_id": self.thread_id,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "session_key": self.session_key,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "turn_count": self.turn_count,
            "max_turns": self.max_turns,
            "status": self.status,
            "turns": [t.to_dict() for t in self.turns],
            "context": self.context
        }
    
    @property
    def is_active(self) -> bool:
        """是否仍活跃"""
        return self.status == "active" and self.turn_count < self.max_turns
    
    def get_last_reply(self) -> Optional[str]:
        """获取最后一条回复"""
        if self.turns:
            return self.turns[-1].reply
        return None


# ============================================================================
# 对话管理器
# ============================================================================

class ConversationManager:
    """对话管理器"""
    
    def __init__(
        self,
        core: BridgeCore = None,
        tracker: MessageTracker = None,
        default_max_turns: int = 10,
        default_timeout: int = 30
    ):
        """
        初始化对话管理器
        
        Args:
            core: BridgeCore 实例
            tracker: MessageTracker 实例
            default_max_turns: 默认最大轮次
            default_timeout: 默认超时时间（秒）
        """
        self.core = core or BridgeCore()
        self.tracker = tracker or MessageTracker()
        self.default_max_turns = default_max_turns
        self.default_timeout = default_timeout
        
        # 活跃线程存储
        self._active_threads: Dict[str, ConversationThread] = {}
    
    # ========== 对话生命周期 ==========
    
    async def start(
        self,
        source_agent: str,
        target_agent: str,
        max_turns: int = None,
        context: Dict[str, Any] = None
    ) -> ConversationThread:
        """
        开始新对话
        
        Args:
            source_agent: 发起方 Agent ID
            target_agent: 目标 Agent ID
            max_turns: 最大轮次，默认使用 default_max_turns
            context: 对话上下文
            
        Returns:
            ConversationThread: 新建的对话线程
            
        Raises:
            BridgeError: 权限检查失败时抛出
        """
        # 检查权限
        if not self.core.check_permission(source_agent, target_agent):
            raise BridgeError(
                BridgeErrorCode.PERMISSION_DENIED,
                f"Agent '{source_agent}' 无权与 Agent '{target_agent}' 通信"
            )
        
        # 生成线程 ID
        thread_id = self._generate_thread_id(target_agent)
        
        # 构建会话键
        session_key = f"agent:{target_agent}:main"
        
        # 创建线程
        thread = ConversationThread(
            thread_id=thread_id,
            source_agent=source_agent,
            target_agent=target_agent,
            session_key=session_key,
            max_turns=max_turns or self.default_max_turns,
            context=context or {}
        )
        
        self._active_threads[thread_id] = thread
        return thread
    
    def _generate_thread_id(self, target_agent: str) -> str:
        """生成线程 ID"""
        return f"conv_{target_agent}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    async def send_turn(
        self,
        thread_id: str,
        message: str,
        timeout: int = None
    ) -> ConversationTurn:
        """
        发送一轮对话
        
        Args:
            thread_id: 线程 ID
            message: 消息内容
            timeout: 超时时间（秒）
            
        Returns:
            ConversationTurn: 这一轮对话的结果
            
        Raises:
            BridgeError: 发送失败时抛出
        """
        thread = self._active_threads.get(thread_id)
        if not thread:
            raise BridgeError(
                BridgeErrorCode.UNKNOWN_ERROR,
                f"对话线程 '{thread_id}' 不存在"
            )
        
        # 检查线程状态
        if thread.status != "active":
            raise BridgeError(
                BridgeErrorCode.UNKNOWN_ERROR,
                f"对话线程已关闭（状态：{thread.status}）"
            )
        
        # 检查轮次限制
        if thread.turn_count >= thread.max_turns:
            raise BridgeError(
                BridgeErrorCode.UNKNOWN_ERROR,
                f"已达到最大轮次限制 ({thread.max_turns})"
            )
        
        # 创建轮次记录
        turn = ConversationTurn(
            turn_number=thread.turn_count + 1,
            from_agent=thread.source_agent,
            to_agent=thread.target_agent,
            message=message
        )
        
        try:
            # 发送消息
            timeout = timeout or self.default_timeout
            result = await self.core.send(
                target_agent=thread.target_agent,
                message=message,
                timeout_seconds=timeout,
                session_key=thread.session_key
            )
            
            # 更新轮次信息
            turn.run_id = result.run_id
            turn.reply = result.reply
            turn.status = "completed"
            
            # 追踪消息
            self.tracker.track(
                run_id=result.run_id,
                session_key=thread.session_key,
                message=message,
                target_agent=thread.target_agent
            )
            self.tracker.update_status(
                result.run_id,
                MessageStatus.REPLIED,
                reply=result.reply
            )
            
        except BridgeError as e:
            turn.status = "failed"
            turn.error = str(e)
            raise
        
        finally:
            # 更新线程
            thread.turns.append(turn)
            thread.turn_count = turn.turn_number
            thread.last_activity_at = datetime.now().isoformat()
        
        return turn
    
    async def end(
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
            send_notification: 是否发送结束通知给对方
        """
        thread = self._active_threads.get(thread_id)
        if not thread:
            return
        
        # 可选：发送结束通知
        if send_notification and thread.is_active:
            try:
                await self.core.send(
                    target_agent=thread.target_agent,
                    message="REPLY_SKIP",  # 特殊标记，结束 ping-pong
                    timeout_seconds=0
                )
            except BridgeError:
                pass  # 忽略结束通知发送失败
        
        # 更新状态
        thread.status = "closed"
        thread.last_activity_at = datetime.now().isoformat()
        if reason:
            thread.context["end_reason"] = reason
    
    # ========== 状态查询 ==========
    
    def get_thread(self, thread_id: str) -> Optional[ConversationThread]:
        """获取对话线程"""
        return self._active_threads.get(thread_id)
    
    def list_active_threads(self) -> List[ConversationThread]:
        """列出所有活跃对话"""
        return [t for t in self._active_threads.values() if t.status == "active"]
    
    def list_threads_by_agent(self, agent_id: str) -> List[ConversationThread]:
        """列出与指定 Agent 的所有对话"""
        return [
            t for t in self._active_threads.values()
            if t.source_agent == agent_id or t.target_agent == agent_id
        ]
    
    def get_thread_summary(self, thread_id: str) -> Optional[Dict]:
        """获取对话摘要"""
        thread = self.get_thread(thread_id)
        if not thread:
            return None
        
        return {
            "thread_id": thread.thread_id,
            "source_agent": thread.source_agent,
            "target_agent": thread.target_agent,
            "status": thread.status,
            "turn_count": thread.turn_count,
            "max_turns": thread.max_turns,
            "created_at": thread.created_at,
            "last_activity_at": thread.last_activity_at,
            "first_message": thread.turns[0].message if thread.turns else None,
            "last_message": thread.turns[-1].message if thread.turns else None,
            "last_reply": thread.get_last_reply()
        }
    
    # ========== 批量操作 ==========
    
    async def end_all_for_agent(self, agent_id: str, reason: str = None) -> int:
        """结束与指定 Agent 的所有对话"""
        threads = self.list_threads_by_agent(agent_id)
        count = 0
        for thread in threads:
            if thread.status == "active":
                await self.end(thread.thread_id, reason=reason)
                count += 1
        return count
    
    def cleanup_closed(self, max_age_hours: int = 24) -> int:
        """清理已关闭的对话"""
        now = datetime.now()
        to_remove = []
        
        for thread_id, thread in self._active_threads.items():
            if thread.status == "closed":
                last_activity = datetime.fromisoformat(thread.last_activity_at)
                age_hours = (now - last_activity).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_remove.append(thread_id)
        
        for thread_id in to_remove:
            del self._active_threads[thread_id]
        
        return len(to_remove)
    
    # ========== 便捷方法 ==========
    
    async def quick_conversation(
        self,
        source_agent: str,
        target_agent: str,
        messages: List[str],
        timeout_per_turn: int = None
    ) -> ConversationThread:
        """
        快速执行一轮完整对话
        
        Args:
            source_agent: 发起方 Agent
            target_agent: 目标 Agent
            messages: 消息列表
            timeout_per_turn: 每轮超时时间
            
        Returns:
            ConversationThread: 完成的对话线程
        """
        thread = await self.start(source_agent, target_agent, max_turns=len(messages))
        
        for message in messages:
            if not thread.is_active:
                break
            await self.send_turn(thread.thread_id, message, timeout=timeout_per_turn)
        
        await self.end(thread.thread_id)
        return thread


# ============================================================================
# CLI 测试
# ============================================================================

def main():
    """CLI 测试入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Conversation Manager - 对话管理器')
    parser.add_argument('command', choices=['test', 'list'], help='命令')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        manager = ConversationManager()
        threads = manager.list_active_threads()
        print(f"\n📋 活跃对话线程：{len(threads)}")
        for t in threads:
            print(f"  {t.thread_id}: {t.source_agent} → {t.target_agent} ({t.turn_count} 轮)")
        print()
    
    elif args.command == 'test':
        print("\n🧪 测试对话管理器...")
        
        # 创建管理器
        manager = ConversationManager()
        
        # 创建测试线程
        thread = asyncio.run(manager.start("main", "su-er"))
        print(f"  ✅ 创建线程：{thread.thread_id}")
        print(f"  状态：{thread.status}")
        
        # 模拟发送（CLI 模式下不会真正发送）
        print(f"\n  📤 模拟发送消息...")
        print(f"  注意：CLI 模式下需要实际 OpenClaw 环境才能发送消息")
        
        # 结束对话
        asyncio.run(manager.end(thread.thread_id, reason="测试完成"))
        print(f"\n  ✅ 结束对话，状态：{thread.status}")
        
        # 获取摘要
        summary = manager.get_thread_summary(thread.thread_id)
        print(f"\n  📋 对话摘要：")
        print(f"    轮次：{summary['turn_count']}/{summary['max_turns']}")


if __name__ == '__main__':
    main()
