#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import json
import time
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_epg import classify_channel, get_sort_key, CATEGORY_ORDER, CN_TZ

tree = ET.parse('epg.xml')
root = tree.getroot()

now_cn = datetime.now(CN_TZ)
today = now_cn.strftime('%Y%m%d')
base_day = int(today)
today_start = base_day * 1440
today_end = (base_day + 1) * 1440

# 按 channel 一次性建立索引，避免对每个频道重复扫描全部节目（O(频道数×节目数) -> O(N+M)）
programmes_by_channel = {}
latest_stop = ''
for programme in root.findall('programme'):
    ch_id = programme.get('channel')
    stop = programme.get('stop') or ''
    if len(stop) >= 12 and stop[:12] > latest_stop:
        latest_stop = stop[:12]
    if ch_id:
        programmes_by_channel.setdefault(ch_id, []).append(programme)


def _to_minutes(date_str, time_str):
    day = int(date_str)
    h = int(time_str[:2])
    m = int(time_str[2:4])
    return day * 1440 + h * 60 + m


def _interval(p):
    """返回节目的绝对分钟区间，无法解析或时长为 0 时返回 None"""
    s = p.get('start') or ''
    e = p.get('stop') or ''
    if len(s) < 12 or len(e) < 12:
        return None
    try:
        s_min = _to_minutes(s[:8], s[8:12])
        e_min = _to_minutes(e[:8], e[8:12])
    except ValueError:
        return None
    if e_min <= s_min:
        return None
    return s_min, e_min


def _min_to_display(min_val, base_day):
    """把绝对分钟转换成当天显示时间；跨到次日会带上"次日"前缀"""
    offset = min_val - base_day * 1440
    if offset < 0:
        return '00:00'
    days = offset // 1440
    rem = offset % 1440
    h = rem // 60
    m = rem % 60
    if days == 0:
        return f"{h:02d}:{m:02d}"
    if days == 1:
        return f"次日 {h:02d}:{m:02d}"
    return f"+{days}天 {h:02d}:{m:02d}"


def _fmt_last_program(stop):
    if not stop or len(stop) < 12:
        return ''
    return f"{stop[:4]}-{stop[4:6]}-{stop[6:8]} {stop[8:10]}:{stop[10:12]}"


channels = []

for channel in root.findall('channel'):
    channel_id = channel.get('id')
    display_names = channel.findall('display-name')
    name = display_names[0].text if display_names else ''
    aliases = list(dict.fromkeys(dn.text for dn in display_names if dn.text and dn.text != name))

    programmes = programmes_by_channel.get(channel_id, [])

    last_program_time = _fmt_last_program(max((p.get('stop') or '' for p in programmes), default=''))

    description_coverage = 0
    if programmes:
        programmes_with_desc = [p for p in programmes if p.find('desc') is not None]
        description_coverage = round((len(programmes_with_desc) / len(programmes)) * 100)

    # 今日节目 = 与今天有交集的节目（包含昨天深夜开始、今天凌晨结束的跨天节目）
    today_items = []
    for p in programmes:
        iv = _interval(p)
        if iv and iv[0] < today_end and iv[1] > today_start:
            today_items.append((iv[0], iv[1], p))
    today_items.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    has_gap = False
    gap_details = ''
    gap_list = []
    if today_items:
        merged = []
        for s_min, e_min, _ in today_items:
            if merged and s_min <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e_min))
            else:
                merged.append((s_min, e_min))

        gaps = []
        day_start = base_day * 1440 + 360
        day_end = today_end
        first_start = merged[0][0]
        if first_start > day_start and first_start - day_start >= 5:
            gaps.append(first_start - day_start)
            gap_list.append({
                'after': '06:00',
                'before': _min_to_display(first_start, base_day),
                'minutes': first_start - day_start
            })
        for i in range(len(merged) - 1):
            gap_min = merged[i + 1][0] - merged[i][1]
            if gap_min >= 5 and merged[i][1] >= day_start and merged[i + 1][0] <= day_end:
                gaps.append(gap_min)
                gap_list.append({
                    'after': _min_to_display(merged[i][1], base_day),
                    'before': _min_to_display(merged[i + 1][0], base_day),
                    'minutes': gap_min
                })
        last_end = merged[-1][1]
        if last_end < day_end and day_end - last_end >= 5:
            gaps.append(day_end - last_end)
            gap_list.append({
                'after': _min_to_display(last_end, base_day),
                'before': '24:00',
                'minutes': day_end - last_end
            })
        if gaps:
            has_gap = True
            gap_details = f"{len(gaps)}处断层(最长{max(gaps)}分钟)"

    today_schedule = []
    used = set()
    for i, (s1_min, e1_min, p) in enumerate(today_items):
        if i in used:
            continue
        title_el = p.find('title')
        desc_el = p.find('desc')
        main_dur = e1_min - s1_min
        sub_programmes = []
        for j in range(i + 1, len(today_items)):
            if j in used:
                continue
            s2_min, e2_min, p2 = today_items[j]
            if s2_min >= e1_min:
                break
            sub_dur = e2_min - s2_min
            if sub_dur < main_dur or (sub_dur == 0 and main_dur > 0):
                t2 = p2.find('title')
                d2 = p2.find('desc')
                sub_programmes.append({
                    'start': _min_to_display(max(s2_min, today_start), base_day),
                    'stop': _min_to_display(e2_min, base_day),
                    'title': t2.text if t2 is not None else '',
                    'desc': d2.text if d2 is not None else ''
                })
                used.add(j)
        today_schedule.append({
            'start': _min_to_display(max(s1_min, today_start), base_day),
            'stop': _min_to_display(e1_min, base_day),
            'title': title_el.text if title_el is not None else '',
            'desc': desc_el.text if desc_el is not None else '',
            'subProgrammes': sub_programmes
        })

    channels.append({
        'id': channel_id,
        'name': name,
        'aliases': aliases,
        'category': classify_channel(name),
        'lastProgramTime': last_program_time,
        'descriptionCoverage': description_coverage,
        'hasGap': has_gap,
        'gapDetails': gap_details,
        'gapList': gap_list,
        'todaySchedule': today_schedule
    })

channels.sort(key=lambda c: get_sort_key(c['name']))

with open('epg_data.json', 'w', encoding='utf-8') as f:
    json.dump({
        'channels': channels,
        # 分类白名单由后端下发，前端不再手抄一份
        'categories': CATEGORY_ORDER,
        'dataEnd': _fmt_last_program(latest_stop),
        'updateTime': time.time()
    }, f, ensure_ascii=False, separators=(',', ':'))

print(f'Coverage calculation completed. {len(channels)} channels.')
