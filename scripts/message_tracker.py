#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Message Tracker - 消息追踪器

职责：
1. 追踪已发送消息的状态
2. 确认消息是否送达
3. 处理超时和状态更新

作者：小千 👡
版本：v2.0
日期：2026-03-23
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Callable
from datetime import datetime


# ============================================================================
# 消息状态定义
# ============================================================================

class MessageStatus(Enum):
    """消息状态"""
    PENDING = "pending"        # 已发送，等待确认
    DELIVERED = "delivered"    # 已送达
    REPLIED = "replied"        # 已收到回复
    FAILED = "failed"          # 发送失败
    TIMEOUT = "timeout"        # 超时
    CANCELLED = "cancelled"    # 已取消


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class TrackedMessage:
    """被追踪的消息"""
    run_id: str
    session_key: str
    message: str
    target_agent: str
    status: MessageStatus
    sent_at: float = field(default_factory=time.time)
    delivered_at: Optional[float] = None
    replied_at: Optional[float] = None
    reply: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    
    @property
    def elapsed_seconds(self) -> float:
        """已用时间（秒）"""
        return time.time() - self.sent_at
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "run_id": self.run_id,
            "session_key": self.session_key,
            "message": self.message,
            "target_agent": self.target_agent,
            "status": self.status.value,
            "sent_at": self.sent_at,
            "delivered_at": self.delivered_at,
            "replied_at": self.replied_at,
            "reply": self.reply,
            "error": self.error,
            "retry_count": self.retry_count,
            "elapsed_seconds": self.elapsed_seconds
        }


# ============================================================================
# 消息追踪器
# ============================================================================

class MessageTracker:
    """消息追踪器"""
    
    def __init__(
        self,
        check_interval: float = 2.0,
        max_pending_age: float = 3600.0
    ):
        """
        初始化消息追踪器
        
        Args:
            check_interval: 状态检查间隔（秒）
            max_pending_age: 消息最大存活时间（秒），超过后自动清理
        """
        self.check_interval = check_interval
        self.max_pending_age = max_pending_age
        
        # 消息存储
        self._pending: Dict[str, TrackedMessage] = {}  # run_id -> TrackedMessage
        self._history: List[TrackedMessage] = []  # 已完成的消息历史
        
        # 回调函数
        self._on_status_change: Optional[Callable[[TrackedMessage], None]] = None
    
    def set_on_status_change(self, callback: Callable[[TrackedMessage], None]) -> None:
        """设置状态变更回调"""
        self._on_status_change = callback
    
    # ========== 消息追踪 ==========
    
    def track(
        self,
        run_id: str,
        session_key: str,
        message: str,
        target_agent: str
    ) -> TrackedMessage:
        """
        开始追踪消息
        
        Args:
            run_id: 运行 ID
            session_key: 会话键
            message: 消息内容
            target_agent: 目标 Agent
            
        Returns:
            TrackedMessage: 追踪的消息对象
        """
        tracked = TrackedMessage(
            run_id=run_id,
            session_key=session_key,
            message=message,
            target_agent=target_agent,
            status=MessageStatus.PENDING
        )
        
        self._pending[run_id] = tracked
        return tracked
    
    def update_status(
        self,
        run_id: str,
        status: MessageStatus,
        reply: str = None,
        error: str = None
    ) -> Optional[TrackedMessage]:
        """
        更新消息状态
        
        Args:
            run_id: 运行 ID
            status: 新状态
            reply: 回复内容
            error: 错误信息
            
        Returns:
            TrackedMessage: 更新后的消息，如果不存在则返回 None
        """
        tracked = self._pending.get(run_id)
        if not tracked:
            return None
        
        old_status = tracked.status
        tracked.status = status
        
        if status == MessageStatus.DELIVERED:
            tracked.delivered_at = time.time()
        elif status == MessageStatus.REPLIED:
            tracked.replied_at = time.time()
            tracked.reply = reply
        elif status in [MessageStatus.FAILED, MessageStatus.TIMEOUT]:
            tracked.error = error
        
        # 触发回调
        if self._on_status_change and old_status != status:
            self._on_status_change(tracked)
        
        # 终态消息移至历史
        if status in [MessageStatus.REPLIED, MessageStatus.FAILED, 
                      MessageStatus.TIMEOUT, MessageStatus.CANCELLED]:
            self._history.append(tracked)
            del self._pending[run_id]
        
        return tracked
    
    def increment_retry(self, run_id: str) -> int:
        """增加重试计数"""
        tracked = self._pending.get(run_id)
        if tracked:
            tracked.retry_count += 1
            return tracked.retry_count
        return 0
    
    # ========== 状态查询 ==========
    
    def get_status(self, run_id: str) -> Optional[MessageStatus]:
        """获取消息状态"""
        tracked = self._pending.get(run_id)
        return tracked.status if tracked else None
    
    def get_message(self, run_id: str) -> Optional[TrackedMessage]:
        """获取追踪的消息"""
        return self._pending.get(run_id)
    
    def is_pending(self, run_id: str) -> bool:
        """检查消息是否仍在等待"""
        tracked = self._pending.get(run_id)
        return tracked is not None and tracked.status == MessageStatus.PENDING
    
    def get_pending_count(self) -> int:
        """获取等待中的消息数量"""
        return len(self._pending)
    
    def get_pending_by_agent(self, target_agent: str) -> List[TrackedMessage]:
        """获取指定 Agent 的所有等待消息"""
        return [
            m for m in self._pending.values()
            if m.target_agent == target_agent
        ]
    
    # ========== 等待机制 ==========
    
    async def wait_for_delivery(
        self,
        run_id: str,
        timeout: float = 60.0
    ) -> MessageStatus:
        """
        等待消息送达确认
        
        Args:
            run_id: 运行 ID
            timeout: 超时时间（秒）
            
        Returns:
            MessageStatus: 最终状态
        """
        tracked = self._pending.get(run_id)
        if not tracked:
            return MessageStatus.FAILED
        
        start = time.time()
        
        while time.time() - start < timeout:
            # 检查是否已送达（通过外部更新状态）
            if tracked.status != MessageStatus.PENDING:
                return tracked.status
            
            await asyncio.sleep(self.check_interval)
        
        # 超时
        self.update_status(run_id, MessageStatus.TIMEOUT, error="等待送达超时")
        return MessageStatus.TIMEOUT
    
    async def wait_for_reply(
        self,
        run_id: str,
        timeout: float = 60.0
    ) -> Optional[str]:
        """
        等待回复
        
        Args:
            run_id: 运行 ID
            timeout: 超时时间（秒）
            
        Returns:
            str: 回复内容，超时返回 None
        """
        tracked = self._pending.get(run_id)
        if not tracked:
            return None
        
        start = time.time()
        
        while time.time() - start < timeout:
            if tracked.status == MessageStatus.REPLIED:
                return tracked.reply
            elif tracked.status in [MessageStatus.FAILED, MessageStatus.TIMEOUT]:
                return None
            
            await asyncio.sleep(self.check_interval)
        
        # 超时
        self.update_status(run_id, MessageStatus.TIMEOUT, error="等待回复超时")
        return None
    
    # ========== 清理机制 ==========
    
    def cleanup_expired(self) -> int:
        """清理过期的等待消息"""
        now = time.time()
        expired_run_ids = [
            run_id for run_id, msg in self._pending.items()
            if now - msg.sent_at > self.max_pending_age
        ]
        
        for run_id in expired_run_ids:
            self.update_status(run_id, MessageStatus.TIMEOUT, error="消息过期")
        
        return len(expired_run_ids)
    
    def cancel(self, run_id: str, reason: str = None) -> bool:
        """取消消息"""
        return self.update_status(
            run_id, 
            MessageStatus.CANCELLED, 
            error=reason or "用户取消"
        ) is not None
    
    def cancel_all_for_agent(self, target_agent: str, reason: str = None) -> int:
        """取消指定 Agent 的所有等待消息"""
        pending = self.get_pending_by_agent(target_agent)
        count = 0
        for msg in pending:
            if self.cancel(msg.run_id, reason):
                count += 1
        return count
    
    # ========== 统计信息 ==========
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        history_statuses = {}
        for msg in self._history:
            status = msg.status.value
            history_statuses[status] = history_statuses.get(status, 0) + 1
        
        return {
            "pending_count": len(self._pending),
            "history_count": len(self._history),
            "by_status": history_statuses,
            "oldest_pending_age": max(
                (m.elapsed_seconds for m in self._pending.values()),
                default=0
            )
        }
    
    def get_history(self, limit: int = 100) -> List[TrackedMessage]:
        """获取历史记录"""
        return self._history[-limit:]


# ============================================================================
# CLI 测试
# ============================================================================

def main():
    """CLI 测试入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Message Tracker - 消息追踪器')
    parser.add_argument('command', choices=['stats', 'test'], help='命令')
    
    args = parser.parse_args()
    
    tracker = MessageTracker()
    
    if args.command == 'stats':
        stats = tracker.get_stats()
        print("\n📊 消息追踪器统计：")
        print(f"  等待中：{stats['pending_count']}")
        print(f"  历史记录：{stats['history_count']}")
        print(f"  状态分布：{stats['by_status']}")
        print()
    
    elif args.command == 'test':
        # 测试追踪
        print("\n🧪 测试消息追踪...")
        
        msg = tracker.track(
            run_id="test-001",
            session_key="agent:su-er:main",
            message="测试消息",
            target_agent="su-er"
        )
        print(f"  开始追踪：{msg.run_id}")
        print(f"  状态：{msg.status.value}")
        
        # 更新状态
        tracker.update_status("test-001", MessageStatus.DELIVERED)
        print(f"  更新为 DELIVERED")
        
        tracker.update_status("test-001", MessageStatus.REPLIED, reply="收到！")
        print(f"  更新为 REPLIED，回复：{msg.reply}")
        
        # 统计
        stats = tracker.get_stats()
        print(f"\n  统计：{stats}")


if __name__ == '__main__':
    main()
