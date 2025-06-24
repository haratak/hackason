import { Newsletter, NewsletterSection } from './types';

export class TemplateEngine {
  /**
   * 連絡帳をHTMLに変換
   */
  toHTML(newsletter: Newsletter): string {
    const sectionsHTML = newsletter.sections
      .sort((a, b) => a.order - b.order)
      .map(section => this.renderSection(section))
      .join('\n');

    return `
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${newsletter.title}</title>
  <style>
    ${this.getStyles()}
  </style>
</head>
<body>
  <div class="newsletter">
    <header class="header">
      <h1 class="title">${newsletter.title}</h1>
      <div class="divider"></div>
      <p class="date">${this.formatPeriod(newsletter.period)}</p>
      <div class="divider"></div>
    </header>
    
    <main class="content">
      ${sectionsHTML}
    </main>
  </div>
</body>
</html>`;
  }

  /**
   * セクションをレンダリング
   */
  private renderSection(section: NewsletterSection): string {
    switch (section.type) {
      case 'photo-with-text':
        return this.renderPhotoWithText(section);
      case 'text-only':
        return this.renderTextOnly(section);
      case 'photo-caption':
        return this.renderPhotoCaption(section);
      default:
        return '';
    }
  }

  /**
   * 写真付きテキストセクション
   */
  private renderPhotoWithText(section: NewsletterSection): string {
    return `
    <section class="section photo-with-text">
      <h2 class="section-title">${section.title}</h2>
      ${section.content.photoUrl ? `
        <div class="photo-container">
          <img src="${section.content.photoUrl}" alt="${section.content.photoDescription || ''}" />
        </div>
      ` : ''}
      ${section.content.text ? `
        <p class="section-text">${section.content.text}</p>
      ` : ''}
    </section>`;
  }

  /**
   * テキストのみセクション
   */
  private renderTextOnly(section: NewsletterSection): string {
    return `
    <section class="section text-only">
      <h2 class="section-title">${section.title}</h2>
      ${section.content.text ? `
        <p class="section-text">${section.content.text}</p>
      ` : ''}
    </section>`;
  }

  /**
   * 写真＋キャプションセクション
   */
  private renderPhotoCaption(section: NewsletterSection): string {
    return `
    <section class="section photo-caption">
      <h2 class="section-title">${section.title}</h2>
      ${section.content.photoUrl ? `
        <div class="photo-container">
          <img src="${section.content.photoUrl}" alt="${section.content.photoDescription || ''}" />
          ${section.content.caption ? `
            <p class="caption">${section.content.caption}</p>
          ` : ''}
        </div>
      ` : ''}
    </section>`;
  }

  /**
   * 期間をフォーマット
   */
  private formatPeriod(period: { start: Date; end: Date }): string {
    const options: Intl.DateTimeFormatOptions = {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    };
    const start = period.start.toLocaleDateString('ja-JP', options);
    const end = period.end.toLocaleDateString('ja-JP', options);
    return `${start} ～ ${end}`;
  }

  /**
   * CSSスタイル
   */
  private getStyles(): string {
    return `
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }

      body {
        font-family: 'Hiragino Kaku Gothic ProN', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
        line-height: 1.8;
        color: #333;
        background-color: #f5f5f5;
      }

      .newsletter {
        max-width: 800px;
        margin: 0 auto;
        background-color: white;
        min-height: 100vh;
      }

      .header {
        text-align: center;
        padding: 40px 20px;
      }

      .title {
        font-size: 32px;
        font-weight: bold;
        margin-bottom: 20px;
        letter-spacing: 0.05em;
      }

      .divider {
        height: 2px;
        background-color: #333;
        margin: 20px auto;
        width: 80%;
      }

      .date {
        font-size: 16px;
        color: #666;
      }

      .content {
        padding: 20px;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 30px;
      }

      .section {
        break-inside: avoid;
      }

      .section.text-only {
        grid-column: span 1;
      }

      .section.photo-with-text {
        grid-column: span 1;
      }

      .section.photo-caption {
        grid-column: span 1;
      }

      .section-title {
        font-size: 20px;
        font-weight: bold;
        margin-bottom: 15px;
        padding-bottom: 5px;
        border-bottom: 1px solid #ddd;
      }

      .section-text {
        font-size: 14px;
        line-height: 1.8;
        text-align: justify;
      }

      .photo-container {
        margin: 15px 0;
      }

      .photo-container img {
        width: 100%;
        height: auto;
        filter: grayscale(100%);
        border: 1px solid #ddd;
      }

      .caption {
        font-size: 12px;
        color: #666;
        text-align: center;
        margin-top: 8px;
      }

      @media print {
        body {
          background-color: white;
        }
        
        .newsletter {
          max-width: 100%;
        }
      }

      @media (max-width: 600px) {
        .content {
          grid-template-columns: 1fr;
        }
        
        .section {
          grid-column: span 1 !important;
        }
      }
    `;
  }
}