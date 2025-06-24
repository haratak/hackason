"""Newsletter generator main module."""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from .types import (
    ChildcareRecord,
    GenerateParams,
    Newsletter,
    NewsletterGenerationError,
    NewsletterLayout,
    NewsletterSection,
    RegenerateParams,
    SectionContent,
)
from .vertex_ai_client import VertexAIClient


class NewsletterGenerator:
    """AI連絡帳生成クラス."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """Initialize generator."""
        self.vertex_ai = VertexAIClient(api_key=api_key, model_name=model_name)
    
    async def generate(self, params: GenerateParams) -> Newsletter:
        """連絡帳を生成する."""
        try:
            # 1. 全ての記録を取得
            all_records = await params.record_reader.search_records(
                child_id=params.child_profile.id,
                date_range=params.period,
                limit=1000,
            )
            
            # 2. セクションごとのコンテンツを生成（全記録を渡す）
            sections = await self._generate_sections_with_all_records(params, all_records)
            
            # 3. 使用した記録のメディアIDを収集
            used_media_ids = await self._collect_used_media_ids(params, sections)
            
            # 4. 連絡帳オブジェクトを構築
            newsletter = Newsletter(
                id=self._generate_id(),
                child_id=params.child_profile.id,
                period=params.period,
                generated_at=datetime.now(),
                version=1,
                title=self._generate_title(params),
                sections=sections,
                used_media_ids=used_media_ids,
                generation_prompt=params.custom_prompt,
                metadata={
                    "child_age": params.child_profile.current_age,
                    "record_count": len(all_records),
                },
            )
            
            return newsletter
            
        except Exception as e:
            raise NewsletterGenerationError(
                "連絡帳の生成に失敗しました", "GENERATION_FAILED", e
            )
    
    async def regenerate(self, params: RegenerateParams) -> Newsletter:
        """連絡帳を再生成する."""
        try:
            newsletter = params.newsletter
            prompt = params.prompt
            target_sections = params.sections_to_regenerate or [
                s.id for s in newsletter.sections
            ]
            
            # セクションごとに再生成（順次実行でレート制限を回避）
            regenerated_sections = []
            
            for section in newsletter.sections:
                if section.id in target_sections:
                    # API呼び出し間に遅延を追加
                    if regenerated_sections:
                        await asyncio.sleep(3.0)
                    
                    regenerated = await self._regenerate_section(section, prompt)
                    regenerated_sections.append(regenerated)
                else:
                    regenerated_sections.append(section)
            
            # 新しいバージョンの連絡帳を作成
            return Newsletter(
                id=newsletter.id,
                child_id=newsletter.child_id,
                period=newsletter.period,
                generated_at=datetime.now(),
                version=newsletter.version + 1,
                title=newsletter.title,
                sections=regenerated_sections,
                used_media_ids=newsletter.used_media_ids,
                generation_prompt=prompt,
                metadata=newsletter.metadata,
            )
            
        except Exception as e:
            raise NewsletterGenerationError(
                "連絡帳の再生成に失敗しました", "REGENERATION_FAILED", e
            )
    
    async def _generate_sections_with_all_records(
        self, params: GenerateParams, all_records: List[ChildcareRecord]
    ) -> List[NewsletterSection]:
        """全ての記録を使用してセクションを生成する."""
        layout = params.layout or self._get_default_layout()
        sections = []
        
        for i, config in enumerate(layout.sections):
            # セクション間に遅延を追加してレート制限を回避
            if i > 0:
                await asyncio.sleep(2.0)
            
            content = await self._generate_section_content_from_all_records(
                config, params, all_records
            )
            
            section = NewsletterSection(
                id=config["id"],
                type=config["type"],
                title=config.get("title") or self._get_section_title(config["type"], params.period),
                content=content,
                order=config["order"],
                metadata=content.metadata,
            )
            sections.append(section)
        
        return sections
    
    async def _generate_section_content_from_all_records(
        self, config: Dict, params: GenerateParams, all_records: List[ChildcareRecord]
    ) -> SectionContent:
        """全ての記録からセクションコンテンツを生成する."""
        section_type = config["type"]
        
        # セクションタイプに応じて関連する記録をフィルタリング
        relevant_records = self._filter_records_for_section(all_records, section_type)
        
        # 記録がない場合の処理
        if not relevant_records:
            return self._generate_empty_content(section_type, params.period)
        
        # セクションタイプに応じたコンテンツ生成
        if section_type in ["overview", "activities", "places-visited", "development"]:
            # テキストのみのセクション
            text = await self.vertex_ai.generate_section_content(
                section_type,
                params.child_profile,
                relevant_records,
                params.timeline,
                self._get_section_instruction(section_type, params.period),
            )
            
            return SectionContent(
                text=text,
                metadata={
                    "record_count": len(relevant_records),
                    "record_ids": [r.id for r in relevant_records],
                },
            )
        
        elif section_type in ["favorite-play", "growth-moment"]:
            # 写真＋テキストのセクション
            selected_record = self._select_best_record(relevant_records, section_type)
            
            text = await self.vertex_ai.generate_section_content(
                section_type,
                params.child_profile,
                relevant_records,
                params.timeline,
                self._get_section_instruction(section_type, params.period),
            )
            
            return SectionContent(
                text=text,
                photo_url=f"gs://bucket/photos/{selected_record.media_id}.jpg"
                if selected_record and selected_record.media_id
                else "placeholder.jpg",
                photo_description=selected_record.activity["description"]
                if selected_record
                else "",
                metadata={
                    "record_count": len(relevant_records),
                    "record_ids": [r.id for r in relevant_records],
                    "selected_record_id": selected_record.id if selected_record else None,
                },
            )
        
        elif section_type in ["first-time", "best-shot"]:
            # 写真＋キャプションのセクション
            selected_record = self._select_best_record(relevant_records, section_type)
            
            if not selected_record:
                return self._generate_empty_content(section_type, params.period)
            
            # 記録からキャプションを生成
            caption = await self.vertex_ai.generate_caption(
                selected_record, section_type
            )
            
            return SectionContent(
                photo_url=f"gs://bucket/photos/{selected_record.media_id}.jpg"
                if selected_record.media_id
                else "placeholder.jpg",
                caption=caption,
                metadata={
                    "record_count": len(relevant_records),
                    "selected_record_id": selected_record.id,
                },
            )
        
        else:
            # デフォルト
            return self._generate_empty_content(section_type, params.period)
    
    def _filter_records_for_section(
        self, records: List[ChildcareRecord], section_type: str
    ) -> List[ChildcareRecord]:
        """セクションタイプに応じて記録をフィルタリング."""
        if section_type == "overview":
            # 全体の様子は全ての記録を使用
            return records
        
        elif section_type == "activities":
            # 活動セクションは様々な活動を含む
            return [r for r in records if any(
                keyword in r.activity.get("type", "").lower() 
                for keyword in ["活動", "遊び", "制作", "音楽", "体操", "お散歩"]
            )]
        
        elif section_type == "favorite-play":
            # お気に入りの遊びは楽しそうな遊び記録
            return [r for r in records if 
                    "遊び" in r.activity.get("type", "") and
                    r.child_state and "楽しそう" in r.child_state.get("mood", "")]
        
        elif section_type == "growth-moment":
            # 成長の瞬間は「できた」「初めて」を含む記録
            return [r for r in records if any(
                keyword in " ".join(r.observations + (r.child_state.get("verbal_expressions", []) if r.child_state else []))
                for keyword in ["できた", "初めて", "成功"]
            )]
        
        elif section_type == "places-visited":
            # 訪れた場所はお散歩や外出記録
            return [r for r in records if any(
                keyword in r.activity.get("type", "")
                for keyword in ["お散歩", "外出", "公園"]
            )]
        
        elif section_type == "first-time":
            # 初めての体験
            return [r for r in records if any(
                "初めて" in tag for tag in r.tags
            ) or "初めて" in " ".join(r.observations)]
        
        elif section_type == "development":
            # できるようになったこと
            return [r for r in records if any(
                keyword in " ".join(r.observations)
                for keyword in ["できた", "できるようになった", "成功"]
            )]
        
        elif section_type == "best-shot":
            # ベストショットは写真がある楽しそうな記録
            return [r for r in records if 
                    r.media_id and 
                    r.child_state and 
                    any(mood in r.child_state.get("mood", "") for mood in ["楽しそう", "笑顔", "満足そう"])]
        
        return []
    
    async def _generate_section_content(
        self, config: Dict, params: GenerateParams
    ) -> SectionContent:
        """セクションのコンテンツを生成する."""
        section_type = config["type"]
        
        # セクションタイプに応じた検索クエリを構築
        search_query = self._build_search_query(section_type)
        search_tags = self._get_search_tags(section_type)
        
        # 育児記録を検索
        records = await params.record_reader.search_records(
            child_id=params.child_profile.id,
            date_range=params.period,
            query=search_query,
            tags=search_tags,
            limit=30,
        )
        
        # 記録がない場合の処理
        if not records:
            return self._generate_empty_content(section_type, params.period)
        
        # セクションタイプに応じたコンテンツ生成
        if section_type in ["overview", "activities", "places-visited", "development"]:
            # テキストのみのセクション
            text = await self.vertex_ai.generate_section_content(
                section_type,
                params.child_profile,
                records,
                params.timeline,
                self._get_section_instruction(section_type, params.period),
            )
            
            return SectionContent(
                text=text,
                metadata={
                    "record_count": len(records),
                    "record_ids": [r.id for r in records],
                },
            )
        
        elif section_type in ["favorite-play", "growth-moment"]:
            # 写真＋説明のセクション
            text = await self.vertex_ai.generate_section_content(
                section_type,
                params.child_profile,
                records,
                params.timeline,
                self._get_section_instruction(section_type, params.period),
            )
            
            # 最も関連性の高い記録の写真を選択
            selected_record = self._select_best_record(records, section_type)
            
            return SectionContent(
                text=text,
                photo_url=f"gs://bucket/photos/{selected_record.media_id}.jpg"
                if selected_record and selected_record.media_id
                else "placeholder.jpg",
                photo_description=selected_record.activity["description"]
                if selected_record
                else "",
                metadata={
                    "record_count": len(records),
                    "record_ids": [r.id for r in records],
                    "selected_record_id": selected_record.id if selected_record else None,
                },
            )
        
        elif section_type in ["first-time", "best-shot"]:
            # 写真＋キャプションのセクション
            selected_record = self._select_best_record(records, section_type)
            
            if not selected_record:
                return SectionContent(
                    photo_url="placeholder.jpg",
                    caption="素敵な瞬間",
                    metadata={"record_count": 0},
                )
            
            # 記録からキャプションを生成
            caption = await self.vertex_ai.generate_caption(
                selected_record, section_type
            )
            
            return SectionContent(
                photo_url=f"gs://bucket/photos/{selected_record.media_id}.jpg"
                if selected_record.media_id
                else "placeholder.jpg",
                caption=caption,
                metadata={
                    "record_count": len(records),
                    "record_ids": [r.id for r in records],
                    "selected_record_id": selected_record.id,
                },
            )
        
        else:
            return SectionContent(
                text=f"{config.get('title', section_type)}の内容",
                photo_url="placeholder.jpg",
                caption="キャプション",
            )
    
    async def _regenerate_section(
        self, section: NewsletterSection, prompt: str
    ) -> NewsletterSection:
        """セクションを再生成する."""
        # テキストコンテンツがある場合のみ再生成
        if section.content.text:
            regenerated_text = await self.vertex_ai.regenerate_content(
                section.content.text, prompt
            )
            
            new_content = SectionContent(
                text=regenerated_text,
                photo_url=section.content.photo_url,
                photo_description=section.content.photo_description,
                caption=section.content.caption,
                metadata=section.content.metadata,
            )
            
            return NewsletterSection(
                id=section.id,
                title=section.title,
                type=section.type,
                content=new_content,
                order=section.order,
                metadata=section.metadata,
            )
        
        return section
    
    def _generate_title(self, params: GenerateParams) -> str:
        """タイトルを生成する."""
        month = params.period["start"].month
        return f"{params.child_profile.name}ちゃんの{month}月の成長記録"
    
    async def _collect_used_media_ids(
        self, params: GenerateParams, sections: List[NewsletterSection]
    ) -> List[str]:
        """使用したメディアIDを収集する."""
        media_ids = []
        
        for section in sections:
            if section.content.metadata and section.content.metadata.get(
                "selected_record_id"
            ):
                records = await params.record_reader.get_records_by_ids(
                    [section.content.metadata["selected_record_id"]]
                )
                if records and records[0].media_id:
                    media_ids.append(records[0].media_id)
        
        return list(set(media_ids))  # 重複を除去
    
    def _generate_id(self) -> str:
        """IDを生成する."""
        return f"{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
    
    def _build_search_query(self, section_type: str) -> str:
        """セクションタイプに応じた検索クエリを構築する."""
        query_map = {
            "overview": "",
            "activities": "活動 遊び",
            "favorite-play": "遊び 楽しい 好き",
            "growth-moment": "成長 できた 初めて",
            "places-visited": "場所 お散歩 外出",
            "first-time": "初めて 新しい 挑戦",
            "development": "できた 成長 発達",
            "best-shot": "笑顔 楽しい 素敵",
        }
        return query_map.get(section_type, "")
    
    def _get_search_tags(self, section_type: str) -> List[str]:
        """セクションタイプに応じた検索タグを取得する."""
        tag_map = {
            "overview": [],
            "activities": ["遊び", "活動"],
            "favorite-play": ["遊び", "楽しい"],
            "growth-moment": ["成長", "達成感"],
            "places-visited": ["お散歩", "外出"],
            "first-time": ["初めて", "新しい"],
            "development": ["成長", "発達"],
            "best-shot": ["笑顔", "楽しい"],
        }
        return tag_map.get(section_type, [])
    
    def _get_section_instruction(self, section_type: str, period: Optional[Dict[str, datetime]] = None) -> str:
        """セクションタイプに応じた生成指示を取得する."""
        # 期間に応じたテキストを決定
        period_text = "この期間"
        if period:
            duration = (period["end"] - period["start"]).days
            period_text = "今月" if duration > 7 else "今週"
        
        instruction_map = {
            "overview": f"{period_text}の全体的な様子を要約してください。提供された記録のみを使用し、新しい情報を追加しないでください。",
            "activities": f"{period_text}行った活動について、記録から抽出して記述してください。",
            "favorite-play": "子どもが特に楽しんでいた遊びについて、具体的な様子を記録から記述してください。",
            "growth-moment": "成長が見られた瞬間について、記録から具体的に記述してください。",
            "places-visited": "訪れた場所について、記録に基づいて記述してください。",
            "first-time": "初めての体験について、記録から抽出して記述してください。",
            "development": "できるようになったことについて、記録から具体的に記述してください。",
            "best-shot": "素敵な瞬間について簡潔に記述してください。",
        }
        return instruction_map.get(section_type, "記録に基づいて記述してください。")
    
    def _select_best_record(
        self, records: List[ChildcareRecord], section_type: str
    ) -> Optional[ChildcareRecord]:
        """最適な記録を選択する."""
        if not records:
            return None
        
        # セクションタイプに応じた優先順位で選択
        if section_type == "first-time":
            # "初めて"タグがある記録を優先
            for record in records:
                if "初めて" in record.tags:
                    return record
        
        if section_type == "best-shot":
            # "笑顔"タグがある記録を優先
            for record in records:
                if "笑顔" in record.tags:
                    return record
        
        # メディアIDがある記録を優先
        for record in records:
            if record.media_id:
                return record
        
        # 最新の記録を返す
        return records[0]
    
    def _generate_empty_content(self, section_type: str, period: Optional[Dict[str, datetime]] = None) -> SectionContent:
        """空のコンテンツを生成する."""
        # 期間に応じたテキストを決定
        period_text = "記録"
        if period:
            duration = (period["end"] - period["start"]).days
            period_text = "今月の記録" if duration > 7 else "今週の記録"
        
        empty_content_map = {
            "overview": SectionContent(text=f"{period_text}はありません。"),
            "activities": SectionContent(text=f"{period_text.replace('記録', '活動記録')}はありません。"),
            "favorite-play": SectionContent(
                text=f"{period_text.replace('記録', '遊びの記録')}はありません。",
                photo_url="placeholder.jpg",
                photo_description="",
            ),
            "growth-moment": SectionContent(
                text=f"{period_text.replace('記録', '成長記録')}はありません。",
                photo_url="placeholder.jpg",
                photo_description="",
            ),
            "places-visited": SectionContent(text=f"{period_text.replace('記録', '外出記録')}はありません。"),
            "first-time": SectionContent(
                photo_url="placeholder.jpg", caption="新しい体験の記録はありません。"
            ),
            "development": SectionContent(text=f"{period_text.replace('記録', '発達記録')}はありません。"),
            "best-shot": SectionContent(
                photo_url="placeholder.jpg", caption=f"{period_text.replace('記録', '写真記録')}はありません。"
            ),
        }
        
        content = empty_content_map.get(
            section_type,
            SectionContent(
                text="記録がありません。", metadata={"record_count": 0}
            ),
        )
        
        if not content.metadata:
            content.metadata = {"record_count": 0}
        
        return content
    
    def _get_section_title(self, section_type: str, period: Dict[str, datetime]) -> str:
        """セクションタイトルを取得する."""
        # 期間が7日以上なら月単位として扱う
        duration = (period["end"] - period["start"]).days
        period_text = "今月" if duration > 7 else "今週"
        
        title_map = {
            "overview": f"{period_text}の様子",
            "activities": f"{period_text}の活動",
            "favorite-play": "お気に入りの遊び",
            "growth-moment": "成長の瞬間",
            "places-visited": "行った場所",
            "first-time": "初めての体験",
            "development": "できるようになったこと",
            "best-shot": f"{period_text}のベストショット",
        }
        return title_map.get(section_type, section_type)
    
    def _get_default_layout(self) -> NewsletterLayout:
        """デフォルトレイアウトを取得する."""
        return NewsletterLayout(
            id="default",
            name="デフォルトレイアウト",
            sections=[
                {"id": "sec-1", "type": "overview", "order": 1},
                {"id": "sec-2", "type": "activities", "order": 2},
                {"id": "sec-3", "type": "favorite-play", "order": 3},
                {"id": "sec-4", "type": "first-time", "order": 4},
                {"id": "sec-5", "type": "best-shot", "order": 5},
            ],
        )