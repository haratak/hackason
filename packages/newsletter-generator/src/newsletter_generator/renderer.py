"""Newsletter renderer module."""

import os
from pathlib import Path
from typing import Dict, List, Optional

try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

from .template_engine import TemplateEngine
from .types import Newsletter, RenderOptions


class NewsletterRenderer:
    """連絡帳レンダラー."""
    
    def __init__(self, template_dir: Optional[str] = None):
        """Initialize renderer."""
        self.template_engine = TemplateEngine(template_dir)
    
    async def render_all(
        self,
        newsletter: Newsletter,
        output_dir: str,
        formats: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """すべての形式で連絡帳をレンダリングする."""
        if formats is None:
            formats = ["html", "pdf"]
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        for format_type in formats:
            if format_type == "html":
                path = await self.render_html(newsletter, output_path)
                results["html"] = str(path)
            elif format_type == "pdf":
                if WEASYPRINT_AVAILABLE:
                    path = await self.render_pdf(newsletter, output_path)
                    results["pdf"] = str(path)
                else:
                    print("⚠️  PDF generation is not available. Install weasyprint and its dependencies.")
        
        return results
    
    async def render_html(self, newsletter: Newsletter, output_dir: Path) -> Path:
        """HTMLファイルとして出力する."""
        html_content = self.template_engine.render_newsletter(newsletter)
        
        filename = f"newsletter_{newsletter.id}.html"
        output_path = output_dir / filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return output_path
    
    async def render_pdf(
        self,
        newsletter: Newsletter,
        output_dir: Path,
        options: Optional[RenderOptions] = None,
    ) -> Path:
        """PDFファイルとして出力する."""
        # まずHTMLを生成
        html_content = self.template_engine.render_newsletter(newsletter)
        
        # WeasyPrintでPDFに変換
        filename = f"newsletter_{newsletter.id}.pdf"
        output_path = output_dir / filename
        
        # CSSファイルのパスを取得
        css_path = self._get_css_path()
        
        # PDFを生成
        html = weasyprint.HTML(string=html_content, base_url=str(css_path.parent))
        css = weasyprint.CSS(filename=str(css_path))
        
        pdf_options = {}
        if options:
            if options.quality:
                pdf_options["pdf_variant"] = f"pdf-{options.quality}"
        
        html.write_pdf(str(output_path), stylesheets=[css], **pdf_options)
        
        return output_path
    
    def _get_css_path(self) -> Path:
        """CSSファイルのパスを取得する."""
        template_dir = self.template_engine.template_dir
        return template_dir / "styles.css"