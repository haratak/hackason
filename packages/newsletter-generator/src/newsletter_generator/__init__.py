"""AI Newsletter Generator Package."""

from .exporter import NewsletterExporter
from .generator import NewsletterGenerator
from .mock_record_reader import MockRecordReader, create_sample_childcare_records
from .renderer import NewsletterRenderer
from .template_engine import TemplateEngine
from .types import (
    ChildProfile,
    ChildcareRecord,
    ChildcareRecordReader,
    GenerateParams,
    Newsletter,
    NewsletterSection,
    RegenerateParams,
    RenderOptions,
)

__all__ = [
    "NewsletterExporter",
    "NewsletterGenerator",
    "MockRecordReader",
    "create_sample_childcare_records",
    "NewsletterRenderer",
    "TemplateEngine",
    "ChildProfile",
    "ChildcareRecord",
    "ChildcareRecordReader",
    "GenerateParams",
    "Newsletter",
    "NewsletterSection",
    "RegenerateParams",
    "RenderOptions",
]

__version__ = "0.1.0"