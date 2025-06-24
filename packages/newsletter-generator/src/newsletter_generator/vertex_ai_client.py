"""Vertex AI client for newsletter generation."""

import asyncio
import os
from typing import List, Optional

import google.generativeai as genai
from google.api_core import exceptions

from .types import ChildProfile, ChildcareRecord, Timeline


class VertexAIClient:
    """Vertex AI クライアント."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """Initialize client with API key authentication."""
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key is required")
        
        genai.configure(api_key=self.api_key)
        
        # モデルの初期化
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.model = genai.GenerativeModel(self.model_name)
        
        # レート制限対策の設定
        self.max_retries = 5
        self.base_delay = 3.0
        self.last_api_call_time = 0
        self.min_api_interval = 2.0
    
    async def generate_section_content(
        self,
        section_type: str,
        child_profile: ChildProfile,
        records: List[ChildcareRecord],
        timeline: Optional[Timeline] = None,
        custom_prompt: Optional[str] = None,
    ) -> str:
        """セクションコンテンツを生成する."""
        prompt = self._build_prompt(
            section_type, child_profile, records, timeline, custom_prompt
        )
        
        return await self._retry_with_backoff(
            lambda: self._generate_content(prompt), "generate_section_content"
        )
    
    async def generate_caption(
        self, record: ChildcareRecord, section_type: str
    ) -> str:
        """育児記録からキャプションを生成する."""
        prompt = f"""
以下の育児記録から、「{section_type}」セクションの写真キャプションを生成してください。

【育児記録】
活動: {record.activity['type']} - {record.activity['description']}
観察記録:
{self._format_observations(record.observations)}
{self._format_child_state(record.child_state)}

【指示】
- 15-25文字程度の簡潔なキャプション
- 記録の内容を要約し、温かみのある表現で
- 記録にない情報は追加しない

キャプションのみを出力してください。"""
        
        return await self._retry_with_backoff(
            lambda: self._generate_content(prompt), "generate_caption"
        )
    
    async def regenerate_content(
        self, original_content: str, user_prompt: str
    ) -> str:
        """コンテンツを再生成する."""
        prompt = f"""
以下の文章を、ユーザーからの指示に従って書き直してください。

【元の文章】
{original_content}

【ユーザーからの指示】
{user_prompt}

保育士の温かい視点は保ちながら、指示に従った文章を生成してください。
文章のみを出力してください。"""
        
        return await self._retry_with_backoff(
            lambda: self._generate_content(prompt), "regenerate_content"
        )
    
    def _build_prompt(
        self,
        section_type: str,
        child_profile: ChildProfile,
        records: List[ChildcareRecord],
        timeline: Optional[Timeline],
        custom_prompt: Optional[str],
    ) -> str:
        """プロンプトを構築する."""
        age_text = f"{child_profile.current_age['years']}歳{child_profile.current_age['months']}ヶ月"
        
        base_prompt = f"""
あなたは保育士の視点で、{child_profile.name}ちゃん（{age_text}）の連絡帳を作成するアシスタントです。

【重要な指示】
- 提供された育児記録のみを使用して文章を作成してください
- 記録にない情報を創作したり、推測したりしないでください
- 記録の内容を要約し、保護者に伝わりやすい形で表現してください

【セクション】{section_type}

【育児記録】
{self._summarize_childcare_records(records)}

【過去の成長記録】
{self._summarize_timeline(timeline) if timeline else '初回のため過去データなし'}
"""
        
        if custom_prompt:
            base_prompt += f"\n【追加の指示】\n{custom_prompt}"
        
        base_prompt += """

以下の点を考慮して、保護者が読んで嬉しくなるような文章を生成してください：
- 記録に基づいた事実のみを記載
- 客観的でありながら温かみのある表現
- 具体的な成長の様子（記録から読み取れる範囲で）
- 年齢に応じた発達の視点
- 200文字程度で簡潔に

文章のみを出力してください。"""
        
        return base_prompt
    
    def _summarize_childcare_records(self, records: List[ChildcareRecord]) -> str:
        """育児記録をサマライズする."""
        if not records:
            return "記録なし"
        
        summaries = []
        for i, record in enumerate(records, 1):
            timestamp = record.timestamp.split("T")[0]
            activity = record.activity
            
            summary = f"""
【記録{i}】{timestamp} - {activity['type']}
活動内容: {activity['description']}
観察記録:
{self._format_observations(record.observations)}
{self._format_child_state(record.child_state)}"""
            
            summaries.append(summary)
        
        return "\n\n".join(summaries)
    
    def _format_observations(self, observations: List[str]) -> str:
        """観察記録をフォーマットする."""
        return "\n".join(f"  - {obs}" for obs in observations)
    
    def _format_child_state(self, child_state: Optional[dict]) -> str:
        """子どもの様子をフォーマットする."""
        if not child_state:
            return ""
        
        lines = ["子どもの様子:"]
        if "mood" in child_state:
            lines.append(f"  - 気分: {child_state['mood']}")
        if "verbal_expressions" in child_state:
            expressions = ", ".join(child_state["verbal_expressions"])
            lines.append(f"  - 発した言葉: {expressions}")
        if "interactions" in child_state:
            interactions = ", ".join(child_state["interactions"])
            lines.append(f"  - 他児との関わり: {interactions}")
        
        return "\n".join(lines)
    
    def _summarize_timeline(self, timeline: Timeline) -> str:
        """タイムラインをサマライズする."""
        # timelineがdictの場合の処理
        if isinstance(timeline, dict):
            milestones = timeline.get("milestones", [])
            preferences = timeline.get("preferences", [])
        else:
            milestones = timeline.milestones
            preferences = timeline.preferences
        
        if not milestones:
            return "なし"
        
        recent_milestones = milestones[-5:]
        milestones_text = "\n".join(
            f"- {m['date']}: {m['description']}" for m in recent_milestones
        )
        
        preferences_text = ""
        if preferences:
            prefs = "\n".join(
                f"- {p['category']}: {', '.join(p['items'])}"
                for p in preferences
            )
            preferences_text = f"\n\n好み・興味:\n{prefs}"
        
        return f"最近のマイルストーン:\n{milestones_text}{preferences_text}"
    
    async def _generate_content(self, prompt: str) -> str:
        """コンテンツを生成する."""
        response = await asyncio.to_thread(
            self.model.generate_content, prompt
        )
        return response.text.strip()
    
    async def _retry_with_backoff(
        self, operation, operation_name: str
    ) -> str:
        """リトライロジック with exponential backoff."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # API呼び出し間隔を確保
                current_time = asyncio.get_event_loop().time()
                time_since_last_call = current_time - self.last_api_call_time
                
                if time_since_last_call < self.min_api_interval:
                    wait_time = self.min_api_interval - time_since_last_call
                    await asyncio.sleep(wait_time)
                
                self.last_api_call_time = asyncio.get_event_loop().time()
                return await operation()
                
            except exceptions.ResourceExhausted as e:
                last_error = e
                delay = self.base_delay * (2 ** attempt) + (0.1 * attempt)
                print(
                    f"Rate limit hit in {operation_name}, "
                    f"retrying in {delay:.1f}s... "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                await asyncio.sleep(delay)
                continue
            
            except Exception as e:
                print(f"{operation_name} error: {e}")
                raise
        
        # 最大リトライ回数に達した場合
        print(f"{operation_name} failed after {self.max_retries} attempts")
        raise last_error