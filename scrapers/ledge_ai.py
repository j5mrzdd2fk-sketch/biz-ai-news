#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ledge.ai スクレイパー
"""

import re
import time
from typing import Optional
from .base import BaseScraper


class LedgeAiScraper(BaseScraper):
    """Ledge.aiのニュース記事をスクレイピングするクラス"""
    
    SITE_NAME = "Ledge.ai"
    BASE_URL = "https://ledge.ai"
    
    CATEGORIES = [
        "/categories/business",
        "/categories/public",
    ]

    def get_article_list(self, max_pages: int = 3) -> list[dict]:
        """カテゴリページから記事一覧を取得"""
        articles = []
        
        for category_url in self.CATEGORIES:
            for page in range(1, max_pages + 1):
                url = f"{self.BASE_URL}{category_url}"
                if page > 1:
                    url = f"{url}?page={page}"
                
                soup = self._fetch_page(url)
                if not soup:
                    break
                
                article_links = soup.find_all("a", href=re.compile(r"^/articles/"))
                
                for link in article_links:
                    href = link.get("href", "")
                    if href and href.startswith("/articles/"):
                        heading = link.find(["h3", "h2", "h1"])
                        title = heading.get_text(strip=True) if heading else link.get_text(strip=True)
                        
                        if title and len(title) > 10:
                            article_url = f"{self.BASE_URL}{href}"
                            if not any(a["url"] == article_url for a in articles):
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
        title_elem = soup.find("h1")
        title = title_elem.get_text(strip=True) if title_elem else ""
        
        # 日付
        date_text = self._extract_date(soup)
        
        # カテゴリ
        category = ""
        for cat_name in ["ビジネス", "公共", "学術＆研究", "エンタメ＆アート"]:
            if cat_name in soup.get_text()[:1000]:
                category = cat_name
                break
        
        # タグ
        tags = []
        tag_links = soup.find_all("a", href=re.compile(r"/search\?q="))
        for tag_link in tag_links[:5]:
            tag_text = tag_link.get_text(strip=True)
            if tag_text and len(tag_text) < 30:
                tags.append(tag_text)
        
        # 本文（複数の方法で取得を試みる）
        content = ""
        
        # 方法1: articleタグ
        article = soup.find("article")
        if article:
            paragraphs = article.find_all("p")
            content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        # 方法2: mainタグ
        if not content:
            main = soup.find("main")
            if main:
                paragraphs = main.find_all("p")
                content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        # 方法3: 全体のpタグ
        if not content:
            paragraphs = soup.find_all("p")
            content = "\n".join(p.get_text(strip=True) for p in paragraphs[:20] if p.get_text(strip=True) and len(p.get_text(strip=True)) > 30)
        
        # 不要なテキストを除去
        content = re.sub(r"画像の出典：.*?\n", "", content)
        content = re.sub(r"関連記事：.*?\n?", "", content)
        content = re.sub(r"^.{0,20}(PR|広告|スポンサー).*?\n", "", content, flags=re.MULTILINE)
        
        return {
            "url": url,
            "title": title,
            "date": date_text,
            "category": category,
            "tags": tags,
            "content": content[:5000]
        }

