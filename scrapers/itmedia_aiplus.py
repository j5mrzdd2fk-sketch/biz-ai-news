#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ITmedia AI+ スクレイパー
"""

import re
import time
from typing import Optional
from .base import BaseScraper


class ITmediaAiPlusScraper(BaseScraper):
    """ITmedia AI+のニュース記事をスクレイピングするクラス"""
    
    SITE_NAME = "ITmedia AI+"
    BASE_URL = "https://www.itmedia.co.jp"
    
    # カテゴリ別のURL
    CATEGORIES = [
        "/aiplus/subtop/news/index.html",      # 速報
        "/aiplus/subtop/genai/index.html",     # 生成AI
        "/aiplus/subtop/dataanalytics/index.html",  # データ分析
        "/aiplus/subtop/computing/index.html",  # 計算資源
        "/aiplus/subtop/robotics/index.html",   # ロボティクス
    ]

    def get_article_list(self, max_pages: int = 3) -> list[dict]:
        """カテゴリページから記事一覧を取得"""
        articles = []
        seen_urls = set()
        
        for category_url in self.CATEGORIES:
            url = f"{self.BASE_URL}{category_url}"
            
            soup = self._fetch_page(url)
            if not soup:
                continue
            
            # 記事リンクを抽出（/aiplus/articles/で始まるリンク）
            article_links = soup.find_all("a", href=re.compile(r"/aiplus/articles/"))
            
            for link in article_links:
                href = link.get("href", "")
                if not href:
                    continue
                
                # 相対パスを絶対パスに変換
                if href.startswith("/"):
                    full_url = f"{self.BASE_URL}{href}"
                elif href.startswith("http"):
                    full_url = href
                else:
                    continue
                
                # 重複チェック
                if full_url in seen_urls:
                    continue
                
                # タイトルを取得
                title = ""
                # h1, h2, h3タグ内のテキストを探す
                heading = link.find(["h1", "h2", "h3", "h4", "h5"])
                if heading:
                    title = heading.get_text(strip=True)
                else:
                    # リンクテキストから取得
                    title = link.get_text(strip=True)
                
                # タイトルが有効な場合のみ追加
                if title and len(title) > 10 and "/aiplus/articles/" in full_url:
                    seen_urls.add(full_url)
                    articles.append({
                        "url": full_url,
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
        title_elem = soup.find("h1")
        if title_elem:
            title = title_elem.get_text(strip=True)
        else:
            # metaタグから取得
            meta_title = soup.find("meta", property="og:title")
            if meta_title:
                title = meta_title.get("content", "").strip()
        
        # 日付
        date_text = ""
        # 日付パターンを探す
        date_patterns = [
            r"(\d{4}年\d{1,2}月\d{1,2}日)",
            r"(\d{4}/\d{1,2}/\d{1,2})",
            r"(\d{4}-\d{2}-\d{2})",
        ]
        
        # metaタグから日付を取得
        meta_date = soup.find("meta", property="article:published_time")
        if meta_date:
            date_content = meta_date.get("content", "")
            # ISO形式から日付を抽出
            match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_content)
            if match:
                date_text = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
        
        # 日付が見つからない場合は本文から抽出
        if not date_text:
            date_text = self._extract_date(soup, date_patterns)
        
        # カテゴリ
        category = ""
        # URLからカテゴリを推測
        if "/news/" in url:
            category = "速報"
        elif "/genai/" in url:
            category = "生成AI"
        elif "/dataanalytics/" in url:
            category = "データ分析"
        elif "/computing/" in url:
            category = "計算資源"
        elif "/robotics/" in url:
            category = "ロボティクス"
        
        # タグ
        tags = []
        # タグリンクを探す
        tag_links = soup.find_all("a", href=re.compile(r"/aiplus/tag/"))
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
        
        # 方法2: mainタグ内のpタグ
        if not content:
            main = soup.find("main")
            if main:
                paragraphs = main.find_all("p")
                content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        # 方法3: id="CMS"やclass="article-body"など
        if not content:
            cms_div = soup.find("div", id="CMS")
            if cms_div:
                paragraphs = cms_div.find_all("p")
                content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        # 方法4: 全体のpタグ（最後の手段）
        if not content:
            paragraphs = soup.find_all("p")
            content = "\n".join(p.get_text(strip=True) for p in paragraphs[:30] 
                              if p.get_text(strip=True) and len(p.get_text(strip=True)) > 30)
        
        # 不要なテキストを除去
        content = re.sub(r"画像の出典：.*?\n", "", content)
        content = re.sub(r"関連記事：.*?\n?", "", content)
        content = re.sub(r"^.{0,20}(PR|広告|スポンサー).*?\n", "", content, flags=re.MULTILINE)
        content = re.sub(r"この記事は.*?から転載.*?\n", "", content, flags=re.MULTILINE)
        
        return {
            "url": url,
            "title": title,
            "date": date_text,
            "category": category,
            "tags": tags,
            "content": content[:5000]
        }

