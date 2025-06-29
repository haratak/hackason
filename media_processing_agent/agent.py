from typing import Dict, Any
from google.adk.agents import Agent
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

# Initialize Vertex AI with values from environment
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
location = os.getenv("GOOGLE_CLOUD_LOCATION")
vertexai.init(project=project_id, location=location)

# Initialize Firestore and other services
db = firestore.Client()
embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
INDEX_ID = os.getenv("VERTEX_AI_INDEX_ID")

# Initialize vector search index if available
vector_search_index = None
if INDEX_ID:
    # MatchingEngineIndex requires full resource name with region
    vector_search_index = MatchingEngineIndex(
        index_name=f"projects/{project_id}/locations/us-central1/indexes/{INDEX_ID}"
    )

logger = logging.getLogger(__name__)
MODEL_NAME = "gemini-2.0-flash-001"

# Child ID will be set when the agent is invoked
# Default to "demo" if not provided
CHILD_ID = "demo"

# Development mode flag - when True, skip Firestore and vector storage
DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "false").lower() in [
    "true",
    "1",
    "yes",
]

# プロンプト定数定義
# objective_analyzer用プロンプト - メディアファイルから客観的な事実を抽出する役割
OBJECTIVE_ANALYZER_PROMPT = """
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

# highlight_identifier用プロンプトテンプレート - 事実データからハイライトシーンを特定しエピソードログを作成する役割
HIGHLIGHT_IDENTIFIER_PROMPT_TEMPLATE = """
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

# root_agent用インストラクション - エージェント全体の処理フローを定義する役割
ROOT_AGENT_INSTRUCTION = """あなたは、メディアファイルを客観的に分析し、ハイライトシーンを特定して構造化されたエピソードログを作成するエージェントです。

処理の流れ：
1. objective_analyzerでメディアファイルを分析
2. highlight_identifierでハイライトを特定してエピソードログを作成
3. save_summaryでFirestoreに保存（episode_idが返される）
4. index_media_analysisで保存したエピソードをベクトル検索用にインデックス化（save_summaryで取得したepisode_idを使用）

注意事項：
- child_idは環境で設定されています（デフォルト: "demo"）
- save_summaryの返り値にあるepisode_idを必ずindex_media_analysisに渡してください"""


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
                f"Could not determine MIME type from URL, defaulting to {
                    mime_type}"
            )

        logger.info(f"Detected MIME type: {mime_type} for URL: {media_uri}")
        media_part = Part.from_uri(uri=media_uri, mime_type=mime_type)

        response = model.generate_content([media_part, OBJECTIVE_ANALYZER_PROMPT])
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

        prompt = HIGHLIGHT_IDENTIFIER_PROMPT_TEMPLATE.format(facts_json=facts_json)

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


def save_summary(episode_log: Dict[str, Any], media_source_uri: str) -> dict:
    """Save the episode log to Firestore (or log in development mode)"""
    try:
        child_id = globals().get("CHILD_ID", "demo")
        development_mode = globals().get("DEVELOPMENT_MODE", False)

        logger.info(
            f"Processing episode for child: {
                child_id} (Development Mode: {development_mode})"
        )
        logger.debug(f"Received episode_log: {episode_log}")

        # Extract data from episode log
        # Handle nested structure if episode_log is wrapped
        if isinstance(episode_log, dict) and "report" in episode_log:
            log_data = episode_log["report"]
        elif (
            isinstance(episode_log, dict)
            and "highlight_identifier_response" in episode_log
        ):
            log_data = episode_log["highlight_identifier_response"].get(
                "report", {})
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

        if development_mode:
            # Development mode: just log the data
            import uuid

            episode_id = f"dev_{uuid.uuid4().hex[:8]}"

            logger.info(
                "📝 [DEVELOPMENT MODE] Episode data that would be saved:")
            logger.info(f"Episode ID: {episode_id}")
            logger.info(
                json.dumps(firestore_data, default=str,
                           ensure_ascii=False, indent=2)
            )

            return {
                "status": "success",
                "episode_id": episode_id,
                "message": f"[DEV MODE] Episode logged with ID: {episode_id}",
                "development_mode": True,
            }
        else:
            # Production mode: save to Firestore
            doc_ref = db.collection("episodes").document()
            doc_ref.set(firestore_data)
            episode_id = doc_ref.id

            logger.info(
                f"✅ Successfully stored episode in Firestore. Document ID: {
                    episode_id}"
            )
            return {
                "status": "success",
                "episode_id": episode_id,
                "message": f"Episode saved with ID: {episode_id}",
            }

    except Exception as e:
        logger.error(f"❌ Failed to store episode in Firestore: {e}")
        return {"status": "error", "error_message": f"Failed to save episode: {str(e)}"}


def index_media_analysis(episode_log: Dict[str, Any], episode_id: str) -> dict:
    """Index the episode data for vector search (or log in development mode)"""
    try:
        child_id = globals().get("CHILD_ID", "demo")
        development_mode = globals().get("DEVELOPMENT_MODE", False)

        if development_mode:
            logger.info("🔍 [DEVELOPMENT MODE] Vector indexing skipped")
            logger.info(f"Would index episode: {
                        episode_id} for child: {child_id}")
            return {
                "status": "skipped",
                "message": "[DEV MODE] Vector indexing skipped",
                "development_mode": True,
            }

        if not vector_search_index:
            logger.warning(
                "Vector search index not configured. Skipping indexing.")
            return {"status": "skipped", "message": "Vector indexing not configured"}

        logger.info(f"Indexing episode {episode_id} for vector search...")

        # Extract elements for vectorization
        # Handle nested structure if episode_log is wrapped
        if "highlight_identifier_response" in episode_log:
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
        embeddings = embedding_model.get_embeddings([text_for_embedding])
        vector = embeddings[0].values

        logger.info(
            f"Upserting datapoint to Vector Search Index with ID: {
                episode_id}..."
        )

        # Upsert to Vector Search Index
        # Using restricts field for user-specific filtering and numeric fields for timestamp filtering

        # Get created_at timestamp as Unix timestamp (seconds since epoch)
        created_at = datetime.now(timezone.utc)
        created_at_timestamp = int(created_at.timestamp())

        vector_search_index.upsert_datapoints(
            datapoints=[
                {
                    "datapoint_id": episode_id,
                    "feature_vector": vector,
                    "restricts": [{"namespace": "child_id", "allow_list": [child_id]}],
                    "numeric_restricts": [
                        {"namespace": "created_at",
                            "value_int": created_at_timestamp}
                    ]
                }
            ]
        )

        logger.info(f"✅ Successfully indexed episode {
                    episode_id} for vector search")
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


def set_child_id(child_id: str=None):
    """Set the child ID for the current session"""
    global CHILD_ID
    CHILD_ID = child_id if child_id else "demo"
    logger.info(f"Child ID set to: {CHILD_ID}")
    return CHILD_ID


def set_development_mode(enabled: bool=False):
    """Enable or disable development mode"""
    global DEVELOPMENT_MODE
    DEVELOPMENT_MODE = enabled
    mode_str = "ENABLED" if enabled else "DISABLED"
    logger.info(f"🔧 Development mode {mode_str}")
    if enabled:
        logger.info("  - Firestore saves will be logged only")
        logger.info("  - Vector indexing will be skipped")
    return DEVELOPMENT_MODE


root_agent = Agent(
    name="episode_generator_agent",
    model=MODEL_NAME,
    description="メディアファイルを分析し、構造化されたエピソードログを生成するエージェント",
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[
        objective_analyzer,
        highlight_identifier,
        save_summary,
        index_media_analysis,
    ],
)
