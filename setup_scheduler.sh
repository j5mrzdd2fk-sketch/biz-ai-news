#!/bin/bash
# Ledge.ai スクレイパー 自動実行セットアップスクリプト

SCRIPT_DIR="/Users/masak/Desktop/ニューススクレイピング"
PLIST_NAME="com.ledgeai.scraper.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "=============================================="
echo "🤖 Ledge.ai スクレイパー 自動実行セットアップ"
echo "=============================================="

# ログディレクトリ作成
mkdir -p "$SCRIPT_DIR/logs"
echo "✅ ログディレクトリを作成: $SCRIPT_DIR/logs"

# LaunchAgentsディレクトリ確認
mkdir -p "$LAUNCH_AGENTS_DIR"

# plistファイルをコピー
cp "$SCRIPT_DIR/$PLIST_NAME" "$LAUNCH_AGENTS_DIR/"
echo "✅ plistファイルをコピー: $LAUNCH_AGENTS_DIR/$PLIST_NAME"

# 既存のジョブをアンロード（エラーは無視）
launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null

# ジョブをロード
launchctl load "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
echo "✅ スケジューラーを起動しました"

# 状態確認
echo ""
echo "📋 スケジューラーの状態:"
launchctl list | grep ledgeai

echo ""
echo "=============================================="
echo "🎉 セットアップ完了！"
echo ""
echo "📌 設定内容:"
echo "   - 実行間隔: 30分ごと"
echo "   - ログ: $SCRIPT_DIR/logs/"
echo ""
echo "📌 便利なコマンド:"
echo "   停止: launchctl unload ~/Library/LaunchAgents/$PLIST_NAME"
echo "   開始: launchctl load ~/Library/LaunchAgents/$PLIST_NAME"
echo "   状態: launchctl list | grep ledgeai"
echo "   ログ: tail -f $SCRIPT_DIR/logs/scraper.log"
echo "=============================================="

