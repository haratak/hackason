"""Type definitions for the newsletter generator."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ChildProfile:
    """子供のプロファイル情報."""
    
    id: str
    name: str
    birth_date: datetime
    gender: Optional[str] = None
    current_age: Optional[Dict[str, int]] = None
    
    def __post_init__(self) -> None:
        """Calculate current age if not provided."""
        if self.current_age is None:
            now = datetime.now()
            age = now - self.birth_date
            years = age.days // 365
            months = (age.days % 365) // 30
            self.current_age = {"years": years, "months": months}


@dataclass
class ChildcareRecord:
    """育児記録データ."""
    
    id: str
    timestamp: str  # ISO 8601形式
    child_id: str
    activity: Dict[str, Any]
    observations: List[str]
    tags: List[str] = field(default_factory=list)
    recorded_by: Optional[str] = None
    child_state: Optional[Dict[str, Any]] = None
    media_id: Optional[str] = None


class ChildcareRecordReader(Protocol):
    """育児記録リーダーのプロトコル."""
    
    async def search_records(
        self,
        child_id: str,
        date_range: Dict[str, datetime],
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[ChildcareRecord]:
        """記録を検索する."""
        ...
    
    def get_records_by_ids(
        self, record_ids: List[str]
    ) -> List[ChildcareRecord]:
        """IDで記録を取得する."""
        ...
    
    def get_records_by_activity_type(
        self,
        child_id: str,
        activity_type: str,
        date_range: Dict[str, datetime],
    ) -> List[ChildcareRecord]:
        """活動タイプで記録を検索する."""
        ...


@dataclass
class Timeline:
    """タイムライン情報."""
    
    child_id: str
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    preferences: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class NewsletterLayout:
    """レイアウト設定."""
    
    id: str
    name: str
    sections: List[Dict[str, Any]]


@dataclass
class GenerateParams:
    """連絡帳生成パラメータ."""
    
    child_profile: ChildProfile
    period: Dict[str, datetime]
    record_reader: ChildcareRecordReader
    timeline: Optional[Timeline] = None
    layout: Optional[NewsletterLayout] = None
    custom_prompt: Optional[str] = None


@dataclass
class SectionContent:
    """セクションコンテンツ."""
    
    text: Optional[str] = None
    photo_url: Optional[str] = None
    photo_description: Optional[str] = None
    caption: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class NewsletterSection:
    """連絡帳セクション."""
    
    id: str
    title: str
    type: str
    content: SectionContent
    order: int
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Newsletter:
    """生成された連絡帳."""
    
    id: str
    child_id: str
    period: Dict[str, datetime]
    generated_at: datetime
    version: int
    title: str
    sections: List[NewsletterSection]
    used_media_ids: List[str] = field(default_factory=list)
    generation_prompt: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RegenerateParams:
    """再生成パラメータ."""
    
    newsletter: Newsletter
    prompt: str
    sections_to_regenerate: Optional[List[str]] = None


@dataclass
class RenderOptions:
    """レンダリングオプション."""
    
    format: str  # 'pdf', 'html'
    quality: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None


class NewsletterGenerationError(Exception):
    """連絡帳生成エラー."""
    
    def __init__(self, message: str, code: str, details: Any = None) -> None:
        """Initialize error."""
        super().__init__(message)
        self.code = code
        self.details = details