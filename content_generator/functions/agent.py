"""
ノートブック生成エージェント
期間と子供IDを受け取って、ベクトル検索でエピソードを収集し、
Geminiでコンテンツを生成してノートブックを作成する
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from google.adk.agents import Agent
from google.cloud import firestore
from google.cloud import aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 環境変数
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "hackason-464007")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
INDEX_ID = os.getenv("VERTEX_AI_INDEX_ID", "")
INDEX_ENDPOINT_ID = os.getenv("VERTEX_AI_INDEX_ENDPOINT_ID", "")
MODEL_NAME = "gemini-2.5-flash"

# グローバル変数（遅延初期化）
_firestore_client = None
_vertex_ai_initialized = False
_embedding_model = None


def get_firestore_client():
    """Firestoreクライアントを取得（遅延初期化）"""
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=PROJECT_ID)
    return _firestore_client


def initialize_vertex_ai():
    """Vertex AIを初期化"""
    global _vertex_ai_initialized
    if not _vertex_ai_initialized:
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        _vertex_ai_initialized = True


def get_embedding_model():
    """埋め込みモデルを取得"""
    global _embedding_model
    if _embedding_model is None:
        initialize_vertex_ai()
        _embedding_model = TextEmbeddingModel.from_pretrained(
            "text-embedding-004")
    return _embedding_model


def search_similar_episodes(
    query_embedding: List[float],
    child_id: str,
    start_date: datetime,
    end_date: datetime,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    ベクトル検索でエピソードを取得
    
    Args:
        query_embedding: 検索クエリの埋め込みベクトル
        child_id: 子供のID
        start_date: 開始日時
        end_date: 終了日時
        top_k: 取得する上位件数
        
    Returns:
        類似エピソードのリスト
    """
    try:
        from google.cloud import aiplatform_v1
        
        # Matching Engine Index Endpoint クライアントを作成
        index_endpoint_client = aiplatform_v1.MatchingEngineIndexEndpointServiceClient()
        
        # Index Endpoint のリソース名を構築
        index_endpoint_name = (
            f"projects/{PROJECT_ID}/locations/{LOCATION}/"
            f"indexEndpoints/{INDEX_ENDPOINT_ID}"
        )
        
        # 日付をUnixタイムスタンプに変換
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        # 検索リクエストを構築
        deployed_index_id = "deployed_index"  # デプロイされたインデックスのID
        
        # 検索を実行
        response = index_endpoint_client.find_neighbors(
            request={
                "index_endpoint": index_endpoint_name,
                "deployed_index_id": deployed_index_id,
                "queries": [{
                    "datapoint": {
                        "feature_vector": query_embedding,
                        "restricts": [{
                            "namespace": "child_id",
                            "allow_list": [child_id]
                        }],
                        "numeric_restricts": [
                            {
                                "namespace": "created_at",
                                "value_int": start_timestamp,
                                "op": "GREATER_EQUAL"
                            },
                            {
                                "namespace": "created_at", 
                                "value_int": end_timestamp,
                                "op": "LESS_EQUAL"
                            }
                        ]
                    },
                    "neighbor_count": top_k
                }]
            }
        )
        
        # 結果からエピソードIDを抽出
        episode_ids = []
        if response.nearest_neighbors:
            for neighbor in response.nearest_neighbors[0].neighbors:
                episode_ids.append(neighbor.datapoint.datapoint_id)
        
        # Firestoreからエピソード情報を取得
        if episode_ids:
            db = get_firestore_client()
            episodes = []
            
            for episode_id in episode_ids:
                doc = db.collection('episodes').document(episode_id).get()
                if doc.exists:
                    episode_data = doc.to_dict()
                    episodes.append({
                        'id': episode_id,
                        'content': episode_data.get('content', ''),
                        'tags': episode_data.get('vector_tags', []),
                        'media_source_uri': episode_data.get('media_source_uri', ''),
                        'created_at': episode_data.get('created_at'),
                        'emotion': episode_data.get('emotion', '')
                    })
            
            return episodes
        
        return []
        
    except Exception as e:
        logger.error(f"Error in vector search: {str(e)}")
        return []


# ========== ツール関数 ==========


def analyze_period_and_themes(
    child_id: str,
    start_date: str,
    end_date: str,
    child_info: Optional[Dict[str, Any]] = None,
    custom_tone: Optional[str] = None,
    custom_focus: Optional[str] = None,
    selected_media_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    期間とテーマを分析し、検索用のクエリを生成する

    Args:
        child_id: 子供のID
        start_date: 開始日（YYYY-MM-DD形式）
        end_date: 終了日（YYYY-MM-DD形式）
        child_info: 子供の基本情報
        custom_tone: カスタムトーン（文章のスタイル）
        custom_focus: カスタムフォーカス（注目してほしいこと）
        selected_media_ids: 選択されたメディアID

    Returns:
        分析結果とテーマ別検索クエリ
    """
    try:
        logger.info(
            f"Analyzing period for child {child_id}: {start_date} to {end_date}"
        )

        # 日付をパース
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        # テーマと検索クエリを定義
        themes = [
            {
                "id": "interest",
                "title": "今週の興味",
                "search_queries": [
                    "興味",
                    "夢中",
                    "好き",
                    "楽しい",
                    "お気に入り",
                    "遊び",
                    "おもちゃ",
                ],
                "prompt_hint": "子供が今週特に興味を持ったことや夢中になったことについて",
            },
            {
                "id": "place",
                "title": "行った！場所",
                "search_queries": [
                    "行った",
                    "お出かけ",
                    "公園",
                    "散歩",
                    "訪問",
                    "外出",
                    "おでかけ",
                ],
                "prompt_hint": "今週訪れた場所や外出のエピソード",
            },
            {
                "id": "first_time",
                "title": "初めての体験",
                "search_queries": ["初めて", "デビュー", "挑戦", "新しい", "はじめて"],
                "prompt_hint": "今週初めて経験したことや新しい挑戦",
            },
            {
                "id": "best_shot",
                "title": "今週のベストショット",
                "search_queries": [
                    "笑顔",
                    "かわいい",
                    "素敵",
                    "最高",
                    "楽しそう",
                    "嬉しそう",
                ],
                "prompt_hint": "今週の最も印象的な瞬間や表情",
            },
            {
                "id": "achievement",
                "title": "できるようになったこと",
                "search_queries": [
                    "できた",
                    "成長",
                    "上手",
                    "覚えた",
                    "言えた",
                    "できるように",
                ],
                "prompt_hint": "今週新しくできるようになったことや成長",
            },
        ]

        # 週のIDを生成
        week_num = (start.day - 1) // 7 + 1
        notebook_id = f"{start.year}_{start.month:02d}_week{week_num}"

        return {
            "status": "success",
            "report": {
                "child_id": child_id,
                "notebook_id": notebook_id,
                "period": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "days": (end - start).days + 1,
                },
                "themes": themes,
                "child_info": child_info or {},
                "custom_tone": custom_tone,
                "custom_focus": custom_focus,
                "selected_media_ids": selected_media_ids or [],
            },
        }

    except Exception as e:
        logger.error(f"Error in analyze_period_and_themes: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def collect_episodes_by_theme(
    theme_info: Dict[str, Any], 
    child_id: str, 
    start_date: str, 
    end_date: str,
    selected_media_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    テーマに基づいてエピソードを収集する
    注意: エピソードはanalysis_resultsドキュメント内に含まれている

    Args:
        theme_info: テーマ情報（ID、タイトル、検索クエリ）
        child_id: 子供のID
        start_date: 開始日
        end_date: 終了日
        selected_media_ids: 選択されたanalysis_resultsのID（指定時はこれらのみを対象）

    Returns:
        収集されたエピソード
    """
    try:
        logger.info(f"Collecting episodes for theme: {theme_info['title']}")

        db = get_firestore_client()

        # 日付をパース
        start = (
            datetime.fromisoformat(start_date)
            if "T" in start_date
            else datetime.strptime(start_date, "%Y-%m-%d")
        )
        end = (
            datetime.fromisoformat(end_date)
            if "T" in end_date
            else datetime.strptime(end_date, "%Y-%m-%d")
        )

        # analysis_resultsコレクションからエピソードを取得
        analysis_ref = db.collection("analysis_results")
        
        # selected_media_idsが指定されている場合は、それらのanalysis_resultsのみを取得
        if selected_media_ids:
            logger.info(f"Filtering analysis results by selected IDs: {selected_media_ids}")
            # IDでフィルタリング
            # Firestoreの制限によりinクエリは最大10件までなので、バッチ処理
            all_analysis_results = []
            for i in range(0, len(selected_media_ids), 10):
                batch_ids = selected_media_ids[i:i+10]
                logger.info(f"Querying analysis_results with IDs in: {batch_ids}")
                # ドキュメントIDで直接取得
                for doc_id in batch_ids:
                    doc = analysis_ref.document(doc_id).get()
                    if doc.exists:
                        all_analysis_results.append(doc)
            logger.info(f"Total analysis results found: {len(all_analysis_results)}")
        else:
            # 通常の期間ベースの取得
            logger.info(f"Getting all analysis results for child_id: {child_id}")
            all_analysis_results = analysis_ref.where("child_id", "==", child_id).stream()

        # analysis_resultsからエピソードを抽出してテーママッチング
        episodes = []
        total_analysis_processed = 0
        
        for doc in all_analysis_results:
            total_analysis_processed += 1
            analysis_data = doc.to_dict()
            analysis_id = doc.id
            
            # captured_atまたはcreated_atを使用して日付を確認
            analysis_date = analysis_data.get("captured_at") or analysis_data.get("created_at")
            
            # デバッグ情報を出力
            if total_analysis_processed <= 3:
                logger.info(f"Processing analysis_result {analysis_id}: media_uri={analysis_data.get('media_uri')}, episode_count={analysis_data.get('episode_count', 0)}")

            # analysis_dateが存在し、期間内かチェック（selected_media_idsがある場合はスキップ）
            if analysis_date:
                if isinstance(analysis_date, str):
                    analysis_date = datetime.fromisoformat(analysis_date)
                
                # selected_media_idsが指定されている場合は期間チェックをスキップ
                if selected_media_ids or (start <= analysis_date <= end):
                    # analysis_results内のepisodes配列を処理
                    analysis_episodes = analysis_data.get("episodes", [])
                    
                    for episode in analysis_episodes:
                        # 検索クエリとのマッチングをチェック
                        content = episode.get("content", "").lower()
                        tags = [tag.lower() for tag in episode.get("tags", [])]
                        
                        # いずれかの検索クエリがコンテンツまたはタグに含まれているか
                        matches = False
                        for search_query in theme_info.get("search_queries", []):
                            query_lower = search_query.lower()
                            if query_lower in content or any(query_lower in tag for tag in tags):
                                matches = True
                                break
                        
                        if matches:
                            # エピソードに追加情報を付与
                            episode_with_meta = episode.copy()
                            episode_with_meta['analysis_id'] = analysis_id
                            episode_with_meta['media_uri'] = analysis_data.get('media_uri')
                            episode_with_meta['child_id'] = analysis_data.get('child_id')
                            episode_with_meta['created_at'] = analysis_date
                            episode_with_meta['image_urls'] = [analysis_data.get('media_uri')] if analysis_data.get('media_uri') else []
                            
                            episodes.append(episode_with_meta)
                            logger.info(f"Episode from analysis {analysis_id} matches theme '{theme_info['title']}'")
        
        logger.info(f"Processed {total_analysis_processed} analysis results, found {len(episodes)} episodes matching theme")

        if len(episodes) == 0:
            logger.warning(f"No episodes found for theme '{theme_info['title']}' with child_id={child_id}")
            if selected_media_ids:
                logger.warning(f"Selected media IDs were: {selected_media_ids}")
        
        return {
            "status": "success",
            "report": {
                "theme": theme_info,
                "episodes": episodes,
                "episode_count": len(episodes),
            },
        }

    except Exception as e:
        logger.error(f"Error in collect_episodes_by_theme: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def generate_topic_content(
    theme_episodes: Dict[str, Any], 
    child_info: Dict[str, Any], 
    topic_layout: str,
    custom_tone: Optional[str] = None,
    custom_focus: Optional[str] = None
) -> Dict[str, Any]:
    """
    テーマとエピソードからトピックコンテンツを生成する

    Args:
        theme_episodes: テーマとエピソードの情報
        child_info: 子供の基本情報
        topic_layout: レイアウトタイプ（large_photo, text_only, etc.）
        custom_tone: カスタムトーン（文章のスタイル）
        custom_focus: カスタムフォーカス（注目してほしいこと）

    Returns:
        生成されたトピックコンテンツ
    """
    try:
        # theme_episodesは collect_episodes_by_theme の report フィールドから来る
        if "report" in theme_episodes:
            theme = theme_episodes["report"]["theme"]
            episodes = theme_episodes["report"]["episodes"]
        else:
            theme = theme_episodes.get("theme", theme_episodes)
            episodes = theme_episodes.get("episodes", [])

        logger.info(
            f"Generating content for theme: {theme['title']} with {len(episodes)} episodes"
        )

        if not episodes:
            # エピソードがない場合のデフォルトコンテンツ
            return {
                "status": "success",
                "report": {
                    "title": theme["title"],
                    "subtitle": None,
                    "content": f"今週は{theme['title']}に関する記録がありませんでした。",
                    "photo": None,
                    "caption": None,
                    "generated": False,
                },
            }

        # Geminiモデルを初期化
        initialize_vertex_ai()
        model = GenerativeModel(MODEL_NAME)

        # プロンプトを構築
        child_name = child_info.get("nickname", "お子さん")
        episodes_text = "\n".join(
            [
                f"- {episode['content']}"
                for episode in episodes[:5]  # 最大5エピソード
            ]
        )

        # カスタムトーンとフォーカスの追加部分を構成
        custom_instructions = ""
        if custom_tone and custom_tone.strip():
            custom_instructions += f"\n\n【リクエストされた文章スタイル】\n{custom_tone}"
        if custom_focus and custom_focus.strip():
            custom_instructions += f"\n\n【特に注目してほしいこと】\n{custom_focus}"

        prompt = f"""
あなたは、子供との思い出を、まるでその場にいたかのように鮮やかに記録するジャーナリストです。
以下のエピソード群を読んで、**解釈や成長の断定はせず、あったことを具体的に、生き生きと描写する**記事を作成してください。

【テーマ】
「{theme['title']}」

【記録されたエピソード】
{episodes_text}{custom_instructions}

【執筆のルール】
- **事実を最優先:** エピソードにある具体的な行動、場所、会話（例：「『走れ走れ』と言った」「イチゴ型の容器で飲んだ」「お祭りに行った」）をそのまま使ってください。
- **成長の決めつけはNG:** 「〇〇ができるようになった」と勝手に結論づけないでください。その子にとっては当たり前のことかもしれません。代わりに「上手に〇〇していましたね」「〇〇している姿が印象的でした」のように、その場の様子を描写するに留めてください。
- **抽象的な言葉を避ける:** 「自立心の芽生え」「五感をフル活用」のような曖昧な表現は使わず、「自分で容器を持って飲んでいた」「お祭りの賑やかな音や食べ物の匂いに囲まれていた」のように具体的に書いてください。
- **情景描写を豊かに:** もしエピソードに場所（お祭り、公園など）の情報があれば、その場の雰囲気が伝わるように書いてください。「お祭りの活気の中で、{child_name}は特に楽しそうでした」のように。
- **親しみやすい「です・ます」調**で記述してください。

【出力形式】
200文字程度の記事
"""

        # コンテンツを生成
        response = model.generate_content(prompt)
        generated_content = response.text.strip()

        # サブタイトルの生成（large_photoの場合）
        subtitle = None
        if topic_layout == "large_photo" and episodes:
            # 最初のエピソードからキーワードを抽出
            subtitle = (
                episodes[0]["tags"][0] if episodes[0].get(
                    "tags") else theme["title"]
            )

        # 画像の選択
        photo = None
        caption = None
        if topic_layout != "text_only":
            for episode in episodes:
                if episode.get("image_urls"):
                    photo = episode["image_urls"][0]
                    # 画像のキャプションを生成
                    caption_prompt = f"{child_name}の{theme['title']}の様子"
                    caption_response = model.generate_content(
                        f"以下の文章から、写真のキャプションを15文字以内で生成してください：\n{episode['content'][:100]}"
                    )
                    caption = caption_response.text.strip()
                    break

        return {
            "status": "success",
            "report": {
                "title": theme["title"],
                "subtitle": subtitle,
                "content": generated_content,
                "photo": photo,
                "caption": caption,
                "generated": True,
                "episode_count": len(episodes),
            },
        }

    except Exception as e:
        logger.error(f"Error in generate_topic_content: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def validate_and_save_notebook(
    notebook_data: Dict[str, Any], child_id: str
) -> Dict[str, Any]:
    """
    生成されたノートブックを検証して保存する

    Args:
        notebook_data: ノートブックデータ
        child_id: 子供のID

    Returns:
        保存結果
    """
    try:
        logger.info(f"Validating and saving notebook for child {child_id}")

        # コンテンツの検証
        topics = notebook_data.get("topics", [])
        valid_topics = 0
        missing_topics = []

        for i, topic in enumerate(topics):
            if topic.get("generated", False) and topic.get("content", "").strip():
                valid_topics += 1
            else:
                missing_topics.append(topic.get("title", f"Topic {i+1}"))

        # ステータスの判定
        if valid_topics == 0:
            return {
                "status": "error",
                "error_message": "コンテンツが生成できませんでした。エピソードが不足しています。",
            }
        elif valid_topics < 3:
            status = "partial_success"
            status_message = (
                f"{len(missing_topics)}個のトピックでコンテンツが不足しています"
            )
        else:
            status = "success"
            status_message = "すべてのトピックが正常に生成されました"

        # Firestoreに保存
        db = get_firestore_client()

        # ノートブックドキュメントを保存
        notebook_ref = (
            db.collection("children")
            .document(child_id)
            .collection("notebooks")
            .document(notebook_data["notebook_id"])
        )

        save_data = {
            "nickname": notebook_data["nickname"],
            "date": datetime.now(),  # 現在時刻を使用
            "period": notebook_data["period"],
            "topics": [
                {
                    "title": topic["title"],
                    "subtitle": topic.get("subtitle"),
                    "content": topic["content"],
                    "photo": topic.get("photo"),
                    "caption": topic.get("caption"),
                }
                for topic in topics
            ],
            "created_at": firestore.SERVER_TIMESTAMP,
            "status": "published",
            "generation_status": status,
            "missing_topics": missing_topics,
        }

        notebook_ref.set(save_data)

        return {
            "status": status,
            "report": {
                "notebook_id": notebook_data["notebook_id"],
                "child_id": child_id,
                "url": f"/children/{child_id}/notebooks/{notebook_data['notebook_id']}",
                "valid_topics": valid_topics,
                "missing_topics": missing_topics,
                "message": status_message,
            },
        }

    except Exception as e:
        logger.error(f"Error in validate_and_save_notebook: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# ========== エージェント定義 ==========

root_agent = Agent(
    name="notebook_generator_agent",
    model=MODEL_NAME,
    description="子供の成長記録ノートブックを生成するエージェント",
    instruction="""
    あなたは子供の成長記録ノートブックを生成するエージェントです。
    
    ノートブックを生成するには、以下の情報が必要です：
    - child_id: 子供のID（必須）
    - start_date: 開始日（YYYY-MM-DD形式、必須）
    - end_date: 終了日（YYYY-MM-DD形式、必須）
    - child_info: 子供の基本情報（オプション、nicknameなど）
    
    ユーザーからこれらの情報が提供されていない場合は、必ず最初に質問してください。
    
    情報が揃ったら、以下の手順でノートブックを生成してください：
    
    1. analyze_period_and_themes: 期間とテーマを分析
    2. collect_episodes_by_theme: 各テーマごとにエピソードを収集（5つのテーマそれぞれに対して実行）
       - エピソードが見つからない場合は、そのテーマをスキップまたはデフォルトコンテンツとする
    3. generate_topic_content: 各テーマのコンテンツを生成（5つのトピックそれぞれに対して実行）
       - レイアウトタイプは以下の順番で使用：
         - Topic 1: large_photo
         - Topic 2: text_only
         - Topic 3: small_photo
         - Topic 4: medium_photo
         - Topic 5: center (text_only)
    4. validate_and_save_notebook: 生成されたノートブックを検証して保存
    
    重要な注意事項：
    - collect_episodes_by_themeでエピソードが見つからない、またはエラーが発生した場合は、
      「指定された期間にエピソードが記録されていないため、ノートブックを生成できません」と
      ユーザーに伝え、処理を中止してください
    - エピソードが1つでも見つかった場合のみ、ノートブック生成を続行してください
    - 生成されたコンテンツは温かく親しみやすい文章にすること
    - 画像がある場合は適切に選択すること
    """,
    tools=[
        analyze_period_and_themes,
        collect_episodes_by_theme,
        generate_topic_content,
        validate_and_save_notebook,
    ],
)


# ========== Cloud Functions用のエントリーポイント ==========


def process_notebook_generation_request(
    child_id: str,
    start_date: str,
    end_date: str,
    child_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Cloud Functionsから呼び出せる関数
    ノートブック生成のリクエストを処理する

    Args:
        child_id: 子供のID
        start_date: 開始日（YYYY-MM-DD形式）
        end_date: 終了日（YYYY-MM-DD形式）
        child_info: 子供の基本情報（nickname等）

    Returns:
        処理結果
    """
    try:
        # 子供の基本情報を取得（提供されていない場合）
        if not child_info:
            db = get_firestore_client()
            child_doc = db.collection("children").document(child_id).get()
            if child_doc.exists:
                child_info = child_doc.to_dict()
            else:
                child_info = {"nickname": "お子さん"}

        # エージェントがツールを実行してノートブックを生成する
        # 注: エージェントはADKフレームワークによって実行される

        return {
            "status": "success",
            "message": "Notebook generation agent is configured",
            "agent_name": root_agent.name,
            "child_id": child_id,
            "period": f"{start_date} to {end_date}",
        }

    except Exception as e:
        logger.error(f"Error in process_notebook_generation_request: {str(e)}")
        return {"status": "error", "error_message": str(e)}

