#!/usr/bin/env python3
"""
Test script for Multi-Faceted Analysis
新しい多角的分析機能をテストするスクリプト
"""

import os
import sys
from dotenv import load_dotenv

# 現在のディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import process_media_for_cloud_function
from google.cloud import firestore
import json

# 環境変数をロード
load_dotenv()

def test_multi_faceted_analysis():
    """多角的分析のテスト"""
    
    # テスト用のメディアURL（実際のURLに置き換えてください）
    test_media_uri = "https://storage.googleapis.com/hackason-464007-media/demo-images/child-playing.jpg"
    
    # テストケース: 異なる月齢での分析
    test_cases = [
        {
            "age_months": 6,
            "description": "6ヶ月の赤ちゃん（お座り、物への興味、人見知りの時期）"
        },
        {
            "age_months": 12,
            "description": "12ヶ月の幼児（歩行開始、言葉の理解、簡単な指示理解）"
        },
        {
            "age_months": 24,
            "description": "24ヶ月の幼児（複雑な遊び、感情表現、社会性の発達）"
        }
    ]
    
    print("=== Multi-Faceted Analysis Test ===\n")
    
    for test_case in test_cases:
        age = test_case["age_months"]
        desc = test_case["description"]
        
        print(f"\n--- Testing {age} months old child ---")
        print(f"Description: {desc}\n")
        
        # 分析を実行
        result = process_media_for_cloud_function(
            media_uri=test_media_uri,
            user_id="test_user",
            child_id="test_child",
            child_age_months=age
        )
        
        if result.get("status") == "success":
            print(f"✅ Success!")
            print(f"Media ID: {result.get('media_id')}")
            print(f"Child Age: {result.get('child_age_months')} months")
            print(f"Perspectives analyzed: {result.get('perspectives_analyzed')}")
            
            # 成功した分析を表示
            successful = result.get("successful_analyses", [])
            print(f"\nSuccessful analyses ({len(successful)}):")
            for analysis in successful:
                print(f"  - {analysis['perspective_type']} (indexed: {analysis['indexed']})")
            
            # 分析ノートを表示
            if result.get("analysis_note"):
                print(f"\nAnalysis note: {result.get('analysis_note')}")
            
            # 失敗した分析がある場合は表示
            failed = result.get("failed_analyses", [])
            if failed:
                print(f"\nFailed analyses ({len(failed)}):")
                for failure in failed:
                    print(f"  - {failure['perspective_type']}: {failure['error']}")
                    
        else:
            print(f"❌ Error: {result.get('error_message')}")
    
    print("\n=== Test completed ===")


def check_firestore_data():
    """Firestoreに保存されたデータを確認"""
    print("\n=== Checking Firestore Data ===\n")
    
    db = firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "hackason-464007"), 
                         database="database")
    
    # 最新のmediaドキュメントを取得
    media_docs = db.collection("media").order_by("created_at", 
                                                direction=firestore.Query.DESCENDING).limit(3).get()
    
    for media_doc in media_docs:
        media_data = media_doc.to_dict()
        print(f"\nMedia ID: {media_doc.id}")
        print(f"Child ID: {media_data.get('child_id')}")
        print(f"Child Age: {media_data.get('child_age_months')} months")
        print(f"Created: {media_data.get('created_at')}")
        
        # 分析結果を取得
        analyses = media_doc.reference.collection("analyses").get()
        print(f"\nAnalyses ({len(analyses)}):")
        
        for analysis_doc in analyses:
            analysis_data = analysis_doc.to_dict()
            print(f"\n  Analysis ID: {analysis_doc.id}")
            print(f"  Perspective: {analysis_data.get('perspective_type')}")
            print(f"  Title: {analysis_data.get('title')}")
            print(f"  Summary: {analysis_data.get('summary')}")
            print(f"  Significance: {analysis_data.get('significance')}")
            print(f"  Future outlook: {analysis_data.get('future_outlook')}")
            print(f"  Tags: {', '.join(analysis_data.get('vector_tags', []))}")
        
        print("\n" + "-" * 50)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Multi-Faceted Analysis")
    parser.add_argument("--check-firestore", action="store_true", 
                       help="Check data saved in Firestore")
    parser.add_argument("--media-uri", type=str, 
                       help="Custom media URI to test")
    
    args = parser.parse_args()
    
    if args.check_firestore:
        check_firestore_data()
    else:
        if args.media_uri:
            # カスタムメディアURIでテスト
            print(f"Testing with custom media URI: {args.media_uri}")
            result = process_media_for_cloud_function(
                media_uri=args.media_uri,
                user_id="test_user",
                child_id="test_child",
                child_age_months=18
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            # 標準テストを実行
            test_multi_faceted_analysis()