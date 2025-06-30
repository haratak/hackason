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


# ========== ツール関数 ==========


def analyze_period_and_themes(
    child_id: str,
    start_date: str,
    end_date: str,
    child_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    期間とテーマを分析し、検索用のクエリを生成する

    Args:
        child_id: 子供のID
        start_date: 開始日（YYYY-MM-DD形式）
        end_date: 終了日（YYYY-MM-DD形式）
        child_info: 子供の基本情報

    Returns:
        分析結果とテーマ別検索クエリ
    """
    try:
        logger.info(
            f"Analyzing period for child {
                child_id}: {start_date} to {end_date}"
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
            },
        }

    except Exception as e:
        logger.error(f"Error in analyze_period_and_themes: {str(e)}")
        return {"status": "error", "error_message": str(e)}


def collect_episodes_by_theme(
    theme_info: Dict[str, Any], child_id: str, start_date: str, end_date: str
) -> Dict[str, Any]:
    """
    テーマに基づいてエピソードを収集する

    Args:
        theme_info: テーマ情報（ID、タイトル、検索クエリ）
        child_id: 子供のID
        start_date: 開始日
        end_date: 終了日

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

        # エピソードコレクションから期間内のエピソードを取得
        # 複合インデックスを避けるため、まず child_id でフィルタ
        episodes_ref = db.collection("episodes")
        all_episodes = episodes_ref.where("child_id", "==", child_id).stream()

        # メモリ内で日付フィルタリングとテーママッチング
        episodes = []
        for doc in all_episodes:
            episode_data = doc.to_dict()
            episode_created_at = episode_data.get("created_at")

            # created_at が datetime オブジェクトまたは文字列の場合の処理
            if episode_created_at:
                if isinstance(episode_created_at, str):
                    episode_created_at = datetime.fromisoformat(
                        episode_created_at)

                # 期間内のエピソードのみ処理
                if start <= episode_created_at <= end:
                    # 検索クエリとのマッチングをチェック（簡易版）
                    content = episode_data.get("content", "").lower()
                    tags = [tag.lower() for tag in episode_data.get("vector_tags", [])]

                    # いずれかの検索クエリがコンテンツまたはタグに含まれているか
                    matches = False
                    for search_query in theme_info.get("search_queries", []):
                        query_lower = search_query.lower()
                        if query_lower in content or any(query_lower in tag for tag in tags):
                            matches = True
                            break

                    if matches:
                        episodes.append(
                            {
                                "id": doc.id,
                                "content": episode_data.get("content", ""),
                                "tags": episode_data.get("vector_tags", []),
                                "media_source_uri": episode_data.get("media_source_uri", ""),
                                "created_at": episode_data.get("created_at"),
                                "emotion": episode_data.get("emotion", "")
                            }
                        )

        # TODO: 実際の実装では、ベクトル検索を使用してより関連性の高いエピソードを取得
        # embedding_model = get_embedding_model()
        # query_embedding = embedding_model.get_embeddings([theme_info['title']])[0].values
        # similar_episodes = search_similar_episodes(query_embedding, child_id, start, end)

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
    theme_episodes: Dict[str, Any], child_info: Dict[str, Any], topic_layout: str
) -> Dict[str, Any]:
    """
    テーマとエピソードからトピックコンテンツを生成する

    Args:
        theme_episodes: テーマとエピソードの情報
        child_info: 子供の基本情報
        topic_layout: レイアウトタイプ（large_photo, text_only, etc.）

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
            f"Generating content for theme: {
                theme['title']} with {len(episodes)} episodes"
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

        prompt = f"""
        以下のエピソードを基に、{child_name}の「{theme['title']}」についての
        温かく親しみやすい文章を生成してください。

        {theme['prompt_hint']}

        エピソード:
        {episodes_text}

        要件:
        - 200-300文字程度
        - 保護者が読んで嬉しくなるような温かい文章
        - 具体的なエピソードを含める
        - 子供の成長や個性が感じられる内容
        - 「です・ます」調で統一
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
                        f"以下の文章から、写真のキャプションを15文字以内で生成してください：\n{
                            episode['content'][:100]}"
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

