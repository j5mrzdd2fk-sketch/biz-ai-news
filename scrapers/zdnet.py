#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZDNet Japan スクレイパー
AI・DX関連のテクノロジーニュースを取得
"""

import re
import time
from typing import Optional
from .base import BaseScraper


class ZDNetScraper(BaseScraper):
    """ZDNet JapanのAI関連ニュースをスクレイピングするクラス"""
    
    SITE_NAME = "ZDNet Japan"
    BASE_URL = "https://japan.zdnet.com"
    
    # スクレイピングするカテゴリ
    CATEGORIES = [
        "/keyword/AI/",
        "/keyword/%E7%94%9F%E6%88%90AI/",  # 生成AI
        "/keyword/DX/",
    ]

    def get_article_list(self, max_pages: int = 2) -> list[dict]:
        """記事一覧を取得"""
        articles = []
        seen_urls = set()
        
        for category_url in self.CATEGORIES:
            url = f"{self.BASE_URL}{category_url}"
            
            soup = self._fetch_page(url)
            if not soup:
                continue
            
            # 記事リンクを抽出
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                
                # /article/ を含むリンクが記事
                if "/article/" not in href:
                    continue
                
                # タイトルを取得
                title = link.get_text(strip=True)
                if not title or len(title) < 15:
                    continue
                
                # 絶対URLに変換
                if href.startswith("/"):
                    article_url = f"{self.BASE_URL}{href}"
                elif href.startswith("http"):
                    article_url = href
                else:
                    continue
                
                # 重複チェック
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)
                
                articles.append({
                    "url": article_url,
                    "title": title[:200]
                })
            
            time.sleep(1)
        
        return articles

    def get_article_content(self, url: str) -> Optional[dict]:
        """記事の詳細情報を取得"""
        soup = self._fetch_page(url)
        if not soup:
            return None
        
        # タイトル
        title = ""
        title_elem = soup.find("h1", class_=re.compile(r"title|heading"))
        if not title_elem:
            title_elem = soup.find("h1")
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 日付
        date_text = ""
        time_elem = soup.find("time")
        if time_elem:
            date_text = time_elem.get_text(strip=True)
        if not date_text:
            date_text = self._extract_date(soup)
        
        # タグ
        tags = []
        tag_section = soup.find(class_=re.compile(r"tag|keyword|category"))
        if tag_section:
            for tag_link in tag_section.find_all("a")[:5]:
                tag_text = tag_link.get_text(strip=True)
                if tag_text and len(tag_text) < 30:
                    tags.append(tag_text)
        
        # 本文
        content = ""
        
        # 方法1: article-body クラス
        article_body = soup.find(class_=re.compile(r"article[_-]?body|article-text|content"))
        if article_body:
            paragraphs = article_body.find_all("p")
            content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        # 方法2: articleタグ
        if not content:
            article_body = soup.find("article")
            if article_body:
                paragraphs = article_body.find_all("p")
                content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        # 方法3: mainタグ
        if not content:
            main = soup.find("main")
            if main:
                paragraphs = main.find_all("p")
                content = "\n".join(p.get_text(strip=True) for p in paragraphs[:20] if p.get_text(strip=True) and len(p.get_text(strip=True)) > 30)
        
        # 広告テキストなどを除去
        content = re.sub(r"(PR|広告|スポンサー|関連記事|ZDNET Japan).*?\n", "", content)
        
        return {
            "url": url,
            "title": title,
            "date": date_text,
            "category": "AI・テクノロジー",
            "tags": tags,
            "content": content[:5000]
        }

