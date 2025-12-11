#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ログ設定モジュール
- ログレベルの導入（INFO, WARNING, ERROR）
- ログローテーション機能
- スタックトレースの記録
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# ログディレクトリ
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ログファイルのパス
SCRAPER_LOG = os.path.join(LOG_DIR, "scraper.log")
SCRAPER_ERROR_LOG = os.path.join(LOG_DIR, "scraper_error.log")
WEBAPP_LOG = os.path.join(LOG_DIR, "webapp.log")
WEBAPP_ERROR_LOG = os.path.join(LOG_DIR, "webapp_error.log")

# ログローテーション設定
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5  # 5ファイルまで保持


def setup_logger(name: str, log_file: str, error_log_file: str = None, level=logging.INFO):
    """
    ロガーをセットアップ
    
    Args:
        name: ロガー名
        log_file: 通常ログファイルのパス
        error_log_file: エラーログファイルのパス（Noneの場合はlog_fileを使用）
        level: ログレベル
    
    Returns:
        logging.Logger: セットアップされたロガー
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 既存のハンドラーをクリア
    logger.handlers = []
    
    # フォーマッター
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 通常ログ用のローテーションハンドラー
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # エラーログ用のローテーションハンドラー
    if error_log_file:
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
    
    # コンソール出力用ハンドラー（開発時のみ）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def get_scraper_logger():
    """スクレイパー用ロガーを取得"""
    return setup_logger(
        'scraper',
        SCRAPER_LOG,
        SCRAPER_ERROR_LOG,
        level=logging.INFO
    )


def get_webapp_logger():
    """Webアプリ用ロガーを取得"""
    return setup_logger(
        'webapp',
        WEBAPP_LOG,
        WEBAPP_ERROR_LOG,
        level=logging.INFO
    )


def log_exception(logger: logging.Logger, error: Exception, context: str = ""):
    """
    例外を詳細にログ記録（スタックトレース含む）
    
    Args:
        logger: ロガー
        error: 例外オブジェクト
        context: エラーが発生したコンテキスト（関数名など）
    """
    import traceback
    
    error_msg = f"{context}: {type(error).__name__}: {str(error)}" if context else f"{type(error).__name__}: {str(error)}"
    logger.error(error_msg)
    logger.error("スタックトレース:\n" + ''.join(traceback.format_exception(type(error), error, error.__traceback__)))

