#!/usr/bin/env python3
"""
Test Multi-Faceted Analysis with sample data
URLアクセスエラーを回避してサンプルデータで多角的分析をテスト
"""

import os
import sys
from dotenv import load_dotenv

# 現在のディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import (
    perspective_determiner,
    dynamic_multi_analyzer,
    save_analysis,
    index_analysis
)
import uuid

# 環境変数をロード
load_dotenv()

def test_multi_faceted_analysis_with_sample():
    """サンプルデータで多角的分析をテスト"""
    print("=== Multi-Faceted Analysis Test with Sample Data ===\n")
    
    # サンプルの客観的事実データ（URLアクセスエラーを回避）
    sample_facts = {
        "all_observed_actions": ["飲み物を飲む", "カップを持つ"],
        "observed_emotions": ["楽しげ", "満足そう"],
        "spoken_words": [],
        "environment": "屋外、砂利の地面、出店のようなものが見える",
        "physical_interactions": ["ストローで飲み物を飲んでいる", "両手で赤い苺型の容器を持っている"],
        "body_movements": []
    }
    
    # テストケース: 30ヶ月の子供
    child_age_months = 30
    print(f"Testing with {child_age_months} months old child")
    print(f"Sample facts: {sample_facts}\n")
    
    # 1. 分析視点を決定
    print("1. Determining perspectives...")
    perspectives_result = perspective_determiner(sample_facts, child_age_months)
    
    if perspectives_result.get("status") != "success":
        print(f"❌ perspective_determiner failed: {perspectives_result}")
        return
    
    perspectives_data = perspectives_result.get("report", {})
    perspectives = perspectives_data.get("perspectives", [])
    
    print(f"✅ Determined {len(perspectives)} perspectives:")
    for i, perspective in enumerate(perspectives, 1):
        print(f"  {i}. {perspective['type']}: {perspective['focus']}")
    
    print(f"\nAnalysis note: {perspectives_data.get('analysis_note', '')}\n")
    
    # 2. 各視点から分析
    print("2. Analyzing from each perspective...")
    analysis_results = []
    
    for i, perspective in enumerate(perspectives, 1):
        print(f"\n--- Perspective {i}: {perspective['type']} ---")
        
        # 分析実行
        analysis_result = dynamic_multi_analyzer(sample_facts, perspective)
        
        if analysis_result.get("status") == "success":
            analysis_data = analysis_result.get("report", {})
            print(f"✅ Analysis successful:")
            print(f"   Title: {analysis_data.get('title', 'N/A')}")
            print(f"   Summary: {analysis_data.get('summary', 'N/A')}")
            print(f"   Significance: {analysis_data.get('significance', 'N/A')}")
            print(f"   Future outlook: {analysis_data.get('future_outlook', 'N/A')}")
            print(f"   Tags: {', '.join(analysis_data.get('vector_tags', []))}")
            
            analysis_results.append({
                "perspective": perspective,
                "analysis": analysis_data,
                "status": "success"
            })
        else:
            print(f"❌ Analysis failed: {analysis_result}")
            analysis_results.append({
                "perspective": perspective,
                "status": "error",
                "error": analysis_result.get("error_message", "Unknown error")
            })
    
    # 3. 保存とインデックス化をテスト（オプション）
    print(f"\n3. Testing save and index (optional)...")
    
    media_id = str(uuid.uuid4())
    successful_saves = 0
    
    for result in analysis_results:
        if result["status"] == "success":
            try:
                # 保存テスト
                save_result = save_analysis(
                    result["analysis"],
                    media_id=media_id,
                    media_source_uri="test://sample-data",
                    child_id="demo",
                    child_age_months=child_age_months,
                    user_id="test_user"
                )
                
                if save_result.get("status") == "success":
                    analysis_id = save_result.get("analysis_id")
                    print(f"✅ Saved {result['perspective']['type']} analysis: {analysis_id}")
                    
                    # インデックス化テスト（Vector Searchが設定されている場合のみ）
                    index_result = index_analysis(
                        result["analysis"],
                        media_id=media_id,
                        analysis_id=analysis_id,
                        child_id="demo",
                        perspective_type=result['perspective']['type']
                    )
                    
                    if index_result.get("status") == "success":
                        print(f"✅ Indexed {result['perspective']['type']} analysis")
                    else:
                        print(f"⚠️ Indexing skipped or failed: {index_result.get('message', 'Unknown')}")
                    
                    successful_saves += 1
                else:
                    print(f"❌ Save failed for {result['perspective']['type']}: {save_result}")
                    
            except Exception as e:
                print(f"❌ Error saving/indexing {result['perspective']['type']}: {e}")
    
    # 結果サマリー
    print(f"\n=== Summary ===")
    print(f"Perspectives determined: {len(perspectives)}")
    print(f"Successful analyses: {sum(1 for r in analysis_results if r['status'] == 'success')}")
    print(f"Successful saves: {successful_saves}")
    print(f"Media ID: {media_id}")


if __name__ == "__main__":
    test_multi_faceted_analysis_with_sample()