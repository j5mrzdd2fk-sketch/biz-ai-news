#!/bin/bash
# AIニュースシステム 自動起動設定スクリプト

echo "🚀 AIニュースシステム 自動起動設定"
echo "=================================="

# プロジェクトディレクトリ
PROJECT_DIR="/Users/masak/Desktop/ニューススクレイピング"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

# ログディレクトリ作成
mkdir -p "$PROJECT_DIR/logs"
echo "✅ ログディレクトリ作成完了"

# 既存のジョブをアンロード（エラーは無視）
launchctl unload "$LAUNCH_AGENTS_DIR/com.ainews.webapp.plist" 2>/dev/null
launchctl unload "$LAUNCH_AGENTS_DIR/com.ledgeai.scraper.plist" 2>/dev/null
echo "✅ 既存ジョブをアンロード"

# plistファイルをコピー
cp "$PROJECT_DIR/com.ainews.webapp.plist" "$LAUNCH_AGENTS_DIR/"
cp "$PROJECT_DIR/com.ledgeai.scraper.plist" "$LAUNCH_AGENTS_DIR/"
echo "✅ 設定ファイルをコピー"

# ジョブをロード
launchctl load "$LAUNCH_AGENTS_DIR/com.ainews.webapp.plist"
launchctl load "$LAUNCH_AGENTS_DIR/com.ledgeai.scraper.plist"
echo "✅ ジョブをロード"

# 状態確認
echo ""
echo "📊 状態確認"
echo "----------"

sleep 2

# Webアプリ確認
if curl -s http://localhost:5001 > /dev/null 2>&1; then
    echo "✅ Webアプリ: 動作中 (http://localhost:5001)"
else
    echo "⏳ Webアプリ: 起動中..."
fi

# 自動収集確認
if launchctl list | grep -q "com.ledgeai.scraper"; then
    echo "✅ 自動収集: 登録済み（1時間ごとに実行）"
else
    echo "❌ 自動収集: 未登録"
fi

echo ""
echo "🎉 設定完了！"
echo ""
echo "📌 注意事項:"
echo "   - Mac起動時に自動で立ち上がります"
echo "   - Webアプリ: http://localhost:5001"
echo "   - 自動収集: 1時間ごとに実行"
echo ""
echo "📁 ログファイル:"
echo "   - $PROJECT_DIR/logs/webapp.log"
echo "   - $PROJECT_DIR/logs/scraper.log"

