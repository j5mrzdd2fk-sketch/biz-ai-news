#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
マルチサイト対応 AIニューススクレイピング & 要約ツール

対応サイト:
- Ledge.ai
- AINOW
- PR TIMES
- ITmedia AI+
"""

import os
import re
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

# Google Sheets関連
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# スクレイパー
from scrapers import LedgeAiScraper, AINowScraper, PRTimesScraper, ITmediaAiPlusScraper

# 設定: 1回の実行で追加する記事数の上限
# 環境変数 MAX_ARTICLES_PER_RUN で変更可能（デフォルト: 10件）
MAX_ARTICLES_PER_RUN = int(os.getenv('MAX_ARTICLES_PER_RUN', '10'))

# 設定: 古い記事を自動削除する期間（日数）
# 環境変数 ARTICLE_RETENTION_DAYS で変更可能（デフォルト: 45日）
ARTICLE_RETENTION_DAYS = int(os.getenv('ARTICLE_RETENTION_DAYS', '45'))

# ログ設定
from logger_config import get_scraper_logger, log_exception

# ロガーを初期化
logger = get_scraper_logger()

# .envファイルから環境変数を読み込み
load_dotenv()

# Google Sheets APIのスコープ
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

# 認証情報のパス
CREDENTIALS_FILE = "/Users/masak/Desktop/ニューススクレイピング/credentials.json"
TOKEN_FILE = "/Users/masak/Desktop/ニューススクレイピング/token.json"

# スプレッドシート名
SPREADSHEET_NAME = "AIニュース要約（マルチサイト）"

# キーワード設定（カテゴリ別）
KEYWORD_CATEGORIES = {
    "企業効率化": [
        "業務効率化", "業務改善", "生産性向上", "コスト削減", "働き方改革",
        "自動化", "効率化", "省力化", "時短",
    ],
    "DX・デジタル化": [
        "DX", "デジタルトランスフォーメーション", "デジタル化", "デジタル変革",
    ],
    "企業導入": [
        "企業導入", "企業事例", "国内企業", "導入事例", "活用事例", "ビジネス活用",
    ],
    "AI・テクノロジー": [
        "AI", "人工知能", "機械学習", "生成AI", "ChatGPT", "GPT", "LLM",
        "AI導入", "AI活用", "データ分析",
    ],
}

# 全キーワードのリスト（フィルタリング用）
KEYWORDS = [
    keyword for keywords in KEYWORD_CATEGORIES.values() for keyword in keywords
]


class ArticleSummarizer:
    """OpenAI APIを使用して記事を要約・評価するクラス"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def summarize_and_score(self, article: dict) -> dict:
        """記事を要約し、重要度スコアを付ける"""
        content = article.get("content", "")
        title = article.get("title", "")
        
        if not content:
            return {"summary": "記事本文が取得できませんでした。", "score": 1}
        
        prompt = f"""以下のAIニュース記事を分析してください。

【タイトル】
{title}

【本文】
{content[:3000]}

---
以下の2つを出力してください：

## 1. 要約（150〜200文字）
- 何が発表/発生したのか（Who/What）
- ビジネスへの影響や意義
- 今後の展望（あれば）

## 2. 重要度スコア（1〜5の整数）
以下の基準で評価：
- 5: 業界全体に影響する重大ニュース（大手企業の大規模導入、画期的な技術発表など）
- 4: 注目すべき重要ニュース（具体的な成果・数値あり、国内大手企業の事例）
- 3: 参考になるニュース（一般的な導入事例、技術解説）
- 2: 軽い情報（イベント告知、小規模な取り組み）
- 1: 重要度低い（プレスリリースのみ、内容薄い）

---
以下の形式で出力してください：
【要約】
（要約文）

【スコア】
（1〜5の数字のみ）"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたはAI・テクノロジー分野に精通したビジネスアナリストです。ニュース記事を的確に要約し、ビジネスパーソンにとっての重要度を評価します。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 要約とスコアを抽出
            summary = ""
            score = 3  # デフォルト
            
            if "【要約】" in result_text:
                parts = result_text.split("【スコア】")
                summary_part = parts[0].replace("【要約】", "").strip()
                summary = summary_part
                
                if len(parts) > 1:
                    score_text = parts[1].strip()
                    # 数字を抽出
                    for char in score_text:
                        if char.isdigit():
                            score = int(char)
                            break
            else:
                summary = result_text
            
            # スコアを1-5の範囲に制限
            score = max(1, min(5, score))
            
            return {"summary": summary, "score": score}
            
        except Exception as e:
            log_exception(logger, e, f"OpenAI API要約エラー (タイトル: {title[:50]})")
            return {"summary": f"要約エラー: {type(e).__name__}: {str(e)}", "score": 1}


class GoogleSheetsExporter:
    """結果をGoogle Sheetsに出力するクラス（カテゴリ別シート対応）"""
    
    def __init__(self):
        self.creds = None
        self.client = None
        self.spreadsheet = None
        self.worksheets = {}  # カテゴリ名 -> worksheet
        self.existing_urls = set()
        self.existing_titles = set()
        self.normalized_urls = {}  # 正規化されたURL -> 元のURL
        self.normalized_titles = {}  # 正規化されたタイトル -> 元のタイトル
        
        self._authenticate()
        self._setup_spreadsheet()
    
    def _authenticate(self):
        """Google認証を行う"""
        print("🔐 Google認証中...")
        logger.info("Google認証を開始")
        
        try:
            if os.path.exists(TOKEN_FILE):
                self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.info("トークンをリフレッシュ中")
                    self.creds.refresh(Request())
                else:
                    logger.info("新しい認証フローを開始")
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                
                with open(TOKEN_FILE, 'w') as token:
                    token.write(self.creds.to_json())
                logger.info("トークンを保存しました")
            
            self.client = gspread.authorize(self.creds)
            print("✅ Google認証完了")
            logger.info("Google認証完了")
        except FileNotFoundError as e:
            error_msg = f"認証ファイルが見つかりません: {CREDENTIALS_FILE}"
            log_exception(logger, e, "Google認証エラー")
            raise FileNotFoundError(error_msg) from e
        except Exception as e:
            log_exception(logger, e, "Google認証エラー")
            raise
    
    def _setup_spreadsheet(self):
        """スプレッドシートをセットアップ（カテゴリ別シート）"""
        is_new = False
        try:
            self.spreadsheet = self.client.open(SPREADSHEET_NAME)
            print(f"📂 既存スプレッドシートを開きました: {SPREADSHEET_NAME}")
            logger.info(f"既存スプレッドシートを開きました: {SPREADSHEET_NAME}")
        except gspread.SpreadsheetNotFound:
            print(f"📄 新規スプレッドシートを作成: {SPREADSHEET_NAME}")
            logger.info(f"新規スプレッドシートを作成: {SPREADSHEET_NAME}")
            try:
                self.spreadsheet = self.client.create(SPREADSHEET_NAME)
                is_new = True
                print(f"🔗 スプレッドシートURL: {self.spreadsheet.url}")
                logger.info(f"スプレッドシートURL: {self.spreadsheet.url}")
            except Exception as e:
                log_exception(logger, e, "スプレッドシート作成エラー")
                raise
        except Exception as e:
            log_exception(logger, e, "スプレッドシートオープンエラー")
            raise
        
        # カテゴリ別シートをセットアップ
        category_names = list(KEYWORD_CATEGORIES.keys()) + ["その他"]
        
        for category in category_names:
            try:
                ws = self.spreadsheet.worksheet(category)
                self.worksheets[category] = ws
                logger.debug(f"シート「{category}」を読み込み")
            except gspread.WorksheetNotFound:
                try:
                    ws = self.spreadsheet.add_worksheet(title=category, rows=200, cols=10)
                    self.worksheets[category] = ws
                    self._setup_sheet_headers(ws, category)
                    logger.info(f"新規シート「{category}」を作成しました")
                except Exception as e:
                    log_exception(logger, e, f"シート「{category}」作成エラー")
                    raise
        
        # デフォルトのシート1を削除（新規の場合）
        if is_new:
            try:
                default_sheet = self.spreadsheet.worksheet("シート1")
                self.spreadsheet.del_worksheet(default_sheet)
                logger.info("デフォルトシート「シート1」を削除しました")
            except Exception as e:
                logger.warning(f"デフォルトシート削除エラー（無視）: {e}")
        
        # 既存URLを読み込み
        self._load_existing_urls()
    
    def _setup_sheet_headers(self, worksheet, category: str):
        """シートのヘッダーと書式を設定"""
        headers = ["No.", "ソース", "タイトル", "日付", "タグ", "重要度", "要約", "URL", "実URL", "カテゴリ"]
        worksheet.update(values=[headers], range_name='A1:J1')
        
        # カテゴリごとの色設定
        colors = {
            "企業効率化": {'red': 0.15, 'green': 0.35, 'blue': 0.55},
            "DX・デジタル化": {'red': 0.25, 'green': 0.45, 'blue': 0.30},
            "企業導入": {'red': 0.50, 'green': 0.30, 'blue': 0.45},
            "AI・テクノロジー": {'red': 0.30, 'green': 0.20, 'blue': 0.60},
            "その他": {'red': 0.40, 'green': 0.40, 'blue': 0.40},
        }
        bg_color = colors.get(category, {'red': 0.3, 'green': 0.3, 'blue': 0.5})
        
        sheet_id = worksheet.id
        requests = [
            # ヘッダー書式
            {'repeatCell': {
                'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 8},
                'cell': {'userEnteredFormat': {
                    'backgroundColor': bg_color,
                    'textFormat': {'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}, 'bold': True, 'fontSize': 11},
                    'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE'
                }},
                'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)'
            }},
            # ヘッダー行高さ
            {'updateDimensionProperties': {
                'range': {'sheetId': sheet_id, 'dimension': 'ROWS', 'startIndex': 0, 'endIndex': 1},
                'properties': {'pixelSize': 40}, 'fields': 'pixelSize'}},
            # 列幅
            {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 1}, 'properties': {'pixelSize': 45}, 'fields': 'pixelSize'}},   # No.
            {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 1, 'endIndex': 2}, 'properties': {'pixelSize': 100}, 'fields': 'pixelSize'}},  # ソース
            {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 2, 'endIndex': 3}, 'properties': {'pixelSize': 300}, 'fields': 'pixelSize'}},  # タイトル
            {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 3, 'endIndex': 4}, 'properties': {'pixelSize': 100}, 'fields': 'pixelSize'}},  # 日付
            {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 4, 'endIndex': 5}, 'properties': {'pixelSize': 140}, 'fields': 'pixelSize'}},  # タグ
            {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 5, 'endIndex': 6}, 'properties': {'pixelSize': 70}, 'fields': 'pixelSize'}},   # 重要度
            {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 6, 'endIndex': 7}, 'properties': {'pixelSize': 500}, 'fields': 'pixelSize'}},  # 要約
            {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 7, 'endIndex': 8}, 'properties': {'pixelSize': 100}, 'fields': 'pixelSize'}},  # URL
            # ヘッダー固定
            {'updateSheetProperties': {
                'properties': {'sheetId': sheet_id, 'gridProperties': {'frozenRowCount': 1}},
                'fields': 'gridProperties.frozenRowCount'
            }}
        ]
        self._execute_batch_update_with_retry(requests)
    
    def _update_worksheet_with_retry(self, worksheet, values, range_name, max_retries=3):
        """worksheet.updateをリトライ付きで実行（レート制限対策）"""
        for attempt in range(max_retries):
            try:
                worksheet.update(values=values, range_name=range_name)
                time.sleep(0.2)  # 成功後も少し待機
                return True
            except Exception as e:
                if "429" in str(e) or "Quota exceeded" in str(e):
                    wait_time = (attempt + 1) * 3  # 3秒、6秒、9秒と増やす
                    print(f"      ⚠️ レート制限エラー。{wait_time}秒待機してリトライ... (試行 {attempt + 1}/{max_retries})")
                    logger.warning(f"Google Sheets APIレート制限エラー。{wait_time}秒待機してリトライ (試行 {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    if attempt == max_retries - 1:
                        # リトライ上限に達した場合、さらに長く待機して最後の試行
                        print(f"      ⚠️ リトライ上限に達しました。さらに60秒待機して最後の試行...")
                        logger.warning("リトライ上限に達しました。さらに60秒待機して最後の試行")
                        time.sleep(60)
                        try:
                            worksheet.update(values=values, range_name=range_name)
                            time.sleep(0.2)
                            print(f"      ✅ 最終リトライ成功")
                            logger.info("最終リトライ成功")
                            return True
                        except Exception as final_error:
                            log_exception(logger, final_error, "最終リトライ失敗")
                            print(f"      ⚠️ 最終リトライも失敗。この操作をスキップします。")
                            return False
                else:
                    # レート制限以外のエラーは詳細をログに記録して再発生
                    log_exception(logger, e, "worksheet.updateエラー")
                    raise
        return False
    
    def _execute_batch_update_with_retry(self, requests, max_retries=3):
        """バッチ更新をリトライ付きで実行（レート制限対策）"""
        for attempt in range(max_retries):
            try:
                self.spreadsheet.batch_update({'requests': requests})
                time.sleep(0.2)  # 成功後も少し待機
                return True
            except Exception as e:
                if "429" in str(e) or "Quota exceeded" in str(e):
                    wait_time = (attempt + 1) * 3  # 3秒、6秒、9秒と増やす
                    print(f"      ⚠️ レート制限エラー。{wait_time}秒待機してリトライ... (試行 {attempt + 1}/{max_retries})")
                    logger.warning(f"Google Sheets APIレート制限エラー（バッチ更新）。{wait_time}秒待機してリトライ (試行 {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    if attempt == max_retries - 1:
                        # リトライ上限に達した場合、さらに長く待機して最後の試行
                        print(f"      ⚠️ リトライ上限に達しました。さらに60秒待機して最後の試行...")
                        logger.warning("リトライ上限に達しました（バッチ更新）。さらに60秒待機して最後の試行")
                        time.sleep(60)
                        try:
                            self.spreadsheet.batch_update({'requests': requests})
                            time.sleep(0.2)
                            print(f"      ✅ 最終リトライ成功")
                            logger.info("最終リトライ成功（バッチ更新）")
                            return True
                        except Exception as final_error:
                            log_exception(logger, final_error, "最終リトライ失敗（バッチ更新）")
                            print(f"      ⚠️ 最終リトライも失敗。この操作をスキップします。")
                            return False
                else:
                    # レート制限以外のエラーは詳細をログに記録して再発生
                    log_exception(logger, e, "batch_updateエラー")
                    raise
        return False
    
    def _normalize_url(self, url: str) -> str:
        """URLを正規化（重複チェック用）"""
        if not url:
            return ""
        
        # HYPERLINK関数から実際のURLを抽出
        if url.startswith('=HYPERLINK') or url.startswith('=hyperlink') or 'HYPERLINK' in url.upper():
            match = re.search(r'HYPERLINK\("([^"]+)"', url, re.IGNORECASE)
            if match:
                url = match.group(1)
        
        # URLを正規化
        url = url.strip()
        
        # "記事を開く"などのテキストが含まれている場合は除外
        if url == "記事を開く" or url == "Open Article":
            return ""
        
        # 末尾のスラッシュを削除
        url = url.rstrip('/')
        
        # クエリパラメータがある場合は削除（記事URLは通常パラメータ不要）
        if '?' in url:
            base, params = url.split('?', 1)
            # 重要なパラメータ（例: id, article_id）がある場合は保持
            if 'id=' in params.lower() or 'article_id=' in params.lower():
                # IDパラメータのみ保持
                param_dict = {}
                for param in params.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        if key.lower() in ['id', 'article_id', 'article']:
                            param_dict[key] = value
                if param_dict:
                    sorted_params = '&'.join([f"{k}={v}" for k, v in sorted(param_dict.items())])
                    url = f"{base}?{sorted_params}"
                else:
                    url = base
            else:
                url = base
        
        return url
    
    def _normalize_title(self, title: str) -> str:
        """タイトルを正規化（重複チェック用）"""
        if not title:
            return ""
        
        # タイトルを正規化（空白を統一、大文字小文字を無視、特殊文字を除去）
        normalized = title.lower().replace(" ", "").replace("　", "").replace("、", "").replace("，", "")
        normalized = normalized.replace("・", "").replace("ー", "").replace("-", "").replace("―", "")
        return normalized
    
    def _load_existing_urls(self):
        """全シートから既存URLとタイトルを読み込む（正規化して保存）"""
        total = 0
        self.existing_urls = set()
        self.existing_titles = set()
        self.normalized_urls = {}
        self.normalized_titles = {}
        
        for category, ws in self.worksheets.items():
            try:
                all_values = ws.get_all_values()
                for row in all_values[1:]:
                    if len(row) >= 3:
                        # タイトル（C列）を保存
                        title = row[2] if len(row) > 2 else ""
                        if title:
                            self.existing_titles.add(title)
                            normalized_title = self._normalize_title(title)
                            if normalized_title:
                                self.normalized_titles[normalized_title] = title
                        
                        # URL（H列またはI列）を保存
                        url = ""
                        if len(row) > 8 and row[8] and row[8].startswith("http"):
                            url = row[8]
                        elif len(row) > 7 and row[7] and row[7].startswith("http"):
                            url = row[7]
                        
                        if url:
                            self.existing_urls.add(url)
                            normalized_url = self._normalize_url(url)
                            if normalized_url:
                                self.normalized_urls[normalized_url] = url
                        
                        total += 1
            except Exception as e:
                log_exception(logger, e, f"シート「{category}」から既存URL読み込みエラー")
        if total > 0:
            print(f"   既存記事数: {total}件（重複チェック用に正規化済み）")
            logger.info(f"既存記事数: {total}件（重複チェック用に正規化済み）")
    
    def is_duplicate(self, url: str, title: str = "") -> bool:
        """URLまたはタイトルが既に存在するかチェック（正規化して比較）"""
        # URLの重複チェック（正規化）
        if url:
            normalized_url = self._normalize_url(url)
            if normalized_url and normalized_url in self.normalized_urls:
                existing_url = self.normalized_urls[normalized_url]
                logger.debug(f"URL重複を検出: {url} (既存: {existing_url})")
                return True
            # 正規化前のURLもチェック（念のため）
            if url in self.existing_urls:
                logger.debug(f"URL重複を検出（正規化前）: {url}")
                return True
        
        # タイトルの重複チェック（正規化）
        if title:
            normalized_title = self._normalize_title(title)
            if normalized_title and normalized_title in self.normalized_titles:
                existing_title = self.normalized_titles[normalized_title]
                logger.debug(f"タイトル重複を検出: {title} (既存: {existing_title})")
                return True
            # 正規化前のタイトルもチェック（念のため）
            if title in self.existing_titles:
                logger.debug(f"タイトル重複を検出（正規化前）: {title}")
                return True
        
        return False
    
    def _get_category(self, article: dict) -> str:
        """記事のカテゴリを判定（複数カテゴリ対応）"""
        text = f"{article.get('title', '')} {' '.join(article.get('tags', []))} {article.get('content', '')[:500]}"
        text_lower = text.lower()
        
        # マッチするカテゴリを全て収集
        matched_categories = []
        
        # 優先順位順にチェック（企業効率化、DX・デジタル化を優先）
        category_priority = [
            "企業効率化",
            "DX・デジタル化",
            "企業導入",
            "AI・テクノロジー",
        ]
        
        for category in category_priority:
            if category in KEYWORD_CATEGORIES:
                keywords = KEYWORD_CATEGORIES[category]
                if any(kw.lower() in text_lower for kw in keywords):
                    matched_categories.append(category)
        
        # マッチしたカテゴリがない場合は「その他」
        if not matched_categories:
            return "その他"
        
        # 複数マッチした場合はカンマ区切りで返す
        # ただし、メインカテゴリ（最初にマッチしたもの）を最初に配置
        return ", ".join(matched_categories)
    
    def add_article(self, article: dict, summary: str, score: int = 3) -> bool:
        """記事データをカテゴリ別シートに追加（複数カテゴリ対応）"""
        url = article.get("url", "")
        title = article.get("title", "")
        
        if self.is_duplicate(url, title):
            return False
        
        # カテゴリ判定（複数カテゴリの場合はカンマ区切り）
        category_str = self._get_category(article)
        categories = [cat.strip() for cat in category_str.split(",")]
        
        # メインカテゴリ（最初のカテゴリ）のシートに追加
        main_category = categories[0] if categories else "その他"
        
        # シートが存在しない場合は作成
        if main_category not in self.worksheets:
            try:
                ws = self.spreadsheet.worksheet(main_category)
                self.worksheets[main_category] = ws
            except gspread.WorksheetNotFound:
                # 新しいシートを作成
                ws = self.spreadsheet.add_worksheet(title=main_category, rows=200, cols=10)
                self.worksheets[main_category] = ws
                self._setup_sheet_headers(ws, main_category)
                print(f"   📄 新規シート「{main_category}」を作成しました")
        
        worksheet = self.worksheets.get(main_category, self.worksheets.get("その他"))
        
        row_num = len(worksheet.col_values(1)) + 1
        article_no = row_num - 1
        
        # シートの行数が不足している場合は追加
        current_row_count = worksheet.row_count
        if row_num > current_row_count:
            rows_to_add = row_num - current_row_count + 10  # 余裕を持って10行追加
            try:
                worksheet.add_rows(rows_to_add)
                print(f"   📏 シート「{main_category}」に行を{rows_to_add}行追加しました（現在: {current_row_count}行 → {current_row_count + rows_to_add}行）")
                logger.info(f"シート「{main_category}」に行を{rows_to_add}行追加しました")
            except Exception as e:
                log_exception(logger, e, f"シート「{main_category}」への行追加エラー")
                # エラーが発生しても続行（既存の行数内で試行）
        
        # 重要度を星で表示
        score_display = "⭐" * score + "☆" * (5 - score)
        
        # データを挿入（I列に実URLを保存）
        # カテゴリ列には複数カテゴリをカンマ区切りで保存
        data = [
            article_no,
            article.get("source", ""),
            article.get("title", ""),
            article.get("date", ""),
            ", ".join(article.get("tags", [])),
            score_display,  # 重要度
            summary,
            "",  # URL列は後でハイパーリンク設定
            url,   # 実URL（Webアプリ用）
            category_str  # カテゴリ（複数の場合はカンマ区切り）
        ]
        
        # データ更新（リトライ付き）
        self._update_worksheet_with_retry(worksheet, values=[data], range_name=f'A{row_num}:J{row_num}')
        
        # 既存URLとタイトルに追加（重複チェック用）
        if url:
            self.existing_urls.add(url)
            normalized_url = self._normalize_url(url)
            if normalized_url:
                self.normalized_urls[normalized_url] = url
        
        if title:
            self.existing_titles.add(title)
            normalized_title = self._normalize_title(title)
            if normalized_title:
                self.normalized_titles[normalized_title] = title
        
        # スコアに応じた背景色
        score_colors = {
            5: {'red': 1.0, 'green': 0.9, 'blue': 0.6},    # 金色
            4: {'red': 0.9, 'green': 0.95, 'blue': 0.7},   # 薄緑
            3: {'red': 1.0, 'green': 1.0, 'blue': 1.0},    # 白
            2: {'red': 0.95, 'green': 0.95, 'blue': 0.95}, # 薄灰
            1: {'red': 0.9, 'green': 0.9, 'blue': 0.9},    # 灰色
        }
        score_bg = score_colors.get(score, score_colors[3])
        
        # 行の書式設定 + URLをハイパーリンクとして設定
        sheet_id = worksheet.id
        requests = [
                # 行の書式設定
                {'repeatCell': {
                    'range': {'sheetId': sheet_id, 'startRowIndex': row_num - 1, 'endRowIndex': row_num, 'startColumnIndex': 0, 'endColumnIndex': 7},
                    'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP', 'textFormat': {'fontSize': 10}}},
                    'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment,textFormat)'
                }},
                # 重要度セルの書式（中央揃え + 背景色）
                {'repeatCell': {
                    'range': {'sheetId': sheet_id, 'startRowIndex': row_num - 1, 'endRowIndex': row_num, 'startColumnIndex': 5, 'endColumnIndex': 6},
                    'cell': {'userEnteredFormat': {
                        'horizontalAlignment': 'CENTER',
                        'verticalAlignment': 'MIDDLE',
                        'backgroundColor': score_bg
                    }},
                    'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment,backgroundColor)'
                }},
                # 行の高さ
                {'updateDimensionProperties': {
                    'range': {'sheetId': sheet_id, 'dimension': 'ROWS', 'startIndex': row_num - 1, 'endIndex': row_num},
                    'properties': {'pixelSize': 120}, 'fields': 'pixelSize'}},
                # URLをクリック可能なハイパーリンクとして設定
                {'updateCells': {
                    'range': {'sheetId': sheet_id, 'startRowIndex': row_num - 1, 'endRowIndex': row_num, 'startColumnIndex': 7, 'endColumnIndex': 8},
                    'rows': [{
                        'values': [{
                            'userEnteredValue': {'stringValue': '🔗 記事を開く'},
                            'textFormatRuns': [{
                                'startIndex': 0,
                                'format': {'link': {'uri': url}, 'foregroundColor': {'red': 0.06, 'green': 0.46, 'blue': 0.88}}
                            }]
                        }]
                    }],
                    'fields': 'userEnteredValue,textFormatRuns'
                }}
            ]
        self._execute_batch_update_with_retry(requests)
        
        return True
    
    def get_spreadsheet_url(self) -> str:
        """スプレッドシートのURLを取得"""
        return self.spreadsheet.url
    
    def get_total_article_count(self) -> int:
        """スプレッドシートの総記事数を取得"""
        total = 0
        for category, ws in self.worksheets.items():
            try:
                all_values = ws.get_all_values()
                # ヘッダーを除いた有効な記事数（7列以上ある行）
                for row in all_values[1:]:
                    if len(row) >= 7 and row[2]:  # タイトルがある行
                        total += 1
            except Exception as e:
                log_exception(logger, e, f"シート「{category}」の記事数取得エラー")
        return total
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """日付文字列をパースしてdatetimeオブジェクトに変換"""
        if not date_str or not date_str.strip():
            return None
        
        date_str = date_str.strip()
        date_formats = [
            '%Y-%m-%d',           # 2024-12-12
            '%Y/%m/%d',           # 2024/12/12
            '%Y年%m月%d日',        # 2024年12月12日
            '%Y-%m-%d %H:%M:%S',  # 2024-12-12 12:00:00
            '%Y/%m/%d %H:%M:%S',  # 2024/12/12 12:00:00
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.split()[0], fmt.split()[0])
            except (ValueError, IndexError):
                continue
        
        # 日付形式が不明な場合はNoneを返す
        return None
    
    def delete_old_articles(self, retention_days: int = 30) -> int:
        """一定期間経過した古い記事を削除（★5の記事は永久保存）"""
        print(f"\n🗑️  {retention_days}日以上経過した古い記事を削除中...（★5は永久保存）")
        logger.info(f"古い記事の削除を開始（保持期間: {retention_days}日、★5は永久保存）")
        
        total_deleted = 0
        preserved_count = 0  # ★5で保存された記事数
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        for category, ws in self.worksheets.items():
            try:
                all_values = ws.get_all_values()
                if len(all_values) <= 1:
                    continue
                
                # ヘッダーを除く
                data_rows = all_values[1:]
                rows_to_delete = []
                
                for row_index, row in enumerate(data_rows, start=2):  # 2行目から（1行目はヘッダー）
                    if len(row) < 4:
                        continue
                    
                    date_str = row[3] if len(row) > 3 else ""  # 日付列（4列目、インデックス3）
                    title = row[2] if len(row) > 2 else ""      # タイトル列（3列目、インデックス2）
                    score_str = row[5] if len(row) > 5 else ""  # 重要度列（6列目、インデックス5）
                    
                    if not date_str or not title:
                        continue
                    
                    # ★5の記事は永久保存（削除対象外）
                    # スコア列から⭐の数を数えて、5個以上あれば永久保存
                    if score_str:
                        star_count = score_str.count("⭐")
                        if star_count >= 5:
                            preserved_count += 1
                            logger.debug(f"永久保存: [{category}] 行{row_index} - ★5記事: {title[:50]}...")
                            continue
                    
                    # 日付をパース
                    article_date = self._parse_date(date_str)
                    if not article_date:
                        # 日付がパースできない場合はスキップ（削除しない）
                        continue
                    
                    # 保持期間を超えているかチェック
                    if article_date < cutoff_date:
                        rows_to_delete.append(row_index)
                        print(f"   🗑️  [{category}] 行{row_index}: {title[:50]}... (日付: {date_str})")
                        logger.info(f"削除対象: [{category}] 行{row_index} - {title[:50]}... (日付: {date_str})")
                
                # 行を削除（後ろから削除する必要がある）
                if rows_to_delete:
                    rows_to_delete.sort(reverse=True)
                    for row_index in rows_to_delete:
                        try:
                            ws.delete_rows(row_index)
                            total_deleted += 1
                            logger.debug(f"行{row_index}を削除しました")
                        except Exception as e:
                            log_exception(logger, e, f"行{row_index}の削除エラー")
                            print(f"      ⚠️ 行{row_index}の削除エラー: {e}")
                
            except Exception as e:
                log_exception(logger, e, f"シート「{category}」の古い記事削除エラー")
                print(f"   ⚠️ シート「{category}」の処理エラー: {e}")
        
        if total_deleted > 0:
            print(f"   ✅ {total_deleted}件の古い記事を削除しました")
            logger.info(f"古い記事の削除完了: {total_deleted}件")
        else:
            print(f"   ✅ 削除対象の記事はありませんでした")
            logger.info("削除対象の記事はありませんでした")
        
        if preserved_count > 0:
            print(f"   💎 {preserved_count}件の★5記事を永久保存しました")
            logger.info(f"★5記事の永久保存: {preserved_count}件")
        
        return total_deleted


def filter_by_keywords(articles: list[dict]) -> list[dict]:
    """キーワードでフィルタリング（緩和版：より多くの記事を通す）"""
    filtered = []
    for article in articles:
        # タイトル、タグ、本文の最初の1000文字をチェック（範囲を拡大）
        text = f"{article.get('title', '')} {' '.join(article.get('tags', []))} {article.get('content', '')[:1000]}"
        # キーワードマッチング（部分一致でもOK）
        if any(keyword.lower() in text.lower() for keyword in KEYWORDS):
            filtered.append(article)
    return filtered


def parse_article_date(date_str: str) -> Optional[datetime]:
    """記事の日付文字列をdatetimeオブジェクトに変換"""
    if not date_str:
        return None
    
    # 様々な日付形式に対応
    date_formats = [
        "%Y/%m/%d",
        "%Y年%m月%d日",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y年%m月%d日 %H:%M",
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
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
    
    return None


def sort_articles_by_date(articles: list[dict], reverse: bool = True) -> list[dict]:
    """記事を日付順にソート（新しい順がデフォルト）"""
    def get_sort_key(article: dict) -> datetime:
        date_str = article.get("date", "")
        parsed_date = parse_article_date(date_str)
        # 日付が解析できない場合は、非常に古い日付として扱う
        if parsed_date is None:
            return datetime(1900, 1, 1)
        return parsed_date
    
    return sorted(articles, key=get_sort_key, reverse=reverse)


def main():
    """メイン処理"""
    print("=" * 70)
    print("🤖 マルチサイト対応 AIニューススクレイピング & 要約ツール")
    print("   📰 対応サイト: Ledge.ai, AINOW, PR TIMES, ITmedia AI+")
    print("=" * 70)
    
    logger.info("=" * 70)
    logger.info("マルチサイト対応 AIニューススクレイピング & 要約ツールを開始")
    logger.info("対応サイト: Ledge.ai, AINOW, PR TIMES, ITmedia AI+")
    logger.info("=" * 70)
    
    # OpenAI APIキーの確認
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        error_msg = "OPENAI_API_KEY が設定されていません"
        logger.error(error_msg)
        print(f"❌ エラー: {error_msg}")
        return
    
    print(f"✅ OpenAI APIキー: 設定済み")
    logger.info("OpenAI APIキー: 設定済み")
    
    # Google Sheets初期化
    try:
        exporter = GoogleSheetsExporter()
    except Exception as e:
        log_exception(logger, e, "Google Sheets初期化エラー")
        print(f"❌ Google Sheets認証エラー: {e}")
        return
    
    # スクレイパーリスト
    scrapers = [
        LedgeAiScraper(),
        AINowScraper(),
        PRTimesScraper(),
        ITmediaAiPlusScraper(),
    ]
    
    # 全サイトから記事を収集
    all_articles = []
    for scraper in scrapers:
        try:
            # 各サイトから最大15件の記事を取得
            articles = scraper.scrape(max_pages=10, max_articles=15)
            print(f"   📰 {scraper.SITE_NAME}: {len(articles)}件取得")
            logger.info(f"{scraper.SITE_NAME}: {len(articles)}件取得")
            all_articles.extend(articles)
        except Exception as e:
            log_exception(logger, e, f"{scraper.SITE_NAME} スクレイピングエラー")
            print(f"⚠️ {scraper.SITE_NAME} でエラー: {e}")
    
    print(f"\n📊 全サイト合計: {len(all_articles)}件")
    
    # サイト別内訳を表示
    source_counts = {}
    for article in all_articles:
        source = article.get("source", "Unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    print("   📂 サイト別内訳:")
    for source, count in source_counts.items():
        print(f"      - {source}: {count}件")
    
    # キーワードフィルタリング
    print("\n🔍 キーワードでフィルタリング中...")
    filtered_articles = filter_by_keywords(all_articles)
    print(f"   フィルタ後: {len(filtered_articles)}件")
    
    # フィルタリング後のサイト別内訳
    filtered_source_counts = {}
    for article in filtered_articles:
        source = article.get("source", "Unknown")
        filtered_source_counts[source] = filtered_source_counts.get(source, 0) + 1
    print("   📂 フィルタ後のサイト別内訳:")
    for source, count in filtered_source_counts.items():
        print(f"      - {source}: {count}件")
    
    # 古い記事の自動削除（新規記事追加前に実行）
    deleted_count = exporter.delete_old_articles(ARTICLE_RETENTION_DAYS)
    if deleted_count > 0:
        print(f"   📊 削除後の総記事数: {exporter.get_total_article_count()}件")
    
    # 重複除外
    new_articles = [a for a in filtered_articles if not exporter.is_duplicate(a.get("url", ""), a.get("title", ""))]
    skipped = len(filtered_articles) - len(new_articles)
    
    if skipped > 0:
        print(f"   ⏭️ 既存記事をスキップ: {skipped}件")
    
    if not new_articles:
        print("\n✅ 新しい記事はありませんでした。")
        print(f"🔗 スプレッドシート: {exporter.get_spreadsheet_url()}")
        return
    
    print(f"   🆕 新規記事: {len(new_articles)}件")
    
    # PR TIMESの記事を最大4つまでに制限
    PR_TIMES_MAX = 4
    pr_times_articles = [a for a in new_articles if a.get("source", "") == "PR TIMES"]
    other_articles = [a for a in new_articles if a.get("source", "") != "PR TIMES"]
    
    # PR TIMESの記事を先着順で最大4つまで選ぶ（日付順ではない）
    pr_times_selected = pr_times_articles[:PR_TIMES_MAX]
    pr_times_skipped = len(pr_times_articles) - len(pr_times_selected)
    
    # その他の記事を日付順（新しい順）にソートしてから最大11つ選ぶ
    print(f"\n📅 その他の記事を日付順（新しい順）にソート中...")
    other_articles_sorted = sort_articles_by_date(other_articles, reverse=True)
    other_selected = other_articles_sorted[:MAX_ARTICLES_PER_RUN - PR_TIMES_MAX]
    other_skipped = len(other_articles) - len(other_selected)
    
    # 日付順ソート結果を表示（デバッグ用）
    if other_articles_sorted:
        print(f"   📅 日付順ソート結果（上位5件）:")
        for i, article in enumerate(other_articles_sorted[:5], 1):
            date_str = article.get("date", "日付不明")
            title = article.get("title", "")[:40]
            print(f"      {i}. [{date_str}] {title}...")
    
    if pr_times_skipped > 0:
        print(f"   ⚠️ PR TIMESの記事を{PR_TIMES_MAX}件に制限（{pr_times_skipped}件をスキップ）")
        logger.info(f"PR TIMESの記事を{PR_TIMES_MAX}件に制限（{pr_times_skipped}件をスキップ）")
    
    if other_skipped > 0:
        print(f"   ⚠️ その他の記事を{MAX_ARTICLES_PER_RUN - PR_TIMES_MAX}件に制限（{other_skipped}件をスキップ）")
        logger.info(f"その他の記事を{MAX_ARTICLES_PER_RUN - PR_TIMES_MAX}件に制限（{other_skipped}件をスキップ）")
    
    # 選んだ記事を結合（まず全記事を要約生成してスコアを取得）
    articles_to_evaluate = pr_times_selected + other_selected
    print(f"   📌 今回評価する記事: {len(articles_to_evaluate)}件（PR TIMES: {len(pr_times_selected)}件、その他: {len(other_selected)}件）")
    
    # 要約生成 + 重要度スコア（全記事を評価）
    summarizer = ArticleSummarizer(api_key)
    print("\n✍️ OpenAI APIで要約 & 重要度評価中...")
    
    # 記事とスコアを保存するリスト
    articles_with_scores = []
    
    for i, article in enumerate(articles_to_evaluate, 1):
        source = article.get('source', '')
        title = article.get('title', '')[:35]
        print(f"   [{i}/{len(articles_to_evaluate)}] [{source}] {title}...")
        logger.info(f"[{i}/{len(articles_to_evaluate)}] [{source}] {title[:50]}...")
        
        try:
            result = summarizer.summarize_and_score(article)
            summary = result["summary"]
            score = result["score"]
            
            print(f"      → 重要度: {'⭐' * score}")
            logger.info(f"重要度: {'⭐' * score}")
            
            # 記事、要約、スコアを保存
            articles_with_scores.append({
                'article': article,
                'summary': summary,
                'score': score
            })
        except Exception as e:
            log_exception(logger, e, f"記事処理エラー: {title[:50]}")
            print(f"      ⚠️ 記事処理エラー: {e}")
        
        time.sleep(0.5)
    
    # 重要度順にソート（スコアが高い順）
    articles_with_scores.sort(key=lambda x: x['score'], reverse=True)
    
    # PR TIMESを最大4つ、その他を重要度順に選ぶ
    pr_times_final = []
    other_final = []
    
    for item in articles_with_scores:
        article = item['article']
        if article.get("source", "") == "PR TIMES":
            if len(pr_times_final) < PR_TIMES_MAX:
                pr_times_final.append(item)
        else:
            other_final.append(item)
    
    # その他の記事を重要度順に最大11つまで選ぶ
    other_final = other_final[:MAX_ARTICLES_PER_RUN - PR_TIMES_MAX]
    
    # 最終的に反映する記事を結合（PR TIMESを先に、その他を重要度順に）
    articles_to_process = pr_times_final + other_final
    
    print(f"\n📊 重要度順に選定完了:")
    print(f"   - PR TIMES: {len(pr_times_final)}件")
    print(f"   - その他（重要度順）: {len(other_final)}件")
    print(f"   - 合計: {len(articles_to_process)}件")
    logger.info(f"重要度順に選定完了: PR TIMES {len(pr_times_final)}件、その他 {len(other_final)}件")
    
    # 記事を反映
    added = 0
    score_stats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    for item in articles_to_process:
        article = item['article']
        summary = item['summary']
        score = item['score']
        score_stats[score] += 1
        
        if exporter.add_article(article, summary, score):
            added += 1
            title = article.get('title', '')[:50]
            logger.info(f"記事を追加しました: {title}")
        else:
            title = article.get('title', '')[:50]
            logger.warning(f"記事の追加に失敗しました（重複の可能性）: {title}")
    
    # サイト別集計（処理した記事のみ）
    source_counts = {}
    for item in articles_to_process:
        article = item['article']
        source = article.get('source', 'Unknown')
        source_counts[source] = source_counts.get(source, 0) + 1
    
    # スプレッドシートの総記事数を取得
    total_articles = exporter.get_total_article_count()
    
    # スキップされた記事数を計算
    total_skipped = pr_times_skipped + other_skipped
    
    print("\n" + "=" * 70)
    print("🎉 処理完了！")
    print(f"   📊 収集記事数: {len(filtered_articles)}件")
    print(f"   ⏭️ 既存記事をスキップ: {skipped}件")
    if total_skipped > 0:
        print(f"   ⚠️ 追加数制限によりスキップ: {total_skipped}件（次回実行時に処理）")
        if pr_times_skipped > 0:
            print(f"      - PR TIMES: {pr_times_skipped}件")
        if other_skipped > 0:
            print(f"      - その他: {other_skipped}件")
    print(f"   🆕 新規追加: {added}件（上限: {MAX_ARTICLES_PER_RUN}件、PR TIMES最大{PR_TIMES_MAX}件）")
    print(f"   📂 サイト別内訳:")
    for source, count in source_counts.items():
        print(f"      - {source}: {count}件")
    print(f"   ⭐ 重要度分布:")
    print(f"      - ⭐⭐⭐⭐⭐ (必読): {score_stats[5]}件")
    print(f"      - ⭐⭐⭐⭐☆ (重要): {score_stats[4]}件")
    print(f"      - ⭐⭐⭐☆☆ (参考): {score_stats[3]}件")
    print(f"      - ⭐⭐☆☆☆ (軽い): {score_stats[2]}件")
    print(f"      - ⭐☆☆☆☆ (低い): {score_stats[1]}件")
    print(f"   📝 スプレッドシート総記事数: {total_articles}件")
    print(f"   🔗 スプレッドシート: {exporter.get_spreadsheet_url()}")
    print("=" * 70)
    
    logger.info("=" * 70)
    logger.info("処理完了")
    logger.info(f"収集記事数: {len(filtered_articles)}件")
    logger.info(f"スキップ: {skipped}件")
    logger.info(f"新規追加: {added}件")
    logger.info(f"スプレッドシート総記事数: {total_articles}件")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()

