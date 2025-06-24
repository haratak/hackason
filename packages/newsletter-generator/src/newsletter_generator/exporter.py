"""Newsletter JSON exporter module."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Union

from .types import Newsletter


class NewsletterExporter:
    """連絡帳のJSONエクスポーター."""
    
    def to_json(self, newsletter: Newsletter, pretty: bool = True) -> str:
        """連絡帳をJSON文字列に変換する."""
        return json.dumps(
            self.to_dict(newsletter),
            ensure_ascii=False,
            indent=2 if pretty else None,
            default=self._json_serializer
        )
    
    def to_dict(self, newsletter: Newsletter) -> Dict[str, Any]:
        """連絡帳を辞書形式に変換する."""
        return {
            "id": newsletter.id,
            "version": newsletter.version,
            "child_id": newsletter.child_id,
            "title": newsletter.title,
            "period": {
                "start": self._serialize_datetime(newsletter.period["start"]),
                "end": self._serialize_datetime(newsletter.period["end"]),
            },
            "sections": [
                {
                    "id": section.id,
                    "type": section.type,
                    "title": section.title,
                    "order": section.order,
                    "content": self._serialize_content(section.content),
                    "metadata": section.metadata or {}
                }
                for section in sorted(newsletter.sections, key=lambda s: s.order)
            ],
            "metadata": newsletter.metadata,
            "generated_at": self._serialize_datetime(newsletter.generated_at),
            "created_at": self._serialize_datetime(
                getattr(newsletter, 'created_at', newsletter.generated_at)
            ),
            "updated_at": self._serialize_datetime(
                getattr(newsletter, 'updated_at', newsletter.generated_at)
            ),
        }
    
    def save_json(self, newsletter: Newsletter, output_path: Union[str, Path]) -> Path:
        """連絡帳をJSONファイルとして保存する."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.to_json(newsletter))
        
        return output_path
    
    def _serialize_content(self, content) -> Dict[str, Any]:
        """SectionContentを辞書形式に変換する."""
        result = {}
        
        if content.text:
            result["text"] = content.text
        if content.photo_url:
            result["photo_url"] = content.photo_url
        if content.photo_description:
            result["photo_description"] = content.photo_description
        if content.caption:
            result["caption"] = content.caption
            
        # メタデータがある場合は追加
        if hasattr(content, 'metadata') and content.metadata:
            result["metadata"] = content.metadata
            
        return result
    
    def _serialize_datetime(self, dt) -> str:
        """datetime オブジェクトをISO形式の文字列に変換する."""
        if isinstance(dt, datetime):
            return dt.isoformat()
        return str(dt)
    
    def _json_serializer(self, obj):
        """JSON シリアライザー for non-serializable objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        raise TypeError(f"Type {type(obj)} not serializable")