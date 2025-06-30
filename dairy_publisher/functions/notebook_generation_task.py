"""
ノートブック生成のバックグラウンドタスク
Pub/Subトリガーで実行される非同期処理
"""
import os
import json
import base64
import logging
from firebase_functions import pubsub_fn, options
from firebase_admin import firestore
from datetime import datetime

# エージェントから必要な関数をインポート
from agent import (
    analyze_period_and_themes,
    collect_episodes_by_theme,
    generate_topic_content,
    validate_and_save_notebook,
    get_firestore_client
)

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Firestoreクライアント
db = firestore.client()


@pubsub_fn.on_message_published(
    topic="notebook-generation",
    timeout_sec=540,
    memory=options.MemoryOption.GB_2
)
def process_notebook_generation(event: pubsub_fn.CloudEvent[pubsub_fn.MessagePublishedData]) -> None:
    """Pub/Subメッセージを受けてノートブック生成を実行"""
    try:
        # メッセージデータを取得
        message_data = base64.b64decode(event.data["message"]["data"]).decode()
        task_data = json.loads(message_data)
        
        child_id = task_data['child_id']
        start_date = task_data['start_date']
        end_date = task_data['end_date']
        child_info = task_data.get('child_info', {})
        notebook_id = task_data['notebook_id']
        
        logger.info(f"Processing notebook generation for {child_id}, notebook: {notebook_id}")
        
        # ノートブックのステータスを更新する関数
        def update_notebook_status(status, progress=None, error=None):
            update_data = {
                'status': status,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            if progress:
                update_data['generation_progress'] = progress
            if error:
                update_data['generation_error'] = error
            
            db.collection('children').document(child_id)\
              .collection('notebooks').document(notebook_id)\
              .update(update_data)
        
        try:
            # ステップ1: テーマの分析（既に完了済みだが、整合性のため再実行）
            update_notebook_status('generating', {
                'current_step': 'collecting_episodes',
                'total_steps': 4,
                'message': 'エピソードを収集中...'
            })
            
            analysis_result = analyze_period_and_themes(
                child_id=child_id,
                start_date=start_date,
                end_date=end_date,
                child_info=child_info
            )
            
            if analysis_result.get("status") != "success":
                raise Exception(analysis_result.get("error_message", "Analysis failed"))
            
            themes = analysis_result["report"]["themes"]
            
            # ステップ2: 各テーマごとにエピソードを収集
            topics = []
            all_episodes_count = 0
            layout_types = ["large_photo", "text_only", "small_photo", "medium_photo", "text_only"]
            
            for i, theme in enumerate(themes):
                # 進捗を更新
                update_notebook_status('generating', {
                    'current_step': 'collecting_episodes',
                    'total_steps': 4,
                    'message': f'{theme["title"]}のエピソードを収集中... ({i+1}/5)'
                })
                
                episodes_result = collect_episodes_by_theme(
                    theme_info=theme,
                    child_id=child_id,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if episodes_result.get("status") == "success":
                    episode_count = episodes_result["report"]["episode_count"]
                    all_episodes_count += episode_count
                    
                    # ステップ3: コンテンツを生成
                    update_notebook_status('generating', {
                        'current_step': 'generating_content',
                        'total_steps': 4,
                        'message': f'{theme["title"]}のコンテンツを生成中... ({i+1}/5)'
                    })
                    
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
            
            # エピソードが見つからなかった場合
            if all_episodes_count == 0:
                update_notebook_status('failed', error={
                    'message': '指定された期間にエピソードが記録されていません',
                    'code': 'NO_EPISODES_FOUND'
                })
                return
            
            # ステップ4: ノートブックを保存
            update_notebook_status('generating', {
                'current_step': 'saving',
                'total_steps': 4,
                'message': 'ノートブックを保存中...'
            })
            
            notebook_data = {
                "notebook_id": notebook_id,
                "nickname": child_info.get("nickname", "お子さん"),
                "period": analysis_result["report"]["period"],
                "topics": topics
            }
            
            # validate_and_save_notebookの代わりに直接更新
            # （既にドキュメントが作成されているため）
            valid_topics = sum(1 for topic in topics if topic.get("generated", False))
            
            final_update = {
                'status': 'published',
                'generation_completed_at': firestore.SERVER_TIMESTAMP,
                'topics': topics,
                'valid_topics': valid_topics,
                'total_episodes': all_episodes_count,
                'date': datetime.now(),
                'period': notebook_data["period"]
            }
            
            # generation_progressフィールドを削除
            db.collection('children').document(child_id)\
              .collection('notebooks').document(notebook_id)\
              .update(final_update)
            
            # 削除のために別途更新
            db.collection('children').document(child_id)\
              .collection('notebooks').document(notebook_id)\
              .update({
                  'generation_progress': firestore.DELETE_FIELD
              })
            
            logger.info(f"Successfully generated notebook {notebook_id} for child {child_id}")
            
        except Exception as e:
            logger.error(f"Error generating notebook: {str(e)}")
            update_notebook_status('failed', error={
                'message': str(e),
                'code': 'GENERATION_ERROR'
            })
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")