#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Bridge - OpenClaw 多 Agent 间通信技能

核心功能：
- Agent 发现与状态查询
- 消息发送（同步/异步）
- 多轮对话管理
- 权限验证

使用方式：
    python agent_bridge.py list                     # 列出可用 Agent
    python agent_bridge.py send su-er "你好"        # 发送消息
    python agent_bridge.py send su-er "你好" --wait # 等待回复
    python agent_bridge.py conversation su-er       # 开始对话
    python agent_bridge.py history su-er            # 查看历史
    python agent_bridge.py config                   # 查看配置

作者：小千 👡
版本：v1.0
日期：2026-03-17
"""

import argparse
import json
import sys
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

# OpenClaw 状态目录
STATE_DIR = os.path.expanduser("~/.openclaw")
CONFIG_PATH = os.path.join(STATE_DIR, "openclaw.json")


def load_config() -> Dict[str, Any]:
    """加载 OpenClaw 配置文件"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 配置文件不存在：{CONFIG_PATH}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ 配置文件解析失败：{e}")
        sys.exit(1)


def check_agent_to_agent_enabled(config: Dict[str, Any]) -> bool:
    """检查 Agent 间通信是否启用"""
    tools = config.get('tools', {})
    agent_to_agent = tools.get('agentToAgent', {})
    return agent_to_agent.get('enabled', False)


def get_allowed_agents(config: Dict[str, Any]) -> List[str]:
    """获取允许通信的 Agent 白名单"""
    tools = config.get('tools', {})
    agent_to_agent = tools.get('agentToAgent', {})
    return agent_to_agent.get('allow', [])


def get_agents_list(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """获取所有已配置的 Agent"""
    agents = config.get('agents', {})
    return agents.get('list', [])


def cmd_list(config: Dict[str, Any]) -> None:
    """列出所有可用 Agent"""
    print("\n📡 可用 Agent 列表：\n")
    
    agents = get_agents_list(config)
    allowed = get_allowed_agents(config)
    enabled = check_agent_to_agent_enabled(config)
    
    if not enabled:
        print("⚠️  警告：Agent 间通信未启用（tools.agentToAgent.enabled = false）\n")
    
    print(f"{'Agent ID':<12} {'名称':<15} {'工作区':<40} {'通信权限':<10}")
    print("-" * 80)
    
    for agent in agents:
        agent_id = agent.get('id', 'unknown')
        identity = agent.get('identity', {})
        name = identity.get('name', agent_id)
        emoji = identity.get('emoji', '')
        workspace = agent.get('workspace', '~/.openclaw/workspace-' + agent_id)
        
        # 截断过长的路径
        if len(workspace) > 38:
            workspace = '...' + workspace[-35:]
        
        permission = "✅" if agent_id in allowed else "❌"
        
        print(f"{agent_id:<12} {emoji} {name:<13} {workspace:<40} {permission:<10}")
    
    print("\n💡 提示：")
    print("   • 使用 send 命令发送消息：python agent_bridge.py send <agent-id> \"消息内容\"")
    print("   • 添加 --wait 参数等待回复")
    print("   • 使用 conversation 开始多轮对话")
    print()


def cmd_send(config: Dict[str, Any], target_agent: str, message: str, wait: bool, timeout: int) -> None:
    """发送消息到指定 Agent"""
    allowed = get_allowed_agents(config)
    agents = get_agents_list(config)
    
    # 验证目标 Agent 是否存在
    agent_ids = [a.get('id') for a in agents]
    if target_agent not in agent_ids:
        print(f"❌ 错误：Agent '{target_agent}' 不存在")
        print(f"   可用 Agent: {', '.join(agent_ids)}")
        sys.exit(1)
    
    # 验证通信权限
    if target_agent not in allowed:
        print(f"❌ 错误：Agent '{target_agent}' 不在通信白名单中")
        print(f"   白名单：{', '.join(allowed)}")
        print(f"   需要在 openclaw.json 中配置 tools.agentToAgent.allow")
        sys.exit(1)
    
    print(f"\n📤 发送消息到 {target_agent}...")
    print(f"   消息内容：{message}")
    print(f"   等待回复：{'是' if wait else '否'}")
    if wait:
        print(f"   超时时间：{timeout}秒")
    
    # 构造 sessions_send 调用说明
    print("\n📋 调用方式（在 OpenClaw 中）：")
    print(f"""
    sessions_send({{
        "sessionKey": "agent:{target_agent}:main",
        "message": {json.dumps(message)},
        "timeoutSeconds": {timeout if wait else 0}
    }})
    """)
    
    print("✅ 消息发送说明已生成")
    print("   注意：此脚本仅生成调用说明，实际发送需在 OpenClaw 会话中执行 sessions_send 工具")
    print()


def cmd_conversation(config: Dict[str, Any], target_agent: str) -> None:
    """开始/继续与指定 Agent 的对话"""
    allowed = get_allowed_agents(config)
    agents = get_agents_list(config)
    
    if target_agent not in [a.get('id') for a in agents]:
        print(f"❌ 错误：Agent '{target_agent}' 不存在")
        sys.exit(1)
    
    if target_agent not in allowed:
        print(f"❌ 错误：Agent '{target_agent}' 不在通信白名单中")
        sys.exit(1)
    
    thread_id = f"conv_{target_agent}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"\n🗨️  与 {target_agent} 的对话线程")
    print("=" * 50)
    print(f"线程 ID: {thread_id}")
    print(f"目标 Agent: {target_agent}")
    print(f"创建时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("📋 多轮对话流程：")
    print("   1. 使用 sessions_send 发送第一条消息（timeoutSeconds > 0）")
    print("   2. 收到回复后，再次调用 sessions_send 继续对话")
    print("   3. 重复步骤 2，最多 5 轮（可配置）")
    print("   4. 回复 REPLY_SKIP 可提前结束对话")
    print()
    print("💡 示例：")
    print(f"""
    # 第一轮
    sessions_send({{
        "sessionKey": "agent:{target_agent}:main",
        "message": "你好，有个任务需要协助",
        "timeoutSeconds": 30
    }})
    
    # 收到回复后继续
    sessions_send({{
        "sessionKey": "agent:{target_agent}:main",
        "message": "好的，具体需求是...",
        "timeoutSeconds": 30
    }})
    """)
    print()


def cmd_history(config: Dict[str, Any], target_agent: str, limit: int) -> None:
    """查看与指定 Agent 的通信历史"""
    agents = get_agents_list(config)
    
    if target_agent not in [a.get('id') for a in agents]:
        print(f"❌ 错误：Agent '{target_agent}' 不存在")
        sys.exit(1)
    
    print(f"\n📜 与 {target_agent} 的通信历史")
    print("=" * 50)
    print(f"会话键：agent:{target_agent}:main")
    print(f"限制条数：{limit}")
    print()
    print("📋 调用方式：")
    print(f"""
    sessions_history({{
        "sessionKey": "agent:{target_agent}:main",
        "limit": {limit},
        "includeTools": false
    }})
    """)
    print()


def cmd_config(config: Dict[str, Any]) -> None:
    """查看 Agent 间通信配置"""
    print("\n⚙️  Agent 间通信配置")
    print("=" * 50)
    
    tools = config.get('tools', {})
    agent_to_agent = tools.get('agentToAgent', {})
    sessions = tools.get('sessions', {})
    
    enabled = agent_to_agent.get('enabled', False)
    allow = agent_to_agent.get('allow', [])
    visibility = sessions.get('visibility', 'tree')
    
    print(f"\n启用状态：{'✅ 已启用' if enabled else '❌ 未启用'}")
    print(f"通信白名单：{', '.join(allow) if allow else '无'}")
    print(f"会话可见性：{visibility}")
    
    print("\n📋 配置位置：")
    print(f"   {CONFIG_PATH}")
    
    print("\n💡 修改建议：")
    if not enabled:
        print("   需要启用 tools.agentToAgent.enabled = true")
    if not allow:
        print("   需要配置 tools.agentToAgent.allow 白名单")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Agent Bridge - OpenClaw 多 Agent 间通信技能',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python agent_bridge.py list                     # 列出可用 Agent
  python agent_bridge.py send su-er "你好"        # 发送消息
  python agent_bridge.py send su-er "你好" --wait # 等待回复
  python agent_bridge.py conversation su-er       # 开始对话
  python agent_bridge.py history su-er            # 查看历史
  python agent_bridge.py config                   # 查看配置
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # list 命令
    subparsers.add_parser('list', help='列出所有可用 Agent')
    
    # send 命令
    send_parser = subparsers.add_parser('send', help='发送消息到指定 Agent')
    send_parser.add_argument('target', help='目标 Agent ID')
    send_parser.add_argument('message', help='消息内容')
    send_parser.add_argument('--wait', action='store_true', help='等待回复')
    send_parser.add_argument('--timeout', type=int, default=30, help='超时时间（秒）')
    
    # conversation 命令
    conv_parser = subparsers.add_parser('conversation', help='开始/继续对话')
    conv_parser.add_argument('target', help='目标 Agent ID')
    
    # history 命令
    hist_parser = subparsers.add_parser('history', help='查看通信历史')
    hist_parser.add_argument('target', help='目标 Agent ID')
    hist_parser.add_argument('--limit', type=int, default=20, help='限制条数')
    
    # config 命令
    subparsers.add_parser('config', help='查看配置')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # 加载配置
    config = load_config()
    
    # 执行命令
    if args.command == 'list':
        cmd_list(config)
    elif args.command == 'send':
        cmd_send(config, args.target, args.message, args.wait, args.timeout)
    elif args.command == 'conversation':
        cmd_conversation(config, args.target)
    elif args.command == 'history':
        cmd_history(config, args.target, args.limit)
    elif args.command == 'config':
        cmd_config(config)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
