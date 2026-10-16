"""Retrieve permitted feed metadata; produce cautious, source-linked news digests.

No article scraping, no AI-generated details, no copying media photographs.
Google News is a discovery feed; its headline is not independent verification.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse, urlencode, urlsplit, urlunsplit, parse_qsl
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
try:
    import feedparser
except ImportError:
    feedparser = None
    from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/articles.json'
FEEDS = ROOT / 'config/feeds.json'
IMAGES = ROOT / 'config/image_map.json'
SETTINGS = ROOT / 'config/settings.json'
TZ = ZoneInfo('Asia/Taipei')
UA = 'MotorDaily/1.0 (GitHub Pages educational news index; attribution and source links)'
LOG = logging.getLogger('motor-daily')

AUTO = ('汽車','機車','重機','新車','駕照','罰鍰','違規','車輛','車廠','交通','國道','電動車','測速','行車','牌照','召回','Toyota','Honda','BMW','Tesla','Hyundai','Kia','Mazda','Ford','Nissan','Subaru','Lexus','Yamaha','SYM','KYMCO','Gogoro','保時捷','豐田','本田','賓士','賓士','福斯','汽機車')
EXCLUDE = ('徵才','招標','得獎','人事任命','競賽報名','活動報名','歲末','研討會')
TW_HINTS = ('台灣','臺灣','交通部','公路局','監理','新台幣','臺北','台北','高雄','台南','臺南','車市','國內')
REGULATION_HINTS = ('修法','草案','預告','施行','上路','公告','立法院','三讀','法規','條例','罰鍰','駕照','監理')
CATEGORY_NAMES = {'new-car':'新車快訊','traffic':'交通法規','global':'全球車壇','motorcycle':'機車專區'}


def clean_text(value):
    text = BeautifulSoup(str(value or ''), 'html.parser').get_text(' ', strip=True)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def safe_url(value):
    try:
        p = urlsplit((value or '').strip())
        if p.scheme not in ('https','http') or not p.netloc or p.username or p.password:
            return ''
        return urlunsplit((p.scheme,p.netloc,p.path,p.query,''))
    except ValueError:
        return ''


def normalized_url(url):
    p = urlsplit(url)
    keep = [(k,v) for k,v in parse_qsl(p.query) if not k.startswith('utm_') and k not in ('fbclid','gclid')]
    return urlunsplit((p.scheme.lower(),p.netloc.lower().removeprefix('www.'),p.path.rstrip('/'),urlencode(keep),''))


def to_datetime(entry):
    for candidate in (entry.get('published'), entry.get('updated')):
        if not candidate: continue
        try:
            dt = parsedate_to_datetime(candidate)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(TZ)
        except (ValueError, TypeError, IndexError):
            try:
                dt = datetime.fromisoformat(candidate.replace('Z','+00:00'))
                return dt.replace(tzinfo=timezone.utc).astimezone(TZ) if dt.tzinfo is None else dt.astimezone(TZ)
            except ValueError:
                pass
    return None


def extract_feed(xml_data):
    if feedparser:
        result = feedparser.parse(xml_data)
        entries = []
        for e in result.entries:
            source = e.get('source', {})
            entries.append({'title':e.get('title',''), 'link':e.get('link',''),
                'summary':e.get('summary',''), 'published':e.get('published',''),
                'updated':e.get('updated',''), 'source_name':source.get('title','')})
        return entries
    root = ET.fromstring(xml_data)
    entries = []
    for node in list(root.findall('.//item')) + list(root.findall('.//{http://www.w3.org/2005/Atom}entry')):
        def val(name):
            x = node.find(name)
            return x.text if x is not None and x.text else ''
        link = val('link')
        if not link:
            a = node.find('{http://www.w3.org/2005/Atom}link')
            link = a.attrib.get('href','') if a is not None else ''
        src = node.find('source')
        entries.append({'title':val('title') or val('{http://www.w3.org/2005/Atom}title'),
                        'link':link, 'summary':val('description') or val('{http://www.w3.org/2005/Atom}summary'),
                        'published':val('pubDate') or val('{http://www.w3.org/2005/Atom}published'),
                        'source_name':(src.text or '') if src is not None else ''})
    return entries


def relevant(title, category):
    value = title.casefold()
    if len(value) < 9: return False
    if any(w.casefold() in value for w in EXCLUDE): return False
    if not any(w.casefold() in value for w in AUTO): return False
    # The global feed may pick up financial/car-maker stories; keep only automotive topics.
    if category == 'global':
        return any(w.casefold() in value for w in ('汽車','車廠','新車','電動車','召回','車款','車型','機車','車輛','駕駛','自動駕駛','Toyota','Tesla','BMW','Ford','Honda','現代汽車','保時捷'))
    return True


def classify(title, feed_category):
    title = title.casefold()
    if any(x.casefold() in title for x in ('機車','速克達','重機','gogoro','kymco','sym ','yamaha mt-','yamaha xmax')):
        return 'motorcycle'
    if any(x.casefold() in title for x in REGULATION_HINTS):
        return 'traffic'
    if feed_category == 'traffic' and any(x in title for x in ('交通','道路','國道','測速','安全','違規','公路')):
        return 'traffic'
    return feed_category


def news_score(title, category, published):
    value = title.casefold()
    score = 40
    if any(k in title for k in TW_HINTS): score += 17
    if any(k in title for k in ('正式','首發','發表','上市','公布','公告','召回','施行')): score += 8
    if category == 'traffic': score += 11
    if any(k in title for k in ('事故','召回','安全')): score += 8
    now = datetime.now(TZ)
    age = max(0,(now - published).total_seconds() / 86400)
    score += max(0, 18 - int(age * 3))
    return min(score, 100)


def policy_status(title):
    # Do not infer policy implementation from a headline; only label explicitly stated stage.
    if '草案' in title or '預告' in title or '擬' in title: return '草案／研議（依來源標題）'
    if '三讀' in title: return '三讀消息（施行日待查）'
    if '施行' in title or '正式上路' in title: return '施行消息（請核對官方日期）'
    if '公布' in title or '公告' in title: return '公告消息（不代表已施行）'
    return '施行狀態未確認'


def article_from_entry(entry, feed, now):
    title = clean_text(entry.get('title'))
    source = clean_text(entry.get('source_name')) or feed['name']
    # Google News often suffixes the headline with a source name.
    if feed['kind'] == 'google_news' and source and title.endswith(' - ' + source):
        title = title[:-(len(source)+3)].strip()
    url = safe_url(entry.get('link'))
    if not url or not relevant(title, feed['category']): return None
    published = to_datetime(entry)
    if published is None or published > now + timedelta(hours=12) or published < now - timedelta(days=15):
        return None
    category = classify(title, feed['category'])
    # Source feeds are just signals. Avoid reconstructing or inventing article body.
    desc = clean_text(entry.get('summary',''))
    if feed['kind'] == 'google_news':
        desc = ''  # Aggregator descriptions contain third-party snippets/headlines.
    else:
        desc = desc.replace(title,'').strip()
    desc = desc[:155].rsplit('。',1)[0] + '。' if len(desc) > 155 and '。' in desc[:155] else desc[:155]
    summary = desc if len(desc) >= 24 else f'本則消息主題為「{title}」。目前取得的是來源索引資訊，請點閱原文確認完整細節。'
    paragraphs = []
    if desc and len(desc) >= 24:
        paragraphs.append(desc)
        paragraphs.append('以上為來源提供的有限摘要，本站尚未對原文全文進行獨立查證，因此不補寫未公開的規格、數字或額外情節。')
    else:
        paragraphs.append(f'依「{source}」公開的新聞標題，這則消息關注「{title}」。目前可以確認的資訊僅限標題、來源及發布時間，尚不足以整理出 300～500 字的完整報導。')
        paragraphs.append('為避免不實推論，本站不會自行填入車款售價、性能數據、事件背景或市場結果。詳細資訊請參閱原始新聞連結。')
    if category == 'traffic':
        paragraphs.append(f'交通規定狀態：{policy_status(title)}。涉及罰鍰、駕照或施行日期時，仍應以主管機關最新正式公告為準。')
    elif category == 'new-car':
        paragraphs.append('新車是否在台灣正式上市、售價與配備內容，仍以原廠或台灣總代理公布資訊為準。')
    elif category == 'motorcycle':
        paragraphs.append('不同年份與市場的機車規格可能不同，台灣售價及販售資訊應以品牌在台官方資料為準。')
    else:
        paragraphs.append('國際市場的車廠政策或產品資訊，不一定直接適用台灣市場；如涉及台灣車主，仍需查核本地官方說明。')
    hashed = hashlib.sha256(normalized_url(url).encode('utf-8')).hexdigest()[:14]
    return {'id':hashed, 'title':title, 'category':category,'source_name':source,'source_url':url,
            'published':published.isoformat(), 'region':'台灣' if category != 'global' else '全球',
            'summary':summary,'paragraphs':paragraphs,'image':None,'image_credit':None,'image_page':None,
            'quality':'brief','demo':False,'score':news_score(title,category,published)}


MODEL_MATCHES = [
    r'Toyota\s+(?:GR86|GR Supra|RAV4|Corolla Cross|Camry|Yaris Cross|bZ4X)',
    r'Honda\s+(?:Civic|CR-V|HR-V|Fit)',
    r'Tesla\s+Model\s+[3YSX]',
    r'BMW\s+(?:M3|M4|X1|X3|i4|iX)',
    r'Mazda\s+(?:MX-5|CX-5|CX-30|Mazda3)',
    r'Hyundai\s+IONIQ\s+[56]',
    r'Porsche\s+(?:911|Taycan|Cayenne)',
    r'Yamaha\s+(?:MT-09|XMAX|TMAX)',
]


def find_commons_photo(article, session):
    """Only use exactly identified model photos with explicit Commons reuse licences."""
    title = article['title']
    hit = next((m.group(0) for pattern in MODEL_MATCHES if (m := re.search(pattern,title,re.I))),None)
    if not hit: return False
    year_match = re.search(r'\b20(?:1[5-9]|2[0-9])\b',title)
    year = year_match.group(0) if year_match else ''
    try:
        r = session.get('https://commons.wikimedia.org/w/api.php',params={
            'action':'query','generator':'search','gsrsearch':f'\"{hit}\"',
            'gsrnamespace':6,'gsrlimit':10,'prop':'imageinfo',
            'iiprop':'url|mime|extmetadata','iiurlwidth':1100,'format':'json'
        },timeout=9)
        r.raise_for_status()
        pages = r.json().get('query',{}).get('pages',{})
        terms = re.findall(r'[a-z0-9]+',hit.casefold())
        for page in pages.values():
            filename = page.get('title','').casefold().replace('_',' ')
            if not all(token in re.findall(r'[a-z0-9]+',filename) for token in terms): continue
            if year and year not in filename: continue
            details = (page.get('imageinfo') or [{}])[0]
            if details.get('mime') not in ('image/jpeg','image/png','image/webp'): continue
            meta = details.get('extmetadata') or {}
            lic = clean_text((meta.get('LicenseShortName') or {}).get('value',''))
            if not re.match(r'^(CC BY(?:-SA)?(?: [1-4]\.0)?|CC0(?: 1\.0)?|Public domain|PD)',lic,re.I): continue
            if re.search(r'\b(?:NC|ND)\b',lic,re.I): continue
            url = safe_url(details.get('thumburl') or details.get('url'))
            pageurl = safe_url(details.get('descriptionurl'))
            if not url or not pageurl: continue
            author = clean_text((meta.get('Artist') or {}).get('value',''))[:100] or 'Wikimedia Commons 貢獻者'
            article['image'] = url
            article['image_page'] = pageurl
            article['image_credit'] = author + ' · ' + lic
            return True
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        LOG.info('Wikimedia image skipped: %s',exc)
    return False


def try_commons_image(article, session, overrides, auto_images=False):
    """Strict, opt-in exact-model photos only. No generic photos mislabelled as specific cars.
    Manual image_map overrides are easiest to review and are recommended.
    """
    if article['category'] == 'traffic': return
    title = article['title']
    for term, data in overrides.items():
        if term.casefold() in title.casefold():
            url = safe_url(data.get('url',''))
            page = safe_url(data.get('page',''))
            credit = data.get('credit','').strip()
            if url and page and credit and data.get('license'):
                article['image'] = url
                article['image_page'] = page
                article['image_credit'] = credit + ' · ' + data['license']
                return
    # Commons photo lookup is conservative; generic, year-mismatched and unlicensed files are rejected.
    if auto_images:
        find_commons_photo(article, session)


def main():
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    now = datetime.now(TZ)
    db = json.loads(DATA.read_text(encoding='utf-8'))
    feeds = json.loads(FEEDS.read_text(encoding='utf-8'))
    manual_images = json.loads(IMAGES.read_text(encoding='utf-8'))
    settings = json.loads(SETTINGS.read_text(encoding='utf-8'))
    existing = [a for a in db.get('articles',[]) if not a.get('demo')]
    known_urls = {normalized_url(a.get('source_url','')) for a in existing}
    known_titles = {re.sub(r'\W','',a.get('title','')).casefold() for a in existing}
    session = requests.Session()
    session.headers.update({'User-Agent':UA, 'Accept':'application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.3'})
    fetched = 0
    searched_photos = 0
    photo_limit = max(0,int(settings.get('max_commons_requests_per_run',5)))
    new_articles = []
    for feed in feeds:
        try:
            r = session.get(feed['url'],timeout=14)
            r.raise_for_status()
            entries = extract_feed(r.content)
            if not entries: raise ValueError('RSS feed has no entries')
            LOG.info('%s: %s entries',feed['name'],len(entries))
            fetched += 1
            for entry in entries[:24]:
                article = article_from_entry(entry,feed,now)
                if not article: continue
                norm = normalized_url(article['source_url'])
                cleaned = re.sub(r'\W','',article['title']).casefold()
                if norm in known_urls or cleaned in known_titles: continue
                known_urls.add(norm); known_titles.add(cleaned)
                allow_photo = bool(settings.get('enable_commons_photos',True)) and searched_photos < photo_limit
                if allow_photo and any(re.search(pattern,article['title'],re.I) for pattern in MODEL_MATCHES):
                    searched_photos += 1
                try_commons_image(article,session,manual_images,allow_photo)
                new_articles.append(article)
        except (requests.RequestException,ValueError,ET.ParseError if feedparser is None else ValueError) as exc:
            LOG.warning('Cannot read %s: %s',feed['name'],exc)
        time.sleep(0.2)
    if fetched:
        new_articles.sort(key=lambda a:(a['score'],a['published']),reverse=True)
        # Prevent a one-time ingestion from overwhelming the site.
        new_articles = new_articles[:24]
        merged = new_articles + existing
        merged.sort(key=lambda a:a.get('published',''), reverse=True)
        db['articles'] = merged[:120]
        db['last_success'] = now.isoformat()
        LOG.info('%d new, %d stored',len(new_articles),len(db['articles']))
    else:
        LOG.warning('All feeds unavailable; preserving last successful content')
    db['last_checked'] = now.isoformat()
    DATA.write_text(json.dumps(db,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if not fetched:
        # Retaining the old news is safer than publishing an empty page.
        return 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
