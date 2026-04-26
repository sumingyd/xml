#!/usr/bin/env python3
"""
合并当天EPG数据到完整EPG文件

由GitHub Actions工作流调用，将epg_today.xml合并到epg.xml中：
1. 从epg.xml中移除当天的旧节目（被新数据替换）
2. 添加当天新节目
3. 清理过期数据
4. 移除空频道
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os
import sys

HISTORY_DAYS = 3


def merge_epg():
    today_file = 'epg_today.xml'
    epg_file = 'epg.xml'

    if not os.path.exists(today_file):
        print("epg_today.xml 不存在，跳过合并")
        return False

    today = datetime.now().strftime('%Y%m%d')

    if not os.path.exists(epg_file):
        tree = ET.parse(today_file)
        ET.indent(tree, space='  ')
        tree.write(epg_file, encoding='utf-8', xml_declaration=True)
        print(f"首次创建: epg_today.xml -> epg.xml")
        return True

    try:
        epg_tree = ET.parse(epg_file)
        epg_root = epg_tree.getroot()
    except Exception as e:
        print(f"epg.xml 解析失败: {e}，使用当天数据替换")
        tree = ET.parse(today_file)
        ET.indent(tree, space='  ')
        tree.write(epg_file, encoding='utf-8', xml_declaration=True)
        return True

    today_tree = ET.parse(today_file)
    today_root = today_tree.getroot()

    to_remove = []
    for programme in epg_root.findall('programme'):
        start = programme.get('start', '')
        if len(start) >= 8 and start[:8] == today:
            to_remove.append(programme)

    for programme in to_remove:
        epg_root.remove(programme)

    print(f"从epg.xml中移除了 {len(to_remove)} 个当天的旧节目")

    existing_channel_ids = set()
    for channel in epg_root.findall('channel'):
        ch_id = channel.get('id', '')
        if ch_id:
            existing_channel_ids.add(ch_id)

    added_channels = 0
    for channel in today_root.findall('channel'):
        ch_id = channel.get('id', '')
        if ch_id and ch_id not in existing_channel_ids:
            epg_root.append(channel)
            added_channels += 1

    print(f"添加了 {added_channels} 个新频道")

    added_programmes = 0
    for programme in today_root.findall('programme'):
        epg_root.append(programme)
        added_programmes += 1

    print(f"添加了 {added_programmes} 个当天节目")

    cutoff = (datetime.now() - timedelta(days=HISTORY_DAYS + 1)).strftime('%Y%m%d%H%M%S')
    old_to_remove = []
    for programme in epg_root.findall('programme'):
        start = programme.get('start', '')
        if len(start) >= 14 and start[:14] < cutoff:
            old_to_remove.append(programme)

    for programme in old_to_remove:
        epg_root.remove(programme)

    print(f"清理了 {len(old_to_remove)} 个过期节目(保留{HISTORY_DAYS}天)")

    channels_with_programmes = set()
    for programme in epg_root.findall('programme'):
        channel_id = programme.get('channel', '')
        if channel_id:
            channels_with_programmes.add(channel_id)

    empty_channels = []
    for channel in epg_root.findall('channel'):
        ch_id = channel.get('id', '')
        if ch_id and ch_id not in channels_with_programmes:
            empty_channels.append(channel)

    for channel in empty_channels:
        epg_root.remove(channel)

    print(f"清理了 {len(empty_channels)} 个空频道")

    ET.indent(epg_tree, space='  ')
    epg_tree.write(epg_file, encoding='utf-8', xml_declaration=True)

    total_programmes = len(epg_root.findall('programme'))
    total_channels = len(epg_root.findall('channel'))
    file_size = os.path.getsize(epg_file)
    print(f"合并完成! 共 {total_channels} 个频道, {total_programmes} 个节目, {file_size / 1024:.1f}KB")

    return True


if __name__ == '__main__':
    success = merge_epg()
    sys.exit(0 if success else 1)
