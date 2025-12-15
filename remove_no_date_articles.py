#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日付なし記事削除スクリプト
Google Sheetsから日付が記載されていない記事を削除します
"""

import os
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
SPREADSHEET_NAME = "AIニュース要約（マルチサイト）"

# 分類ごとのシート名（すべてのシートを処理する場合は空リスト）
SHEET_NAMES = []  # 空の場合は全シートを処理


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


def remove_no_date_articles():
    """日付が記載されていない記事を削除"""
    print("=" * 60)
    print("🗑️  日付なし記事削除ツール")
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
    sheets_to_process = SHEET_NAMES if SHEET_NAMES else spreadsheet.worksheets()
    
    for sheet in sheets_to_process:
        if isinstance(sheet, str):
            # シート名で指定されている場合
            try:
                worksheet = spreadsheet.worksheet(sheet)
                sheet_name = sheet
            except gspread.WorksheetNotFound:
                print(f"   ⚠️ シート「{sheet}」が見つかりません。スキップします。")
                continue
        else:
            # ワークシートオブジェクトの場合
            worksheet = sheet
            sheet_name = sheet.title
        
        print(f"\n📋 シート「{sheet_name}」を処理中...")
        
        # 全データを取得
        all_values = worksheet.get_all_values()
        if len(all_values) <= 1:
            print(f"   📝 データがありません。スキップします。")
            continue
        
        # ヘッダーを除く
        data_rows = all_values[1:]
        
        # 日付なし記事を検出
        rows_to_delete = []
        
        for row_index, row in enumerate(data_rows, start=2):  # 2行目から（1行目はヘッダー）
            if len(row) < 4:
                continue
            
            # 列のインデックス: row[0]: No, row[1]: ソース, row[2]: タイトル, row[3]: 日付
            date = row[3] if len(row) > 3 else ""
            title = row[2] if len(row) > 2 else ""
            
            # 日付が空または空白のみの場合
            if not date or not date.strip():
                rows_to_delete.append(row_index)
                print(f"   🗑️  行{row_index}: 日付なし - {title[:50]}...")
                total_deleted += 1
        
        # 日付なし行を削除（後ろから削除する必要がある）
        if rows_to_delete:
            rows_to_delete.sort(reverse=True)
            for row_index in rows_to_delete:
                try:
                    worksheet.delete_rows(row_index)
                    print(f"      ✅ 行{row_index}を削除しました")
                except Exception as e:
                    print(f"      ⚠️ 行{row_index}の削除エラー: {e}")
        else:
            print(f"   ✅ 日付なし記事はありませんでした")
    
    print("\n" + "=" * 60)
    if total_deleted > 0:
        print(f"🎉 削除完了！合計 {total_deleted}件の日付なし記事を削除しました。")
    else:
        print("✅ 日付なし記事は見つかりませんでした。")
    print("=" * 60)


if __name__ == "__main__":
    remove_no_date_articles()

