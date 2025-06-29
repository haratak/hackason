from typing import Dict, Any
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

import json
import logging
from google.cloud.aiplatform_v1beta1.types import index_endpoint
from vertexai.generative_models import GenerativeModel, Part
from vertexai.language_models import TextEmbeddingModel
import vertexai
from google.cloud import firestore
from google.cloud.aiplatform import MatchingEngineIndex

# Load environment variables
load_dotenv()


# Get environment variables
def get_project_id():
    return os.getenv("GOOGLE_CLOUD_PROJECT", "hackason-464007")


def get_location():
    return os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")


def get_index_id():
    return os.getenv("VERTEX_AI_INDEX_ID")


def get_index_endpoint_id():
    return os.getenv("VERTEX_AI_INDEX_ENDPOINT_ID")


# Initialize services lazily
_db = None
_embedding_model = None
_vector_search_index = None


def get_firestore_client():
    global _db
    if _db is None:
        _db = firestore.Client(project=get_project_id())
    return _db


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        vertexai.init(project=get_project_id(), location=get_location())
        _embedding_model = TextEmbeddingModel.from_pretrained(
            "text-embedding-004")
    return _embedding_model


def get_vector_search_index():
    global _vector_search_index
    if _vector_search_index is None:
        index_id = get_index_id()
        if index_id:
            _vector_search_index = MatchingEngineIndex(
                index_name=f"projects/{get_project_id()}/locations/{get_location()}/indexes/{index_id}"
            )
    return _vector_search_index


logger = logging.getLogger(__name__)
MODEL_NAME = "gemini-2.0-flash-001"

# Child ID will be set when the agent is invoked
# Default to "demo" if not provided
CHILD_ID = "demo"


def objective_analyzer(media_uri: str) -> dict:
    """Extract objective facts from media files"""
    model = GenerativeModel(MODEL_NAME)
    try:
        # Determine MIME type from URL extension
        media_uri_lower = media_uri.lower()

        # Extract extension from URL (handle query parameters)
        url_path = media_uri_lower.split("?")[0]

        # Check common image formats
        if any(url_path.endswith(ext) for ext in [".jpg", ".jpeg"]):
            mime_type = "image/jpeg"
        elif url_path.endswith(".png"):
            mime_type = "image/png"
        elif url_path.endswith(".gif"):
            mime_type = "image/gif"
        elif url_path.endswith(".webp"):
            mime_type = "image/webp"
        elif url_path.endswith(".bmp"):
            mime_type = "image/bmp"
        # Check common video formats
        elif url_path.endswith(".mp4"):
            mime_type = "video/mp4"
        elif url_path.endswith(".avi"):
            mime_type = "video/x-msvideo"
        elif url_path.endswith(".mov"):
            mime_type = "video/quicktime"
        elif url_path.endswith(".webm"):
            mime_type = "video/webm"
        elif url_path.endswith(".mkv"):
            mime_type = "video/x-matroska"
        else:
            # Default to image/jpeg if can't determine
            mime_type = "image/jpeg"
            logger.warning(
                f"Could not determine MIME type from URL, defaulting to {mime_type}"
            )

        logger.info(f"Detected MIME type: {mime_type} for URL: {media_uri}")
        media_part = Part.from_uri(uri=media_uri, mime_type=mime_type)

        prompt = """
        あなたは、子供の行動を観察する客観的な分析システムです。
        この画像/動画から観察できる全ての客観的な事実をリストアップしてください。

        【厳守事項】
        - 観察された事実のみを記述し、解釈や感想は含めないでください
        - 年齢や月齢の推測は行わないでください
        - JSONのみを返してください

        {
            "all_observed_actions": ["観察された全ての行動のリスト"],
            "observed_emotions": ["表情から読み取れる感情のリスト"],
            "spoken_words": ["聞き取れた発話内容（ある場合）"],
            "environment": "場所や環境の客観的な描写",
            "physical_interactions": ["物理的な相互作用（触る、持つ、指差すなど）"],
            "body_movements": ["体の動き（歩く、座る、手を振るなど）"]
        }
        """

        response = model.generate_content([media_part, prompt])
        response_text = response.text.strip()

        logger.info(f"Raw response from model: {response_text[:200]}...")

        import re

        json_match = re.search(r"```json\s*(.*?)\s*```",
                               response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

        response_text = response_text.strip()

        if not response_text:
            logger.error("Empty response from model")
            return {"status": "error", "error_message": "Empty response from model"}

        try:
            facts = json.loads(response_text)
            return {"status": "success", "report": facts}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                "status": "error",
                "error_message": f"Failed to parse JSON: {str(e)}",
            }

    except Exception as e:
        return {"status": "error", "error_message": str(e)}


def highlight_identifier(facts: Dict[str, Any]) -> dict:
    """Identify highlight moments and create a structured episode log"""
    model = GenerativeModel(MODEL_NAME)
    try:
        facts_json = json.dumps(facts, ensure_ascii=False, indent=2)

        prompt = f"""
        あなたは、子供の行動記録から、最も重要で記憶に残る「ハイライト」を抽出し、構造化されたデータを作成する専門家です。

        以下の客観的な事実データから、最も特徴的なハイライトシーンを一つだけ特定し、要約してください。

        【事実データ】
        {facts_json}

        【作成指針】
        - 最も感情豊か、あるいは成長が感じられる瞬間をハイライトとして選んでください。
        - **あなたの感想や主観的な物語は一切含めず**、客観的な事実の要約に徹してください。
        - **ベクトル検索で後から見つけやすいように、具体的で客観的なタグを生成してください。**

        以下のJSON形式で、最終的な「エピソードログ」を返してください：
        {{
            "title": "ハイライトシーンの客観的なタイトル（15文字以内）",
            "summary": "ハイライトシーンの客観的で具体的な状況説明（100文字程度）。発話があれば「」で引用する。",
            "emotion": "ハイライトシーンでの主な感情",
            "activities": ["ハイライト中の具体的な活動"],
            "development_milestones": ["このハイライトが示す発達の兆候"],
            "vector_tags": ["検索用の具体的で客観的なタグ（例：公園, 滑り台, 笑顔, 走る）"]
        }}
        """

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        import re

        json_match = re.search(r"```json\s*(.*?)\s*```",
                               response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

        episode_log = json.loads(response_text)
        return {"status": "success", "report": episode_log}

    except Exception as e:
        return {"status": "error", "error_message": str(e)}


def save_summary(
    episode_log: Dict[str, Any],
    media_source_uri: str,
    child_id: str = "",
    user_id: str = "",
    media_upload_id: str = None,
    captured_at = None,
) -> dict:
    """Save the episode log to Firestore"""
    try:
        # Use provided child_id or default
        if not child_id:
            child_id = globals().get("CHILD_ID", "demo")

        logger.info(f"Saving episode to Firestore for child: {child_id}...")

        # Extract data from episode log
        # Handle nested structure if episode_log is wrapped
        if isinstance(episode_log, dict) and "report" in episode_log:
            log_data = episode_log["report"]
        else:
            log_data = episode_log

        episode_content = log_data.get("summary", "")
        episode_title = log_data.get("title", "無題")

        # Prepare Firestore document
        firestore_data = {
            "child_id": child_id,
            "title": episode_title,
            "content": episode_content,
            "media_source_uri": media_source_uri,
            "emotion": log_data.get("emotion", ""),
            "activities": log_data.get("activities", []),
            "development_milestones": log_data.get("development_milestones", []),
            "vector_tags": log_data.get("vector_tags", []),
            "created_at": datetime.now(timezone.utc),
        }

        # Add user_id if provided
        if user_id:
            firestore_data["user_id"] = user_id
            
        # Add media_upload_id reference if provided
        if media_upload_id:
            firestore_data["media_upload_id"] = media_upload_id
            
        # Add captured_at if provided, otherwise use current time
        if captured_at:
            firestore_data["captured_at"] = captured_at
        else:
            firestore_data["captured_at"] = datetime.now(timezone.utc)

        # Save to Firestore
        db = get_firestore_client()
        doc_ref = db.collection("episodes").document()
        doc_ref.set(firestore_data)
        episode_id = doc_ref.id

        logger.info(
            f"✅ Successfully stored episode in Firestore. Document ID: {episode_id}"
        )
        return {
            "status": "success",
            "episode_id": episode_id,
            "message": f"Episode saved with ID: {episode_id}",
        }

    except Exception as e:
        logger.error(f"❌ Failed to store episode in Firestore: {e}")
        return {"status": "error", "error_message": f"Failed to save episode: {str(e)}"}


def index_media_analysis(
    episode_log: Dict[str, Any], episode_id: str, child_id: str = ""
) -> dict:
    """Index the episode data for vector search"""
    try:
        # Use provided child_id or default
        if not child_id:
            child_id = globals().get("CHILD_ID", "demo")

        vector_search_index = get_vector_search_index()
        if not vector_search_index:
            logger.warning(
                "Vector search index not configured. Skipping indexing.")
            return {"status": "skipped", "message": "Vector indexing not configured"}

        logger.info(f"Indexing episode {episode_id} for vector search...")

        # Extract elements for vectorization
        # Handle nested structure if episode_log is wrapped
        if isinstance(episode_log, dict) and "report" in episode_log:
            log_data = episode_log["report"]
        elif "highlight_identifier_response" in episode_log:
            log_data = episode_log["highlight_identifier_response"].get(
                "report", {})
        else:
            log_data = episode_log

        tags = log_data.get("vector_tags", [])
        activities = log_data.get("activities", [])
        milestones = log_data.get("development_milestones", [])
        emotion = log_data.get("emotion", "")
        summary = log_data.get("summary", "")

        # Create rich text for embedding
        text_for_embedding = " ".join(
            [
                summary,
                emotion,
                " ".join(tags),
                " ".join(activities),
                " ".join(milestones),
            ]
        ).strip()

        if not text_for_embedding:
            logger.warning(
                "No text content to vectorize. Skipping vector index.")
            return {"status": "skipped", "message": "No content to vectorize"}

        logger.info(f"Vectorizing text: '{text_for_embedding[:100]}...'")

        # Generate embeddings
        embedding_model = get_embedding_model()
        embeddings = embedding_model.get_embeddings([text_for_embedding])
        vector = embeddings[0].values

        logger.info(
            f"Upserting datapoint to Vector Search Index with ID: {episode_id}..."
        )

        # Get created_at timestamp as Unix timestamp (seconds since epoch)
        created_at = datetime.now(timezone.utc)
        created_at_timestamp = int(created_at.timestamp())

        # Upsert to Vector Search Index
        # Using restricts field for user-specific filtering and numeric fields for timestamp filtering
        vector_search_index.upsert_datapoints(
            datapoints=[
                {
                    "datapoint_id": episode_id,
                    "feature_vector": vector,
                    "restricts": [{"namespace": "child_id", "allow_list": [child_id]}],
                    "numeric_restricts": [
                        {"namespace": "created_at",
                            "value_int": created_at_timestamp}
                    ],
                }
            ]
        )

        logger.info(f"✅ Successfully indexed episode {episode_id} for vector search")
        return {
            "status": "success",
            "message": f"Episode indexed with ID: {episode_id}",
        }

    except Exception as e:
        logger.error(f"❌ Failed to index episode for vector search: {e}")
        return {
            "status": "error",
            "error_message": f"Failed to index episode: {str(e)}",
        }


def set_child_id(child_id: str = ""):
    """Set the child ID for the current session"""
    global CHILD_ID
    CHILD_ID = child_id if child_id else "demo"
    logger.info(f"Child ID set to: {CHILD_ID}")
    return CHILD_ID


def process_media_for_cloud_function(
    media_uri: str, user_id: str = "", child_id: str = "", 
    media_upload_id: str = None, captured_at = None
) -> Dict[str, Any]:
    """
    Cloud Functionsから呼び出せる関数
    メディアファイルを分析し、エピソードを生成して保存する
    """
    try:
        # 1. 客観的事実を分析
        facts_result = objective_analyzer(media_uri)
        if facts_result.get("status") != "success":
            return facts_result

        facts = facts_result.get("report", {})

        # 2. ハイライトを特定
        episode_result = highlight_identifier(facts)
        if episode_result.get("status") != "success":
            return episode_result

        episode_data = episode_result.get("report", {})

        # 3. エピソードを保存
        save_result = save_summary(
            episode_data, media_uri, child_id=child_id, user_id=user_id,
            media_upload_id=media_upload_id, captured_at=captured_at
        )
        if save_result.get("status") != "success":
            return save_result

        episode_id = save_result.get("episode_id")

        # 4. 検索用インデックス化
        index_result = index_media_analysis(
            episode_data, episode_id, child_id=child_id)

        return {
            "status": "success",
            "episode_id": episode_id,
            "episode_data": episode_data,
            "objective_facts": facts,
            "indexed": index_result.get("status") == "success",
        }

    except Exception as e:
        logger.error(f"Error processing media: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# ADK Agent initialization は Cloud Functions では不要
# root_agent = Agent(
#     name="episode_generator_agent",
#     model=MODEL_NAME,
#     description="メディアファイルを分析し、構造化されたエピソードログを生成するエージェント",
#     instruction="""あなたは、メディアファイルを客観的に分析し、ハイライトシーンを特定して構造化されたエピソードログを作成するエージェントです。
#
# 処理の流れ：
# 1. objective_analyzerでメディアファイルを分析
# 2. highlight_identifierでハイライトを特定してエピソードログを作成
# 3. save_summaryでFirestoreに保存（episode_idが返される）
# 4. index_media_analysisで保存したエピソードをベクトル検索用にインデックス化（save_summaryで取得したepisode_idを使用）
#
# 注意事項：
# - child_idは環境で設定されています（デフォルト: "demo"）
# - save_summaryの返り値にあるepisode_idを必ずindex_media_analysisに渡してください""",
#     tools=[
#         objective_analyzer,
#         highlight_identifier,
#         save_summary,
#         index_media_analysis,
#     ],
# )
