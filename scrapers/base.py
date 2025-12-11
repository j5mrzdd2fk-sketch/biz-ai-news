#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ニュースサイトスクレイパーの基底クラス
"""

import re
import time
from abc import ABC, abstractmethod
from typing import Optional
import requests
from bs4 import BeautifulSoup


class BaseScraper(ABC):
    """ニュースサイトスクレイパーの基底クラス"""
    
    # サブクラスでオーバーライドする
    SITE_NAME = "Base"
    BASE_URL = ""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
        })
    
    @abstractmethod
    def get_article_list(self, max_pages: int = 3) -> list[dict]:
        """記事一覧を取得（サブクラスで実装）"""
        pass
    
    @abstractmethod
    def get_article_content(self, url: str) -> Optional[dict]:
        """記事の詳細情報を取得（サブクラスで実装）"""
        pass
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """ページを取得してBeautifulSoupオブジェクトを返す"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # エンコーディングを適切に処理
            # 1. レスポンスヘッダーから取得
            # 2. apparent_encodingで自動検出
            # 3. UTF-8をデフォルトとして使用
            encoding = response.encoding
            if not encoding or encoding == 'ISO-8859-1':
                encoding = response.apparent_encoding or 'utf-8'
            
            # コンテンツをデコード
            try:
                content = response.content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                try:
                    content = response.content.decode('utf-8')
                except UnicodeDecodeError:
                    content = response.content.decode('shift_jis', errors='ignore')
            
            return BeautifulSoup(content, "html.parser")
        except requests.RequestException as e:
            print(f"  ⚠️ ページ取得エラー ({self.SITE_NAME}): {e}")
            return None
    
    def _extract_date(self, soup: BeautifulSoup, patterns: list[str] = None) -> str:
        """日付を抽出"""
        if patterns is None:
            patterns = [
                r"(\d{4}/\d{1,2}/\d{1,2})",
                r"(\d{4}年\d{1,2}月\d{1,2}日)",
                r"(\d{4}-\d{2}-\d{2})",
            ]
        
        page_text = soup.get_text()
        for pattern in patterns:
            match = re.search(pattern, page_text)
            if match:
                return match.group(1)
        return ""
    
    def scrape(self, max_pages: int = 3, max_articles: int = 30) -> list[dict]:
        """記事をスクレイピングして返す"""
        print(f"\n📰 {self.SITE_NAME} からニュースを取得中...")
        
        # 記事一覧を取得
        articles = self.get_article_list(max_pages)
        print(f"   {len(articles)}件の記事を発見")
        
        # 記事詳細を取得
        detailed_articles = []
        for i, article in enumerate(articles[:max_articles]):
            print(f"  📰 [{i+1}/{min(len(articles), max_articles)}] {article.get('url', '')[:50]}...")
            detail = self.get_article_content(article["url"])
            if detail:
                detail["source"] = self.SITE_NAME
                detailed_articles.append(detail)
            time.sleep(0.5)  # サーバー負荷軽減
        
        print(f"   ✅ {len(detailed_articles)}件の記事詳細を取得")
        return detailed_articles

