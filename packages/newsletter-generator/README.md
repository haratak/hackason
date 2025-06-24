# AI連絡帳ジェネレーター

保育園の育児記録から、AIを使って構造化された連絡帳コンテンツを生成するPythonパッケージです。

## 特徴

- 🤖 Google Gemini APIを使用したコンテンツ生成
- 📊 構造化されたJSON形式での出力
- 🎯 セクションタイプに応じた適切なコンテンツ生成
- 📅 期間に応じた動的なタイトル（週/月単位）
- 🔍 RAGパターンによる関連記録の検索と活用

## クイックスタート

### インストール

```bash
# Python 3.12環境のセットアップ
uv venv
uv pip install -e .
```

### 環境変数の設定

```bash
# Google API Key (必須)
export GOOGLE_API_KEY=your-api-key
```

### 実行

```bash
# サンプルの実行
make run

# または直接実行
uv run python examples/basic_example.py
```

## 基本的な使い方

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

asyncio.run(main())
```

## 出力例

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
      "content": {
        "text": "太郎ちゃん（3歳0ヶ月）は今月も元気に過ごしました..."
      }
    }
  ]
}
```

## ドキュメント

詳細なドキュメントは以下を参照してください：

- [詳細README](docs/README.md) - 機能詳細、AI/LLM活用の説明、全体システムでの位置づけ
- [アーキテクチャ](docs/ARCHITECTURE.md) - システム設計、クラス構成、拡張方法

## 開発

```bash
# 開発環境のセットアップ
make init

# テストの実行（実装予定）
make test

# 出力ファイルのクリーンアップ
make clean-output
```

## ライセンス

MIT