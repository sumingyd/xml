#!/usr/bin/env python3
"""
合并days/目录下所有日期EPG文件到完整EPG文件

由GitHub Actions工作流调用：
1. 清理days/目录中过期的日期文件
2. 合并所有日期文件为完整的epg.xml
3. 移除没有节目的空频道
"""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os
import sys
import glob

HISTORY_DAYS = 7
DAYS_DIR = 'days'


def merge_epg():
    if not os.path.exists(DAYS_DIR):
        print(f"{DAYS_DIR}/ 目录不存在，跳过合并")
        return False

    today = datetime.now().strftime('%Y%m%d')
    cutoff = (datetime.now() - timedelta(days=HISTORY_DAYS)).strftime('%Y%m%d')

    day_files = sorted(glob.glob(os.path.join(DAYS_DIR, 'epg_*.xml')))

    if not day_files:
        print(f"{DAYS_DIR}/ 目录下没有EPG文件，跳过合并")
        return False

    removed_files = []
    for f in day_files[:]:
        basename = os.path.basename(f)
        date_str = basename.replace('epg_', '').replace('.xml', '')
        if len(date_str) == 8 and date_str < cutoff:
            os.remove(f)
            removed_files.append(basename)
            day_files.remove(f)

    if removed_files:
        print(f"清理了 {len(removed_files)} 个过期日期文件: {', '.join(removed_files)}")

    if not day_files:
        print("清理后没有剩余日期文件，跳过合并")
        return True

    all_channels = {}
    all_programmes = []

    for f in day_files:
        try:
            tree = ET.parse(f)
            root = tree.getroot()
            for channel in root.findall('channel'):
                ch_id = channel.get('id', '')
                if ch_id and ch_id not in all_channels:
                    all_channels[ch_id] = channel
            for programme in root.findall('programme'):
                all_programmes.append(programme)
        except Exception as e:
            print(f"解析 {f} 失败: {e}，跳过")

    channels_with_programmes = set()
    for programme in all_programmes:
        channel_id = programme.get('channel', '')
        if channel_id:
            channels_with_programmes.add(channel_id)

    empty_count = 0
    for ch_id in list(all_channels.keys()):
        if ch_id not in channels_with_programmes:
            del all_channels[ch_id]
            empty_count += 1

    if empty_count:
        print(f"移除了 {empty_count} 个空频道")

    tv = ET.Element('tv')
    tv.set('generator-info-name', 'EPG')
    for channel in all_channels.values():
        tv.append(channel)
    for programme in all_programmes:
        tv.append(programme)

    tree = ET.ElementTree(tv)
    ET.indent(tree, space='  ')
    tree.write('epg.xml', encoding='utf-8', xml_declaration=True)

    file_size = os.path.getsize('epg.xml')
    print(f"合并完成! {len(day_files)} 个日期文件, {len(all_channels)} 个频道, {len(all_programmes)} 个节目, {file_size / 1024:.1f}KB")

    return True


if __name__ == '__main__':
    success = merge_epg()
    sys.exit(0 if success else 1)
