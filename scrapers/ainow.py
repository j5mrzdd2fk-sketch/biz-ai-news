#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AINOW スクレイパー
"""

import re
import time
from typing import Optional
from .base import BaseScraper


class AINowScraper(BaseScraper):
    """AINOWのニュース記事をスクレイピングするクラス"""
    
    SITE_NAME = "AINOW"
    BASE_URL = "https://ainow.ai"

    def get_article_list(self, max_pages: int = 3) -> list[dict]:
        """記事一覧を取得"""
        articles = []
        
        for page in range(1, max_pages + 1):
            if page == 1:
                url = self.BASE_URL
            else:
                url = f"{self.BASE_URL}/page/{page}/"
            
            soup = self._fetch_page(url)
            if not soup:
                break
            
            # 記事リンクを抽出
            article_links = soup.find_all("a", href=re.compile(rf"{self.BASE_URL}/\d+/"))
            
            for link in article_links:
                href = link.get("href", "")
                if href and re.match(rf"{self.BASE_URL}/\d+/", href):
                    # タイトルを取得
                    heading = link.find(["h2", "h3", "h1"])
                    title = heading.get_text(strip=True) if heading else link.get_text(strip=True)
                    
                    if title and len(title) > 10 and not any(a["url"] == href for a in articles):
                        articles.append({
                            "url": href,
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
        title_elem = soup.find("h1", class_=re.compile(r"entry-title|post-title|title"))
        if not title_elem:
            title_elem = soup.find("h1")
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 日付
        date_text = ""
        date_elem = soup.find(class_=re.compile(r"date|time|posted"))
        if date_elem:
            date_text = self._extract_date(soup)
        if not date_text:
            date_text = self._extract_date(soup)
        
        # カテゴリ
        category = ""
        cat_elem = soup.find(class_=re.compile(r"category|cat"))
        if cat_elem:
            category = cat_elem.get_text(strip=True)[:20]
        
        # タグ
        tags = []
        tag_section = soup.find(class_=re.compile(r"tag|keyword"))
        if tag_section:
            tag_links = tag_section.find_all("a")
            for tag_link in tag_links[:5]:
                tag_text = tag_link.get_text(strip=True)
                if tag_text and len(tag_text) < 30:
                    tags.append(tag_text)
        
        # 本文
        content = ""
        article_body = soup.find(class_=re.compile(r"entry-content|post-content|article-body"))
        if not article_body:
            article_body = soup.find("article")
        
        if article_body:
            paragraphs = article_body.find_all("p")
            content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        return {
            "url": url,
            "title": title,
            "date": date_text,
            "category": category,
            "tags": tags,
            "content": content[:5000]
        }

