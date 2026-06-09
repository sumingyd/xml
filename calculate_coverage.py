#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import json
import time
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_epg import classify_channel, get_sort_key, CATEGORY_ORDER

tree = ET.parse('epg.xml')
root = tree.getroot()

today = datetime.now().strftime('%Y%m%d')
tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')


def _fmt_time(t):
    if not t or len(t) < 12:
        return ''
    return f"{t[8:10]}:{t[10:12]}"


channels = []

for channel in root.findall('channel'):
    channel_id = channel.get('id')
    display_names = channel.findall('display-name')
    name = display_names[0].text if display_names else ''
    aliases = list(dict.fromkeys(dn.text for dn in display_names if dn.text and dn.text != name))

    programmes = []
    for programme in root.findall('programme'):
        if programme.get('channel') == channel_id:
            programmes.append(programme)

    last_program_time = ''
    if programmes:
        programmes.sort(key=lambda p: p.get('stop'), reverse=True)
        stop_time = programmes[0].get('stop')
        if stop_time:
            year = stop_time[:4]
            month = stop_time[4:6]
            day = stop_time[6:8]
            hour = stop_time[8:10]
            minute = stop_time[10:12]
            last_program_time = f"{year}-{month}-{day} {hour}:{minute}"

    description_coverage = 0
    if programmes:
        programmes_with_desc = [p for p in programmes if p.find('desc') is not None]
        description_coverage = round((len(programmes_with_desc) / len(programmes)) * 100)

    today_programmes = []
    for p in programmes:
        start = p.get('start', '')
        if start and start[:8] == today:
            today_programmes.append(p)

    has_gap = False
    gap_details = ''
    gap_list = []
    if len(today_programmes) >= 2:
        intervals = []
        for p in today_programmes:
            s = p.get('start', '')
            e = p.get('stop', '')
            if s and e and len(s) >= 12 and len(e) >= 12:
                s_min = int(s[8:10]) * 60 + int(s[10:12])
                e_min = int(e[8:10]) * 60 + int(e[10:12])
                if e_min > s_min:
                    intervals.append((s_min, e_min))
        if intervals:
            intervals.sort()
            merged = [intervals[0]]
            for s, e in intervals[1:]:
                if s <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append((s, e))
            gaps = []
            for i in range(len(merged) - 1):
                gap_min = merged[i + 1][0] - merged[i][1]
                if gap_min >= 5:
                    gaps.append(gap_min)
                    gap_list.append({
                        'after': '{:02d}:{:02d}'.format(*divmod(merged[i][1], 60)),
                        'before': '{:02d}:{:02d}'.format(*divmod(merged[i + 1][0], 60)),
                        'minutes': gap_min
                    })
            if gaps:
                has_gap = True
                gap_details = f"{len(gaps)}处断层(最长{max(gaps)}分钟)"

    today_schedule = []
    for p in today_programmes:
        start = p.get('start', '')
        stop = p.get('stop', '')
        title_el = p.find('title')
        desc_el = p.find('desc')
        today_schedule.append({
            'start': _fmt_time(start),
            'stop': _fmt_time(stop),
            'title': title_el.text if title_el is not None else '',
            'desc': desc_el.text if desc_el is not None else ''
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
        'updateTime': time.time()
    }, f, ensure_ascii=False, indent=2)

print(f'Coverage calculation completed. {len(channels)} channels.')
