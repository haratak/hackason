# AI連絡帳ジェネレーター

保育園の育児記録から、AIを使って構造化された連絡帳コンテンツを生成するPythonパッケージです。

## 特徴

- 🤖 Google Gemini APIを使用したコンテンツ生成
- 📊 構造化されたJSON形式での出力
- 🎯 セクションタイプに応じた適切なコンテンツ生成
- 📅 期間に応じた動的なタイトル（週/月単位）
- 🔍 RAGパターンによる関連記録の検索と活用

## インストール

```bash
# Python 3.12環境のセットアップ
uv venv
uv pip install -e .
```

## 使い方

### 基本的な使い方

```python
import asyncio
from datetime import datetime
from newsletter_generator import (
    NewsletterGenerator,
    NewsletterExporter,
    GenerateParams,
    ChildProfile,
    MockRecordReader,
    create_sample_childcare_records,
)

async def main():
    # 生成器とエクスポーターを初期化
    generator = NewsletterGenerator()
    exporter = NewsletterExporter()
    
    # モックデータを準備
    reader = MockRecordReader()
    reader.add_records(create_sample_childcare_records())
    
    # パラメータを設定
    params = GenerateParams(
        child_profile=ChildProfile(
            id="child-123",
            name="太郎",
            birth_date=datetime(2022, 6, 1),
            gender="male",
        ),
        period={
            "start": datetime(2024, 1, 1),
            "end": datetime(2024, 1, 31),
        },
        record_reader=reader,
    )
    
    # 連絡帳を生成
    newsletter = await generator.generate(params)
    
    # JSONとして出力
    json_str = exporter.to_json(newsletter)
    print(json_str)
    
    # ファイルに保存
    exporter.save_json(newsletter, "output/newsletter.json")

asyncio.run(main())
```

## 出力形式

生成されるJSONの構造:

```json
{
  "id": "1750806080_357f2782",
  "version": 1,
  "child_id": "child-123",
  "title": "太郎ちゃんの1月の成長記録",
  "period": {
    "start": "2024-01-01T00:00:00",
    "end": "2024-01-31T00:00:00"
  },
  "sections": [
    {
      "id": "sec-1",
      "type": "overview",
      "title": "今月の様子",
      "order": 1,
      "content": {
        "text": "太郎ちゃん（3歳0ヶ月）は今月も元気に...",
        "metadata": {
          "record_count": 30,
          "record_ids": ["rec-001", "rec-002", ...]
        }
      }
    },
    {
      "id": "sec-2",
      "type": "favorite-play",
      "title": "お気に入りの遊び",
      "order": 3,
      "content": {
        "text": "ブロック遊びに夢中で...",
        "photo_url": "gs://bucket/photos/photo-123.jpg",
        "photo_description": "ブロック遊び"
      }
    },
    {
      "id": "sec-3",
      "type": "first-time",
      "title": "初めての体験",
      "order": 4,
      "content": {
        "photo_url": "gs://bucket/photos/photo-456.jpg",
        "caption": "初めてのボールキック！"
      }
    }
  ],
  "metadata": {
    "child_age": {"years": 3, "months": 0},
    "record_count": 30
  },
  "generated_at": "2025-06-25T12:34:56"
}
```

## セクションタイプ

- **overview**: 全体の様子（テキストのみ）
- **activities**: 活動記録（テキストのみ）
- **favorite-play**: お気に入りの遊び（テキスト＋写真）
- **growth-moment**: 成長の瞬間（テキスト＋写真）
- **places-visited**: 訪れた場所（テキストのみ）
- **first-time**: 初めての体験（写真＋キャプション）
- **development**: できるようになったこと（テキストのみ）
- **best-shot**: ベストショット（写真＋キャプション）

## 環境変数

```bash
# Google API Key (必須)
export GOOGLE_API_KEY=your-api-key

# 使用するモデル (オプション、デフォルト: gemini-1.5-flash)
export GEMINI_MODEL=gemini-1.5-flash
```

## 開発

```bash
# 開発環境のセットアップ
make init

# サンプルの実行
make run

# 出力ファイルのクリーンアップ
make clean-output
```

## ライセンス

MIT