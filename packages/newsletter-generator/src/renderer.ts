import puppeteer from 'puppeteer';
import { Newsletter, RenderOptions } from './types';
import { TemplateEngine } from './template-engine';
import * as fs from 'fs/promises';
import * as path from 'path';

export class NewsletterRenderer {
  private templateEngine: TemplateEngine;

  constructor() {
    this.templateEngine = new TemplateEngine();
  }

  /**
   * 連絡帳をPDFにレンダリング
   */
  async renderToPDF(
    newsletter: Newsletter,
    outputPath: string
  ): Promise<void> {
    const html = this.templateEngine.toHTML(newsletter);
    
    const browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    try {
      const page = await browser.newPage();
      
      // HTMLを設定
      await page.setContent(html, {
        waitUntil: 'networkidle0'
      });
      
      // A4サイズでPDF生成
      await page.pdf({
        path: outputPath,
        format: 'A4',
        printBackground: true,
        margin: {
          top: '20mm',
          right: '15mm',
          bottom: '20mm',
          left: '15mm'
        }
      });
    } finally {
      await browser.close();
    }
  }

  /**
   * 連絡帳を画像にレンダリング
   */
  async renderToImage(
    newsletter: Newsletter,
    outputPath: string,
    options: RenderOptions = { format: 'png' }
  ): Promise<void> {
    const html = this.templateEngine.toHTML(newsletter);
    
    const browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    try {
      const page = await browser.newPage();
      
      // ビューポートサイズを設定
      await page.setViewport({
        width: options.width || 1200,
        height: options.height || 1600,
        deviceScaleFactor: 2 // 高解像度
      });
      
      // HTMLを設定
      await page.setContent(html, {
        waitUntil: 'networkidle0'
      });
      
      // スクリーンショット撮影
      await page.screenshot({
        path: outputPath,
        type: options.format as 'png' | 'jpeg',
        quality: options.format === 'jpeg' ? (options.quality || 90) : undefined,
        fullPage: true
      });
    } finally {
      await browser.close();
    }
  }

  /**
   * 連絡帳をHTMLファイルとして保存
   */
  async renderToHTML(
    newsletter: Newsletter,
    outputPath: string
  ): Promise<void> {
    const html = this.templateEngine.toHTML(newsletter);
    await fs.writeFile(outputPath, html, 'utf-8');
  }

  /**
   * 複数形式で一括レンダリング
   */
  async renderAll(
    newsletter: Newsletter,
    outputDir: string,
    formats: ('pdf' | 'png' | 'html')[] = ['pdf', 'png', 'html']
  ): Promise<Record<string, string>> {
    // 出力ディレクトリを作成
    await fs.mkdir(outputDir, { recursive: true });
    
    const outputs: Record<string, string> = {};
    const baseFileName = `newsletter_${newsletter.id}`;
    
    for (const format of formats) {
      const outputPath = path.join(outputDir, `${baseFileName}.${format}`);
      
      switch (format) {
        case 'pdf':
          await this.renderToPDF(newsletter, outputPath);
          break;
        case 'png':
          await this.renderToImage(newsletter, outputPath, { format: 'png' });
          break;
        case 'html':
          await this.renderToHTML(newsletter, outputPath);
          break;
      }
      
      outputs[format] = outputPath;
    }
    
    return outputs;
  }
}