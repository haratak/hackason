"""Template engine for newsletter rendering."""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .types import Newsletter, NewsletterSection


class TemplateEngine:
    """テンプレートエンジン."""
    
    def __init__(self, template_dir: Optional[str] = None):
        """Initialize template engine."""
        if template_dir is None:
            # デフォルトのテンプレートディレクトリを使用
            package_dir = Path(__file__).parent
            template_dir = package_dir / "templates"
            
        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        
        # カスタムフィルタを追加
        self.env.filters["format_date"] = self._format_date
        self.env.filters["format_age"] = self._format_age
    
    def render_newsletter(self, newsletter: Newsletter) -> str:
        """連絡帳をHTMLにレンダリングする."""
        template = self.env.get_template("newsletter.html")
        
        context = {
            "newsletter": newsletter,
            "sections": self._prepare_sections(newsletter.sections),
            "date_range": self._format_date_range(newsletter.period),
        }
        
        return template.render(context)
    
    def _prepare_sections(self, sections: List[NewsletterSection]) -> List[Dict[str, Any]]:
        """セクションをテンプレート用に準備する."""
        prepared = []
        
        for section in sections:
            section_data = {
                "id": section.id,
                "title": section.title,
                "type": section.type,
                "content": section.content,
                "template_name": self._get_section_template_name(section.type),
            }
            prepared.append(section_data)
        
        return prepared
    
    def _get_section_template_name(self, section_type: str) -> str:
        """セクションタイプに応じたテンプレート名を取得する."""
        template_map = {
            "overview": "section_text.html",
            "activities": "section_text.html",
            "favorite-play": "section_photo_text.html",
            "growth-moment": "section_photo_text.html",
            "places-visited": "section_text.html",
            "first-time": "section_photo_caption.html",
            "development": "section_text.html",
            "best-shot": "section_photo_caption.html",
        }
        return template_map.get(section_type, "section_text.html")
    
    def _format_date(self, date: datetime) -> str:
        """日付をフォーマットする."""
        return date.strftime("%Y年%m月%d日")
    
    def _format_date_range(self, period: Dict[str, datetime]) -> str:
        """期間をフォーマットする."""
        start = self._format_date(period["start"])
        end = self._format_date(period["end"])
        return f"{start} ～ {end}"
    
    def _format_age(self, age: Dict[str, int]) -> str:
        """年齢をフォーマットする."""
        return f"{age['years']}歳{age['months']}ヶ月"