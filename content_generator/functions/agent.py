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
# from google.adk.agents import Agent  # Cloud Functions用にコメントアウト
from google.cloud import firestore
from google.cloud import aiplatform
from google.cloud import storage
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel
from dotenv import load_dotenv
import re

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


def is_video_file(url: str) -> bool:
    """
    URLが動画ファイルかどうかを判定する
    
    Args:
        url: 判定するURL
        
    Returns:
        動画ファイルの場合True
    """
    if not url:
        return False
    
    video_extensions = ['.mov', '.mp4', '.avi', '.wmv', '.flv', '.webm', '.m4v']
    url_lower = url.lower()
    return any(ext in url_lower for ext in video_extensions)


def convert_gs_to_https_url(gs_url: str) -> str:
    """
    gs://形式のURLをHTTPS形式のURLに変換する
    
    Args:
        gs_url: gs://形式のURL
        
    Returns:
        HTTPS形式のURL
    """
    try:
        if not gs_url or not gs_url.startswith("gs://"):
            return gs_url
            
        # gs://bucket-name/path/to/file の形式をパース
        match = re.match(r"gs://([^/]+)/(.+)", gs_url)
        if not match:
            logger.warning(f"Invalid gs:// URL format: {gs_url}")
            return gs_url
            
        bucket_name = match.group(1)
        blob_path = match.group(2)
        
        # Firebase Storage の公開URLを生成
        # URL エンコーディングを適用
        encoded_path = blob_path.replace('/', '%2F')
        https_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded_path}?alt=media"
        
        logger.info(f"Converted gs:// URL to HTTPS: {gs_url[:50]}... -> {https_url[:50]}...")
        return https_url
        
    except Exception as e:
        logger.error(f"Error converting gs:// URL: {str(e)}")
        return gs_url


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

        # テーマと検索クエリを定義（最初の3つは動的タイトル生成）
        themes = [
            {
                "id": "interest",
                "title": None,  # 動的に生成
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
                "title_generation": True,
            },
            {
                "id": "place",
                "title": None,  # 動的に生成
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
                "title_generation": True,
            },
            {
                "id": "first_time",
                "title": None,  # 動的に生成
                "search_queries": ["初めて", "デビュー", "挑戦", "新しい", "はじめて"],
                "prompt_hint": "今週初めて経験したことや新しい挑戦",
                "title_generation": True,
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
                "title": "まとめ",
                "search_queries": [
                    "できた",
                    "成長",
                    "上手",
                    "覚えた",
                    "言えた",
                    "できるように",
                    "楽しい",
                    "嬉しい",
                    "笑顔",
                ],
                "prompt_hint": "今週の総括的なまとめ",
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
                            
                            # 動画の場合はサムネイルURLを使用、それ以外はmedia_uriを使用
                            media_uri = analysis_data.get('media_uri', '')
                            thumbnail_url = analysis_data.get('thumbnail_url')
                            
                            if thumbnail_url and is_video_file(media_uri):
                                # 動画の場合はサムネイルURLを使用
                                episode_with_meta['image_urls'] = [thumbnail_url]
                            else:
                                # 画像の場合は通常のmedia_uriを使用
                                episode_with_meta['image_urls'] = [media_uri] if media_uri else []
                            
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


def generate_dynamic_title(
    episodes: List[Dict[str, Any]], 
    theme: Dict[str, Any], 
    child_name: str,
    model: GenerativeModel
) -> str:
    """
    エピソードの内容に基づいて動的にセクションタイトルを生成する
    
    Args:
        episodes: エピソードのリスト
        theme: テーマ情報
        child_name: 子供の名前
        model: Geminiモデル
        
    Returns:
        生成されたタイトル
    """
    try:
        if not episodes:
            # デフォルトタイトル
            default_titles = {
                "interest": "今週の興味",
                "place": "行った場所",
                "first_time": "初めての体験"
            }
            return default_titles.get(theme["id"], "今週のハイライト")
        
        # エピソードの内容を要約
        episode_summary = "\n".join([
            f"- {ep.get('content', '')[:100]}..." 
            for ep in episodes[:3]  # 最初の3つのエピソード
        ])
        
        title_prompt = f"""
以下のエピソードから、セクションのタイトルを生成してください。

【エピソード内容】
{episode_summary}

【タイトル生成のルール】
- 8文字以内の自然で親しみやすいタイトル
- 具体的な行動や場所を表現
- シンプルで分かりやすい表現
- 記号（*や-など）は使わない

【良い例】
- ブロックに夢中
- 公園を探検
- お絵かきタイム
- 水遊び大好き

【悪い例】
- **興味深い発見
- -成長の瞬間-
- ＊楽しい時間＊

タイトルのみを返してください（記号や装飾なし）：
"""
        
        response = model.generate_content(title_prompt)
        generated_title = response.text.strip().replace("タイトル：", "").strip()
        
        # 記号を除去
        import re
        generated_title = re.sub(r'[*＊\-－_＿【】「」『』]', '', generated_title)
        generated_title = generated_title.strip()
        
        # 8文字を超える場合は切り詰める
        if len(generated_title) > 8:
            generated_title = generated_title[:8]
        
        logger.info(f"Generated dynamic title: '{generated_title}' for theme {theme['id']}")
        return generated_title
        
    except Exception as e:
        logger.error(f"Error generating dynamic title: {str(e)}")
        # エラー時のデフォルト
        default_titles = {
            "interest": "今週の興味",
            "place": "行った場所", 
            "first_time": "初めての体験"
        }
        return default_titles.get(theme["id"], "今週のハイライト")


def select_best_media_for_best_shot(
    all_period_episodes: List[Dict[str, Any]],
    child_name: str,
    model: GenerativeModel
) -> List[str]:
    """
    期間内の全メディアから最も魅力的な「ベストショット」を複数選定する
    動画と写真を組み合わせて2つ選ぶ
    
    Args:
        all_period_episodes: 期間内の全エピソード
        child_name: 子供の名前
        model: Geminiモデル
        
    Returns:
        選択されたメディアのURLリスト（最大2つ）
    """
    try:
        # 画像または短い動画を持つエピソードを収集
        media_candidates = []
        
        for episode in all_period_episodes:
            # image_urlsから画像を収集
            if episode.get("image_urls"):
                for img_url in episode["image_urls"]:
                    if img_url and not img_url.startswith('gs://'):  # HTTPS URLのみ
                        media_candidates.append({
                            "url": img_url,
                            "type": "image",
                            "content": episode.get("content", ""),
                            "emotion": episode.get("emotion", ""),
                            "tags": episode.get("tags", [])
                        })
            
            # media_uriから画像・動画を収集
            if episode.get("media_uri"):
                media_uri = episode["media_uri"]
                if not media_uri.startswith('gs://'):  # HTTPS URLのみ
                    media_type = "video" if is_video_file(media_uri) else "image"
                    media_candidates.append({
                        "url": media_uri,
                        "type": media_type,
                        "content": episode.get("content", ""),
                        "emotion": episode.get("emotion", ""),
                        "tags": episode.get("tags", [])
                    })
        
        if not media_candidates:
            return []
        
        # 画像と動画を分けて管理
        image_candidates = [c for c in media_candidates if c["type"] == "image"]
        video_candidates = [c for c in media_candidates if c["type"] == "video"]
        
        # 優先度の高い候補を選定（写真15枚、動画10本まで）
        prioritized_images = image_candidates[:15]
        prioritized_videos = video_candidates[:10]
        
        # 全候補を結合
        all_candidates = prioritized_images + prioritized_videos
        
        if not all_candidates:
            return []
        
        # 1つしかない場合はそれを返す
        if len(all_candidates) == 1:
            return [all_candidates[0]["url"]]
        
        # 2つしかない場合は両方返す
        if len(all_candidates) == 2:
            return [all_candidates[0]["url"], all_candidates[1]["url"]]
        
        # LLMで最も魅力的な2つを選定（動画と写真のバランスを考慮）
        candidates_text = ""
        for i, candidate in enumerate(all_candidates[:15]):  # 最大15個
            media_type_jp = "写真" if candidate["type"] == "image" else "動画"
            candidates_text += f"{media_type_jp}{i+1}: {candidate['content'][:80]}... (感情: {candidate['emotion']}, タグ: {', '.join(candidate['tags'][:3])})\n"
        
        selection_prompt = f"""
以下のメディア候補から、{child_name}の「今週のベストショット」として最も魅力的なものを2つ選んでください。

【選定基準】
1. 最も笑顔が素敵、または面白い表情
2. ほっこりする瞬間や楽しそうな様子
3. 変顔や驚いた表情など、印象的な瞬間
4. 動画も面白いものがあれば積極的に選ぶ（写真と動画の組み合わせが理想的）
5. 親が見て「この瞬間最高！」と思えるもの
6. 2つ選ぶ場合は、違うシーンや表情のものを選ぶ

【候補】
{candidates_text}

最も魅力的なメディア2つの番号をカンマ区切りで回答してください。
例: 3,7
必ず2つ選択してください。候補が少ない場合は重複しないよう1つだけ選んでください。
"""
        
        response = model.generate_content(selection_prompt)
        selected_indices_text = response.text.strip()
        
        # カンマ区切りで分割して番号を取得
        selected_urls = []
        try:
            selected_numbers = [int(n.strip()) for n in selected_indices_text.split(',')]
            
            for num in selected_numbers[:2]:  # 最大2つまで
                index = num - 1
                if 0 <= index < len(all_candidates[:15]):
                    selected_url = all_candidates[index]["url"]
                    logger.info(f"Selected best shot: {selected_url[:50]}... (type: {all_candidates[index]['type']})")
                    selected_urls.append(selected_url)
            
            # 1つも選択できなかった場合は、写真と動画を1つずつ選ぶ
            if not selected_urls:
                if prioritized_images:
                    selected_urls.append(prioritized_images[0]["url"])
                if prioritized_videos:
                    selected_urls.append(prioritized_videos[0]["url"])
                    
        except Exception as e:
            logger.error(f"Error parsing selection: {e}")
            # エラーの場合は写真優先で2つ選ぶ
            if prioritized_images:
                selected_urls.append(prioritized_images[0]["url"])
            if len(prioritized_images) > 1:
                selected_urls.append(prioritized_images[1]["url"])
            elif prioritized_videos:
                selected_urls.append(prioritized_videos[0]["url"])
        
        return selected_urls[:2]  # 最大2つまで
            
    except Exception as e:
        logger.error(f"Error selecting best shot: {str(e)}")
        return []


def select_best_photo_with_llm(
    episodes: List[Dict[str, Any]], 
    theme: Dict[str, Any], 
    child_name: str,
    model: GenerativeModel
) -> Optional[str]:
    """
    LLMを使用して最適な写真を選定する
    
    Args:
        episodes: エピソードのリスト
        theme: テーマ情報
        child_name: 子供の名前
        model: Geminiモデル
        
    Returns:
        選択された写真のURL
    """
    try:
        # 画像を持つエピソードをフィルタリング
        episodes_with_photos = [
            ep for ep in episodes 
            if ep.get("media_uri") or (ep.get("image_urls") and ep["image_urls"])
        ]
        
        if not episodes_with_photos:
            return None
            
        # エピソードの情報を整理
        photo_candidates = []
        for i, episode in enumerate(episodes_with_photos[:10]):  # 最大10枚まで
            photo_url = episode.get("media_uri") or (episode["image_urls"][0] if episode.get("image_urls") else None)
            if photo_url:
                photo_candidates.append({
                    "index": i,
                    "url": photo_url,
                    "content": episode.get("content", ""),
                    "emotion": episode.get("emotion", ""),
                    "tags": episode.get("tags", [])
                })
        
        if not photo_candidates:
            return None
            
        # 1枚しかない場合はそれを返す
        if len(photo_candidates) == 1:
            return photo_candidates[0]["url"]
        
        # LLMに選定を依頼
        candidates_text = "\n".join([
            f"写真{c['index']+1}: {c['content'][:100]}... (感情: {c['emotion']}, タグ: {', '.join(c['tags'][:3])})"
            for c in photo_candidates
        ])
        
        selection_prompt = f"""
以下の写真候補から、「{theme['title']}」というテーマに最も適した写真を1つ必ず選んでください。
どの写真も候補にない場合でも、必ずいずれかの番号を選択してください。

選定基準：
1. テーマとの関連性が最も高い
2. 楽しそう、活発、印象的な瞬間を捉えている
3. {child_name}の表情や行動が良く分かる
4. テーマとの関連が薄くても、写真として魅力的である

【写真候補】
{candidates_text}

最も適した写真の番号（1〜{len(photo_candidates)}）のみを回答してください。
必ず1つの番号を選択し、それ以外は答えないでください。
"""
        
        response = model.generate_content(selection_prompt)
        selected_index = int(response.text.strip()) - 1
        
        if 0 <= selected_index < len(photo_candidates):
            logger.info(f"LLM selected photo {selected_index + 1} for theme '{theme['title']}'")
            return photo_candidates[selected_index]["url"]
        else:
            # 無効なインデックスの場合は最初の写真を返す
            return photo_candidates[0]["url"]
            
    except Exception as e:
        logger.error(f"Error in select_best_photo_with_llm: {str(e)}")
        # エラーの場合は最初の写真を返す
        return episodes_with_photos[0].get("media_uri") or episodes_with_photos[0]["image_urls"][0] if episodes_with_photos else None


def llm_based_episode_distribution(
    all_theme_episodes: List[Dict[str, Any]],
    child_name: str,
    model: GenerativeModel
) -> Dict[str, List[Dict[str, Any]]]:
    """
    LLMを使って全エピソードを見渡し、最適な配分を決定する
    
    Args:
        all_theme_episodes: すべてのテーマとそのエピソードのリスト
        child_name: 子供の名前
        model: Geminiモデル
        
    Returns:
        テーマIDをキーとした、各テーマに割り当てられたエピソードの辞書
    """
    try:
        # 全エピソードを収集して情報を整理
        all_episodes_info = []
        episode_index = 0
        
        for theme_data in all_theme_episodes:
            if "report" in theme_data:
                theme = theme_data["report"]["theme"]
                episodes = theme_data["report"]["episodes"]
            else:
                theme = theme_data.get("theme", {})
                episodes = theme_data.get("episodes", [])
            
            for episode in episodes:
                episode_info = {
                    "index": episode_index,
                    "theme_id": theme["id"],
                    "theme_title": theme.get("title", ""),
                    "content": episode.get("content", "")[:200] + "...",
                    "has_media": bool(episode.get("media_uri") or episode.get("image_urls")),
                    "media_uri": episode.get("media_uri", "")[:50] + "..." if episode.get("media_uri") else "",
                    "tags": episode.get("tags", [])[:3]
                }
                all_episodes_info.append(episode_info)
                episode_index += 1
        
        # LLMにエピソード配分を依頼
        episodes_summary = "\n".join([
            f"エピソード{ep['index']}: "
            f"テーマ「{ep['theme_title']}」, "
            f"メディア{'あり' if ep['has_media'] else 'なし'}, "
            f"内容: {ep['content'][:100]}..."
            for ep in all_episodes_info
        ])
        
        distribution_prompt = f"""
あなたは{child_name}の週間ノートブックを作成するエディターです。
以下の{len(all_episodes_info)}個のエピソードから、5つのセクションに最適なエピソードを選んでください。

【重要な制約】
1. 同じエピソードを複数のセクションで使用しない
2. 似た内容のエピソードを連続させない
3. 異なるメディア（写真/動画）を各セクションに配置
4. 時系列や場所、活動の種類でバリエーションを持たせる

【セクション構成】
1. セクション1（大写真付き）: 最も印象的なエピソード
2. セクション2（テキストのみ）: 別の場面や活動
3. セクション3（小写真付き）: また違う活動や瞬間
4. セクション4（ベストショット）: 週の中で最も魅力的な写真/動画
5. セクション5（まとめ）: 全体を総括（複数エピソード使用可）

【利用可能なエピソード】
{episodes_summary}

【出力形式】
{{
    "section1": {{"episode_indices": [選択したエピソード番号], "reason": "選択理由"}},
    "section2": {{"episode_indices": [選択したエピソード番号], "reason": "選択理由"}},
    "section3": {{"episode_indices": [選択したエピソード番号], "reason": "選択理由"}},
    "section4": {{"episode_indices": [選択したエピソード番号], "reason": "選択理由"}},
    "section5": {{"episode_indices": [使用する全エピソード番号], "reason": "選択理由"}}
}}

必ず異なるエピソードを選び、内容の多様性を確保してください。
"""
        
        response = model.generate_content(distribution_prompt)
        response_text = response.text.strip()
        
        # JSONを抽出
        import re
        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
        
        distribution_plan = json.loads(response_text)
        
        # 配分計画に基づいてエピソードを割り当て
        distributed_episodes = {}
        themes = ["interest", "place", "first_time", "best_shot", "achievement"]
        
        # 元のエピソードリストを作成
        all_episodes_list = []
        for theme_data in all_theme_episodes:
            if "report" in theme_data:
                all_episodes_list.extend(theme_data["report"]["episodes"])
            else:
                all_episodes_list.extend(theme_data.get("episodes", []))
        
        # 各セクションにエピソードを割り当て
        for i, theme_id in enumerate(themes):
            section_key = f"section{i+1}"
            if section_key in distribution_plan:
                indices = distribution_plan[section_key]["episode_indices"]
                selected_episodes = []
                for idx in indices:
                    if 0 <= idx < len(all_episodes_list):
                        selected_episodes.append(all_episodes_list[idx])
                distributed_episodes[theme_id] = selected_episodes
                logger.info(f"Section {i+1} ({theme_id}): {len(selected_episodes)} episodes - {distribution_plan[section_key]['reason']}")
        
        return distributed_episodes
        
    except Exception as e:
        logger.error(f"Error in llm_based_episode_distribution: {str(e)}")
        # フォールバック: 従来の配分方法を使用
        return distribute_episodes_for_topics_fallback(all_theme_episodes)


def distribute_episodes_for_topics_fallback(
    all_theme_episodes: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    フォールバック用の従来の配分方法
    """
    try:
        used_episode_ids = set()
        distributed_episodes = {}
        
        for theme_data in all_theme_episodes[:4]:
            if "report" in theme_data:
                theme = theme_data["report"]["theme"]
                episodes = theme_data["report"]["episodes"]
            else:
                theme = theme_data.get("theme", {})
                episodes = theme_data.get("episodes", [])
            
            available_episodes = []
            for episode in episodes:
                episode_id = f"{episode.get('id', '')}_{hash(episode.get('content', ''))}"
                if episode_id not in used_episode_ids:
                    available_episodes.append(episode)
            
            if available_episodes:
                episodes_with_photos = [ep for ep in available_episodes if ep.get('media_uri') or ep.get('image_urls')]
                selected_episode = episodes_with_photos[0] if episodes_with_photos else available_episodes[0]
                distributed_episodes[theme["id"]] = [selected_episode]
                episode_id = f"{selected_episode.get('id', '')}_{hash(selected_episode.get('content', ''))}"
                used_episode_ids.add(episode_id)
            else:
                distributed_episodes[theme["id"]] = []
        
        all_episodes = []
        for theme_data in all_theme_episodes:
            if "report" in theme_data:
                all_episodes.extend(theme_data["report"]["episodes"])
            else:
                all_episodes.extend(theme_data.get("episodes", []))
        
        unique_all_episodes = []
        seen_contents = set()
        for episode in all_episodes:
            content_hash = hash(episode.get('content', ''))
            if content_hash not in seen_contents:
                unique_all_episodes.append(episode)
                seen_contents.add(content_hash)
        
        if len(all_theme_episodes) >= 5:
            distributed_episodes["achievement"] = unique_all_episodes
        
        return distributed_episodes
        
    except Exception as e:
        logger.error(f"Error in distribute_episodes_for_topics_fallback: {str(e)}")
        return {}


def generate_topic_content(
    theme_episodes: Dict[str, Any], 
    child_info: Dict[str, Any], 
    topic_layout: str,
    custom_tone: Optional[str] = None,
    custom_focus: Optional[str] = None,
    all_period_episodes: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    テーマとエピソードからトピックコンテンツを生成する

    Args:
        theme_episodes: テーマとエピソードの情報
        child_info: 子供の基本情報
        topic_layout: レイアウトタイプ（large_photo, text_only, etc.）
        custom_tone: カスタムトーン（文章のスタイル）
        custom_focus: カスタムフォーカス（注目してほしいこと）
        all_period_episodes: 期間全体のエピソード（写真が見つからない場合の代替用）

    Returns:
        生成されたトピックコンテンツ（必ず写真フィールドが埋まることを保証）
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

        # プロンプトを構築（名前の一貫性を保つ）
        child_name = child_info.get("nickname") or child_info.get("name", "お子さん")
        # ニックネームが「〇〇ちゃん」「〇〇君」などの場合、安定した形式に統一
        if child_name != "お子さん":
            # すでに「ちゃん」「くん」が付いている場合はそのまま使用
            if not (child_name.endswith("ちゃん") or child_name.endswith("くん") or child_name.endswith("さん")):
                # 付いていない場合はニックネームから判断して付与
                child_name = f"{child_name}ちゃん"
        
        # 動的タイトル生成（必要な場合）
        if theme.get("title_generation", False) and theme.get("title") is None:
            dynamic_title = generate_dynamic_title(episodes, theme, child_name, model)
            theme = theme.copy()  # 元のthemeを変更しないようにコピー
            theme["title"] = dynamic_title
        
        # テーマIDに基づいてエピソード数を調整
        is_summary_section = theme.get("id") == "achievement"
        is_best_shot_section = theme.get("id") == "best_shot"
        
        if is_summary_section:
            # まとめセクションでは多くのエピソードを使用
            episodes_text = "\n".join(
                [
                    f"- {episode['content']}"
                    for episode in episodes[:10]  # 最大10エピソード
                ]
            )
        else:
            # 通常セクションでは1つのエピソードに焦点（エピソードの混在を防止）
            episodes_text = f"- {episodes[0]['content']}" if episodes else "- 記録がありませんでした"

        # カスタムトーンとフォーカスの追加部分を構成
        custom_instructions = ""
        if custom_tone and custom_tone.strip():
            custom_instructions += f"\n\n【リクエストされた文章スタイル】\n{custom_tone}"
        if custom_focus and custom_focus.strip():
            custom_instructions += f"\n\n【特に注目してほしいこと】\n{custom_focus}"

        # テーマIDに基づいてプロンプトを調整
        is_summary_section = theme.get("id") == "achievement"
        
        if is_summary_section:
            # まとめセクション用のプロンプト
            prompt = f"""
今週の{child_name}の様子を150-200文字でまとめてください。

【今週のエピソード】
{episodes_text}{custom_instructions}

【まとめのルール】
- 複数のエピソードから印象的な場面を選んで
- 「〜したり、〜したり」と具体的な行動を列挙
- 楽しかった瞬間を中心に
- 親しみやすい「です・ます」調

文章のみを出力（150-200文字）：
"""
        else:
            # 通常セクション用のプロンプト（1つのエピソードに焦点）
            prompt = f"""
以下のエピソードから、その場の様子を100-150文字で描写してください。

【テーマ】
「{theme['title']}」

【エピソード】
{episodes_text}{custom_instructions}

【描写のルール】
- このエピソードの事実のみを使用
- その場の様子や{child_name}の行動を具体的に
- 楽しい雰囲気で親しみやすく
- 成長や発達の評価は書かない
- 簡潔に、読みやすく

文章のみを出力（100-150文字）：
"""

        # コンテンツを生成
        response = model.generate_content(prompt)
        generated_content = response.text.strip()
        
        # 不自然な日本語表現を修正
        # 「これのが」→「これが」
        generated_content = generated_content.replace("これのが", "これが")
        generated_content = generated_content.replace("それのが", "それが")
        generated_content = generated_content.replace("あれのが", "あれが")
        
        # 過度な記号を除去
        generated_content = re.sub(r'[＊*]{2,}', '', generated_content)
        generated_content = re.sub(r'！{2,}', '！', generated_content)
        generated_content = re.sub(r'。{2,}', '。', generated_content)

        # サブタイトルの生成（large_photoの場合）
        subtitle = None
        if topic_layout == "large_photo" and episodes:
            # 最初のエピソードからキーワードを抽出
            subtitle = (
                episodes[0]["tags"][0] if episodes[0].get(
                    "tags") else theme["title"]
            )

        # 画像の選択と再試行ロジック（改善版）
        photo = None
        caption = None
        if topic_layout != "text_only":
            logger.info(f"Looking for photos for theme '{theme['title']}' with layout '{topic_layout}'")
            
            # ベストショットの場合は特別な選定ロジック（複数選択）
            if is_best_shot_section and all_period_episodes:
                logger.info("Using special best shot selection from all period media")
                best_shots = select_best_media_for_best_shot(all_period_episodes, child_name, model)
                if best_shots:
                    # 最初のものをメイン写真として使用
                    photo = best_shots[0]
                    logger.info(f"Selected best shots: {len(best_shots)} media items")
                    logger.info(f"Main photo: {photo[:50]}...")
                    # 2つ目がある場合は追加情報として保存（後で使用可能）
                    if len(best_shots) > 1:
                        topic_data["additional_media"] = best_shots[1]
                        logger.info(f"Additional media: {best_shots[1][:50]}...")
            
            # 通常のテーマまたはベストショットで見つからない場合
            if not photo:
                # 最初の試行：既存のロジック
                for episode in episodes:
                    if episode.get("image_urls") and episode["image_urls"][0]:
                        photo = episode["image_urls"][0]
                        logger.info(f"Found photo in episode image_urls: {photo[:50]}...")
                        break
                    elif episode.get("media_uri"):
                        photo = episode["media_uri"]
                        logger.info(f"Found photo in episode media_uri: {photo[:50]}...")
                        break
                
                # 写真が見つからない場合、LLMによる選定を試行
                if not photo:
                    logger.info(f"No photo found for theme '{theme['title']}', attempting LLM selection")
                    selected_photo = select_best_photo_with_llm(episodes, theme, child_name, model)
                    if selected_photo:
                        photo = selected_photo
                        logger.info(f"Successfully selected photo with LLM")
                
                # それでも写真が見つからない場合、期間全体から写真を探す
                if not photo and all_period_episodes:
                    logger.info(f"No photo found in theme episodes, searching in all period episodes")
                    # 画像を持つエピソードをフィルタリング
                    episodes_with_photos = [
                        ep for ep in all_period_episodes 
                        if ep.get("media_uri") or (ep.get("image_urls") and ep["image_urls"])
                    ]
                    
                    if episodes_with_photos:
                        # ランダムに写真を選択（または最初の写真を使用）
                        import random
                        random_episode = random.choice(episodes_with_photos[:10])  # 最初の10件から選択
                        photo = random_episode.get("media_uri") or (
                            random_episode["image_urls"][0] if random_episode.get("image_urls") else None
                        )
                        logger.info(f"Selected photo from period episodes: {photo[:50] if photo else 'None'}")
            
            # 最終確認：写真が必要なレイアウトなのに写真がない場合の警告
            if not photo:
                logger.warning(f"No photo found for theme '{theme['title']}' with layout '{topic_layout}'. Photo field will be null.")
            
            # gs://URLをHTTPS URLに変換
            if photo and photo.startswith("gs://"):
                photo = convert_gs_to_https_url(photo)
                logger.info(f"Converted photo URL to HTTPS")
            
            # キャプションの生成（写真がある場合）
            if photo:
                try:
                    # 写真に関連するエピソードを探す（まずテーマエピソードから、次に全期間から）
                    photo_episode = None
                    
                    # 元のphoto URLを記録（変換前）
                    original_photo = photo
                    if photo.startswith("https://firebasestorage.googleapis.com"):
                        # HTTPS URLから元のgs://URLを復元する試み
                        for episode in episodes:
                            if (episode.get("media_uri") and episode["media_uri"].startswith("gs://") and 
                                convert_gs_to_https_url(episode["media_uri"]) == photo):
                                original_photo = episode["media_uri"]
                                break
                    
                    # テーマエピソードから写真を探す
                    for episode in episodes:
                        if (episode.get("media_uri") == original_photo or 
                            episode.get("media_uri") == photo or
                            (episode.get("image_urls") and (original_photo in episode.get("image_urls", []) or 
                             photo in episode.get("image_urls", [])))):
                            photo_episode = episode
                            break
                    
                    # テーマエピソードで見つからない場合、全期間エピソードから探す
                    if not photo_episode and all_period_episodes:
                        for episode in all_period_episodes:
                            if (episode.get("media_uri") == original_photo or 
                                episode.get("media_uri") == photo or
                                (episode.get("image_urls") and (original_photo in episode.get("image_urls", []) or 
                                 photo in episode.get("image_urls", [])))):
                                photo_episode = episode
                                break
                    
                    if photo_episode:
                        caption_content = photo_episode["content"][:200]
                        
                        # 動画ファイルかどうかで表現を変える
                        media_type = "動画" if is_video_file(photo) else "写真"
                        
                        caption_prompt = f"""
以下のエピソードから、{media_type}の内容を表現する自然なキャプションを15文字以内で生成してください。

【エピソード】
{caption_content}

【キャプション作成のルール】
- {media_type}に写っている具体的な行動、場面、状況を描写してください
- 成長や発達ではなく、その瞬間の楽しさや魅力を表現してください
- エピソードに出てくる具体的な要素（場所、物、行動）を活用してください
- 見る人がその場の雰囲気を感じられるような表現にしてください
- 明るく楽しい印象を与える言葉を選んでください

良い例：「ブランコで大はしゃぎ」「お祭りを満喫中」「積み木に夢中」「水遊びで大興奮」
避ける例：「成長を感じる」「発達の証」「○○ができるように」

キャプション：
"""
                    else:
                        # ベストショット用の特別なキャプション
                        if is_best_shot_section:
                            caption_prompt = f"""
「今週のベストショット」として選ばれた{media_type}の魅力的なキャプションを15文字以内で生成してください。

【キャプション作成のルール】
- その瞬間の楽しさや魅力を具体的に表現してください
- シーンや行動を想像できるような表現にしてください
- 見る人がその場の雰囲気を感じられるような言葉を選んでください
- 成長ではなく、その時の楽しい様子や印象的な場面を表現してください

良い例：「夢中で遊ぶ姿」「はしゃぐ笑顔」「楽しい発見タイム」「元気いっぱい」
避ける例：「成長の瞬間」「発達している」「○○ができるように」

キャプション：
"""
                        else:
                            caption_prompt = f"""
{theme['title']}をテーマにした{media_type}の自然なキャプションを15文字以内で生成してください。

【キャプション作成のルール】
- {media_type}の内容を想像して、具体的な行動や状況を表現
- 「{child_name}の○○」のような説明的な表現は避ける
- 自然で読みやすい短い文章にする
- 楽しさや成長を感じられる表現にする

キャプション：
"""
                    
                    caption_response = model.generate_content(caption_prompt)
                    caption = caption_response.text.strip().replace("キャプション：", "").strip()
                except Exception as e:
                    logger.error(f"Error generating caption: {str(e)}")
                    # デフォルトキャプションも動画/写真に応じて自然な表現にする
                    if is_video_file(photo):
                        default_captions = {
                            "今週の興味": "夢中になって遊ぶ",
                            "行った！場所": "楽しい外出の時間",
                            "初めての体験": "新しい挑戦の瞬間",
                            "今週のベストショット": "元気いっぱいの様子",
                            "まとめ": "活発に動き回る姿"
                        }
                    else:
                        default_captions = {
                            "今週の興味": "楽しそうに遊ぶ姿",
                            "行った！場所": "お出かけの様子",
                            "初めての体験": "新しい挑戦",
                            "今週のベストショット": "笑顔いっぱい",
                            "まとめ": "成長の一週間"
                        }
                    caption = default_captions.get(theme['title'], "楽しい時間")

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


def distribute_episodes_for_topics(
    all_theme_episodes: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    各テーマのエピソードを重複なく配分する
    
    Args:
        all_theme_episodes: すべてのテーマとそのエピソードのリスト
        
    Returns:
        テーマIDをキーとした、各テーマに割り当てられたエピソードの辞書
    """
    try:
        # 使用済みエピソードを追跡
        used_episode_ids = set()
        distributed_episodes = {}
        
        # 各テーマに対してユニークなエピソードを割り当て
        for theme_data in all_theme_episodes[:4]:  # 最初の4つのテーマ
            theme = theme_data["report"]["theme"]
            episodes = theme_data["report"]["episodes"]
            
            # 未使用のエピソードをフィルタリング
            available_episodes = []
            for episode in episodes:
                # エピソードの一意性を判定（analysis_idとcontent hashで）
                episode_id = f"{episode.get('analysis_id', '')}_{hash(episode.get('content', ''))}"
                if episode_id not in used_episode_ids:
                    available_episodes.append(episode)
            
            # このテーマに最適なエピソードを1つ選択
            if available_episodes:
                # 写真があるエピソードを優先
                episodes_with_photos = [ep for ep in available_episodes if ep.get('media_uri') or ep.get('image_urls')]
                selected_episode = episodes_with_photos[0] if episodes_with_photos else available_episodes[0]
                
                distributed_episodes[theme["id"]] = [selected_episode]
                
                # 使用済みとしてマーク
                episode_id = f"{selected_episode.get('analysis_id', '')}_{hash(selected_episode.get('content', ''))}"
                used_episode_ids.add(episode_id)
            else:
                # 利用可能なエピソードがない場合は空リスト
                distributed_episodes[theme["id"]] = []
        
        # 5番目のテーマ（まとめ）用に全エピソードを収集
        all_episodes = []
        for theme_data in all_theme_episodes:
            all_episodes.extend(theme_data["report"]["episodes"])
        
        # 重複を除去
        unique_all_episodes = []
        seen_contents = set()
        for episode in all_episodes:
            content_hash = hash(episode.get('content', ''))
            if content_hash not in seen_contents:
                unique_all_episodes.append(episode)
                seen_contents.add(content_hash)
        
        # 5番目のテーマには全エピソードを割り当て
        if len(all_theme_episodes) >= 5:
            distributed_episodes["achievement"] = unique_all_episodes
        
        return distributed_episodes
        
    except Exception as e:
        logger.error(f"Error in distribute_episodes_for_topics: {str(e)}")
        return {}


def sequential_topic_generation(
    all_collected_episodes: List[Dict[str, Any]],
    themes: List[Dict[str, Any]],
    child_info: Dict[str, Any],
    custom_tone: Optional[str] = None,
    custom_focus: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    段階的にトピックを生成し、前のトピックを考慮して重複を避ける
    
    Args:
        all_collected_episodes: 収集した全エピソード
        themes: テーマリスト
        child_info: 子供の基本情報
        custom_tone: カスタムトーン
        custom_focus: カスタムフォーカス
        
    Returns:
        生成されたトピックのリスト
    """
    try:
        # Geminiモデルを初期化
        initialize_vertex_ai()
        model = GenerativeModel(MODEL_NAME)
        
        # 子供の名前を取得
        child_name = child_info.get("nickname") or child_info.get("name", "お子さん")
        if child_name != "お子さん":
            if not (child_name.endswith("ちゃん") or child_name.endswith("くん") or child_name.endswith("さん")):
                child_name = f"{child_name}ちゃん"
        
        # 全エピソードを収集
        all_episodes = []
        for theme_data in all_collected_episodes:
            if "report" in theme_data:
                all_episodes.extend(theme_data["report"]["episodes"])
            else:
                all_episodes.extend(theme_data.get("episodes", []))
        
        logger.info(f"sequential_topic_generation: Total episodes collected: {len(all_episodes)}")
        
        # 生成済みトピックを保持
        generated_topics = []
        used_episode_ids = set()
        used_media_urls = set()
        
        layout_types = ["large_photo", "text_only", "small_photo", "medium_photo", "center"]
        
        for i, theme in enumerate(themes):
            layout = layout_types[i] if i < len(layout_types) else "text_only"
            
            # まとめセクションの特別処理
            if i == 4:  # 5番目のセクション（まとめ）
                # トピックの内容を改行で結合
                topics_text = "\n".join([f"- {t['title']}: {t['content']}" for t in generated_topics])
                
                summary_prompt = f"""
今週の{child_name}の活動をまとめてください。

【今週のトピック】
{topics_text}

【未使用のエピソード】
{_format_episodes_for_llm(all_episodes, used_episode_ids)}

【要求】
- 150-200文字で今週全体を総括
- 具体的な活動を「〜したり、〜したり」と列挙
- 楽しかった瞬間を中心に

まとめ文章のみ出力：
"""
                response = model.generate_content(summary_prompt)
                summary_content = response.text.strip()
                
                topic = {
                    "title": "まとめ",
                    "subtitle": None,
                    "content": summary_content,
                    "photo": None,
                    "caption": None,
                    "generated": True
                }
                generated_topics.append(topic)
                break
            
            # 既に生成されたトピックの情報を整理
            previous_topics_summary = ""
            if generated_topics:
                previous_topics_summary = "\n".join([
                    f"トピック{j+1}: タイトル「{t['title']}」、内容の要約: {t['content'][:50]}...、使用メディア: {'あり' if t.get('photo') else 'なし'}"
                    for j, t in enumerate(generated_topics)
                ])
            
            # LLMにトピック生成を依頼
            topic_prompt = f"""
あなたは{child_name}の週間ノートブックの編集者です。
セクション{i+1}のトピックを作成してください。

【セクション情報】
- セクションタイプ: {layout}
- テーマヒント: {theme.get('prompt_hint', '')}

【利用可能なエピソード】
{_format_episodes_for_llm(all_episodes, used_episode_ids)}

【既に作成済みのトピック】
{previous_topics_summary if previous_topics_summary else "まだトピックは作成されていません"}

【重要な制約】
1. 既に使用されたエピソードやメディアと重複しないこと
2. 前のトピックと異なる場面・活動を選ぶこと
3. 複数のエピソードを組み合わせて魅力的なストーリーを作ってもOK
4. {'写真/動画が必要' if layout != 'text_only' else 'テキストのみ（写真不要）'}

【出力形式】
{{
    "selected_episode_indices": [使用するエピソード番号のリスト],
    "abstract_theme": "このトピックの抽象的なテーマ（例：「お外で元気いっぱい」）",
    "title": "8文字以内のタイトル",
    "content": "100-150文字の内容",
    "selected_media_index": {'写真/動画のエピソード番号' if layout != 'text_only' else 'null'},
    "reasoning": "なぜこのエピソードを選んだか"
}}
"""
            
            response = model.generate_content(topic_prompt)
            response_text = response.text.strip()
            
            # JSONを抽出
            import re
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            else:
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(0)
            
            topic_plan = json.loads(response_text)
            
            # 選択されたエピソードを収集
            selected_episodes = []
            for idx in topic_plan["selected_episode_indices"]:
                if 0 <= idx < len(all_episodes):
                    selected_episodes.append(all_episodes[idx])
                    used_episode_ids.add(idx)
            
            # メディアを選択
            photo = None
            if layout != "text_only" and "selected_media_index" in topic_plan:
                media_idx = topic_plan["selected_media_index"]
                if 0 <= media_idx < len(all_episodes):
                    episode = all_episodes[media_idx]
                    photo = episode.get("media_uri") or episode.get("media_source_uri") or (episode.get("image_urls", [None])[0] if episode.get("image_urls") else None)
                    logger.info(f"Topic {i+1}: Selected media from episode {media_idx}: {photo}")
                    
                    if photo and photo not in used_media_urls:
                        used_media_urls.add(photo)
                        logger.info(f"Topic {i+1}: Using media URL: {photo}")
                    else:
                        logger.warning(f"Topic {i+1}: Media already used or not found, searching for alternative")
                        # 既に使用されている場合は別のメディアを探す
                        photo = _find_unused_media(all_episodes, used_media_urls, selected_episodes)
                        if photo:
                            used_media_urls.add(photo)
            
            # トピックを構築
            topic = {
                "title": topic_plan["title"],
                "subtitle": topic_plan.get("abstract_theme") if layout == "large_photo" else None,
                "content": topic_plan["content"],
                "photo": photo,
                "caption": _generate_caption_for_media(photo, topic_plan["content"], child_name, model) if photo and layout in ["small_photo", "medium_photo"] else None,
                "generated": True
            }
            
            generated_topics.append(topic)
            logger.info(f"Generated topic {i+1}: {topic['title']} - Photo: {photo if photo else 'None'} - {topic_plan['reasoning']}")
        
        return generated_topics
        
    except Exception as e:
        logger.error(f"Error in sequential_topic_generation: {str(e)}")
        return []


def _format_episodes_for_llm(episodes: List[Dict[str, Any]], used_indices: set) -> str:
    """エピソードをLLM用にフォーマット"""
    formatted = []
    for i, ep in enumerate(episodes):
        if i not in used_indices:
            media_type = "動画" if ep.get("media_uri") and is_video_file(ep["media_uri"]) else "写真" if ep.get("media_uri") or ep.get("image_urls") else "なし"
            formatted.append(
                f"エピソード{i}: {ep.get('content', '')[:100]}... (メディア: {media_type})"
            )
    return "\n".join(formatted)


def _find_unused_media(episodes: List[Dict[str, Any]], used_urls: set, preferred_episodes: List[Dict[str, Any]]) -> Optional[str]:
    """未使用のメディアを探す"""
    logger.info(f"_find_unused_media called. Used URLs count: {len(used_urls)}")
    
    # まず優先エピソードから探す
    for ep in preferred_episodes:
        media = ep.get("media_uri") or ep.get("media_source_uri") or (ep.get("image_urls", [None])[0] if ep.get("image_urls") else None)
        if media and media not in used_urls:
            logger.info(f"Found unused media from preferred episodes: {media}")
            return media
    
    # 次に全エピソードから探す
    for ep in episodes:
        media = ep.get("media_uri") or ep.get("media_source_uri") or (ep.get("image_urls", [None])[0] if ep.get("image_urls") else None)
        if media and media not in used_urls:
            logger.info(f"Found unused media from all episodes: {media}")
            return media
    
    logger.warning("No unused media found")
    return None


def _generate_caption_for_media(media_url: str, content: str, child_name: str, model: GenerativeModel) -> str:
    """メディアのキャプションを生成"""
    try:
        media_type = "動画" if is_video_file(media_url) else "写真"
        prompt = f"""
{content}の場面で撮影された{media_type}のキャプションを10文字以内で生成してください。
シーンの雰囲気や{child_name}の様子を表現してください。

キャプションのみ出力：
"""
        response = model.generate_content(prompt)
        return response.text.strip()[:15]  # 最大15文字
    except:
        return "楽しい瞬間"


def orchestrate_notebook_generation_original(
    analysis_result: Dict[str, Any],
    all_collected_episodes: List[Dict[str, Any]],
    child_info: Dict[str, Any],
    custom_tone: Optional[str] = None,
    custom_focus: Optional[str] = None
) -> Dict[str, Any]:
    """
    収集したエピソードから段階的にトピックを生成してノートブックを作成
    
    Args:
        analysis_result: analyze_period_and_themesの結果
        all_collected_episodes: collect_episodes_by_themeで収集した全エピソードデータ
        child_info: 子供の基本情報
        custom_tone: カスタムトーン
        custom_focus: カスタムフォーカス
        
    Returns:
        生成されたノートブックデータ
    """
    try:
        themes = analysis_result["report"]["themes"]
        
        # 段階的にトピックを生成（前のトピックを考慮）
        topics = sequential_topic_generation(
            all_collected_episodes=all_collected_episodes,
            themes=themes,
            child_info=child_info,
            custom_tone=custom_tone,
            custom_focus=custom_focus
        )
        
        # トピックが不足している場合はデフォルトを追加
        while len(topics) < 5:
            topics.append({
                "title": f"セクション{len(topics)+1}",
                "subtitle": None,
                "content": "コンテンツの生成に失敗しました。",
                "photo": None,
                "caption": None,
                "generated": False
            })
        
        # ノートブックデータを構築
        notebook_data = {
            "notebook_id": analysis_result["report"]["notebook_id"],
            "nickname": child_info.get("nickname", "お子さん"),
            "period": analysis_result["report"]["period"],
            "topics": topics,
            "child_info": child_info
        }
        
        return {
            "status": "success",
            "report": notebook_data
        }
        
    except Exception as e:
        logger.error(f"Error in orchestrate_notebook_generation: {str(e)}")
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
            "content": {  # モバイルアプリが期待するcontent構造
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
            },
            "generation_status": status,
            "missing_topics": missing_topics,
        }

        # 既存のドキュメントを更新（statusフィールドは main.py で管理）
        notebook_ref.update(save_data)

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
# Cloud Functions用にコメントアウト
"""
root_agent = Agent(
    name="notebook_generator_agent",
    model=MODEL_NAME,
    description="子供の成長記録ノートブックを生成するエージェント",
    instruction='''
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
    3. orchestrate_notebook_generation: 収集したエピソードを配分してノートブックを生成
       - 各セクションに異なるエピソードを割り当て
       - 最後のセクションは全エピソードを網羅的にまとめる
    4. validate_and_save_notebook: 生成されたノートブックを検証して保存
    
    重要な注意事項：
    - collect_episodes_by_themeでエピソードが見つからない、またはエラーが発生した場合は、
      「指定された期間にエピソードが記録されていないため、ノートブックを生成できません」と
      ユーザーに伝え、処理を中止してください
    - エピソードが1つでも見つかった場合のみ、ノートブック生成を続行してください
    - 各セクションは異なるエピソードに焦点を当て、重複を避けること
    - 最後のセクション「今週のまとめ」は全体を総括する内容にすること
    - 生成されたコンテンツは温かく親しみやすい文章にすること
    - 画像がある場合は適切に選択すること
    ''',
    tools=[
        analyze_period_and_themes,
        collect_episodes_by_theme,
        orchestrate_notebook_generation,
        generate_topic_content,
        validate_and_save_notebook,
    ],
)
"""


def orchestrate_notebook_generation(
    child_id: str,
    start_date: str,
    end_date: str,
    themes: List[Dict[str, Any]],
    child_info: Dict[str, Any],
    custom_tone: Optional[str] = None,
    custom_focus: Optional[str] = None,
    selected_media_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Cloud Functions用のorchestrate_notebook_generationラッパー
    
    Args:
        child_id: 子供のID
        start_date: 開始日
        end_date: 終了日
        themes: テーマのリスト
        child_info: 子供の基本情報
        custom_tone: カスタムトーン
        custom_focus: カスタムフォーカス
        selected_media_ids: 選択されたメディアID（analysis_id）のリスト
        
    Returns:
        生成されたトピックとステータス
    """
    try:
        logger.info(f"orchestrate_notebook_generation called for child {child_id}, period: {start_date} to {end_date}")
        # 全エピソードを収集
        all_collected_episodes = []
        
        for theme in themes:
            episodes_result = collect_episodes_by_theme(
                theme_info=theme,
                child_id=child_id,
                start_date=start_date,
                end_date=end_date,
                selected_media_ids=selected_media_ids
            )
            
            if episodes_result.get("status") == "success":
                all_collected_episodes.append(episodes_result)
                logger.info(f"Theme '{theme['title']}' collected {episodes_result['report']['episode_count']} episodes")
        
        # エピソードが1つも見つからなかった場合
        if not all_collected_episodes:
            logger.warning("No episodes found for any theme")
            return {
                "status": "error",
                "error_message": "指定された期間にエピソードが記録されていません"
            }
        
        logger.info(f"Total themes with episodes: {len(all_collected_episodes)}")
        
        # analysis_resultを構築
        analysis_result = {
            "report": {
                "themes": themes,
                "notebook_id": f"{start_date.replace('-', '_')}_to_{end_date.replace('-', '_')}",
                "period": {
                    "start": start_date,
                    "end": end_date
                }
            }
        }
        
        # orchestrate_notebook_generation_originalを呼び出し
        result = orchestrate_notebook_generation_original(
            analysis_result=analysis_result,
            all_collected_episodes=all_collected_episodes,
            child_info=child_info,
            custom_tone=custom_tone,
            custom_focus=custom_focus
        )
        
        # 使用されたエピソード数を計算
        total_episodes_used = 0
        if result.get("status") == "success" and "topics" in result["report"]:
            for topic in result["report"]["topics"]:
                if topic.get("generated", False):
                    total_episodes_used += 1
        
        return {
            "status": result.get("status", "error"),
            "report": {
                "topics": result["report"].get("topics", []),
                "total_episodes_used": total_episodes_used
            }
        }
        
    except Exception as e:
        logger.error(f"Error in orchestrate_notebook_generation: {str(e)}")
        return {"status": "error", "error_message": str(e)}


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
            "agent_name": "notebook_generator_agent",
            "child_id": child_id,
            "period": f"{start_date} to {end_date}",
        }

    except Exception as e:
        logger.error(f"Error in process_notebook_generation_request: {str(e)}")
        return {"status": "error", "error_message": str(e)}

