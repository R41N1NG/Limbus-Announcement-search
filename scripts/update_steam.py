import datetime as dt
import html
import json
from pathlib import Path
import re
import time
import urllib.request

APP = 1973530
TZ = dt.timezone(dt.timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]
PATTERN = r'(<script id="archive-data" type="application/json">)(.*?)(</script>)'

def fetch():
    url = f'https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={APP}&count=100&maxlength=0&feeds=steam_community_announcements&format=json'
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'LimbusNoticeArchive/1.0'})
            with urllib.request.urlopen(req, timeout=45) as response:
                payload = json.load(response)
            assert payload['appnews']['appid'] == APP
            rows = payload['appnews']['newsitems']
            assert isinstance(rows, list) and rows, '接口未返回公告'
            return rows
        except Exception:
            if attempt == 2: raise
            time.sleep(5 * (attempt + 1))

def merge(data, rows):
    known = {str(e['id']) for e in data['entries']}
    added = 0
    for row in rows:
        if row.get('feedname') != 'steam_community_announcements': continue
        gid = str(row['gid'])
        if gid in known: continue
        stamp = dt.datetime.fromtimestamp(int(row['date']), TZ)
        raw = row.get('contents', '')
        title = row['title']
        url = row['url']
        assert isinstance(raw, str) and isinstance(title, str) and url.startswith('https://')
        images = re.findall(r'\[img\](.*?)\[/img\]', raw, re.S | re.I)
        images = [u.replace('{STEAM_CLAN_IMAGE}', 'https://clan.cloudflare.steamstatic.com/images') for u in images]
        images = list(dict.fromkeys(u for u in images if u.startswith('https://')))
        plain = re.sub(r'\[img\].*?\[/img\]', '', raw, flags=re.S | re.I)
        plain = html.unescape(re.sub(r'<[^>]+>|\[/?[a-zA-Z*]+(?:=[^\]]*)?\]', '', plain)).strip()
        category = '其他公告'
        for needle, label in [('known issues','已知问题'), ('hotfix','热修'), ('scheduled','定期更新'), ('maintenance','维护'), ('extraction','提取')]:
            if needle in title.lower(): category = label; break
        data['entries'].append(dict(id=gid, title_zh=title, title_en=title,
            published_at=stamp.isoformat(), published_display_date=stamp.strftime('%Y-%m-%d'),
            update_date_label='', category=category, summary_zh='',
            reading_status='自动收录英文原文；尚未关联零协译文', tags=[],
            body_text=plain, contents_raw=raw, source_url=url, official_images=images,
            chinese_sources=[], special_note=False, full_text_archived=True))
        known.add(gid); added += 1
    data['entries'].sort(key=lambda e: e['published_at'], reverse=True)
    assert len(known) == len(data['entries'])
    return added

def main():
    page = (ROOT / 'index.html').read_text(encoding='utf-8')
    data = json.loads(re.search(PATTERN, page, re.S)[2])
    added = merge(data, fetch())
    now = dt.datetime.now(TZ).strftime('%Y-%m-%d %H:%M')
    data['last_automatic_check'] = now
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    page = re.sub(PATTERN, lambda m: m[1] + payload + m[3], page, flags=re.S)
    notice = f'<div class="notice"><strong>已收录{len(data["entries"])}条Steam公告。</strong><br>最近自动检查：{now}（北京时间）。自动更新仅收录Steam英文原文；中文译文关联及特殊备注仍需人工核对。图片文字无法搜索。</div>'
    page = re.sub(r'<div class="notice">.*?</div>', notice, page, flags=re.S)
    assert len(json.loads(re.search(PATTERN, page, re.S)[2])['entries']) == len(data['entries'])
    for name in ['index.html', 'Steam公告查阅库.html']:
        temporary = ROOT / (name + '.tmp')
        temporary.write_text(page, encoding='utf-8')
        temporary.replace(ROOT / name)
    print(f'本次新增 {added} 条；总计 {len(data["entries"])} 条。')

if __name__ == '__main__': main()
