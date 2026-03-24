#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import json
import os

# 解析epg.xml文件
tree = ET.parse('epg.xml')
root = tree.getroot()

# 构建频道数据
channels = []

# 定义频道顺序（从1.txt读取）
channel_order = []
try:
    with open('1.txt', 'r', encoding='utf-8') as f:
        channel_order = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    pass

# 创建频道名称到排序位置的映射
name_to_index = {}
for index, name in enumerate(channel_order):
    name_to_index[name] = index

# 遍历所有频道
for channel in root.findall('channel'):
    channel_id = channel.get('id')
    
    # 获取频道名称
    display_names = channel.findall('display-name')
    name = display_names[0].text if display_names else ''
    
    # 查找该频道的所有节目
    programmes = []
    for programme in root.findall('programme'):
        if programme.get('channel') == channel_id:
            programmes.append(programme)
    
    # 计算最后节目时间
    last_program_time = ''
    if programmes:
        # 按结束时间排序，取最后一个
        programmes.sort(key=lambda p: p.get('stop'), reverse=True)
        stop_time = programmes[0].get('stop')
        if stop_time:
            # 格式：20260321010000 +0800
            year = stop_time[:4]
            month = stop_time[4:6]
            day = stop_time[6:8]
            hour = stop_time[8:10]
            minute = stop_time[10:12]
            last_program_time = f"{year}-{month}-{day} {hour}:{minute}"
    
    # 计算节目描述覆盖率
    description_coverage = 0
    if programmes:
        programmes_with_desc = [p for p in programmes if p.find('desc') is not None]
        description_coverage = round((len(programmes_with_desc) / len(programmes)) * 100)
    
    channels.append({
        'id': channel_id,
        'name': name,
        'lastProgramTime': last_program_time,
        'descriptionCoverage': description_coverage
    })

# 按照频道顺序排序
channels.sort(key=lambda c: name_to_index.get(c['name'], 999999))

# 生成JSON文件
with open('epg_data.json', 'w', encoding='utf-8') as f:
    json.dump({
        'channels': channels,
        'updateTime': os.path.getmtime('epg.xml')
    }, f, ensure_ascii=False, indent=2)

print('Coverage calculation completed.')
