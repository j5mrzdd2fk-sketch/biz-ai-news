#!/bin/bash
# マルチサイト AIニューススクレイパー実行スクリプト

cd /Users/masak/Desktop/ニューススクレイピング

# .envファイルを読み込み
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Python実行（multi_site_scraper.pyを使用）
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 multi_site_scraper.py

