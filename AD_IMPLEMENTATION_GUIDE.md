# 広告実装ガイド

## 📢 広告を追加する方法

### 1. Google AdSenseの設定

1. **AdSenseアカウント作成**
   - https://www.google.com/adsense/ にアクセス
   - 「今すぐ始める」をクリック
   - Googleアカウントでログイン
   - サイトURLを登録: `https://biz-ai-news.onrender.com`
   - 審査を申請（数日〜数週間かかります）

2. **広告コードの取得**
   - AdSenseダッシュボードにログイン
   - 「広告」→「広告ユニット」を選択
   - 広告タイプを選択（推奨: 「表示広告」→「レスポンシブ」）
   - 広告コードをコピー

### 2. サイトへの実装

#### ステップ1: 広告用CSSスタイルを追加

`webapp/templates/index.html` の `<style>` セクション内に以下を追加:

```css
/* 広告用スタイル */
.ad-container {
    text-align: center;
    margin: 20px 0;
    padding: 15px;
    background: var(--bg-card);
    border-radius: 8px;
    border: 1px solid var(--border);
}

.ad-container ins {
    display: block;
    margin: 0 auto;
}

/* モバイル対応 */
@media (max-width: 768px) {
    .ad-container {
        margin: 15px 0;
        padding: 10px;
    }
}
```

#### ステップ2: 広告を配置する場所

**場所1: フィルターの下（記事一覧の上）**

`webapp/templates/index.html` の `<form class="filters">` の直後（約757行目）に追加:

```html
        </form>

        <!-- 広告エリア1: フィルターの下 -->
        <div class="ad-container">
            <!-- Google AdSenseコードをここに貼り付け -->
            <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX"
                 crossorigin="anonymous"></script>
            <ins class="adsbygoogle"
                 style="display:block"
                 data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
                 data-ad-slot="XXXXXXXXXX"
                 data-ad-format="auto"
                 data-full-width-responsive="true"></ins>
            <script>
                 (adsbygoogle = window.adsbygoogle || []).push({});
            </script>
        </div>

        {% if news_list %}
```

**場所2: 記事一覧の間（5記事ごと）**

`webapp/templates/index.html` の記事ループ内（約796行目の `<tbody>` 内）に追加:

```html
                <tbody>
                    {% for news in news_list %}
                    <tr>
                        <!-- 記事の内容 -->
                    </tr>
                    
                    {% if loop.index % 5 == 0 %}
                    <!-- 広告エリア: 5記事ごと -->
                    <tr>
                        <td colspan="7" style="padding: 20px; background: var(--bg-card);">
                            <div class="ad-container">
                                <!-- Google AdSenseコードをここに貼り付け -->
                                <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX"
                                     crossorigin="anonymous"></script>
                                <ins class="adsbygoogle"
                                     style="display:block"
                                     data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
                                     data-ad-slot="XXXXXXXXXX"
                                     data-ad-format="auto"
                                     data-full-width-responsive="true"></ins>
                                <script>
                                     (adsbygoogle = window.adsbygoogle || []).push({});
                                </script>
                            </div>
                        </td>
                    </tr>
                    {% endif %}
                    {% endfor %}
```

**場所3: フッター上**

`webapp/templates/index.html` の `<footer>` の直前（約960行目）に追加:

```html
    </main>

    <!-- 広告エリア3: フッター上 -->
    <div class="container">
        <div class="ad-container">
            <!-- Google AdSenseコードをここに貼り付け -->
            <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX"
                 crossorigin="anonymous"></script>
            <ins class="adsbygoogle"
                 style="display:block"
                 data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
                 data-ad-slot="XXXXXXXXXX"
                 data-ad-format="auto"
                 data-full-width-responsive="true"></ins>
            <script>
                 (adsbygoogle = window.adsbygoogle || []).push({});
            </script>
        </div>
    </div>

    <footer>
```

### 3. 実装のポイント

- **広告の数**: 1ページに3〜5個程度が適切
- **配置**: コンテンツを邪魔しないように配置
- **レスポンシブ**: AdSenseのレスポンシブ広告を使用
- **パフォーマンス**: AdSenseは自動的に非同期読み込み

### 4. 注意事項

- AdSenseの審査には数日〜数週間かかります
- 審査通過後、広告が表示されるようになります
- プライバシーポリシーページが必要です
- 広告コードの `ca-pub-XXXXXXXXXXXXXXXX` と `data-ad-slot="XXXXXXXXXX"` は、AdSenseから取得した実際の値に置き換えてください

### 5. テスト方法

- 審査通過前は、広告が表示されません
- 審査通過後、数時間で広告が表示され始めます
- AdSenseダッシュボードで広告の表示状況を確認できます

