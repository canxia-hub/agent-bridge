#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多轮对话示例

演示如何使用 Agent Bridge 进行多轮对话。

作者：小千 👡
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from bridge_api import AgentBridge, BridgeError
from bridge_core import BridgeErrorCode


async def example_multi_turn_conversation():
    """多轮对话示例"""
    
    bridge = AgentBridge(source_agent="main")
    
    print("=" * 60)
    print("🗨️  Agent Bridge 多轮对话示例")
    print("=" * 60)
    
    target_agent = "su-er"
    
    # 1. 开始对话
    print("\n1️⃣ 开始新对话:")
    try:
        thread = await bridge.start_conversation(
            target_agent=target_agent,
            max_turns=5
        )
        print(f"   线程 ID: {thread.thread_id}")
        print(f"   目标: {thread.target_agent}")
        print(f"   最大轮次: {thread.max_turns}")
    except BridgeError as e:
        print(f"   ❌ 启动失败: {e.message}")
        return
    
    # 2. 第一轮对话
    print("\n2️⃣ 第一轮对话:")
    try:
        turn1 = await bridge.continue_conversation(
            thread.thread_id,
            "你好，素儿。请告诉我你当前的状态",
            timeout=30
        )
        print(f"   发送: {turn1.message[:50]}...")
        print(f"   回复: {turn1.reply[:100]}..." if turn1.reply and len(turn1.reply) > 100 else f"   回复: {turn1.reply}")
        print(f"   状态: {turn1.status}")
    except BridgeError as e:
        print(f"   ❌ 发送失败: {e.message}")
    
    # 3. 第二轮对话
    print("\n3️⃣ 第二轮对话:")
    try:
        turn2 = await bridge.continue_conversation(
            thread.thread_id,
            "好的，请问你最近处理过哪些任务？",
            timeout=30
        )
        print(f"   发送: {turn2.message[:50]}...")
        print(f"   回复: {turn2.reply[:100]}..." if turn2.reply and len(turn2.reply) > 100 else f"   回复: {turn2.reply}")
        print(f"   状态: {turn2.status}")
    except BridgeError as e:
        print(f"   ❌ 发送失败: {e.message}")
    
    # 4. 第三轮对话（确认）
    print("\n4️⃣ 第三轮对话:")
    try:
        turn3 = await bridge.continue_conversation(
            thread.thread_id,
            "收到，辛苦了。暂时没有其他问题。",
            timeout=30
        )
        print(f"   发送: {turn3.message[:50]}...")
        print(f"   回复: {turn3.reply[:100]}..." if turn3.reply and len(turn3.reply) > 100 else f"   回复: {turn3.reply}")
        print(f"   状态: {turn3.status}")
    except BridgeError as e:
        print(f"   ❌ 发送失败: {e.message}")
    
    # 5. 结束对话
    print("\n5️⃣ 结束对话:")
    await bridge.end_conversation(
        thread.thread_id,
        reason="测试完成",
        send_notification=False
    )
    print(f"   ✅ 对话已结束")
    
    # 6. 对话摘要
    print("\n6️⃣ 对话摘要:")
    summary = bridge.conversations.get_thread_summary(thread.thread_id)
    if summary:
        print(f"   轮次: {summary['turn_count']}/{summary['max_turns']}")
        print(f"   状态: {summary['status']}")
        print(f"   持续时间: 从 {summary['created_at']} 到 {summary['last_activity_at']}")
    
    print("\n" + "=" * 60)
    print("✅ 多轮对话示例完成")
    print("=" * 60)


async def example_quick_conversation():
    """快速对话示例（一次性发送多条消息）"""
    
    bridge = AgentBridge(source_agent="main")
    
    print("\n" + "=" * 60)
    print("⚡ 快速对话示例")
    print("=" * 60)
    
    try:
        # 一次性发送多条消息完成对话
        thread = await bridge.conversations.quick_conversation(
            source_agent="main",
            target_agent="su-er",
            messages=[
                "你好，素儿",
                "请确认收到",
            ],
            timeout_per_turn=30
        )
        
        print(f"\n对话完成！")
        print(f"  轮次: {thread.turn_count}")
        print(f"  最后回复: {thread.get_last_reply()[:100] if thread.get_last_reply() else 'N/A'}...")
        
    except BridgeError as e:
        print(f"❌ 错误: {e.message}")


async def example_error_handling():
    """错误处理示例"""
    
    bridge = AgentBridge(source_agent="main")
    
    print("\n" + "=" * 60)
    print("⚠️  错误处理示例")
    print("=" * 60)
    
    # 1. 测试不存在的 Agent
    print("\n1️⃣ 测试不存在的 Agent:")
    try:
        await bridge.ping("non-existent-agent")
    except BridgeError as e:
        print(f"   错误码: {e.code.value}")
        print(f"   错误消息: {e.message}")
    
    # 2. 测试超时
    print("\n2️⃣ 测试超时处理:")
    try:
        reply = await bridge.ask("su-er", "测试消息", timeout=1)  # 1 秒超时
    except BridgeError as e:
        if e.code == BridgeErrorCode.TIMEOUT:
            print(f"   ⏱️ 等待回复超时（预期行为）")
        else:
            print(f"   ❌ 其他错误: {e.message}")
    
    # 3. 使用重试机制
    print("\n3️⃣ 使用重试机制:")
    try:
        result = await bridge.send("su-er", "测试重试", timeout=30)
        print(f"   发送结果: {result.status}")
    except BridgeError as e:
        print(f"   重试后仍失败: {e.message}")


def main():
    """主入口"""
    print("\n⚠️  注意：此示例需要在 OpenClaw 环境中运行\n")
    
    # 选择要运行的示例
    import argparse
    parser = argparse.ArgumentParser(description='多轮对话示例')
    parser.add_argument('--quick', action='store_true', help='运行快速对话示例')
    parser.add_argument('--error', action='store_true', help='运行错误处理示例')
    args = parser.parse_args()
    
    if args.quick:
        asyncio.run(example_quick_conversation())
    elif args.error:
        asyncio.run(example_error_handling())
    else:
        asyncio.run(example_multi_turn_conversation())


if __name__ == '__main__':
    main()
