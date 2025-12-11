# Renderデプロイ手順

## 1. 事前準備

### 必要な環境変数

Renderのダッシュボードで以下の環境変数を設定してください：

#### 必須
- **OPENAI_API_KEY**: OpenAI APIのキー（形式: `sk-xxxxx...`）
- **GOOGLE_SHEETS_TOKEN**: `token.json`の内容をJSON文字列として設定

#### オプション
- **FLASK_DEBUG**: `false`（本番環境ではデバッグモードをOFF）
- **GOOGLE_SHEETS_CREDENTIALS**: `credentials.json`の内容（必要に応じて）

### GOOGLE_SHEETS_TOKENの取得方法

ローカル環境で以下のコマンドを実行：

```bash
cat token.json
```

出力されたJSONをそのまま環境変数`GOOGLE_SHEETS_TOKEN`に設定します。

または、1行にまとめる場合：

```bash
cat token.json | python3 -m json.tool | tr -d '\n'
```

## 2. GitHubリポジトリにプッシュ

```bash
git add .
git commit -m "Deploy to Render"
git push origin main
```

## 3. RenderでWebサービスを作成

1. Renderのダッシュボードにログイン
2. 「New」→「Web Service」を選択
3. GitHubリポジトリを接続
4. 以下の設定を入力：
   - **Name**: `biz-ai-news`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python webapp/app.py`

## 4. 環境変数を設定

Renderのダッシュボードで：
1. 「Environment」タブを開く
2. 以下の環境変数を追加：
   - `OPENAI_API_KEY`: あなたのOpenAI APIキー
   - `GOOGLE_SHEETS_TOKEN`: token.jsonの内容
   - `FLASK_DEBUG`: `false`

## 5. デプロイ

1. 「Save Changes」をクリック
2. 自動でビルドとデプロイが開始されます
3. ログを確認してエラーがないか確認

## 6. カスタムドメイン設定（オプション）

1. 「Settings」タブを開く
2. 「Custom Domains」セクションでドメインを追加
3. DNS設定を確認

## トラブルシューティング

### エラー: Google認証エラー
- `GOOGLE_SHEETS_TOKEN`が正しく設定されているか確認
- JSON形式が正しいか確認（改行やスペースの問題）

### エラー: ポートエラー
- `PORT`環境変数は自動で設定されるため、手動設定不要

### エラー: モジュールが見つからない
- `requirements.txt`に必要なパッケージが含まれているか確認

