#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重複記事削除スクリプト
Google Sheetsから重複した記事を削除します
- URLが同じ記事
- タイトルが同じ記事
"""

import os
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import gspread

# Google Sheets APIのスコープ
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

# 認証情報のパス
CREDENTIALS_FILE = "/Users/masak/Desktop/ニューススクレイピング/credentials.json"
TOKEN_FILE = "/Users/masak/Desktop/ニューススクレイピング/token.json"

# スプレッドシート名
SPREADSHEET_NAME = "Ledge.ai AIニュース要約"

# 分類ごとのシート名
SHEET_NAMES = ["企業効率化", "DX・デジタル化", "企業導入", "その他"]


def normalize_url(url: str) -> str:
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


def normalize_title(title: str) -> str:
    """タイトルを正規化（重複チェック用）"""
    if not title:
        return ""
    
    # タイトルを正規化（空白を統一、大文字小文字を無視、特殊文字を除去）
    normalized = title.lower().replace(" ", "").replace("　", "").replace("、", "").replace("，", "")
    normalized = normalized.replace("・", "").replace("ー", "").replace("-", "").replace("―", "")
    return normalized


def authenticate():
    """Google認証を行う"""
    print("🔐 Google認証中...")
    
    creds = None
    
    # 既存のトークンがあれば読み込み
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # 認証が必要な場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # トークンを保存
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    client = gspread.authorize(creds)
    print("✅ Google認証完了")
    return client


def remove_duplicates():
    """重複記事を削除"""
    print("=" * 60)
    print("🗑️  重複記事削除ツール")
    print("=" * 60)
    
    # 認証
    client = authenticate()
    
    # スプレッドシートを開く
    try:
        spreadsheet = client.open(SPREADSHEET_NAME)
        print(f"📂 スプレッドシートを開きました: {SPREADSHEET_NAME}")
    except gspread.SpreadsheetNotFound:
        print(f"❌ エラー: スプレッドシート「{SPREADSHEET_NAME}」が見つかりません。")
        return
    
    total_deleted = 0
    
    # 各シートを処理
    for sheet_name in SHEET_NAMES:
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            print(f"\n📋 シート「{sheet_name}」を処理中...")
        except gspread.WorksheetNotFound:
            print(f"   ⚠️ シート「{sheet_name}」が見つかりません。スキップします。")
            continue
        
        # 全データを取得
        all_values = worksheet.get_all_values()
        if len(all_values) <= 1:
            print(f"   📝 データがありません。スキップします。")
            continue
        
        # ヘッダーを除く
        data_rows = all_values[1:]
        
        # 重複を検出
        seen_urls = {}
        seen_titles = {}
        rows_to_delete = []
        
        for row_index, row in enumerate(data_rows, start=2):  # 2行目から（1行目はヘッダー）
            if len(row) < 7:
                continue
            
            title = row[1] if len(row) > 1 else ""
            url = row[6] if len(row) > 6 else ""
            
            # URLを正規化
            normalized_url = normalize_url(url)
            normalized_title = normalize_title(title)
            
            # URLベースの重複チェック
            if normalized_url and normalized_url in seen_urls:
                rows_to_delete.append(row_index)
                print(f"   🗑️  行{row_index}: URL重複 - {title[:50]}...")
                total_deleted += 1
                continue
            
            # タイトルベースの重複チェック
            if normalized_title and normalized_title in seen_titles:
                rows_to_delete.append(row_index)
                print(f"   🗑️  行{row_index}: タイトル重複 - {title[:50]}...")
                total_deleted += 1
                continue
            
            # 記録
            if normalized_url:
                seen_urls[normalized_url] = row_index
            if normalized_title:
                seen_titles[normalized_title] = row_index
        
        # 重複行を削除（後ろから削除する必要がある）
        if rows_to_delete:
            # 降順にソート（後ろの行から削除）
            rows_to_delete.sort(reverse=True)
            
            for row_index in rows_to_delete:
                try:
                    worksheet.delete_rows(row_index)
                    print(f"      ✅ 行{row_index}を削除しました")
                except Exception as e:
                    print(f"      ⚠️ 行{row_index}の削除エラー: {e}")
        else:
            print(f"   ✅ 重複はありませんでした")
    
    print("\n" + "=" * 60)
    print("🎉 処理完了！")
    print(f"   🗑️  削除した記事数: {total_deleted}件")
    print("=" * 60)


if __name__ == "__main__":
    try:
        remove_duplicates()
    except KeyboardInterrupt:
        print("\n\n⚠️ 処理が中断されました。")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

