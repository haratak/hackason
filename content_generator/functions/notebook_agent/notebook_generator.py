"""
ノートブック生成エージェント
期間と子供IDを受け取って、ベクトル検索でエピソードを収集し、
Geminiでコンテンツを生成してノートブックを作成する
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json

# GCP関連のインポート（実装時に追加）
# from google.cloud import firestore
# from google.cloud import aiplatform
# import vertexai
# from vertexai.generative_models import GenerativeModel

logger = logging.getLogger(__name__)


class ContentStatus(Enum):
    """コンテンツ生成のステータス"""
    SUCCESS = "success"
    INSUFFICIENT_DATA = "insufficient_data"  # データ不足
    NO_EPISODES = "no_episodes"  # エピソードが見つからない
    GENERATION_FAILED = "generation_failed"  # 生成失敗
    PARTIAL_SUCCESS = "partial_success"  # 部分的成功


@dataclass
class Episode:
    """エピソードデータ"""
    episode_id: str
    child_id: str
    content: str
    tags: List[str]
    created_at: datetime
    image_urls: List[str] = None
    embedding_vector: List[float] = None


@dataclass
class NotebookTopic:
    """ノートブックのトピック"""
    title: str
    subtitle: Optional[str]
    content: str
    photo: Optional[str]
    caption: Optional[str]
    topic_type: str  # "large_photo", "text_only", "small_photo", "medium_photo", "center"


@dataclass
class GenerationResult:
    """生成結果"""
    status: ContentStatus
    notebook_data: Optional[Dict]
    error_message: Optional[str]
    missing_topics: List[str] = None


class NotebookGenerator:
    """ノートブック生成エージェント"""
    
    # トピックのテーマと検索クエリ
    TOPIC_THEMES = [
        {
            "id": "interest",
            "title": "今週の興味",
            "search_queries": ["興味", "夢中", "好き", "楽しい", "お気に入り"],
            "prompt_hint": "子供が今週特に興味を持ったことや夢中になったことについて"
        },
        {
            "id": "place",
            "title": "行った！場所",
            "search_queries": ["行った", "お出かけ", "公園", "散歩", "訪問"],
            "prompt_hint": "今週訪れた場所や外出のエピソード"
        },
        {
            "id": "first_time",
            "title": "初めての体験",
            "search_queries": ["初めて", "デビュー", "挑戦", "新しい"],
            "prompt_hint": "今週初めて経験したことや新しい挑戦"
        },
        {
            "id": "best_shot",
            "title": "今週のベストショット",
            "search_queries": ["笑顔", "かわいい", "素敵", "最高"],
            "prompt_hint": "今週の最も印象的な瞬間や表情"
        },
        {
            "id": "achievement",
            "title": "できるようになったこと",
            "search_queries": ["できた", "成長", "上手", "覚えた", "言えた"],
            "prompt_hint": "今週新しくできるようになったことや成長"
        }
    ]
    
    def __init__(self, firestore_client=None, vertex_ai_client=None):
        """
        Args:
            firestore_client: Firestoreクライアント
            vertex_ai_client: Vertex AIクライアント
        """
        self.firestore = firestore_client
        self.vertex_ai = vertex_ai_client
        self.gemini_model = None  # GenerativeModel("gemini-pro")
        
    def generate_notebook(
        self,
        child_id: str,
        start_date: datetime,
        end_date: datetime,
        child_info: Optional[Dict] = None
    ) -> GenerationResult:
        """
        ノートブックを生成する
        
        Args:
            child_id: 子供のID
            start_date: 開始日
            end_date: 終了日
            child_info: 子供の基本情報（nickname等）
            
        Returns:
            GenerationResult: 生成結果
        """
        try:
            logger.info(f"Generating notebook for child {child_id}, period: {start_date} to {end_date}")
            
            # 1. 各テーマごとにエピソードを収集
            episodes_by_theme = self._collect_episodes_by_themes(child_id, start_date, end_date)
            
            # 2. エピソードの量をチェック
            validation_result = self._validate_episodes(episodes_by_theme)
            if validation_result["status"] == ContentStatus.NO_EPISODES:
                return GenerationResult(
                    status=ContentStatus.NO_EPISODES,
                    notebook_data=None,
                    error_message="指定期間にエピソードが見つかりませんでした"
                )
            
            # 3. 各トピックのコンテンツを生成
            topics = self._generate_topics(episodes_by_theme, child_info)
            
            # 4. ノートブックデータを構築
            notebook_data = self._build_notebook_data(
                child_id=child_id,
                child_info=child_info,
                topics=topics,
                period_start=start_date,
                period_end=end_date
            )
            
            # 5. 生成結果を返す
            return GenerationResult(
                status=validation_result["status"],
                notebook_data=notebook_data,
                error_message=None,
                missing_topics=validation_result.get("missing_topics", [])
            )
            
        except Exception as e:
            logger.error(f"Failed to generate notebook: {str(e)}")
            return GenerationResult(
                status=ContentStatus.GENERATION_FAILED,
                notebook_data=None,
                error_message=str(e)
            )
    
    def _collect_episodes_by_themes(
        self,
        child_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, List[Episode]]:
        """
        テーマごとにエピソードを収集する
        
        Returns:
            Dict[theme_id, List[Episode]]
        """
        episodes_by_theme = {}
        
        for theme in self.TOPIC_THEMES:
            # ベクトル検索でエピソードを取得（仮実装）
            episodes = self._search_episodes_by_vector(
                child_id=child_id,
                search_queries=theme["search_queries"],
                start_date=start_date,
                end_date=end_date
            )
            episodes_by_theme[theme["id"]] = episodes
            
        return episodes_by_theme
    
    def _search_episodes_by_vector(
        self,
        child_id: str,
        search_queries: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> List[Episode]:
        """
        ベクトル検索でエピソードを取得する（仮実装）
        実際の実装では、Vertex AI Vector Searchなどを使用
        """
        # TODO: 実際のベクトル検索実装
        # 1. search_queriesをembeddingに変換
        # 2. Vector Searchで類似エピソードを検索
        # 3. 期間とchild_idでフィルタリング
        
        # 仮のエピソードデータを返す
        dummy_episodes = []
        return dummy_episodes
    
    def _validate_episodes(self, episodes_by_theme: Dict[str, List[Episode]]) -> Dict:
        """
        エピソードの量と質を検証する
        
        Returns:
            Dict with status and missing_topics
        """
        total_episodes = sum(len(episodes) for episodes in episodes_by_theme.values())
        missing_topics = []
        
        # 各テーマのエピソード数をチェック
        for theme_id, episodes in episodes_by_theme.items():
            if len(episodes) == 0:
                theme = next(t for t in self.TOPIC_THEMES if t["id"] == theme_id)
                missing_topics.append(theme["title"])
        
        # ステータスを決定
        if total_episodes == 0:
            return {"status": ContentStatus.NO_EPISODES, "missing_topics": missing_topics}
        elif len(missing_topics) >= 3:  # 半分以上のトピックが欠けている
            return {"status": ContentStatus.INSUFFICIENT_DATA, "missing_topics": missing_topics}
        elif len(missing_topics) > 0:
            return {"status": ContentStatus.PARTIAL_SUCCESS, "missing_topics": missing_topics}
        else:
            return {"status": ContentStatus.SUCCESS, "missing_topics": []}
    
    def _generate_topics(
        self,
        episodes_by_theme: Dict[str, List[Episode]],
        child_info: Optional[Dict]
    ) -> List[NotebookTopic]:
        """
        各トピックのコンテンツを生成する
        """
        topics = []
        topic_layouts = ["large_photo", "text_only", "small_photo", "medium_photo", "center"]
        
        for i, theme in enumerate(self.TOPIC_THEMES):
            episodes = episodes_by_theme.get(theme["id"], [])
            
            if not episodes:
                # エピソードがない場合はデフォルトコンテンツ
                topic = self._generate_default_topic(theme, topic_layouts[i])
            else:
                # Geminiでコンテンツ生成
                topic = self._generate_topic_with_gemini(
                    theme=theme,
                    episodes=episodes,
                    layout_type=topic_layouts[i],
                    child_info=child_info
                )
            
            topics.append(topic)
        
        return topics
    
    def _generate_topic_with_gemini(
        self,
        theme: Dict,
        episodes: List[Episode],
        layout_type: str,
        child_info: Optional[Dict]
    ) -> NotebookTopic:
        """
        Geminiを使ってトピックコンテンツを生成する
        """
        # プロンプトを構築
        prompt = self._build_generation_prompt(theme, episodes, child_info)
        
        # Geminiで生成（仮実装）
        # response = self.gemini_model.generate_content(prompt)
        # generated_content = response.text
        
        # 仮のコンテンツ
        generated_content = f"{theme['title']}に関するエピソードから生成されたコンテンツ"
        
        # 画像を選択
        photo_url = self._select_best_photo(episodes) if layout_type != "text_only" else None
        
        return NotebookTopic(
            title=theme["title"],
            subtitle=f"{theme['title']}のサブタイトル" if layout_type == "large_photo" else None,
            content=generated_content,
            photo=photo_url,
            caption="写真のキャプション" if photo_url else None,
            topic_type=layout_type
        )
    
    def _build_generation_prompt(
        self,
        theme: Dict,
        episodes: List[Episode],
        child_info: Optional[Dict]
    ) -> str:
        """
        Gemini用のプロンプトを構築する
        """
        child_name = child_info.get("nickname", "お子さん") if child_info else "お子さん"
        
        episodes_text = "\n".join([
            f"- {episode.content}"
            for episode in episodes[:5]  # 最大5エピソード
        ])
        
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
        """
        
        return prompt
    
    def _select_best_photo(self, episodes: List[Episode]) -> Optional[str]:
        """
        エピソードから最適な画像を選択する
        """
        # 画像があるエピソードを優先
        for episode in episodes:
            if episode.image_urls:
                return episode.image_urls[0]
        
        # デフォルト画像
        return "https://via.placeholder.com/400x200/FFE5CC/333333?text=No+Image"
    
    def _generate_default_topic(self, theme: Dict, layout_type: str) -> NotebookTopic:
        """
        エピソードがない場合のデフォルトトピックを生成
        """
        return NotebookTopic(
            title=theme["title"],
            subtitle=None,
            content=f"今週は{theme['title']}に関する記録がありませんでした。",
            photo=None,
            caption=None,
            topic_type=layout_type
        )
    
    def _build_notebook_data(
        self,
        child_id: str,
        child_info: Optional[Dict],
        topics: List[NotebookTopic],
        period_start: datetime,
        period_end: datetime
    ) -> Dict:
        """
        最終的なノートブックデータを構築する
        """
        # 週のIDを生成（例: 2024_06_week1）
        week_num = (period_start.day - 1) // 7 + 1
        notebook_id = f"{period_start.year}_{period_start.month:02d}_week{week_num}"
        
        return {
            "notebook_id": notebook_id,
            "child_id": child_id,
            "nickname": child_info.get("nickname", "お子さん") if child_info else "お子さん",
            "date": period_end,  # 週の最終日
            "period": {
                "start": period_start,
                "end": period_end
            },
            "topics": [
                {
                    "title": topic.title,
                    "subtitle": topic.subtitle,
                    "content": topic.content,
                    "photo": topic.photo,
                    "caption": topic.caption
                }
                for topic in topics
            ],
            "created_at": datetime.now(),
            "status": "published"
        }


# 使用例
if __name__ == "__main__":
    # エージェントのインスタンス化
    generator = NotebookGenerator()
    
    # ノートブック生成
    result = generator.generate_notebook(
        child_id="taro_2020",
        start_date=datetime(2024, 6, 1),
        end_date=datetime(2024, 6, 7),
        child_info={"nickname": "たろうくん"}
    )
    
    print(f"Status: {result.status}")
    if result.notebook_data:
        print(f"Generated notebook: {result.notebook_data['notebook_id']}")