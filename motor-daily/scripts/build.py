"""Generate complete GitHub Pages site from data/articles.json. No runtime server needed."""
from __future__ import annotations
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'dist'
TPE = ZoneInfo('Asia/Taipei')
CATEGORIES = [
    {'key':'new-car','name':'新車快訊','en':'NEW CAR RELEASES','caption':'車款發表、台灣上市、售價與改款資訊','index':1,'art':'hero-car.svg'},
    {'key':'traffic','name':'交通法規','en':'TAIWAN TRAFFIC POLICY','caption':'台灣道路政策、罰鍰、駕照及監理新制','index':2,'art':'hero-traffic.svg'},
    {'key':'global','name':'全球車壇','en':'GLOBAL MOTOR INDUSTRY','caption':'車企合作、產業發展及重大安全資訊','index':3,'art':'hero-global.svg'},
    {'key':'motorcycle','name':'機車專區','en':'TWO WHEEL CULTURE','caption':'速克達、重機、機車新車及產業動態','index':4,'art':'hero-moto.svg'},
]
LOOKUP = {a['key']:a for a in CATEGORIES}


def date_format(iso):
    if not iso: return '未提供'
    try:
        dt = datetime.fromisoformat(iso.replace('Z','+00:00'))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TPE).strftime('%Y.%m.%d')
    except (TypeError,ValueError):
        return '日期待確認'


def prepare_article(a):
    a = dict(a)
    category = LOOKUP.get(a.get('category'),LOOKUP['global'])
    a['category_name'] = category['name']
    a['art'] = category['art']
    a['date_text'] = date_format(a.get('published'))
    a['summary'] = a.get('summary','')
    a['paragraphs'] = [p for p in a.get('paragraphs',[]) if p]
    # Do not leak unsafe, non-http URLs into links or image src.
    from update_news import safe_url
    a['source_url'] = safe_url(a.get('source_url'))
    a['image'] = safe_url(a.get('image'))
    a['image_page'] = safe_url(a.get('image_page'))
    return a


def write(path, contents):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(contents,encoding='utf-8')


def main():
    db = json.loads((ROOT/'data/articles.json').read_text(encoding='utf-8'))
    articles = [prepare_article(a) for a in db.get('articles',[]) if a.get('id') and a.get('title') and a.get('category') in LOOKUP]
    articles.sort(key=lambda a:a.get('published',''),reverse=True)
    if DEST.exists(): shutil.rmtree(DEST)
    DEST.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'assets',DEST/'assets')
    env = Environment(loader=FileSystemLoader(ROOT/'templates'),autoescape=select_autoescape(['html','xml']))
    now = datetime.now(TPE)
    last = db.get('last_success')
    common = {'categories':CATEGORIES,'year':now.year,'display_date':now.strftime('%Y.%m.%d'),
              'last_success_text':date_format(last) if last else '尚未完成第一次自動更新',
              'demo_mode':any(a.get('demo') for a in articles)}
    featured = max(articles,key=lambda a:(a.get('score',0),a.get('published',''))) if articles else None
    side = [a for a in sorted(articles,key=lambda a:(a.get('score',0),a.get('published','')),reverse=True) if a is not featured][:2]
    home = env.get_template('home.html').render(**common,active='all',root='./',hero=featured,top_side=side,
                         articles=articles[:12],issue=now.strftime('%m.%d'))
    write(DEST/'index.html',home)
    for c in CATEGORIES:
        content = env.get_template('category.html').render(**common,root='../../',active=c['key'],category=c,
                     articles=[a for a in articles if a['category']==c['key']])
        write(DEST/'category'/c['key']/'index.html',content)
    for a in articles:
        related = [b for b in articles if b['id']!=a['id']]
        related.sort(key=lambda b:(b['category']==a['category'],b['published']),reverse=True)
        html = env.get_template('article.html').render(**common,root='../../',active=a['category'],article=a,related=related[:3],
                  description=a['summary'][:150])
        write(DEST/'article'/a['id']/'index.html',html)
    write(DEST/'.nojekyll','')
    write(DEST/'robots.txt','User-agent: *\nAllow: /\n')
    print(f'Built {len(articles)} articles and {len(CATEGORIES)} categories at {DEST}')

if __name__=='__main__': main()
