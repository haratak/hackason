import { TemplateEngine } from '../template-engine';
import type { Newsletter, NewsletterSection } from '../types';

describe('TemplateEngine', () => {
  let engine: TemplateEngine;

  beforeEach(() => {
    engine = new TemplateEngine();
  });

  describe('toHTML', () => {
    it('連絡帳を正しくHTMLに変換できる', () => {
      const newsletter = createTestNewsletter();
      
      const html = engine.toHTML(newsletter);
      
      // 基本的な構造を確認
      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('<html lang="ja">');
      expect(html).toContain(newsletter.title);
      
      // 各セクションが含まれていることを確認
      newsletter.sections.forEach(section => {
        expect(html).toContain(section.title);
        if (section.content.text) {
          expect(html).toContain(section.content.text);
        }
      });
    });

    it('期間を正しくフォーマットできる', () => {
      const newsletter = createTestNewsletter();
      
      const html = engine.toHTML(newsletter);
      
      expect(html).toContain('2024年1月1日 ～ 2024年1月31日');
    });

    it('各セクションタイプが正しくレンダリングされる', () => {
      const newsletter = createTestNewsletter();
      
      const html = engine.toHTML(newsletter);
      
      // photo-with-text セクション
      expect(html).toContain('section photo-with-text');
      expect(html).toContain('<img src="photo1.jpg"');
      
      // text-only セクション
      expect(html).toContain('section text-only');
      
      // photo-caption セクション
      expect(html).toContain('section photo-caption');
      expect(html).toContain('<p class="caption">素敵な笑顔</p>');
    });

    it('レスポンシブデザインのスタイルが含まれる', () => {
      const newsletter = createTestNewsletter();
      
      const html = engine.toHTML(newsletter);
      
      expect(html).toContain('@media (max-width: 600px)');
      expect(html).toContain('grid-template-columns: 1fr');
    });

    it('印刷用のスタイルが含まれる', () => {
      const newsletter = createTestNewsletter();
      
      const html = engine.toHTML(newsletter);
      
      expect(html).toContain('@media print');
    });
  });
});

// テスト用の連絡帳データを作成
function createTestNewsletter(): Newsletter {
  const sections: NewsletterSection[] = [
    {
      id: 'section-1',
      title: '今週の興味',
      type: 'photo-with-text',
      content: {
        text: 'ブロック遊びに夢中でした',
        photoUrl: 'photo1.jpg',
        photoDescription: 'ブロックで遊ぶ様子'
      },
      order: 1
    },
    {
      id: 'section-2',
      title: '行った場所',
      type: 'text-only',
      content: {
        text: '公園でたくさん遊びました'
      },
      order: 2
    },
    {
      id: 'section-3',
      title: '今週のベストショット',
      type: 'photo-caption',
      content: {
        photoUrl: 'photo2.jpg',
        caption: '素敵な笑顔'
      },
      order: 3
    }
  ];

  return {
    id: 'newsletter-001',
    childId: 'child-123',
    period: {
      start: new Date('2024-01-01'),
      end: new Date('2024-01-31')
    },
    generatedAt: new Date(),
    version: 1,
    title: '太郎ちゃんの1月の成長記録',
    sections,
    usedMediaIds: ['media-001', 'media-002']
  };
}