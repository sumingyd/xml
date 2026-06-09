#!/usr/bin/env python3
"""
合并days/目录下所有日期EPG文件到完整EPG文件

由GitHub Actions工作流调用：
1. 清理days/目录中过期的日期文件
2. 合并所有日期文件为完整的epg.xml
3. 移除没有节目的空频道
"""
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
from collections import OrderedDict
import os
import sys
import glob

HISTORY_DAYS = 7
DAYS_DIR = 'days'

CATEGORY_ORDER = ['央视', '卫视', '4K超高清', '付费', '国际', '省级', '市级', '县级', '其他']

CATEGORY_RULES = OrderedDict([
    ('央视', [
        r'^CCTV-(?!4 (美洲|欧洲))', r'^中国中央',
    ]),
    ('卫视', [
        r'^.{2,3}卫视$', r'^.{2,3}卫视-',
    ]),
    ('4K超高清', [
        r'4K', r'超高清',
    ]),
    ('付费', [
        r'^CHC', r'^CCTV(?!-(\d+\+?|\d+ ))', r'^金鹰卡通$', r'^卡酷少儿$', r'^精彩影视$', r'^都市剧场$',
        r'^金鹰纪实$', r'^北京纪实科教$', r'^法治天地$', r'^中国教育', r'^中学生$',
        r'^求索纪录$', r'^游戏风云$', r'^生活时尚$', r'^动漫秀场$', r'^东方财经$',
        r'^财富天下$', r'^中国交通$', r'^乐游$', r'^快乐垂钓$', r'^四海钓鱼$',
        r'^文物宝库$', r'^梨园$', r'^武术世界$', r'^汽摩$', r'^海洋频道$',
        r'^环球旅游$', r'^生态环境$', r'^茶$', r'^金色学堂$', r'^书画$',
        r'^优漫卡通$', r'^新动漫$', r'^嘉佳卡通$', r'^优优宝贝$', r'^中华特产$',
        r'^重温经典影视$', r'^居家购物$', r'^风云音乐$', r'^风云剧场$', r'^第一剧场$',
        r'^怀旧剧场$', r'^世界地理$', r'^发现之旅$', r'^老故事$', r'^兵器科技$',
        r'^女性时尚$', r'^摄影频道$', r'^天翼高清$', r'^书画频道$', r'^国学频道$',
        r'^戏曲频道$', r'^音乐频道$', r'^电影频道$', r'^电视指南$',
        r'^天元围棋$', r'^环球奇观$', r'^现代女性$', r'^中医药$', r'^国学$',
        r'^多彩文体$', r'^聚鲨环球精选$', r'^趯球$',
    ]),
    ('国际', [
        r'^CCTV-4 (美洲|欧洲)', r'^CGTN',
    ]),
])

PROVINCES = ['北京', '天津', '上海', '重庆',
             '河北', '山西', '辽宁', '吉林', '黑龙江',
             '江苏', '浙江', '安徽', '福建', '江西', '山东',
             '河南', '湖北', '湖南', '广东', '海南',
             '四川', '贵州', '云南', '陕西', '甘肃', '青海',
             '内蒙古', '广西', '西藏', '宁夏', '新疆']

PREFECTURES = {
    '北京': ['北京'],
    '天津': ['天津'],
    '上海': ['上海'],
    '重庆': ['重庆'],
    '河北': ['石家庄', '唐山', '秦皇岛', '邯郸', '邢台', '保定', '张家口',
             '承德', '沧州', '廊坊', '衡水'],
    '山西': ['太原', '大同', '阳泉', '长治', '晋城', '朔州', '晋中',
             '运城', '忻州', '临汾', '吕梁'],
    '辽宁': ['沈阳', '大连', '鞍山', '抚顺', '本溪', '丹东', '锦州',
             '营口', '阜新', '辽阳', '盘锦', '铁岭', '朝阳', '葫芦岛'],
    '吉林': ['长春', '吉林', '四平', '辽源', '通化', '白山', '松原',
             '白城', '延边'],
    '黑龙江': ['哈尔滨', '齐齐哈尔', '牡丹江', '佳木斯', '大庆', '鸡西',
               '双鸭山', '伊春', '七台河', '鹤岗', '绥化', '黑河', '大兴安岭'],
    '江苏': ['南京', '无锡', '徐州', '常州', '苏州', '南通', '连云港',
             '淮安', '盐城', '扬州', '镇江', '泰州', '宿迁'],
    '浙江': ['杭州', '宁波', '温州', '嘉兴', '湖州', '绍兴', '金华',
             '衢州', '舟山', '台州', '丽水'],
    '安徽': ['合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '淮北', '铜陵',
             '安庆', '黄山', '阜阳', '宿州', '滁州', '六安', '宣城',
             '池州', '亳州'],
    '福建': ['福州', '厦门', '莆田', '三明', '泉州', '漳州', '南平',
             '龙岩', '宁德'],
    '江西': ['南昌', '景德镇', '萍乡', '九江', '新余', '鹰潭', '赣州',
             '吉安', '宜春', '抚州', '上饶'],
    '山东': ['济南', '青岛', '淄博', '枣庄', '东营', '烟台', '潍坊',
             '济宁', '泰安', '威海', '日照', '临沂', '德州', '聊城',
             '滨州', '菏泽', '莱芜'],
    '河南': ['郑州', '开封', '洛阳', '平顶山', '安阳', '鹤壁', '新乡',
             '焦作', '濮阳', '许昌', '漯河', '三门峡', '南阳', '商丘',
             '信阳', '周口', '驻马店', '济源'],
    '湖北': ['武汉', '黄石', '十堰', '宜昌', '襄阳', '鄂州', '荆门',
             '孝感', '荆州', '黄冈', '咸宁', '随州', '恩施'],
    '湖南': ['长沙', '株洲', '湘潭', '衡阳', '邵阳', '岳阳', '常德',
             '张家界', '益阳', '郴州', '永州', '怀化', '娄底', '湘西'],
    '广东': ['广州', '深圳', '珠海', '汕头', '佛山', '韶关', '湛江',
             '肇庆', '江门', '茂名', '惠州', '梅州', '汕尾', '河源',
             '阳江', '清远', '东莞', '中山', '潮州', '揭阳', '云浮'],
    '海南': ['海口', '三亚', '三沙', '儋州'],
    '四川': ['成都', '自贡', '攀枝花', '泸州', '德阳', '绵阳', '广元',
             '遂宁', '内江', '乐山', '南充', '眉山', '宜宾', '广安',
             '达州', '雅安', '巴中', '资阳', '阿坝', '甘孜', '凉山'],
    '贵州': ['贵阳', '六盘水', '遵义', '安顺', '毕节', '铜仁',
             '黔西南', '黔东南', '黔南'],
    '云南': ['昆明', '曲靖', '玉溪', '保山', '昭通', '丽江', '普洱',
             '临沧', '楚雄', '红河', '文山', '西双版纳', '大理',
             '德宏', '怒江', '迪庆'],
    '陕西': ['西安', '铜川', '宝鸡', '咸阳', '渭南', '延安', '汉中',
             '榆林', '安康', '商洛'],
    '甘肃': ['兰州', '嘉峪关', '金昌', '白银', '天水', '武威', '张掖',
             '平凉', '酒泉', '庆阳', '定西', '陇南', '临夏', '甘南'],
    '青海': ['西宁', '海东', '海北', '海南', '黄南', '果洛', '玉树', '海西'],
    '内蒙古': ['呼和浩特', '包头', '乌海', '赤峰', '通辽', '鄂尔多斯',
               '呼伦贝尔', '巴彦淖尔', '乌兰察布', '兴安', '锡林郭勒',
               '阿拉善'],
    '广西': ['南宁', '柳州', '桂林', '梧州', '北海', '防城港', '钦州',
             '贵港', '玉林', '百色', '贺州', '河池', '来宾', '崇左'],
    '西藏': ['拉萨', '日喀则', '昌都', '林芝', '山南', '那曲', '阿里'],
    '宁夏': ['银川', '石嘴山', '吴忠', '固原', '中卫'],
    '新疆': ['乌鲁木齐', '克拉玛依', '吐鲁番', '哈密', '昌吉', '博尔塔拉',
             '巴音郭楞', '阿克苏', '克孜勒苏', '喀什', '和田', '伊犁',
             '塔城', '阿勒泰', '石河子', '五家渠', '阿拉尔',
             '图木舒克', '北屯', '铁门关', '双河', '可克达拉',
             '昆玉', '胡杨河', '新星'],
}

MUNICIPAL_PROVINCES = {'北京', '天津', '上海', '重庆'}


def _match_province(name):
    for prov in PROVINCES:
        if name.startswith(prov):
            return prov
    return None


def _match_prefecture(name):
    for prov, cities in PREFECTURES.items():
        for city in cities:
            if name.startswith(city):
                return prov, city
    return None


def classify_channel(name):
    if not name:
        return '其他'
    for category, patterns in CATEGORY_RULES.items():
        for pattern in patterns:
            if re.search(pattern, name):
                return category
    if re.search(r'广播$', name):
        return '县级'
    prov = _match_province(name)
    if prov:
        rest = name[len(prov):]
        if rest.startswith('卫视'):
            return '卫视'
        if prov in MUNICIPAL_PROVINCES:
            if not rest or rest in ('综合广播', '经济广播', '交通广播'):
                return '省级'
            return '市级'
        if not rest or rest in ('齐鲁', '新闻', '综艺', '体育', '生活', '文旅',
                                '农科', '少儿', '教育卫视', '综合广播', '经济广播',
                                '交通广播', '公共', '教育'):
            return '省级'
        return '市级'
    pref_result = _match_prefecture(name)
    if pref_result:
        prov, city = pref_result
        rest = name[len(city):]
        if not rest or re.match(r'^-\d+$', rest):
            return '市级'
        if re.search(r'^(综合|新闻|生活|公共|娱乐|综艺|影视|体育|文旅|教育|少儿|购物|科教|高新|都市|经济|文化|乡村|民生|信息|文艺|社教|国际|城市|QTV|鲁中)', rest):
            return '市级'
        return '县级'
    if re.search(r'(综合|新闻|生活|公共|娱乐|综艺|影视|体育|文旅|教育|少儿|购物|科教|高新|都市|经济|文化|乡村|民生|信息|文艺|频道|TV)$', name):
        return '市级'
    return '县级'


def get_sort_key(name):
    category = classify_channel(name)
    cat_idx = CATEGORY_ORDER.index(category) if category in CATEGORY_ORDER else len(CATEGORY_ORDER)
    sub_key = name
    m = re.match(r'^CCTV-(\d+\+?)\s', name)
    if m:
        num_str = m.group(1)
        if num_str.endswith('+'):
            sub_num = int(num_str[:-1]) + 0.5
        else:
            sub_num = int(num_str)
        sub_key = (0, sub_num, name)
    elif re.match(r'^CGTN', name):
        sub_key = (1, name)
    elif category == '央视':
        sub_key = (2, name)
    else:
        sub_key = (99, name)
    return (cat_idx, sub_key)


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

    removed_overlap = 0
    ch_programmes = {}
    for p in all_programmes:
        ch_id = p.get('channel', '')
        if ch_id not in ch_programmes:
            ch_programmes[ch_id] = []
        ch_programmes[ch_id].append(p)

    def _parse_min(t):
        if not t:
            return 0
        t = t.split()[0]
        if len(t) < 12:
            return 0
        return int(t[:8]) * 1440 + int(t[8:10]) * 60 + int(t[10:12])

    cleaned_programmes = []
    for ch_id, progs in ch_programmes.items():
        progs.sort(key=lambda p: (p.get('start', ''), _parse_min(p.get('stop', '')) - _parse_min(p.get('start', ''))))
        used = set()
        for i, p in enumerate(progs):
            if i in used:
                continue
            s1_min = _parse_min(p.get('start', ''))
            e1_min = _parse_min(p.get('stop', ''))
            main_dur = e1_min - s1_min
            if main_dur <= 0:
                cleaned_programmes.append(p)
                continue
            for j in range(i + 1, len(progs)):
                if j in used:
                    continue
                p2 = progs[j]
                s2_min = _parse_min(p2.get('start', ''))
                e2_min = _parse_min(p2.get('stop', ''))
                if s2_min >= e1_min:
                    break
                sub_dur = e2_min - s2_min
                if sub_dur < main_dur or (sub_dur == 0 and main_dur > 0):
                    used.add(j)
                    removed_overlap += 1
            cleaned_programmes.append(p)

    if removed_overlap:
        print(f"清理了 {removed_overlap} 个重叠子节目")

    def get_channel_sort_key(ch):
        display_names = ch.findall('display-name')
        name = display_names[0].text if display_names else ''
        return get_sort_key(name)

    sorted_channels = sorted(all_channels.values(), key=get_channel_sort_key)

    tv = ET.Element('tv')
    tv.set('generator-info-name', 'EPG')
    for channel in sorted_channels:
        tv.append(channel)
    for programme in cleaned_programmes:
        tv.append(programme)

    tree = ET.ElementTree(tv)
    ET.indent(tree, space='  ')
    tree.write('epg.xml', encoding='utf-8', xml_declaration=True)

    file_size = os.path.getsize('epg.xml')
    print(f"合并完成! {len(day_files)} 个日期文件, {len(all_channels)} 个频道, {len(cleaned_programmes)} 个节目, {file_size / 1024:.1f}KB")

    return True


if __name__ == '__main__':
    success = merge_epg()
    sys.exit(0 if success else 1)
