"""Basic example of newsletter generation."""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from newsletter_generator import (
    ChildProfile,
    GenerateParams,
    MockRecordReader,
    NewsletterExporter,
    NewsletterGenerator,
    create_sample_childcare_records,
)


def create_sample_data() -> GenerateParams:
    """サンプルデータを作成する."""
    # モック育児記録リーダーを作成
    mock_reader = MockRecordReader()
    
    # サンプル育児記録を追加
    sample_records = create_sample_childcare_records()
    mock_reader.add_records(sample_records)
    
    return GenerateParams(
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
        record_reader=mock_reader,
        timeline={
            "child_id": "child-123",
            "milestones": [
                {
                    "id": "milestone-001",
                    "type": "first_walk",
                    "date": "2023-12-15",
                    "description": "初めて一人で歩いた",
                    "media_ids": [],
                }
            ],
            "preferences": [
                {
                    "category": "toy",
                    "items": ["ブロック", "ボール"],
                    "last_observed": datetime(2024, 1, 20),
                }
            ],
            "last_updated": datetime.now(),
        },
    )


async def main() -> None:
    """メイン処理."""
    print("連絡帳生成のサンプルを実行します...\n")
    
    # 環境変数を読み込み
    load_dotenv()
    
    # API キーの確認
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("⚠️  GOOGLE_API_KEY が設定されていません。")
        print("\n設定方法:")
        print("1. .env ファイルを作成（推奨）:")
        print("   cp .env.example .env")
        print("   # .env ファイルを編集して GOOGLE_API_KEY を設定")
        print("\n2. または環境変数で設定:")
        print("   export GOOGLE_API_KEY=your-actual-api-key\n")
        return
    
    try:
        # 生成器を初期化
        generator = NewsletterGenerator()
        exporter = NewsletterExporter()
        
        # サンプルデータを作成
        params = create_sample_data()
        
        print("📝 連絡帳を生成中...")
        print("- 育児記録から情報を読み込み中...")
        newsletter = await generator.generate(params)
        
        print("\n✅ 連絡帳が生成されました:")
        print(f"- ID: {newsletter.id}")
        print(f"- タイトル: {newsletter.title}")
        print(f"- セクション数: {len(newsletter.sections)}")
        print(
            f"- 期間: {newsletter.period['start'].strftime('%Y/%m/%d')} ～ "
            f"{newsletter.period['end'].strftime('%Y/%m/%d')}"
        )
        print(f"- 使用した育児記録数: {newsletter.metadata.get('record_count', 0)}件")
        
        # JSONとして出力
        output_path = Path("./examples/output")
        output_path.mkdir(parents=True, exist_ok=True)
        
        print("\n📄 JSONファイルを出力中...")
        json_path = output_path / f"newsletter_{newsletter.id}.json"
        exporter.save_json(newsletter, json_path)
        
        print(f"\n✅ 出力完了:")
        print(f"- JSON: {json_path}")
        
        # コンソールにも構造を表示
        print("\n📋 生成されたコンテンツ構造:")
        newsletter_dict = exporter.to_dict(newsletter)
        for section in newsletter_dict["sections"]:
            print(f"\n【{section['title']}】(type: {section['type']})")
            content = section["content"]
            if content.get("text"):
                print(f"  テキスト: {content['text'][:100]}...")
            if content.get("caption"):
                print(f"  キャプション: {content['caption']}")
            if content.get("photo_url"):
                print(f"  写真URL: {content['photo_url']}")
        
        # 再生成のサンプル（レート制限を考慮してコメントアウト）
        # print("\n🔄 プロンプトで再生成中...")
        # 
        # # 初回生成から少し間隔を空ける
        # print("⏳ レート制限回避のため5秒待機中...")
        # await asyncio.sleep(5)
        # 
        # regenerated = await generator.regenerate(
        #     RegenerateParams(
        #         newsletter=newsletter,
        #         prompt="育児記録の具体的な観察内容をより詳しく記載してください",
        #     )
        # )
        # 
        # print(f"✅ 再生成完了 (バージョン: {regenerated.version})")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())