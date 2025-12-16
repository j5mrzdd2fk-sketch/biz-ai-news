#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIニュースポータル - Webアプリケーション
"""

import os
import sys
import traceback
import hashlib
import urllib.parse
import re
from flask import Flask, render_template, jsonify, request, Response, abort, make_response
from datetime import datetime

# 親ディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gspread
from google.oauth2.credentials import Credentials

# ログ設定
from logger_config import get_webapp_logger, log_exception

app = Flask(__name__)

# テンプレートの自動リロードを有効化（開発時）
app.config['TEMPLATES_AUTO_RELOAD'] = True

# ロガーを初期化
logger = get_webapp_logger()

# 設定
SPREADSHEET_NAME = "AIニュース要約（マルチサイト）"

# 環境変数から認証情報を取得（Render用）
# 環境変数が設定されている場合はそれを使用、なければファイルから読み込む
GOOGLE_SHEETS_TOKEN = os.getenv('GOOGLE_SHEETS_TOKEN')
GOOGLE_SHEETS_CREDENTIALS = os.getenv('GOOGLE_SHEETS_CREDENTIALS')

# トークンファイルのパス（ローカル環境用）
TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.json")
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.file']


def generate_article_id(title, date, source):
    """記事の一意のIDを生成（タイトル、日付、ソースから）"""
    # タイトル、日付、ソースを組み合わせてハッシュ化
    combined = f"{title}|{date}|{source}"
    # SHA256ハッシュを生成し、最初の16文字を使用
    article_id = hashlib.sha256(combined.encode('utf-8')).hexdigest()[:16]
    return article_id


def parse_date_to_datetime(date_str):
    """日付文字列をdatetimeオブジェクトに変換（ソート用）"""
    if not date_str:
        return datetime(1900, 1, 1)  # 日付がない場合は非常に古い日付として扱う
    
    # 様々な日付形式に対応
    date_formats = [
        "%Y年%m月%d日 %H時%M分",  # 2025年12月9日 15時30分
        "%Y年%m月%d日",            # 2025年12月9日
        "%Y-%m-%d %H:%M:%S",       # 2025-12-09 15:30:00
        "%Y-%m-%d",                # 2025-12-09
        "%Y/%m/%d %H:%M:%S",       # 2025/12/09 15:30:00
        "%Y/%m/%d",                # 2025/12/09
    ]
    
    # 時刻部分を分離
    if "時" in date_str and "分" in date_str:
        # 2025年12月9日 15時30分 の形式
        try:
            # 日付部分と時刻部分を分離
            if " " in date_str:
                date_part, time_part = date_str.split(" ", 1)
            else:
                date_part = date_str
                time_part = ""
            
            # 時刻を抽出
            hour = 0
            minute = 0
            if time_part:
                hour_match = re.search(r'(\d+)時', time_part)
                minute_match = re.search(r'(\d+)分', time_part)
                if hour_match:
                    hour = int(hour_match.group(1))
                if minute_match:
                    minute = int(minute_match.group(1))
            
            # 日付をパース
            date_only = re.sub(r'\d+時\d+分', '', date_part).strip()
            for fmt in ["%Y年%m月%d日", "%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    parsed_date = datetime.strptime(date_only, fmt)
                    return parsed_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                except ValueError:
                    continue
        except Exception:
            pass
    
    # 通常の日付形式を試す
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # 正規表現で抽出を試みる
    date_match = re.search(r'(\d{4})[/年-](\d{1,2})[/月-](\d{1,2})', date_str)
    if date_match:
        year, month, day = date_match.groups()
        try:
            return datetime(int(year), int(month), int(day))
        except ValueError:
            pass
    
    # パースできない場合は非常に古い日付として扱う
    return datetime(1900, 1, 1)


def convert_to_iso8601(date_str):
    """日付文字列をISO 8601形式に変換"""
    if not date_str:
        return None
    
    # parse_date_to_datetimeを使って変換
    parsed_date = parse_date_to_datetime(date_str)
    
    # デフォルト日付の場合はNoneを返す
    if parsed_date == datetime(1900, 1, 1):
        return None
    
    # ISO 8601形式に変換（JST: UTC+9）
    return parsed_date.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def get_sheets_client():
    """Google Sheets クライアントを取得"""
    try:
        import json
        
        # 環境変数から認証情報を取得（Render用）
        if GOOGLE_SHEETS_TOKEN:
            # 環境変数からトークンを読み込む
            token_data = json.loads(GOOGLE_SHEETS_TOKEN)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            logger.info("環境変数からGoogle認証情報を読み込みました")
        elif os.path.exists(TOKEN_FILE):
            # ローカル環境: ファイルから読み込む
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            logger.info("ファイルからGoogle認証情報を読み込みました")
        else:
            raise FileNotFoundError("Google認証情報が見つかりません。環境変数GOOGLE_SHEETS_TOKENまたはtoken.jsonファイルが必要です。")
        
        return gspread.authorize(creds)
    except FileNotFoundError as e:
        log_exception(logger, e, "Google Sheets認証ファイルが見つかりません")
        raise
    except json.JSONDecodeError as e:
        log_exception(logger, e, "Google認証情報のJSON解析エラー")
        raise ValueError("GOOGLE_SHEETS_TOKENの形式が正しくありません") from e
    except Exception as e:
        log_exception(logger, e, "Google Sheets認証エラー")
        raise


# キャッシュ用のグローバル変数
_news_cache = None
_cache_timestamp = None
CACHE_DURATION = 60  # 1分間キャッシュ（短縮して最新データを反映しやすく）

def get_all_news(use_cache=True):
    """全ニュースを取得（キャッシュ機能付き）"""
    global _news_cache, _cache_timestamp
    
    import time
    current_time = time.time()
    
    # キャッシュが有効な場合は返す
    if use_cache and _news_cache is not None and _cache_timestamp is not None:
        if current_time - _cache_timestamp < CACHE_DURATION:
            return _news_cache
    
    try:
        client = get_sheets_client()
        spreadsheet = client.open(SPREADSHEET_NAME)
        logger.debug("スプレッドシートを開きました")
    except Exception as e:
        log_exception(logger, e, "スプレッドシートオープンエラー")
        raise
    
    all_news = []
    
    # バッチでデータを取得（パフォーマンス改善）
    try:
        for worksheet in spreadsheet.worksheets():
            category = worksheet.title
            try:
                # get_all_values()は一度に全データを取得（効率的）
                rows = worksheet.get_all_values()
                
                # ヘッダーをスキップ
                for row in rows[1:]:
                    if len(row) >= 7:
                        # スコアを数値に変換
                        score_str = row[5] if len(row) > 5 else ""
                        score = score_str.count("⭐")
                        
                        # URLを取得（I列に実URLがあればそれを使用、なければGoogle検索リンク）
                        url = ""
                        if len(row) > 8 and row[8].startswith("http"):
                            url = row[8]
                        elif len(row) > 7 and row[7].startswith("http"):
                            url = row[7]
                        else:
                            # Google検索リンクを生成
                            title = row[2]
                            url = f"https://www.google.com/search?q={urllib.parse.quote(title)}"
                        
                        # カテゴリを取得（J列に複数カテゴリがあればそれを使用、なければシート名）
                        article_category = category
                        if len(row) > 9 and row[9]:
                            article_category = row[9]  # J列のカテゴリ情報
                        
                        # 記事IDを生成
                        article_id = generate_article_id(row[2], row[3], row[1])
                        
                        news_item = {
                            "id": article_id,
                            "no": row[0],
                            "source": row[1],
                            "title": row[2],
                            "date": row[3],
                            "tags": row[4],
                            "score": score,
                            "score_display": score_str,
                            "summary": row[6],
                            "url": url,
                            "category": article_category  # 複数カテゴリの場合はカンマ区切り
                        }
                        all_news.append(news_item)
            except Exception as e:
                log_exception(logger, e, f"シート「{category}」のデータ取得エラー")
                # エラーが発生しても他のシートの処理は続行
                continue
        
        # 日付順（新しい順）、同日内はスコア順でソート
        # 日付をdatetimeオブジェクトに変換してからソート
        all_news.sort(key=lambda x: (parse_date_to_datetime(x["date"]), x["score"]), reverse=True)
        
        # キャッシュに保存
        _news_cache = all_news
        _cache_timestamp = current_time
        
        logger.info(f"ニュースデータを取得しました: {len(all_news)}件")
        return all_news
    except Exception as e:
        log_exception(logger, e, "ニュースデータ取得エラー")
        raise


@app.route('/')
def index():
    """トップページ"""
    try:
        # キャッシュを無視するパラメータがあれば強制更新
        force_refresh = request.args.get('refresh', '').lower() == 'true'
        if force_refresh:
            logger.info("キャッシュを無視してニュースデータを強制更新")
        news_list = get_all_news(use_cache=not force_refresh)
    except Exception as e:
        log_exception(logger, e, "トップページ表示エラー")
        # エラー時は空のリストを返す
        news_list = []
        logger.error("ニュースデータの取得に失敗しました。空のリストを返します。")
    
    # カテゴリを抽出（複数カテゴリの場合は分割）
    categories_set = set()
    for n in news_list:
        for cat in [c.strip() for c in n["category"].split(",")]:
            categories_set.add(cat)
    
    # カテゴリの表示順序を固定（優先順位順、「その他」を最後に）
    # データに存在しなくても、固定カテゴリリストを表示
    category_order = [
        "企業効率化",
        "DX・デジタル化",
        "企業導入",
        "AI・テクノロジー"
    ]
    
    # 固定カテゴリリストを常に表示（データに存在しない場合でも）
    categories = category_order.copy()
    # 固定順序にないカテゴリも追加（「その他」以外）
    for cat in sorted(categories_set):
        if cat not in categories and cat != "その他":
            categories.append(cat)
    
    # 「その他」を最後に追加
    if "その他" in categories_set:
        categories.append("その他")
    
    # フィルタパラメータ
    category_filter = request.args.get('category', '')
    score_filter = request.args.get('score', '')
    search_query = request.args.get('q', '')
    sort_by = request.args.get('sort', 'date')  # ソート順: date, score, category, source
    page = request.args.get('page', 1, type=int)
    per_page = 30  # 1ページあたりの件数
    
    # フィルタリング
    filtered_news = news_list
    
    if category_filter:
        # 複数カテゴリ（カンマ区切り）に対応
        filtered_news = [n for n in filtered_news 
                        if category_filter in [cat.strip() for cat in n["category"].split(",")]]
    
    if score_filter:
        min_score = int(score_filter)
        filtered_news = [n for n in filtered_news if n["score"] >= min_score]
    
    if search_query:
        query_lower = search_query.lower()
        filtered_news = [n for n in filtered_news if 
                        query_lower in n["title"].lower() or 
                        query_lower in n["summary"].lower() or
                        query_lower in n["tags"].lower()]
    
    # ソート機能
    if sort_by == 'score':
        filtered_news.sort(key=lambda x: (x["score"], parse_date_to_datetime(x["date"])), reverse=True)
    elif sort_by == 'category':
        filtered_news.sort(key=lambda x: (x["category"], parse_date_to_datetime(x["date"])), reverse=True)
    elif sort_by == 'source':
        filtered_news.sort(key=lambda x: (x["source"], parse_date_to_datetime(x["date"])), reverse=True)
    else:  # date (デフォルト)
        filtered_news.sort(key=lambda x: (parse_date_to_datetime(x["date"]), x["score"]), reverse=True)
    
    # ページネーション
    total_filtered = len(filtered_news)
    total_pages = (total_filtered + per_page - 1) // per_page  # 切り上げ
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_news = filtered_news[start_idx:end_idx]
    
    response = make_response(render_template('index.html', 
                          news_list=paginated_news, 
                          categories=categories,
                          current_category=category_filter,
                          current_score=score_filter,
                          current_search=search_query,
                          current_sort=sort_by,
                          total_count=len(news_list),
                          filtered_count=total_filtered,
                          current_page=page,
                          total_pages=total_pages,
                          per_page=per_page))
    
    # キャッシュを防ぐヘッダーを追加
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


@app.route('/api/news')
def api_news():
    """ニュース一覧API"""
    try:
        news_list = get_all_news()
        logger.debug(f"API: ニュース一覧を返却: {len(news_list)}件")
        return jsonify(news_list)
    except Exception as e:
        log_exception(logger, e, "API: ニュース一覧取得エラー")
        return jsonify({"error": "ニュースデータの取得に失敗しました"}), 500


@app.route('/api/stats')
def api_stats():
    """統計情報API"""
    try:
        news_list = get_all_news()
        
        # カテゴリ別集計
        category_counts = {}
        source_counts = {}
        score_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        
        for news in news_list:
            cat = news["category"]
            src = news["source"]
            score = news["score"]
            
            category_counts[cat] = category_counts.get(cat, 0) + 1
            source_counts[src] = source_counts.get(src, 0) + 1
            if score in score_counts:
                score_counts[score] += 1
        
        logger.debug(f"API: 統計情報を返却: 総数{len(news_list)}件")
        return jsonify({
            "total": len(news_list),
            "by_category": category_counts,
            "by_source": source_counts,
            "by_score": score_counts
        })
    except Exception as e:
        log_exception(logger, e, "API: 統計情報取得エラー")
        return jsonify({"error": "統計情報の取得に失敗しました"}), 500


@app.route('/privacy')
def privacy():
    """プライバシーポリシー"""
    return render_template('privacy.html')


@app.route('/about')
def about():
    """運営者情報"""
    return render_template('about.html')


@app.route('/contact')
def contact():
    """お問い合わせ"""
    return render_template('contact.html')


@app.route('/article/<article_id>')
def article_detail(article_id):
    """記事詳細ページ"""
    try:
        news_list = get_all_news()
        
        # 記事IDで記事を検索
        article = None
        for news in news_list:
            if news.get("id") == article_id:
                article = news
                break
        
        if not article:
            logger.warning(f"記事が見つかりません: article_id={article_id}")
            abort(404)
        
        # 関連記事を取得（同じカテゴリの記事、最大5件）
        related_articles = []
        article_categories = [cat.strip() for cat in article["category"].split(",")]
        for news in news_list:
            if news.get("id") != article_id:
                news_categories = [cat.strip() for cat in news["category"].split(",")]
                # カテゴリが重複している記事を関連記事として追加
                if any(cat in news_categories for cat in article_categories):
                    related_articles.append(news)
                    if len(related_articles) >= 5:
                        break
        
        # 日付順でソート
        related_articles.sort(key=lambda x: parse_date_to_datetime(x["date"]), reverse=True)
        
        # ベースURL
        base_url = request.url_root.rstrip('/')
        article_url = f"{base_url}/article/{article_id}"
        
        # 日付をISO 8601形式に変換
        iso_date = convert_to_iso8601(article.get("date", ""))
        
        logger.info(f"記事詳細ページを表示: article_id={article_id}, title={article['title'][:50]}")
        
        return render_template('article.html',
                              article=article,
                              related_articles=related_articles,
                              base_url=base_url,
                              article_url=article_url,
                              iso_date=iso_date)
    except Exception as e:
        log_exception(logger, e, f"記事詳細ページ表示エラー: article_id={article_id}")
        abort(500)


@app.route('/api/survey', methods=['POST'])
def api_survey():
    """アンケート回答を保存"""
    from datetime import datetime
    
    try:
        data = request.get_json()
        if not data:
            logger.warning("API: アンケートデータが空です")
            return jsonify({"error": "No data"}), 400
        
        # CSVファイルに保存
        survey_file = os.path.join(os.path.dirname(__file__), 'survey_results.csv')
        
        # ファイルが存在しない場合はヘッダーを追加
        file_exists = os.path.exists(survey_file)
        
        with open(survey_file, 'a', encoding='utf-8') as f:
            if not file_exists:
                f.write('timestamp,age,job,industry,source\n')
                logger.info("アンケート結果ファイルを新規作成しました")
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            age = data.get('age', '')
            job = data.get('job', '')
            industry = data.get('industry', '')
            source = data.get('source', '')
            f.write(f'{timestamp},{age},{job},{industry},{source}\n')
        
        logger.info(f"アンケート回答を保存しました: age={age}, job={job}, industry={industry}")
        return jsonify({"status": "ok"})
    except Exception as e:
        log_exception(logger, e, "API: アンケート保存エラー")
        return jsonify({"error": "アンケートの保存に失敗しました"}), 500


def get_survey_data():
    """アンケートデータを読み込んで集計"""
    import csv
    from collections import Counter
    
    survey_file = os.path.join(os.path.dirname(__file__), 'survey_results.csv')
    
    if not os.path.exists(survey_file):
        return {
            'total': 0,
            'data': [],
            'stats': {
                'age': {},
                'job': {},
                'industry': {},
                'source': {}
            }
        }
    
    data = []
    age_counts = Counter()
    job_counts = Counter()
    industry_counts = Counter()
    source_counts = Counter()
    
    with open(survey_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 古いフォーマット（industryカラムがない）に対応
            normalized_row = {
                'timestamp': row.get('timestamp', ''),
                'age': row.get('age', ''),
                'job': row.get('job', ''),
                'industry': row.get('industry', ''),
                'source': row.get('source', '')
            }
            data.append(normalized_row)
            
            if normalized_row['age']:
                age_counts[normalized_row['age']] += 1
            if normalized_row['job']:
                job_counts[normalized_row['job']] += 1
            if normalized_row['industry']:
                industry_counts[normalized_row['industry']] += 1
            if normalized_row['source']:
                source_counts[normalized_row['source']] += 1
    
    return {
        'total': len(data),
        'data': data,
        'stats': {
            'age': dict(age_counts),
            'job': dict(job_counts),
            'industry': dict(industry_counts),
            'source': dict(source_counts)
        }
    }


@app.route('/admin')
def admin():
    """管理画面"""
    survey_data = get_survey_data()
    return render_template('admin.html', survey=survey_data)


@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """キャッシュをクリア"""
    global _news_cache, _cache_timestamp
    _news_cache = None
    _cache_timestamp = None
    return jsonify({"status": "ok", "message": "キャッシュをクリアしました"})


@app.route('/api/refresh-news', methods=['POST'])
def refresh_news():
    """ニュースデータを強制的に再取得"""
    news_list = get_all_news(use_cache=False)  # キャッシュを無視して取得
    return jsonify({
        "status": "ok", 
        "message": "ニュースデータを更新しました",
        "count": len(news_list)
    })


@app.route('/sitemap.xml')
def sitemap():
    """XMLサイトマップを生成"""
    try:
        import xml.etree.ElementTree as ET
        from datetime import datetime
        
        # ルート要素を作成
        urlset = ET.Element('urlset')
        urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        
        # ホームページを含める
        base_url = 'https://biz-ai-news.onrender.com'
        
        url = ET.SubElement(urlset, 'url')
        ET.SubElement(url, 'loc').text = base_url
        ET.SubElement(url, 'lastmod').text = datetime.now().strftime('%Y-%m-%d')
        ET.SubElement(url, 'changefreq').text = 'hourly'
        ET.SubElement(url, 'priority').text = '1.0'
        
        # 記事の個別ページをサイトマップに追加（最新100件）
        try:
            news_list = get_all_news()
            for news in news_list[:100]:  # 最新100件のみ
                if news.get('id'):
                    article_url = f"{base_url}/article/{news['id']}"
                    url = ET.SubElement(urlset, 'url')
                    ET.SubElement(url, 'loc').text = article_url
                    # 日付をパースしてlastmodに設定
                    try:
                        # 日付形式をパース（複数形式に対応）
                        date_str = news.get('date', '')
                        if date_str:
                            # 日付をパース（簡易版）
                            parsed_date = date_str.split()[0] if ' ' in date_str else date_str
                            ET.SubElement(url, 'lastmod').text = parsed_date
                        else:
                            ET.SubElement(url, 'lastmod').text = datetime.now().strftime('%Y-%m-%d')
                    except:
                        ET.SubElement(url, 'lastmod').text = datetime.now().strftime('%Y-%m-%d')
                    ET.SubElement(url, 'changefreq').text = 'weekly'
                    ET.SubElement(url, 'priority').text = '0.8'
        except Exception as e:
            log_exception(logger, e, "サイトマップ: 記事ページの追加エラー")
            # エラーが発生してもホームページのURLは含める
        
        # XMLを文字列に変換
        xml_str = ET.tostring(urlset, encoding='utf-8', method='xml')
        xml_str = b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        
        return Response(xml_str, mimetype='application/xml')
    except Exception as e:
        log_exception(logger, e, "サイトマップ生成エラー")
        return Response('<?xml version="1.0" encoding="UTF-8"?><urlset></urlset>', mimetype='application/xml')


@app.route('/robots.txt')
def robots():
    """robots.txtを返す"""
    try:
        robots_content = """User-agent: *
Allow: /
Disallow: /admin
Disallow: /api/

Sitemap: https://biz-ai-news.onrender.com/sitemap.xml
"""
        return Response(robots_content, mimetype='text/plain')
    except Exception as e:
        log_exception(logger, e, "robots.txt生成エラー")
        # エラー時でも基本的なrobots.txtを返す
        robots_content = """User-agent: *
Allow: /

Sitemap: https://biz-ai-news.onrender.com/sitemap.xml
"""
        return Response(robots_content, mimetype='text/plain')


@app.route('/ads.txt')
def ads_txt():
    """ads.txtを返す（Google AdSense用）"""
    try:
        ads_content = "google.com, pub-1202448154240053, DIRECT, f08c47fec0942fa0\n"
        return Response(ads_content, mimetype='text/plain')
    except Exception as e:
        log_exception(logger, e, "ads.txt生成エラー")
        # エラー時でも基本的なads.txtを返す
        ads_content = "google.com, pub-1202448154240053, DIRECT, f08c47fec0942fa0\n"
        return Response(ads_content, mimetype='text/plain')


@app.errorhandler(404)
def not_found(error):
    """404エラーハンドラー"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """500エラーハンドラー"""
    log_exception(logger, error, "500エラーが発生しました")
    return render_template('500.html'), 500


if __name__ == '__main__':
    # 本番環境用の設定
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print("🚀 AIニュースポータルを起動中...")
    if debug:
        print(f"   http://localhost:{port} でアクセスしてください")
    else:
        print(f"   本番モードで起動中（ポート: {port}）")
    
    logger.info(f"Webアプリを起動: ポート={port}, デバッグモード={debug}")
    
    app.run(debug=debug, host='0.0.0.0', port=port)

