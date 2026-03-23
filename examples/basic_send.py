#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础发送示例

演示如何使用 Agent Bridge 发送消息。

运行方式：
    # 在 OpenClaw 会话中直接调用 sessions_send
    # 或使用高级 API

作者：小千 👡
"""

import asyncio
import sys
import os

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bridge_api import AgentBridge, BridgeError


async def example_basic_send():
    """基础发送示例"""
    
    # 创建 Bridge 实例
    bridge = AgentBridge(source_agent="main")
    
    print("=" * 60)
    print("📡 Agent Bridge 基础发送示例")
    print("=" * 60)
    
    # 1. 列出可用 Agent
    print("\n1️⃣ 列出可用 Agent:")
    agents = bridge.list_agents()
    for a in agents:
        status = "✅" if a["is_allowed"] else "❌"
        print(f"   {status} {a['emoji']} {a['name']} ({a['id']})")
    
    # 2. Ping 测试
    print("\n2️⃣ Ping 测试通信:")
    target = "su-er"
    is_ok = await bridge.ping(target, timeout=10)
    print(f"   {target}: {'✅ 通信正常' if is_ok else '❌ 通信失败'}")
    
    # 3. 发送通知
    print("\n3️⃣ 发送通知（不等待回复）:")
    success = await bridge.notify(target, "这是一条测试通知")
    print(f"   发送结果: {'✅ 成功' if success else '❌ 失败'}")
    
    # 4. 提问并等待回复
    print("\n4️⃣ 提问并等待回复:")
    try:
        reply = await bridge.ask(target, "你好，请确认收到消息", timeout=30)
        print(f"   回复: {reply[:100]}..." if len(reply) > 100 else f"   回复: {reply}")
    except BridgeError as e:
        print(f"   ❌ 错误: {e.message}")
    
    print("\n" + "=" * 60)
    print("✅ 示例完成")
    print("=" * 60)


async def example_with_tools():
    """在 OpenClaw 环境中使用（注入工具）"""
    
    # 在 OpenClaw 会话中，工具会自动注入
    # 这里展示如何手动设置
    
    bridge = AgentBridge(source_agent="main")
    
    # 如果在 OpenClaw 会话中，可以这样注入工具
    # bridge.set_tools(sessions_send, sessions_history, sessions_list)
    
    # 然后就可以正常使用了
    result = await bridge.send("su-er", "测试消息", timeout=30)
    
    print(f"状态: {result.status}")
    print(f"回复: {result.reply}")


def main():
    """主入口"""
    print("\n⚠️  注意：此示例需要在 OpenClaw 环境中运行")
    print("   或确保已配置正确的工具注入\n")
    
    # 运行示例
    asyncio.run(example_basic_send())


if __name__ == '__main__':
    main()
