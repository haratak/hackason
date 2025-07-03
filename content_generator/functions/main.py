"""
Firebase Cloud Functions for Notebook Generation
ノートブック生成機能をCloud Functionsとして提供
"""
import os
from firebase_functions import firestore_fn, options, scheduler_fn
from firebase_functions.firestore_fn import (
    on_document_created,
    Event,
    DocumentSnapshot,
)
from firebase_admin import initialize_app, firestore
from google.cloud import firestore as firestore_client
from datetime import datetime, timedelta
import json

# エージェントから必要な関数をインポート
from agent import (
    analyze_period_and_themes,
    orchestrate_notebook_generation,
    validate_and_save_notebook,
    get_firestore_client
)

# Firebase Admin SDKの初期化
initialize_app()

# Firestoreクライアント
db = firestore.client()

# 環境変数
PROJECT_ID = os.environ.get('GCLOUD_PROJECT', 'hackason-464007')


@on_document_created(
    document="children/{childId}/notebooks/{notebookId}",
    timeout_sec=540,  # 9分のタイムアウト
    memory=options.MemoryOption.GB_2,  # 2GBのメモリ
)
def generate_notebook_on_create(event: Event[DocumentSnapshot]) -> None:
    """Firestoreドキュメント作成トリガーでノートブック生成を実行"""
    try:
        # イベントデータを取得
        snapshot = event.data
        if not snapshot:
            print("No data found in document snapshot")
            return
            
        # ドキュメントのパスから情報を取得
        child_id = event.params["childId"]
        notebook_doc_id = event.params["notebookId"]
        
        # ドキュメントデータを取得
        notebook_request = snapshot.to_dict()
        
        # ステータスをチェック（既に処理済みの場合はスキップ）
        if notebook_request.get('status') != 'requested':
            print(f"Notebook {notebook_doc_id} is not in 'requested' status")
            return
            
        # ステータスを即座に processing に更新
        notebook_ref = db.collection('children').document(child_id).collection('notebooks').document(notebook_doc_id)
        notebook_ref.update({
            'status': 'processing',
            'processingStartedAt': firestore.SERVER_TIMESTAMP
        })
        
        # 必要なパラメータを取得
        period_info = notebook_request.get('period', {})
        start_date = period_info.get('start')
        end_date = period_info.get('end')
        
        # デバッグログ（必要に応じてコメントアウト）
        # print(f"Raw start_date type: {type(start_date)}, value: {start_date}")
        # print(f"Raw end_date type: {type(end_date)}, value: {end_date}")
        
        # Timestampをdatetime文字列に変換
        if hasattr(start_date, 'seconds'):
            start_date = datetime.fromtimestamp(start_date.seconds).strftime("%Y-%m-%d")
        elif hasattr(start_date, 'timestamp'):
            # DatetimeWithNanoseconds型の場合
            start_date = start_date.strftime("%Y-%m-%d")
        elif isinstance(start_date, str):
            # 既に文字列の場合はそのまま使用
            pass
        else:
            # その他の場合はstrに変換して日付部分のみ抽出
            start_date_str = str(start_date)
            # "2025-06-22 15:00:00+00:00" を "2025-06-22" に変換
            start_date = start_date_str.split(' ')[0] if ' ' in start_date_str else start_date_str
        
        if hasattr(end_date, 'seconds'):
            end_date = datetime.fromtimestamp(end_date.seconds).strftime("%Y-%m-%d")
        elif hasattr(end_date, 'timestamp'):
            # DatetimeWithNanoseconds型の場合
            end_date = end_date.strftime("%Y-%m-%d")
        elif isinstance(end_date, str):
            # 既に文字列の場合はそのまま使用
            pass
        else:
            # その他の場合はstrに変換して日付部分のみ抽出
            end_date_str = str(end_date)
            # "2025-06-28 15:00:00+00:00" を "2025-06-28" に変換
            end_date = end_date_str.split(' ')[0] if ' ' in end_date_str else end_date_str
            
        # カスタマイズ情報を取得
        customization = notebook_request.get('customization', {})
        custom_tone = customization.get('tone', '')
        custom_focus = customization.get('focus', '')
        
        # ソース情報を取得（選択されたコンテンツ）
        sources = notebook_request.get('sources', [])
        selected_analysis_ids = [s['analysisId'] for s in sources if s.get('included', True)]
        selected_media_ids = [s['mediaId'] for s in sources if s.get('included', True)]
            
        print(f"Processing notebook request: {notebook_doc_id}")
        print(f"Child ID: {child_id}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Selected analysis IDs: {selected_analysis_ids}")
        print(f"Selected media IDs: {selected_media_ids}")
        print(f"Custom tone: {custom_tone}")
        print(f"Custom focus: {custom_focus}")
        
        # 子供の基本情報を取得
        child_doc = db.collection('children').document(child_id).get()
        if child_doc.exists:
            child_info = child_doc.to_dict()
        else:
            child_info = {"nickname": "お子さん"}
        
        # ノートブック生成処理を実行
        # 1. 期間とテーマを分析
        analysis_result = analyze_period_and_themes(
            child_id=child_id,
            start_date=start_date,
            end_date=end_date,
            child_info=child_info,
            custom_tone=custom_tone,
            custom_focus=custom_focus,
            selected_media_ids=selected_media_ids
        )
        
        if analysis_result.get("status") != "success":
            # エラー時はステータスを failed に更新
            notebook_ref.update({
                'status': 'failed',
                'error': analysis_result.get("error_message", "Failed to analyze period"),
                'processingCompletedAt': firestore.SERVER_TIMESTAMP
            })
            return
        
        analysis_report = analysis_result["report"]
        themes = analysis_report["themes"]
        
        # 2. orchestrate_notebook_generationを使用してコンテンツを生成
        orchestration_result = orchestrate_notebook_generation(
            child_id=child_id,
            start_date=start_date,
            end_date=end_date,
            themes=themes,
            child_info=child_info,
            custom_tone=custom_tone,
            custom_focus=custom_focus,
            selected_media_ids=selected_analysis_ids  # analysis_idsを渡す
        )
        
        if orchestration_result.get("status") != "success":
            # エラー時はステータスを failed に更新
            notebook_ref.update({
                'status': 'failed',
                'error': orchestration_result.get("error_message", "Failed to generate content"),
                'processingCompletedAt': firestore.SERVER_TIMESTAMP
            })
            return
        
        topics = orchestration_result["report"]["topics"]
        all_episodes_count = orchestration_result["report"].get("total_episodes_used", 0)
        
        # エピソードが1つも見つからなかった場合
        if all_episodes_count == 0:
            notebook_ref.update({
                'status': 'failed',
                'error': "指定された期間にエピソードが記録されていないため、ノートブックを生成できません。",
                'processingCompletedAt': firestore.SERVER_TIMESTAMP
            })
            return
        
        # 3. ノートブックを検証して保存
        notebook_data = {
            "notebook_id": notebook_doc_id,  # Firestoreが生成したドキュメントIDを使用
            "nickname": child_info.get("nickname", "お子さん"),
            "period": analysis_report["period"],
            "topics": topics,
            "customization": {
                "tone": custom_tone,
                "focus": custom_focus
            },
            "sources": sources  # 選択されたメディア情報を保持
        }
        
        save_result = validate_and_save_notebook(
            notebook_data=notebook_data,
            child_id=child_id
        )
        
        if save_result.get("status") in ["success", "partial_success"]:
            # ノートブックリクエストドキュメントを更新
            notebook_ref.update({
                'status': 'completed',
                'notebookUrl': save_result["report"]["url"],
                'validTopics': save_result["report"]["valid_topics"],
                'processingCompletedAt': firestore.SERVER_TIMESTAMP
            })
            
            # 生成ログを記録
            db.collection('notebook_generation_logs').add({
                'child_id': child_id,
                'notebook_id': notebook_doc_id,
                'period': {
                    'start': start_date,
                    'end': end_date
                },
                'status': save_result["status"],
                'valid_topics': save_result["report"]["valid_topics"],
                'missing_topics': save_result["report"]["missing_topics"],
                'selected_media_count': len(selected_media_ids),
                'generated_at': firestore.SERVER_TIMESTAMP,
                'generated_by': 'firestore_trigger'
            })
            
            print(f"Successfully completed notebook {notebook_doc_id} for child {child_id}")
        else:
            # エラー時はステータスを failed に更新
            notebook_ref.update({
                'status': 'failed',
                'error': save_result.get("error_message", "Failed to save notebook"),
                'processingCompletedAt': firestore.SERVER_TIMESTAMP
            })
            
    except Exception as e:
        print(f"Error generating notebook: {str(e)}")
        
        # エラー時はステータスを failed に更新
        try:
            if 'notebook_ref' in locals():
                notebook_ref.update({
                    'status': 'failed',
                    'error': str(e),
                    'processingCompletedAt': firestore.SERVER_TIMESTAMP
                })
        except Exception as update_error:
            print(f"Failed to update status: {str(update_error)}")


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
                
                # orchestrate_notebook_generationを使用してコンテンツを生成
                orchestration_result = orchestrate_notebook_generation(
                    child_id=child_id,
                    start_date=start_date,
                    end_date=end_date,
                    themes=themes,
                    child_info=child_info,
                    custom_tone=None,
                    custom_focus=None,
                    selected_media_ids=None
                )
                
                if orchestration_result.get("status") != "success":
                    print(f"Failed to generate content for {child_id}: {orchestration_result.get('error_message')}")
                    error_count += 1
                    continue
                
                topics = orchestration_result["report"]["topics"]
                all_episodes_count = orchestration_result["report"].get("total_episodes_used", 0)
                
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