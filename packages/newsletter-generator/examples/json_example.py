"""Simple JSON output example."""

import asyncio
import json
import os

from dotenv import load_dotenv

from newsletter_generator import (
    ChildProfile,
    GenerateParams,
    MockRecordReader,
    NewsletterExporter,
    NewsletterGenerator,
    create_sample_childcare_records,
)


async def main():
    """メイン処理."""
    # 環境変数を読み込み
    load_dotenv()
    
    # API キーの確認
    if not os.getenv("GOOGLE_API_KEY"):
        print("❌ エラー: Google API キーが設定されていません")
        return
    
    # 生成器とエクスポーターを初期化
    generator = NewsletterGenerator()
    exporter = NewsletterExporter()
    
    # テストデータを準備
    mock_reader = MockRecordReader()
    mock_reader.add_records(create_sample_childcare_records())
    
    params = GenerateParams(
        child_profile=ChildProfile(
            id="child-123",
            name="太郎",
            birth_date=asyncio.get_event_loop().run_until_complete(
                asyncio.coroutine(lambda: __import__('datetime').datetime(2022, 6, 1))()
            ),
            gender="male",
        ),
        period={
            "start": __import__('datetime').datetime(2024, 1, 1),
            "end": __import__('datetime').datetime(2024, 1, 31),
        },
        record_reader=mock_reader,
    )
    
    # 連絡帳を生成
    print("🤖 連絡帳を生成中...")
    newsletter = await generator.generate(params)
    
    # JSONとして出力（整形して表示）
    print("\n📋 生成された連絡帳 (JSON形式):")
    print("=" * 60)
    print(exporter.to_json(newsletter))
    print("=" * 60)
    
    # 構造の概要を表示
    print("\n📊 コンテンツ概要:")
    data = exporter.to_dict(newsletter)
    print(f"- タイトル: {data['title']}")
    print(f"- 期間: {data['period']['start']} ～ {data['period']['end']}")
    print(f"- セクション数: {len(data['sections'])}")
    
    for section in data['sections']:
        print(f"\n  [{section['type']}] {section['title']}")
        content = section['content']
        if 'text' in content:
            print(f"    - テキスト: {len(content['text'])}文字")
        if 'caption' in content:
            print(f"    - キャプション: {content['caption']}")
        if 'photo_url' in content:
            print(f"    - 写真: あり")


if __name__ == "__main__":
    asyncio.run(main())