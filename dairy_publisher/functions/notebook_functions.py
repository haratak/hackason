"""
Firebase Cloud Functions for Notebook Generation
ノートブック生成機能をCloud Functionsとして提供
"""
import os
import base64
from firebase_functions import firestore_fn, https_fn, options, scheduler_fn
from firebase_functions.firestore_fn import (
    on_document_created,
    Event,
    DocumentSnapshot,
)
from firebase_admin import initialize_app, firestore
from google.cloud import firestore as firestore_client
from google.cloud import pubsub_v1
from datetime import datetime, timedelta
import json

# エージェントから必要な関数をインポート
from agent import (
    analyze_period_and_themes,
    collect_episodes_by_theme,
    generate_topic_content,
    validate_and_save_notebook,
    get_firestore_client
)

# Firebase Admin SDKの初期化
initialize_app()

# Firestoreクライアント
db = firestore.client()

# 環境変数
PROJECT_ID = os.environ.get('GCLOUD_PROJECT', 'hackason-464007')


@https_fn.on_request(
    timeout_sec=540,  # 9分のタイムアウト
    memory=options.MemoryOption.GB_2,  # 2GBのメモリ
    cors=options.CorsOptions(
        cors_origins="*",
        cors_methods=["POST"],
    ),
)
def generate_notebook_http(req: https_fn.Request) -> https_fn.Response:
    """HTTPトリガーでノートブック生成を実行"""
    try:
        # リクエストボディを取得
        request_json = req.get_json()
        
        if not request_json:
            return https_fn.Response(
                {"error": "Request body is required"},
                status=400
            )
            
        # 必要なパラメータを取得
        child_id = request_json.get('child_id')
        start_date = request_json.get('start_date')
        end_date = request_json.get('end_date')
        child_info = request_json.get('child_info', None)
        
        # パラメータの検証
        if not child_id:
            return https_fn.Response(
                {"error": "child_id is required"},
                status=400
            )
        if not start_date:
            return https_fn.Response(
                {"error": "start_date is required (YYYY-MM-DD format)"},
                status=400
            )
        if not end_date:
            return https_fn.Response(
                {"error": "end_date is required (YYYY-MM-DD format)"},
                status=400
            )
            
        print(f"Generating notebook for child: {child_id}")
        print(f"Period: {start_date} to {end_date}")
        
        # 子供の基本情報を取得（提供されていない場合）
        if not child_info:
            child_doc = db.collection('children').document(child_id).get()
            if child_doc.exists:
                child_info = child_doc.to_dict()
            else:
                child_info = {"nickname": "お子さん"}
        
        # まず、期間とテーマを分析してnotebook_idを取得
        analysis_result = analyze_period_and_themes(
            child_id=child_id,
            start_date=start_date,
            end_date=end_date,
            child_info=child_info
        )
        
        if analysis_result.get("status") != "success":
            return https_fn.Response(
                {
                    "status": "error",
                    "error": analysis_result.get("error_message", "Failed to analyze period")
                },
                status=500
            )
        
        notebook_id = analysis_result["report"]["notebook_id"]
        
        # ノートブックのステータスドキュメントを作成（処理中状態）
        notebook_ref = db.collection('children').document(child_id)\
                         .collection('notebooks').document(notebook_id)
        
        notebook_ref.set({
            'status': 'generating',  # 生成中
            'generation_started_at': firestore.SERVER_TIMESTAMP,
            'period': {
                'start': start_date,
                'end': end_date
            },
            'nickname': child_info.get('nickname', 'お子さん'),
            'topics': [],  # 後で更新される
            'generation_progress': {
                'current_step': 'analyzing',
                'total_steps': 4,
                'message': '期間とテーマを分析中...'
            }
        })
        
        # Pub/Subにメッセージを送信（バックグラウンド処理）
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, 'notebook-generation')
        
        message_data = {
            'child_id': child_id,
            'start_date': start_date,
            'end_date': end_date,
            'child_info': child_info,
            'notebook_id': notebook_id
        }
        
        # メッセージを送信
        future = publisher.publish(
            topic_path,
            data=json.dumps(message_data).encode('utf-8')
        )
        
        # 非同期処理として即座にレスポンスを返す
        return https_fn.Response({
            'status': 'accepted',
            'notebook_id': notebook_id,
            'message': 'ノートブックの生成を開始しました。生成には数分かかります。',
            'check_status_url': f'/children/{child_id}/notebooks/{notebook_id}'
        }, status=202)  # 202 Accepted
            
    except Exception as e:
        print(f"Error generating notebook: {str(e)}")
        return https_fn.Response(
            {
                'status': 'error',
                'error': str(e)
            },
            status=500
        )


@scheduler_fn.on_schedule(
    schedule="every monday 09:00",  # 毎週月曜日の朝9時
    timezone="Asia/Tokyo",
    timeout_sec=540,
    memory=options.MemoryOption.GB_2
)
def generate_weekly_notebooks(req: scheduler_fn.ScheduledEvent) -> None:
    """週次でノートブックを自動生成"""
    try:
        # 先週の日付範囲を計算
        today = datetime.now()
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        
        start_date = last_monday.strftime("%Y-%m-%d")
        end_date = last_sunday.strftime("%Y-%m-%d")
        
        print(f"Generating weekly notebooks for period: {start_date} to {end_date}")
        
        # アクティブな子供のリストを取得
        children_ref = db.collection('children').where('status', '==', 'active')
        
        success_count = 0
        error_count = 0
        
        for child_doc in children_ref.stream():
            child_id = child_doc.id
            child_info = child_doc.to_dict()
            
            try:
                print(f"Processing child: {child_id} ({child_info.get('nickname', 'Unknown')})")
                
                # ノートブック生成処理（HTTPトリガーと同じロジック）
                analysis_result = analyze_period_and_themes(
                    child_id=child_id,
                    start_date=start_date,
                    end_date=end_date,
                    child_info=child_info
                )
                
                if analysis_result.get("status") != "success":
                    raise Exception(analysis_result.get("error_message", "Analysis failed"))
                
                analysis_report = analysis_result["report"]
                themes = analysis_report["themes"]
                notebook_id = analysis_report["notebook_id"]
                
                # 各テーマごとにエピソードを収集してコンテンツを生成
                topics = []
                all_episodes_count = 0
                layout_types = ["large_photo", "text_only", "small_photo", "medium_photo", "text_only"]
                
                for i, theme in enumerate(themes):
                    episodes_result = collect_episodes_by_theme(
                        theme_info=theme,
                        child_id=child_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if episodes_result.get("status") == "success":
                        episode_count = episodes_result["report"]["episode_count"]
                        all_episodes_count += episode_count
                        
                        content_result = generate_topic_content(
                            theme_episodes=episodes_result["report"],
                            child_info=child_info,
                            topic_layout=layout_types[i]
                        )
                        
                        if content_result.get("status") == "success":
                            topics.append(content_result["report"])
                        else:
                            topics.append({
                                "title": theme["title"],
                                "subtitle": None,
                                "content": f"{theme['title']}に関する記録がありませんでした。",
                                "photo": None,
                                "caption": None,
                                "generated": False
                            })
                    else:
                        topics.append({
                            "title": theme["title"],
                            "subtitle": None,
                            "content": f"{theme['title']}に関する記録がありませんでした。",
                            "photo": None,
                            "caption": None,
                            "generated": False
                        })
                
                # エピソードが見つかった場合のみ保存
                if all_episodes_count > 0:
                    notebook_data = {
                        "notebook_id": notebook_id,
                        "nickname": child_info.get("nickname", "お子さん"),
                        "period": analysis_report["period"],
                        "topics": topics
                    }
                    
                    save_result = validate_and_save_notebook(
                        notebook_data=notebook_data,
                        child_id=child_id
                    )
                    
                    if save_result.get("status") in ["success", "partial_success"]:
                        success_count += 1
                        print(f"Successfully generated notebook for {child_id}")
                    else:
                        error_count += 1
                        print(f"Failed to save notebook for {child_id}: {save_result.get('error_message')}")
                else:
                    print(f"No episodes found for {child_id} in the period")
                    
            except Exception as e:
                error_count += 1
                print(f"Error processing child {child_id}: {str(e)}")
        
        # 処理結果のサマリーを記録
        db.collection('notebook_generation_logs').add({
            'type': 'weekly_batch',
            'period': {
                'start': start_date,
                'end': end_date
            },
            'results': {
                'success_count': success_count,
                'error_count': error_count,
                'total_children': success_count + error_count
            },
            'generated_at': firestore.SERVER_TIMESTAMP,
            'generated_by': 'scheduler'
        })
        
        print(f"Weekly notebook generation completed. Success: {success_count}, Errors: {error_count}")
        
    except Exception as e:
        print(f"Error in weekly notebook generation: {str(e)}")
        
        # エラーログを記録
        db.collection('notebook_generation_logs').add({
            'type': 'weekly_batch_error',
            'error': str(e),
            'generated_at': firestore.SERVER_TIMESTAMP,
            'generated_by': 'scheduler'
        })