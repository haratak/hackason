"""
生成されたエピソードの詳細を確認
"""
from google.cloud import firestore
import json

# Firestoreクライアントを初期化
db = firestore.Client(project="hackason-464007")

# エピソードIDを指定
episode_id = "AKzmb7KlKwnA9V0d2IhI"

# エピソードドキュメントを取得
print(f"📝 Fetching episode details for ID: {episode_id}\n")

episode_doc = db.collection('episodes').document(episode_id).get()

if episode_doc.exists:
    episode_data = episode_doc.to_dict()
    
    print("🎬 Episode Details:")
    print("=" * 60)
    
    # 基本情報
    print(f"Episode ID: {episode_id}")
    print(f"User ID: {episode_data.get('user_id', 'N/A')}")
    print(f"Child ID: {episode_data.get('child_id', 'N/A')}")
    print(f"Created At: {episode_data.get('created_at', 'N/A')}")
    
    # エピソード情報
    print(f"\n📋 Episode Title: {episode_data.get('episode_title', 'N/A')}")
    print(f"Description: {episode_data.get('description', 'N/A')}")
    
    # メディア情報
    print(f"\n🎥 Media URI: {episode_data.get('media_uri', 'N/A')}")
    print(f"Duration: {episode_data.get('duration', 'N/A')}")
    
    # ハイライト
    highlights = episode_data.get('highlights', [])
    if highlights:
        print(f"\n✨ Highlights ({len(highlights)} found):")
        for i, highlight in enumerate(highlights[:3], 1):  # 最初の3つのハイライトを表示
            print(f"\n  {i}. {highlight.get('title', 'N/A')}")
            print(f"     Time: {highlight.get('timestamp', 'N/A')}")
            print(f"     Description: {highlight.get('description', 'N/A')[:100]}...")
            print(f"     Emotion: {highlight.get('emotion', 'N/A')}")
    
    # 客観的事実
    facts = episode_data.get('objective_facts', {})
    if facts:
        print(f"\n📊 Objective Facts:")
        print(f"   Subjects Identified: {facts.get('subjects_identified', 'N/A')}")
        print(f"   Activities: {facts.get('activities', 'N/A')}")
        print(f"   Setting: {facts.get('setting', 'N/A')}")
    
    # 全データを表示（デバッグ用）
    print(f"\n\n🔍 Full Episode Data (JSON):")
    print("=" * 60)
    # 長いテキストを整形
    formatted_data = json.dumps(episode_data, indent=2, default=str, ensure_ascii=False)
    print(formatted_data[:2000] + "..." if len(formatted_data) > 2000 else formatted_data)
    
else:
    print(f"❌ Episode not found with ID: {episode_id}")