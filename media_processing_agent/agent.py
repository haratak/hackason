from typing import Dict, Any, List
from google.adk.agents import Agent
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
                index_name=f"projects/{get_project_id()
                                       }/locations/{get_location()}/indexes/{index_id}"
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
                f"Could not determine MIME type from URL, defaulting to {
                    mime_type}"
            )

        logger.info(f"Detected MIME type: {mime_type} for URL: {media_uri}")
        
        # Try gs:// URL first, then fallback to original URL
        try:
            media_part = Part.from_uri(uri=media_uri, mime_type=mime_type)
        except Exception as gs_error:
            logger.warning(f"gs:// URL failed, trying original URL: {gs_error}")
            media_part = Part.from_uri(uri=original_uri, mime_type=mime_type)

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
        if "Cannot fetch content from the provided URL" in error_msg or "URL_ERROR" in error_msg:
            return {
                "status": "error", 
                "error_message": "メディアファイルにアクセスできませんでした。Firebase StorageのURLがVertex AIからアクセス可能であることを確認してください。",
                "error_details": {
                    "original_error": error_msg,
                    "solutions": [
                        "Firebase StorageのCORS設定を確認する",
                        "Vertex AI Service Accountに適切な権限があることを確認する", 
                        "メディアファイルが公開アクセス可能かCloud Storageバケットの権限を確認する"
                    ]
                }
            }
        
        return {"status": "error", "error_message": str(e)}


def perspective_determiner(facts: Dict[str, Any], child_age_months: int) -> dict:
    """Determine analysis perspectives based on media type, child age and observed facts"""
    model = GenerativeModel(MODEL_NAME)
    try:
        facts_json = json.dumps(facts, ensure_ascii=False, indent=2)
        media_type = facts.get("media_type", "image")

        if media_type == "video":
            # 動画の場合：多角的な視点（発達、感情、思い出、面白い瞬間など）
            prompt = f"""
            あなたは、子供の成長記録を多角的に分析する専門家です。動画から観察される様々な側面を捉えてください。

            【入力情報】
            メディアタイプ: 動画
            月齢: {child_age_months}ヶ月
            観察された事実:
            {facts_json}

            【タスク】
            動画から観察される内容を基に、以下の観点から最も重要な視点を最大4つ選択してください：

            【分析の観点】
            1. 発達・成長の視点
               - 言語発達（発話、理解）
               - 運動発達（動き、器用さ）
               - 認知・社会性の発達

            2. 感情・思い出の視点
               - 楽しい瞬間、面白いポイント
               - 家族や周りの人との関わり
               - 特別な体験や初めての経験

            3. 赤ちゃん特有の視点（該当する月齢の場合）
               - かわいい仕草や特徴
               - この時期ならではの行動
               - 親子の絆を感じる瞬間

            【出力形式】
            {{
                "perspectives": [
                    {{
                        "type": "視点名（development, emotional_moment, funny_point, baby_features等）",
                        "focus": "この視点で注目すべき具体的なポイント",
                        "reason": "なぜこの視点が重要・特別なのか",
                        "observable_signs": ["動画から観察された具体的な要素"]
                    }}
                ],
                "analysis_note": "この動画が捉えた瞬間の総合的な意味"
            }}
            """
        else:
            # 写真の場合：シーン特定と感情・思い出に限定
            prompt = f"""
            あなたは、写真から場面や感情を読み取る専門家です。この写真が捉えた瞬間の意味を分析してください。

            【入力情報】
            メディアタイプ: 写真
            月齢: {child_age_months}ヶ月
            観察された事実:
            {facts_json}

            【タスク】
            写真から読み取れるシーン、感情、思い出の観点から分析視点を最大4つまで選択してください。
            ※写真では発達評価は行わず、その瞬間の情景や感情に焦点を当ててください。

            【視点選択の指針】
            1. シーンの特定
               - どんな場所やイベントか（お祭り、公園、家など）
               - 季節や時期の推測
               - 背景から読み取れる状況

            2. 感情の瞬間
               - 表情から読み取れる感情
               - その瞬間の雰囲気
               - 楽しさや喜びの表現

            3. 思い出としての価値
               - 特別な体験や初めての経験
               - 家族や友達との関わり
               - 記念すべき瞬間

            【出力形式】
            {{
                "perspectives": [
                    {{
                        "type": "視点名（scene_context, emotional_moment, special_memory等）",
                        "focus": "この視点で注目すべき具体的なポイント",
                        "reason": "なぜこの瞬間が特別なのか",
                        "observable_signs": ["写真から読み取れる具体的な要素"]
                    }}
                ],
                "analysis_note": "この写真が捉えた瞬間の総合的な意味"
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
            f"Raw response from perspective_determiner: {
                response_text[:200]}..."
        )

        # Extract JSON from response
        import re

        json_match = re.search(r"```json\s*(.*?)\s*```",
                               response_text, re.DOTALL)
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
        あなたは、指定された視点から子供の瞬間を分析する専門家です。

        【入力情報】
        メディアタイプ: {media_type}
        分析視点: {perspective['type']}
        着目ポイント: {perspective['focus']}
        観察された事実:
        {facts_json}

        【タスク】
        上記の視点から、観察された内容を分析し、親にとって価値のある洞察を提供してください。

        【分析の指針】
        1. 客観的事実に基づいた分析を行う
        2. {"動画の場合は発達的意義や成長の様子を含める" if media_type == "video" else "写真の場合はその瞬間の情景や感情に焦点を当てる"}
        3. 親が喜ぶような温かい解釈を心がける
        4. {"将来の成長への期待を含める" if media_type == "video" else "思い出としての価値を強調する"}
        5. タグは「楽しい出来事」「成長の記録」「新しい挑戦」「感動の瞬間」など、新聞記事として引っ張りやすいフレーズにする

        【出力形式】
        {{
            "perspective_type": "{perspective['type']}",
            "title": "この瞬間を表す印象的なタイトル（15文字以内）",
            "summary": "観察された行動の具体的な描写と、この視点での意味（100文字程度）",
            "significance": "この視点から見た発達的重要性や親へのメッセージ",
            "future_outlook": "今後の成長で期待できること",
            "vector_tags": ["より情緒的で検索しやすいタグを5-8個生成。例：「初めてできた喜びの瞬間」「小さな手で大きな挑戦」「笑顔あふれる成長の一歩」「親子で分かち合う達成感」など、感情と成長が伝わる10-20文字程度のフレーズ"]
        }}

        【注意事項】
        - 医学的診断や断定的な評価は避ける
        - 温かみのある表現を使う
        - 専門用語は最小限にし、分かりやすい言葉を使う
        """

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Extract JSON from response
        import re

        json_match = re.search(r"```json\s*(.*?)\s*```",
                               response_text, re.DOTALL)
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
        - **タグは新聞記事のような視点で、「楽しい記事」「成長の記事」「挑戦の記事」として検索されやすいように作成してください。**
        - **タグは感情や成長の様子が伝わる10-20文字のフレーズにしてください。**

        以下のJSON形式で、最終的な「エピソードログ」を返してください：
        {{
            "title": "ハイライトシーンの客観的なタイトル（15文字以内）",
            "summary": "ハイライトシーンの客観的で具体的な状況説明（100文字程度）。発話があれば「」で引用する。",
            "emotion": "ハイライトシーンでの主な感情",
            "activities": ["ハイライト中の具体的な活動"],
            "development_milestones": ["このハイライトが示す発達の兆候"],
            "vector_tags": ["より情緒的で検索しやすいタグを5-8個生成。例：「初めての大冒険」「ドキドキワクワクの挑戦」「できたよ！の笑顔」「成長を感じる瞬間」など、感情と体験が伝わる10-20文字程度のフレーズ"]
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
あなたは、子供の写真を撮る親の気持ちがわかる、共感力の高いアシスタントです。
以下の分析結果を読んで、「親がなぜこの瞬間を写真に残したかったのか」その理由を推測してください。
そして、その推測した気持ちを表現する、最もふさわしいタイトルを1つ作成してください。

【分析結果の要約】
{combined_text}

【推測のヒント】
1. **子供の表情や仕草:** どんなところが可愛い？面白い？
2. **状況:** 日常と違う特別な点はどこか？（場所、イベント、服装など）
3. **成長の記録:** 「これができるようになった！」という感動はどこにあるか？

【タイトルの条件】
- 親の「撮りたかった気持ち」が伝わるようなタイトルにする。
- 具体的で、情景が目に浮かぶような表現を使う。
- 15〜20文字程度で、最後に内容に合った絵文字を1つ付ける。

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
            
            # Create abstract episode structure
            episode_entry = {
                "id": str(uuid.uuid4()),
                "type": ep_data.get("perspective_type", ep_data.get("type", "general")),
                "title": ep_data.get("title", ""),
                "summary": ep_data.get("summary", ""),
                "content": ep_data.get("content", ep_data.get("significance", "")),
                "tags": ep_data.get("vector_tags", ep_data.get("tags", [])),
                "metadata": {
                    "future_outlook": ep_data.get("future_outlook", ""),
                    "significance": ep_data.get("significance", ""),
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


def save_analysis(
    analysis_log: Dict[str, Any],
    media_id: str = "",
    media_source_uri: str = "",
    child_id: str = "",
    child_age_months: int = 0,
    user_id: str = "",
    captured_at: datetime = None,
) -> dict:
    """Backward compatibility: Save single analysis as episode"""
    return save_multi_episode_analysis(
        episodes=[analysis_log],
        media_id=media_id,
        media_source_uri=media_source_uri,
        child_id=child_id,
        child_age_months=child_age_months,
        user_id=user_id,
        captured_at=captured_at,
    )


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


def index_analysis(
    analysis_log: Dict[str, Any],
    media_id: str,
    analysis_id: str,
    child_id: str = "",
    perspective_type: str = "",
) -> dict:
    """Backward compatibility: Index single analysis as episode"""
    # Add id to the analysis if not present
    if isinstance(analysis_log, dict):
        if "report" in analysis_log:
            analysis_log["report"]["id"] = analysis_id
        else:
            analysis_log["id"] = analysis_id
    
    return index_episodes(
        episodes=[analysis_log],
        media_id=media_id,
        child_id=child_id,
    )


def save_summary(
    episode_log: Dict[str, Any],
    media_source_uri: str,
    child_id: str = "",
    user_id: str = "",
) -> dict:
    """Save the episode log to Firestore (backward compatibility)"""
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

        # Save to Firestore
        db = get_firestore_client()
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


def index_media_analysis(
    episode_log: Dict[str, Any], episode_id: str, child_id: str = ""
) -> dict:
    """Index the episode data for vector search (backward compatibility)"""
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
            f"Upserting datapoint to Vector Search Index with ID: {
                episode_id}..."
        )

        # Get captured_at timestamp as Unix timestamp (seconds since epoch)
        # Note: This function is deprecated and doesn't have access to captured_at
        # Using created_at as fallback for backward compatibility
        created_at = datetime.now(timezone.utc)
        created_at_timestamp = int(created_at.timestamp())

        # Upsert to Vector Search Index
        # Using restricts field for all filtering
        restricts = [
            {"namespace": "child_id", "allow_list": [child_id]}
        ]
        
        # Add captured_at timestamp if available
        restricts.append(
            {"namespace": "captured_at", "value_int": created_at_timestamp}
        )
        
        vector_search_index.upsert_datapoints(
            datapoints=[
                {
                    "datapoint_id": episode_id,
                    "feature_vector": vector,
                    "restricts": restricts,
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


def set_child_id(child_id: str = ""):
    """Set the child ID for the current session"""
    global CHILD_ID
    CHILD_ID = child_id if child_id else "demo"
    logger.info(f"Child ID set to: {CHILD_ID}")
    return CHILD_ID


async def analyze_perspective(
    facts: Dict[str, Any],
    perspective: Dict[str, Any],
    media_id: str,
    media_source_uri: str,
    child_id: str,
    child_age_months: int,
    user_id: str,
) -> Dict[str, Any]:
    """Analyze a single perspective asynchronously"""
    try:
        # Analyze from this perspective
        analysis_result = dynamic_multi_analyzer(facts, perspective)
        if analysis_result.get("status") != "success":
            logger.error(
                f"Failed to analyze perspective {
                    perspective['type']}: {analysis_result}"
            )
            return analysis_result

        analysis_data = analysis_result.get("report", {})

        # Save analysis
        save_result = save_analysis(
            analysis_data,
            media_id=media_id,
            media_source_uri=media_source_uri,
            child_id=child_id,
            child_age_months=child_age_months,
            user_id=user_id,
        )

        if save_result.get("status") != "success":
            logger.error(
                f"Failed to save analysis for perspective {
                    perspective['type']}: {save_result}"
            )
            return save_result

        analysis_id = save_result.get("analysis_id")

        # Index analysis
        index_result = index_analysis(
            analysis_data,
            media_id=media_id,
            analysis_id=analysis_id,
            child_id=child_id,
            perspective_type=perspective["type"],
        )

        return {
            "status": "success",
            "perspective_type": perspective["type"],
            "analysis_id": analysis_id,
            "analysis_data": analysis_data,
            "indexed": index_result.get("status") == "success",
        }

    except Exception as e:
        logger.error(
            f"Error analyzing perspective {perspective.get('type', 'unknown')}: {
                str(e)}"
        )
        return {
            "status": "error",
            "perspective_type": perspective.get("type", "unknown"),
            "error_message": str(e),
        }


def calculate_age_months(birth_date: datetime) -> int:
    """Calculate age in months from birthdate"""
    today = datetime.now(timezone.utc)
    months = (today.year - birth_date.year) * \
        12 + today.month - birth_date.month
    # Adjust if the day hasn't come yet this month
    if today.day < birth_date.day:
        months -= 1
    return max(0, months)  # Ensure non-negative


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
                f"Auto-calculated age for child {
                    child_id}: {child_age_months} months"
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


root_agent = Agent(
    name="episode_generator_agent",
    model=MODEL_NAME,
    description="メディアファイルを分析し、構造化されたエピソードログを生成するエージェント",
    instruction="""あなたは、メディアファイルを多角的に分析し、月齢に応じた視点から構造化されたエピソードログを作成するエージェントです。

## 標準的な処理フロー（単一エピソード生成）：
1. objective_analyzerでメディアファイルを分析
2. highlight_identifierでハイライトを特定してエピソードログを作成
3. save_summaryでFirestoreに保存（episode_idが返される）
4. index_media_analysisで保存したエピソードをベクトル検索用にインデックス化

## 高度な処理フロー（多角的分析）：
1. objective_analyzerでメディアファイルを分析
2. perspective_determinerで月齢に基づく分析視点を決定（複数の視点が返される）
3. 各視点に対してdynamic_multi_analyzerを個別に実行
   - perspective_determinerの結果から各perspectiveを取り出す
   - 各perspectiveに対してdynamic_multi_analyzerツールを個別に呼び出す
4. save_multi_episode_analysisで全てのエピソードを1つのドキュメントに保存
5. index_episodesで全エピソードをベクトル検索用にインデックス化

**重要な実行方法：**
- perspective_determinerで複数の視点を取得後、各視点に対して個別にdynamic_multi_analyzerを呼び出す
- 各perspectiveオブジェクトを一つずつdynamic_multi_analyzerの引数として渡す
- 全ての分析が完了したら、その結果をepisodesとしてリストにまとめる
- save_multi_episode_analysisに全分析結果のリストとmedia_source_uriを渡して保存
- 保存結果のmedia_idとepisodesを使ってindex_episodesを呼び出す

注意事項：
- child_idは環境で設定されています（デフォルト: "demo"）
- 月齢情報がある場合は多角的分析を推奨
- save_summaryの返り値にあるepisode_idを必ずindex_media_analysisに渡してください""",
    tools=[
        objective_analyzer,
        highlight_identifier,
        save_summary,
        index_media_analysis,
        perspective_determiner,
        dynamic_multi_analyzer,
        save_analysis,
        index_analysis,
        save_multi_episode_analysis,
        index_episodes,
    ],
)
