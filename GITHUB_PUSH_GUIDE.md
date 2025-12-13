# GitHubへのプッシュ手順（初心者向け）

## 📋 事前準備

1. **GitHubアカウントを持っていること**
   - まだの場合は https://github.com/join で作成

2. **GitHubリポジトリを作成済みであること**
   - https://github.com/new でリポジトリを作成
   - リポジトリ名を入力（例: `biz-ai-news`）
   - 「Create repository」をクリック

## 🔗 ステップ1: リポジトリのURLを確認

1. GitHubで作成したリポジトリのページを開く
2. 緑色の「**Code**」ボタンをクリック
3. 「**HTTPS**」タブが選択されていることを確認
4. 表示されるURLをコピー

**例**: `https://github.com/your-username/biz-ai-news.git`

## 📝 ステップ2: ターミナルでコマンドを実行

### 1. リモートリポジトリを追加

```bash
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git
```

**実際の例**:
```bash
git remote add origin https://github.com/masak/biz-ai-news.git
```

**このコマンドの意味**:
- `git remote add`: リモートリポジトリを追加する
- `origin`: リモートの名前（慣習的に使う名前）
- `https://...`: GitHubリポジトリのURL

### 2. ブランチ名をmainに変更

```bash
git branch -M main
```

**このコマンドの意味**:
- GitHubの標準ブランチ名は`main`
- 現在のブランチ名を`main`に変更する

### 3. GitHubにプッシュ（アップロード）

```bash
git push -u origin main
```

**このコマンドの意味**:
- `git push`: ローカルのコードをGitHubにアップロードする
- `-u`: 次回から`git push`だけでプッシュできるように設定
- `origin`: プッシュ先のリモート名
- `main`: プッシュするブランチ名

## 🔐 認証について

初回プッシュ時、GitHubの認証が求められます。

### 方法1: Personal Access Token（推奨）

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 「Generate new token」をクリック
3. スコープで`repo`にチェック
4. 生成されたトークンをコピー
5. パスワード入力時に、ユーザー名にはGitHubのユーザー名、パスワードにはトークンを入力

### 方法2: GitHub CLI

```bash
gh auth login
```

## ✅ 確認方法

プッシュが成功すると、GitHubのリポジトリページでファイルが表示されます。

## ❌ よくあるエラーと対処法

### エラー1: "remote origin already exists"

**意味**: 既にリモートが追加されています

**対処法**:
```bash
# 既存のリモートを確認
git remote -v

# 削除してから再追加
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git
```

### エラー2: "Authentication failed"

**意味**: 認証に失敗しました

**対処法**:
- Personal Access Tokenを使用しているか確認
- トークンのスコープに`repo`が含まれているか確認

### エラー3: "Permission denied"

**意味**: リポジトリへのアクセス権限がありません

**対処法**:
- リポジトリのURLが正しいか確認
- リポジトリの所有者であることを確認

## 📞 次のステップ

プッシュが完了したら、Renderでの設定に進みます。

詳細は `DEPLOY.md` を参照してください。
