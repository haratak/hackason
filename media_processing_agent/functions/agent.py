from typing import Dict, Any, List, Optional
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

import json
import logging
import asyncio
import uuid
from google.cloud.aiplatform_v1beta1.types import index_endpoint
from vertexai.generative_models import GenerativeModel, Part
from vertexai.language_models import TextEmbeddingModel
import vertexai
from google.cloud import firestore
from google.cloud.aiplatform import MatchingEngineIndex
from google.cloud import storage

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
        _embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
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
MODEL_NAME = "gemini-2.5-flash"

# Child ID will be set when the agent is invoked
# Default to "demo" if not provided
CHILD_ID = "demo"


def convert_firebase_url_to_gs(firebase_url: str) -> str:
    """Convert Firebase download URL to gs:// format for better Vertex AI access"""
    try:
        # Extract bucket and object path from Firebase URL
        if "firebasestorage.app" in firebase_url and "/o/" in firebase_url:
            # Parse Firebase Storage download URL
            parts = firebase_url.split("/o/")
            if len(parts) >= 2:
                bucket_part = parts[0].split("/")[-1]  # Get bucket name
                object_part = parts[1].split("?")[0]  # Remove query parameters

                # URL decode the object path
                import urllib.parse

                object_path = urllib.parse.unquote(object_part)

                gs_url = f"gs://{bucket_part}/{object_path}"
                logger.info(f"Converted Firebase URL to gs:// format: {gs_url}")
                return gs_url
    except Exception as e:
        logger.warning(f"Failed to convert Firebase URL: {e}")

    return firebase_url  # Return original if conversion fails


def objective_analyzer(media_uri: str) -> dict:
    """Extract objective facts from media files"""
    model = GenerativeModel(MODEL_NAME)
    try:
        # Try to convert Firebase URL to gs:// format for better access
        original_uri = media_uri
        if "firebasestorage.app" in media_uri:
            media_uri = convert_firebase_url_to_gs(media_uri)

        # Determine MIME type from URL extension
        media_uri_lower = original_uri.lower()

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

        # Try gs:// URL first, then fallback to original URL
        try:
            media_part = Part.from_uri(uri=media_uri, mime_type=mime_type)
        except Exception as gs_error:
            logger.warning(f"gs:// URL failed, trying original URL: {gs_error}")
            media_part = Part.from_uri(uri=original_uri, mime_type=mime_type)

        prompt = """
        あなたは、写真や動画からシーンを正確に読み取る分析システムです。
        この画像/動画から観察できる具体的なシーン情報と行動事実をリストアップしてください。

        【分析の重点】
        - 子供が「何をしているか」を具体的に特定する
        - その場の状況や環境を詳しく描写する
        - 子供の表情や動作を客観的に記録する
        - 成長や発達の推測は行わず、見たままを記述する

        【出力形式】
        {
            "scene_description": "その場のシーン全体の描写（場所、時間帯、周りの状況など）",
            "child_actions": ["子供が行っている具体的な行動のリスト"],
            "child_expressions": ["観察できる表情や感情表現"],
            "objects_and_items": ["子供が触れている、使っている、見ている物のリスト"],
            "environment_details": ["背景、場所、周囲の人や物の詳細"],
            "body_posture": ["姿勢や体の位置（座っている、立っている、寝ているなど）"],
            "spoken_or_sounds": ["聞こえる言葉、音、声（ある場合）"],
            "clothing_and_appearance": ["服装や身に着けているもの"]
        }
        """

        response = model.generate_content([media_part, prompt])
        response_text = response.text.strip()

        logger.info(f"Raw response from model: {response_text[:200]}...")

        import re

        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
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
            # Add media type to facts
            facts["media_type"] = "video" if mime_type.startswith("video/") else "image"
            return {"status": "success", "report": facts}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                "status": "error",
                "error_message": f"Failed to parse JSON: {str(e)}",
            }

    except Exception as e:
        error_msg = str(e)

        # Check for URL access errors
        if (
            "Cannot fetch content from the provided URL" in error_msg
            or "URL_ERROR" in error_msg
        ):
            return {
                "status": "error",
                "error_message": "メディアファイルにアクセスできませんでした。Firebase StorageのURLがVertex AIからアクセス可能であることを確認してください。",
                "error_details": {
                    "original_error": error_msg,
                    "solutions": [
                        "Firebase StorageのCORS設定を確認する",
                        "Vertex AI Service Accountに適切な権限があることを確認する",
                        "メディアファイルが公開アクセス可能かCloud Storageバケットの権限を確認する",
                    ],
                },
            }

        return {"status": "error", "error_message": str(e)}


def perspective_determiner(facts: Dict[str, Any], child_age_months: int) -> dict:
    """Determine analysis perspectives focused on scene identification and action description"""
    model = GenerativeModel(MODEL_NAME)
    try:
        facts_json = json.dumps(facts, ensure_ascii=False, indent=2)
        media_type = facts.get("media_type", "image")

        # 動画・写真共通でシーン特定に焦点を当てる
        prompt = f"""
        あなたは、子供の行動シーンを特定・分析する専門家です。
        観察された事実から、このメディアで「子供が何をしているか」を具体的に特定してください。

        【入力情報】
        メディアタイプ: {media_type}
        月齢: {child_age_months}ヶ月
        観察された事実:
        {facts_json}

        【分析の重点】
        成長や発達ではなく、「そのとき子供が何をしていたか」「どんなシーンか」の特定に焦点を当ててください。

        【分析視点の選択指針】
        1. **行動の特定**
           - 子供の具体的な動作や行為
           - 何をしている最中なのか
           - どんな遊びや活動をしているか

        2. **シーンの背景**
           - どこで起きているシーンか
           - どんな状況や環境か
           - 周囲に何があるか

        3. **表情や感情の瞬間**
           - その時の子供の気持ちや反応
           - 楽しそう、真剣、驚いているなど
           - 表情から読み取れるその瞬間の感情

        4. **物や人との関わり**
           - どんな物を使っているか
           - 誰かと一緒にいるか
           - 何に注目しているか

        【出力形式】
        {{
            "perspectives": [
                {{
                    "type": "視点名（action_focus, scene_context, emotional_moment, interaction_focus等）",
                    "focus": "この視点で特定すべき具体的なシーンや行動",
                    "reason": "なぜこのシーンが興味深いか",
                    "observable_signs": ["メディアから観察された具体的な要素"]
                }}
            ],
            "analysis_note": "このメディアが捉えたシーンの概要"
        }}
        """

        prompt += """
        
        【重要】
        - 視点数は最大4つまで
        - 実際に観察された内容に基づく視点のみを選択
        - 各視点は重複しないように独立した観点から選ぶ
        """

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        logger.info(
            f"Raw response from perspective_determiner: {response_text[:200]}..."
        )

        # Extract JSON from response
        import re

        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

        perspectives = json.loads(response_text)
        return {"status": "success", "report": perspectives}

    except Exception as e:
        logger.error(f"Error in perspective_determiner: {e}")
        return {"status": "error", "error_message": str(e)}


def dynamic_multi_analyzer(facts: Dict[str, Any], perspective: Dict[str, Any]) -> dict:
    """Analyze facts from a specific perspective"""
    model = GenerativeModel(MODEL_NAME)
    try:
        # Validate perspective structure
        if "type" not in perspective:
            return {
                "status": "error",
                "error_message": "perspective must contain 'type' field",
            }
        if "focus" not in perspective:
            return {
                "status": "error",
                "error_message": "perspective must contain 'focus' field",
            }

        facts_json = json.dumps(facts, ensure_ascii=False, indent=2)
        media_type = facts.get("media_type", "image")

        prompt = f"""
        あなたは、子供のシーンや行動を具体的に描写する記録専門家です。
        観察された事実から、指定された視点で「子供が何をしているか」を具体的に描写してください。

        【入力情報】
        メディアタイプ: {media_type}
        分析視点: {perspective['type']}
        着目ポイント: {perspective['focus']}
        観察された事実:
        {facts_json}

        【分析の重点】
        成長や発達の評価ではなく、「その瞬間に子供が何をしていたか」「どんなシーンだったか」の具体的な描写に焦点を当ててください。

        【描写の指針】
        1. **具体的な行動の記録**: 子供が実際に行っている動作や行為を詳しく描写
        2. **シーンの情景描写**: その場の雰囲気、環境、状況を生き生きと表現
        3. **表情や反応の観察**: その瞬間の子供の感情や表情を客観的に記録
        4. **楽しい瞬間の強調**: そのシーンの面白さや魅力的な点を親しみやすく表現
        5. **検索しやすいタグ**: 具体的な行動や場面を表すキーワードを生成

        【出力形式】
        {{
            "perspective_type": "{perspective['type']}",
            "title": "そのシーンを表す具体的なタイトル（15文字以内）",
            "summary": "子供の行動とその時の状況を具体的に描写（100文字程度）",
            "content": "そのシーンの詳しい描写と、なぜその瞬間が印象的なのかの説明",
            "scene_keywords": ["そのシーンや行動を表現するキーワード"],
            "vector_tags": ["具体的な行動や場面を表すタグを5-8個。例：「積み木で遊ぶ時間」「お祭りを楽しむ姿」「水遊びに夢中」「おやつタイムの笑顔」など、行動や場面が分かる10-20文字程度のフレーズ"]
        }}

        【注意事項】
        - 成長の評価や発達の判断は行わない
        - 「できるようになった」などの断定的な表現は避ける
        - その瞬間の楽しさや魅力を中心に描写する
        - 親が見て「この瞬間素敵だな」と思えるような表現を心がける
        """

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Extract JSON from response
        import re

        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

        analysis = json.loads(response_text)
        return {"status": "success", "report": analysis}

    except Exception as e:
        logger.error(f"Error in dynamic_multi_analyzer: {e}")
        return {"status": "error", "error_message": str(e)}




def generate_emotional_title(episodes: List[Dict[str, Any]]) -> str:
    """Generate an emotional title for timeline display (15-20 chars)"""
    try:
        # エピソードから具体的な情報を収集
        locations = []
        actions = []
        emotions = []
        objects = []
        
        for episode in episodes:
            if isinstance(episode, dict):
                summary = episode.get("summary", "")
                tags = episode.get("tags", episode.get("vector_tags", []))
                
                # 場所やイベントの抽出
                for place in ["公園", "お祭り", "家", "おうち", "外", "部屋", "庭", "海", "山", "川"]:
                    if place in summary:
                        locations.append(place)
                
                # 具体的な行動の抽出
                for action in ["遊ぶ", "笑う", "走る", "歩く", "食べる", "飲む", "見る", "持つ", "触る"]:
                    if action in summary:
                        actions.append(action)
                
                # 感情の抽出
                if "笑顔" in summary or "楽しい" in summary or "嬉しい" in summary:
                    emotions.append("楽しい")
                if "真剣" in summary or "集中" in summary:
                    emotions.append("夢中")
                
                # 具体的な物の抽出（タグから）
                for tag in tags:
                    # 物や具体的な要素を含むタグを探す
                    if any(item in tag for item in ["ボトル", "おもちゃ", "本", "ボール", "いちご", "食べ物"]):
                        objects.append(tag)
        
        # タイトル生成用のプロンプト作成
        vertexai.init(project=get_project_id(), location=get_location())
        model = GenerativeModel(MODEL_NAME)

        
        # エピソードからより詳細な情報を抽出
        combined_text = "\n".join([
            f"- {episode.get('summary', '')}" for episode in episodes if episode.get('summary')
        ])
        
        prompt = f"""
あなたは、子供の日常シーンを魅力的に表現するタイトル作成の専門家です。
以下の分析結果から、「その瞬間に子供が何をしていたか」を表現する魅力的なタイトルを作成してください。

【分析結果の要約】
{combined_text}

【タイトル作成の重点】
1. **具体的な行動やシーン**: 子供が何をしているか分かるように
2. **その場の雰囲気**: 楽しそう、夢中、のんびりなど、その時の様子
3. **親しみやすさ**: 見る人がほっこりするような表現

【避けるべき表現】
- 成長や発達を強調する表現（「できるようになった」など）
- 抽象的すぎる表現

【良い例】
- 「積み木に夢中な午後」
- 「お祭りを楽しむ笑顔」
- 「おやつタイムの真剣顔」
- 「水遊びで大はしゃぎ」

【タイトルの条件】
- その瞬間の行動やシーンが分かる具体的な表現
- 15〜20文字程度で、最後に内容に合った絵文字を1つ付ける
- 親が見て「この瞬間いいな」と思えるような表現

【出力形式】
タイトルのみ
"""
        
        response = model.generate_content(prompt)
        emotional_title = response.text.strip()
        
        return emotional_title
        
    except Exception as e:
        logger.error(f"Failed to generate emotional title: {e}")
        return "🌈きょうのできごと"


def save_multi_episode_analysis(
    episodes: List[Dict[str, Any]],
    media_id: str = "",
    media_source_uri: str = "",
    child_id: str = "",
    child_age_months: int = 0,
    user_id: str = "",
    captured_at: datetime = None,
    thumbnail_url: str = None,
) -> dict:
    """Save multiple episodes as nested array in a single media document"""
    try:
        # Generate media_id if not provided
        if not media_id:
            media_id = str(uuid.uuid4())
            logger.info(f"Generated new media_id: {media_id}")

        # Use provided child_id or default
        if not child_id:
            child_id = globals().get("CHILD_ID", "demo")

        logger.info(f"Saving {len(episodes)} episodes for media: {media_id}")

        db = get_firestore_client()

        # Prepare episodes data
        episodes_data = []
        for episode in episodes:
            # Extract episode data
            if isinstance(episode, dict) and "report" in episode:
                ep_data = episode["report"]
            else:
                ep_data = episode

            # Create scene-focused episode structure
            episode_entry = {
                "id": str(uuid.uuid4()),
                "type": ep_data.get("perspective_type", ep_data.get("type", "general")),
                "title": ep_data.get("title", ""),
                "summary": ep_data.get("summary", ""),
                "content": ep_data.get("content", ep_data.get("summary", "")),
                "tags": ep_data.get("vector_tags", ep_data.get("tags", [])),
                "scene_keywords": ep_data.get("scene_keywords", []),
                "metadata": {
                    "scene_description": ep_data.get("scene_description", ""),
                    "perspective_type": ep_data.get("perspective_type", ""),
                },
                "created_at": datetime.now(timezone.utc),
            }
            episodes_data.append(episode_entry)

        # Generate emotional title for timeline
        emotional_title = generate_emotional_title(episodes_data)

        # Save all data in single document
        media_data = {
            "media_uri": media_source_uri,
            "child_id": child_id,
            "child_age_months": child_age_months,
            "user_id": user_id,
            "emotional_title": emotional_title,  # For timeline display
            "episodes": episodes_data,
            "episode_count": len(episodes_data),
            "captured_at": captured_at if captured_at else datetime.now(timezone.utc),  # Use provided captured_at or current time
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        
        # Add thumbnail URL if provided (for videos)
        if thumbnail_url:
            media_data["thumbnail_url"] = thumbnail_url

        # Save to Firestore
        media_ref = db.collection("analysis_results").document(media_id)
        media_ref.set(media_data)

        logger.info(f"✅ Successfully saved {len(episodes_data)} episodes for media: {media_id}")

        return {
            "status": "success",
            "media_id": media_id,
            "emotional_title": emotional_title,
            "episode_count": len(episodes_data),
            "episodes": episodes_data,
        }

    except Exception as e:
        logger.error(f"❌ Failed to save episodes: {e}")
        return {
            "status": "error",
            "error_message": f"Failed to save episodes: {str(e)}",
        }




def index_episodes(
    episodes: List[Dict[str, Any]],
    media_id: str,
    child_id: str = "",
    captured_at: datetime = None,
) -> dict:
    """Index multiple episodes for vector search"""
    try:
        # Use provided child_id or default
        if not child_id:
            child_id = globals().get("CHILD_ID", "demo")

        vector_search_index = get_vector_search_index()
        if not vector_search_index:
            logger.warning("Vector search index not configured. Skipping indexing.")
            return {"status": "skipped", "message": "Vector indexing not configured"}

        indexed_count = 0
        for episode in episodes:
            try:
                # Extract episode data
                if isinstance(episode, dict) and "report" in episode:
                    ep_data = episode["report"]
                else:
                    ep_data = episode

                episode_id = ep_data.get("id", str(uuid.uuid4()))

                # Create text for embedding - tags only
                tags = ep_data.get("tags", [])
                if not tags:
                    logger.warning(f"No tags found for episode {episode_id}, skipping indexing")
                    continue

                embedding_text = " ".join(tags)

                # Generate embeddings
                embedding_model = get_embedding_model()
                embeddings = embedding_model.get_embeddings([embedding_text])

                if embeddings and len(embeddings) > 0:
                    embedding_vector = embeddings[0].values

                    # Create datapoint
                    datapoint_id = f"{media_id}_{episode_id}"
                    restricts = [
                        {"namespace": "media_id", "allow_list": [media_id]},
                        {"namespace": "child_id", "allow_list": [child_id]},
                    ]
                    
                    # Add captured_at timestamp if provided
                    if captured_at:
                        captured_at_timestamp = int(captured_at.timestamp())
                        restricts.append(
                            {"namespace": "captured_at", "value_int": captured_at_timestamp}
                        )
                    
                    datapoint = {
                        "datapoint_id": datapoint_id,
                        "feature_vector": embedding_vector,
                        "restricts": restricts,
                    }

                    # Upsert to index
                    vector_search_index.upsert_datapoints([datapoint])
                    indexed_count += 1
                    logger.info(f"Indexed episode {episode_id}")

            except Exception as e:
                logger.error(f"Failed to index episode: {e}")
                continue

        logger.info(f"✅ Successfully indexed {indexed_count}/{len(episodes)} episodes")
        return {
            "status": "success",
            "indexed_count": indexed_count,
            "total_episodes": len(episodes),
        }

    except Exception as e:
        logger.error(f"❌ Failed to index episodes: {e}")
        return {
            "status": "error",
            "error_message": f"Failed to index episodes: {str(e)}",
        }








def set_child_id(child_id: str = ""):
    """Set the child ID for the current session"""
    global CHILD_ID
    CHILD_ID = child_id if child_id else "demo"
    logger.info(f"Child ID set to: {CHILD_ID}")
    return CHILD_ID




def calculate_age_months(birth_date: datetime) -> int:
    """Calculate age in months from birthdate"""
    today = datetime.now(timezone.utc)
    months = (today.year - birth_date.year) * 12 + today.month - birth_date.month
    # Adjust if the day hasn't come yet this month
    if today.day < birth_date.day:
        months -= 1
    return max(0, months)  # Ensure non-negative


def generate_video_thumbnail_if_needed(media_uri: str) -> Optional[str]:
    """
    動画ファイルのサムネイルが存在しない場合は生成する
    
    Args:
        media_uri: 動画ファイルのURI（gs://またはhttps://）
        
    Returns:
        サムネイルのURL（生成済みまたは新規生成）、失敗時はNone
    """
    try:
        # video_thumbnailモジュールをインポート
        from video_thumbnail import generate_video_thumbnail, get_thumbnail_path
        
        # URIからバケット名とパスを抽出
        if media_uri.startswith('gs://'):
            # gs://bucket-name/path/to/file
            parts = media_uri[5:].split('/', 1)
            if len(parts) != 2:
                return None
            bucket_name, object_path = parts
        elif 'firebasestorage.googleapis.com' in media_uri or 'firebasestorage.app' in media_uri:
            # Firebase Storage URLからパスを抽出
            import urllib.parse
            parsed = urllib.parse.urlparse(media_uri)
            path_parts = parsed.path.split('/o/')
            if len(path_parts) < 2:
                return None
            
            # バケット名を抽出
            if 'firebasestorage.googleapis.com' in media_uri:
                bucket_name = parsed.path.split('/')[3]
            else:
                bucket_name = parsed.hostname.split('.')[0]
            
            # オブジェクトパスを抽出（URLデコード）
            object_path = urllib.parse.unquote(path_parts[1].split('?')[0])
        else:
            logger.warning(f"Unsupported media URI format: {media_uri}")
            return None
        
        # サムネイルのパスを生成
        thumbnail_path = get_thumbnail_path(object_path)
        
        # サムネイルが既に存在するか確認
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        thumbnail_blob = bucket.blob(thumbnail_path)
        
        if thumbnail_blob.exists():
            logger.info(f"Thumbnail already exists: gs://{bucket_name}/{thumbnail_path}")
            return f"gs://{bucket_name}/{thumbnail_path}"
        
        # サムネイルを生成（自動的に最適なフレームを選択）
        logger.info(f"Generating thumbnail for: {media_uri}")
        thumbnail_url = generate_video_thumbnail(
            video_url=media_uri,
            bucket_name=bucket_name,
            output_path=thumbnail_path,
            time_offset=None  # 自動選択モード
        )
        
        return thumbnail_url
        
    except Exception as e:
        logger.error(f"Error in generate_video_thumbnail_if_needed: {str(e)}")
        return None


def get_child_age_months(child_id: str) -> int:
    """Get child's age in months from Firestore"""
    try:
        db = get_firestore_client()
        child_doc = db.collection("children").document(child_id).get()

        if child_doc.exists:
            child_data = child_doc.to_dict()
            birth_date = child_data.get("birthDate")

            if birth_date:
                # birthDate is a Firestore Timestamp
                return calculate_age_months(birth_date)

        logger.warning(f"Could not find birthDate for child_id: {child_id}")
        return 12  # Default to 12 months

    except Exception as e:
        logger.error(f"Error getting child age: {e}")
        return 12  # Default to 12 months


def process_media_for_cloud_function(
    media_uri: str,
    user_id: str = "",
    child_id: str = "",
    child_age_months: int = None,  # Auto-calculate if not provided
    captured_at: datetime = None,  # Media capture date/time
) -> Dict[str, Any]:
    """
    Cloud Functionsから呼び出せる関数
    メディアファイルを多角的に分析し、複数のエピソードを生成して保存する
    """
    try:
        # Auto-calculate age if not provided
        if child_age_months is None and child_id:
            child_age_months = get_child_age_months(child_id)
            logger.info(
                f"Auto-calculated age for child {child_id}: {child_age_months} months"
            )
        elif child_age_months is None:
            child_age_months = 12  # Default if no child_id

        # Generate unique media ID
        media_id = str(uuid.uuid4())

        # 1. 客観的事実を分析
        facts_result = objective_analyzer(media_uri)
        if facts_result.get("status") != "success":
            return facts_result

        facts = facts_result.get("report", {})
        
        # 動画の場合はサムネイルを生成
        thumbnail_url = None
        if facts.get("media_type") == "video":
            thumbnail_url = generate_video_thumbnail_if_needed(media_uri)
            if thumbnail_url:
                logger.info(f"Generated video thumbnail: {thumbnail_url}")

        # 2. 月齢に基づいて分析視点を決定
        perspectives_result = perspective_determiner(facts, child_age_months)
        if perspectives_result.get("status") != "success":
            return perspectives_result

        perspectives_data = perspectives_result.get("report", {})
        perspectives = perspectives_data.get("perspectives", [])

        if not perspectives:
            return {
                "status": "error",
                "error_message": "No perspectives determined for analysis",
            }

        logger.info(f"Determined {len(perspectives)} perspectives for analysis")

        # 3. 各視点から並行して分析を実行
        episodes = []
        for perspective in perspectives:
            analysis_result = dynamic_multi_analyzer(facts, perspective)

            if analysis_result.get("status") == "success":
                analysis_data = analysis_result.get("report", {})
                # Add perspective type to the analysis
                analysis_data["type"] = perspective["type"]
                analysis_data["perspective_type"] = perspective["type"]
                episodes.append(analysis_data)
                logger.info(f"✅ Successfully analyzed perspective: {perspective['type']}")
            else:
                logger.error(f"❌ Failed to analyze perspective {perspective['type']}: {analysis_result.get('error_message', 'Unknown error')}")

        if not episodes:
            return {
                "status": "error",
                "error_message": "Failed to generate any episodes",
            }

        # 4. Save all episodes in single document
        save_result = save_multi_episode_analysis(
            episodes=episodes,
            media_id=media_id,
            media_source_uri=media_uri,
            child_id=child_id,
            child_age_months=child_age_months,
            user_id=user_id,
            captured_at=captured_at,
            thumbnail_url=thumbnail_url,  # サムネイルURLを追加
        )

        if save_result.get("status") != "success":
            return save_result

        # 5. Index all episodes for vector search
        index_result = index_episodes(
            episodes=save_result.get("episodes", []),
            media_id=media_id,
            child_id=child_id,
            captured_at=captured_at,
        )

        # Return comprehensive result
        return {
            "status": "success",
            "media_id": media_id,
            "emotional_title": save_result.get("emotional_title", ""),
            "child_age_months": child_age_months,
            "episode_count": len(episodes),
            "indexed_count": index_result.get("indexed_count", 0),
            "perspectives": [ep["type"] for ep in episodes],
            "analysis_note": perspectives_data.get("analysis_note", ""),
        }

    except Exception as e:
        logger.error(f"Error processing media: {str(e)}")
        return {"status": "error", "error_message": str(e)}


# Cloud Functions では ADK Agent は使用しない
