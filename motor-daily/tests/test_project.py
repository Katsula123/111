import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from email.utils import format_datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build
import update_news as news

class NewsTests(unittest.TestCase):
    def test_url_safety(self):
        self.assertEqual(news.safe_url('javascript:alert(1)'), '')
        self.assertEqual(news.safe_url('data:text/html,xx'), '')
        self.assertEqual(news.safe_url('https://example.org/a#x'),'https://example.org/a')
        self.assertNotEqual(news.safe_url('https://news.google.com/'), '')

    def test_classification(self):
        self.assertEqual(news.classify('台灣機車新款發表','new-car'),'motorcycle')
        self.assertEqual(news.classify('道路交通法規修正草案','global'),'traffic')
        self.assertEqual(news.policy_status('違規草案預告'),'草案／研議（依來源標題）')
        self.assertEqual(news.policy_status('交通新制'),'施行狀態未確認')

    def test_short_source_no_fabricated_details(self):
        when=format_datetime(datetime.now(timezone.utc))
        a=news.article_from_entry({'title':'台灣汽車新車發表消息','link':'https://example.org/real-news','published':when,'summary':'', 'source_name':'測試來源'},
             {'name':'測試','kind':'google_news','category':'new-car'},datetime.now(news.TZ))
        self.assertIsNotNone(a)
        self.assertEqual(a['quality'],'brief')
        self.assertNotIn('300匹',json.dumps(a,ensure_ascii=False))
        self.assertTrue(a['source_url'].startswith('https://'))

    def test_rss_fallback_parser(self):
        xml=b'<rss version="2.0"><channel><item><title>Toyota new car</title><link>https://example.org/1</link><pubDate>Fri, 16 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(news.extract_feed(xml)[0]['title'],'Toyota new car')

    def test_offline_update_replaces_demo_with_real_source_item(self):
        when=format_datetime(datetime.now(timezone.utc))
        xml=f'<rss version="2.0"><channel><item><title>台灣汽車新車正式發表</title><link>https://example.org/news/1</link><pubDate>{when}</pubDate><description>官方發表消息。</description></item></channel></rss>'.encode('utf-8')
        class FakeResponse:
            content=xml
            def raise_for_status(self): pass
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'feeds.json').write_text(json.dumps([{'name':'測試RSS','kind':'official','category':'new-car','url':'https://example.org/rss'}]))
            (p/'images.json').write_text('{}')
            (p/'settings.json').write_text('{"enable_commons_photos":false}')
            (p/'articles.json').write_text(json.dumps({'articles':[{'id':'demo','title':'展示','demo':True}]}))
            with patch.object(news,'DATA',p/'articles.json'), patch.object(news,'FEEDS',p/'feeds.json'), patch.object(news,'IMAGES',p/'images.json'), patch.object(news,'SETTINGS',p/'settings.json'), patch.object(news.requests.Session,'get',return_value=FakeResponse()):
                news.main()
            result=json.loads((p/'articles.json').read_text())
            self.assertEqual(len(result['articles']),1)
            self.assertFalse(result['articles'][0]['demo'])
            self.assertTrue(result['last_success'])

    def test_date_taiwan(self):
        self.assertEqual(build.date_format('2026-10-15T19:00:00+00:00'),'2026.10.16')

    def test_demo_build_and_links(self):
        build.main()
        dist=ROOT/'dist'
        self.assertTrue((dist/'index.html').exists())
        self.assertTrue((dist/'article/guide-new-car/index.html').exists())
        self.assertTrue((dist/'category/traffic/index.html').exists())
        text=(dist/'index.html').read_text(encoding='utf-8')
        self.assertIn('MOTOR',text)
        self.assertIn('網站展示模式',text)

if __name__ == '__main__': unittest.main()
