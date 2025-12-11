#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PR TIMES スクレイパー
企業のプレスリリースからAI・DX関連ニュースを取得
"""

import re
import time
from typing import Optional
from .base import BaseScraper


class PRTimesScraper(BaseScraper):
    """PR TIMESのプレスリリースをスクレイピングするクラス"""
    
    SITE_NAME = "PR TIMES"
    BASE_URL = "https://prtimes.jp"
    
    # スクレイピングするキーワードカテゴリ
    SEARCH_KEYWORDS = [
        "生成AI",
        "DX",
        "業務効率化",
        "AI導入",
    ]

    def get_article_list(self, max_pages: int = 2) -> list[dict]:
        """記事一覧を取得"""
        articles = []
        seen_urls = set()
        
        for keyword in self.SEARCH_KEYWORDS:
            url = f"{self.BASE_URL}/topics/keywords/{keyword}"
            
            soup = self._fetch_page(url)
            if not soup:
                continue
            
            # プレスリリースリンクを抽出
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                
                # /main/html/rd/p/で始まるリンクがプレスリリース
                if "/main/html/rd/p/" not in href:
                    continue
                
                # タイトルを取得
                title = link.get_text(strip=True)
                if not title or len(title) < 15:
                    continue
                
                # 絶対URLに変換
                if href.startswith("/"):
                    article_url = f"{self.BASE_URL}{href}"
                else:
                    article_url = href
                
                # 重複チェック
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)
                
                articles.append({
                    "url": article_url,
                    "title": title[:200],
                    "keyword": keyword
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
        
        # 会社名（タグとして使用）
        tags = []
        company_elem = soup.find(class_=re.compile(r"company-name|company"))
        if not company_elem:
            company_elem = soup.find("a", href=lambda x: x and "/company/" in str(x))
        if company_elem:
            company_name = company_elem.get_text(strip=True)
            if company_name:
                tags.append(company_name[:30])
        
        # カテゴリ（タグ要素から取得）
        tag_section = soup.find(class_=re.compile(r"tag|category|keyword"))
        if tag_section:
            for tag_link in tag_section.find_all("a")[:3]:
                tag_text = tag_link.get_text(strip=True)
                if tag_text and len(tag_text) < 30 and tag_text not in tags:
                    tags.append(tag_text)
        
        # 本文
        content = ""
        
        # 方法1: content クラス
        article_body = soup.find(class_=re.compile(r"content|body|text"))
        if article_body:
            paragraphs = article_body.find_all(["p", "div"])
            content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True) and len(p.get_text(strip=True)) > 20)
        
        # 方法2: article タグ
        if not content:
            article_body = soup.find("article")
            if article_body:
                content = article_body.get_text(strip=True)
        
        # 方法3: main タグ
        if not content:
            main = soup.find("main")
            if main:
                content = main.get_text(strip=True)
        
        # 広告・不要テキスト除去
        content = re.sub(r"(お問い合わせ|プレスリリース詳細|関連URL|プロフィール).*", "", content, flags=re.DOTALL)
        
        return {
            "url": url,
            "title": title,
            "date": date_text,
            "category": "プレスリリース",
            "tags": tags,
            "content": content[:5000]
        }

