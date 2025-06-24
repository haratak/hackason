import {
  GenerateParams,
  Newsletter,
  NewsletterSection,
  RegenerateParams,
  NewsletterGenerationError,
  MediaAnalysis,
  Timeline,
  DetectedObject
} from './types';
import { VertexAIClient } from './vertex-ai-client';
import { TemplateEngine } from './template-engine';
import { format } from 'date-fns';
import { ja } from 'date-fns/locale';

export class NewsletterGenerator {
  private vertexAI: VertexAIClient;
  private templateEngine: TemplateEngine;

  constructor(
    private projectId: string,
    private location: string = 'asia-northeast1'
  ) {
    this.vertexAI = new VertexAIClient(projectId, location);
    this.templateEngine = new TemplateEngine();
  }

  /**
   * 連絡帳を生成する
   */
  async generate(params: GenerateParams): Promise<Newsletter> {
    try {
      // 1. 期間内のメディアを整理
      const organizedMedia = this.organizeMediaByDate(params.mediaAnalyses);
      
      // 2. 重要なイベントを抽出
      const highlights = await this.extractHighlights(
        params.mediaAnalyses,
        params.timeline
      );
      
      // 3. セクションごとのコンテンツを生成
      const sections = await this.generateSections(
        params,
        organizedMedia,
        highlights
      );
      
      // 4. 連絡帳オブジェクトを構築
      const newsletter: Newsletter = {
        id: this.generateId(),
        childId: params.childProfile.id,
        period: params.period,
        generatedAt: new Date(),
        version: 1,
        title: this.generateTitle(params),
        sections,
        usedMediaIds: this.extractUsedMediaIds(sections, params.mediaAnalyses),
        generationPrompt: params.customPrompt,
        metadata: {
          childAge: params.childProfile.currentAge,
          mediaCount: params.mediaAnalyses.length
        }
      };

      return newsletter;
    } catch (error) {
      throw new NewsletterGenerationError(
        '連絡帳の生成に失敗しました',
        'GENERATION_FAILED',
        error
      );
    }
  }

  /**
   * 連絡帳を再生成する
   */
  async regenerate(params: RegenerateParams): Promise<Newsletter> {
    try {
      const { newsletter, prompt, sectionsToRegenerate } = params;
      
      // 再生成するセクションを決定
      const targetSections = sectionsToRegenerate || newsletter.sections.map(s => s.id);
      
      // セクションごとに再生成（順次実行でレート制限を回避）
      const regeneratedSections: NewsletterSection[] = [];
      
      for (let i = 0; i < newsletter.sections.length; i++) {
        const section = newsletter.sections[i];
        
        if (targetSections.includes(section.id)) {
          // API呼び出し間に遅延を追加
          if (regeneratedSections.length > 0) {
            await new Promise(resolve => setTimeout(resolve, 3000));
          }
          
          const regenerated = await this.regenerateSection(section, prompt);
          regeneratedSections.push(regenerated);
        } else {
          regeneratedSections.push(section);
        }
      }

      // 新しいバージョンの連絡帳を作成
      return {
        ...newsletter,
        version: newsletter.version + 1,
        generatedAt: new Date(),
        sections: regeneratedSections,
        generationPrompt: prompt
      };
    } catch (error) {
      throw new NewsletterGenerationError(
        '連絡帳の再生成に失敗しました',
        'REGENERATION_FAILED',
        error
      );
    }
  }

  /**
   * メディアを日付ごとに整理
   */
  private organizeMediaByDate(mediaAnalyses: MediaAnalysis[]): Map<string, MediaAnalysis[]> {
    const organized = new Map<string, MediaAnalysis[]>();
    
    mediaAnalyses.forEach(media => {
      const dateKey = format(media.capturedAt, 'yyyy-MM-dd');
      const existing = organized.get(dateKey) || [];
      organized.set(dateKey, [...existing, media]);
    });
    
    return organized;
  }

  /**
   * ハイライトを抽出
   */
  private async extractHighlights(
    mediaAnalyses: MediaAnalysis[],
    timeline?: Timeline
  ): Promise<any[]> {
    const highlights = [];
    
    // 笑顔が多い写真を抽出
    const smilingPhotos = mediaAnalyses
      .filter(m => m.expressions?.some(e => 
        (e.type === 'smile' || e.type === 'laugh') && e.confidence > 0.8
      ))
      .sort((a, b) => {
        const aMaxConfidence = Math.max(...(a.expressions?.map(e => e.confidence) || [0]));
        const bMaxConfidence = Math.max(...(b.expressions?.map(e => e.confidence) || [0]));
        return bMaxConfidence - aMaxConfidence;
      });
    
    if (smilingPhotos.length > 0) {
      highlights.push({
        type: 'best_smile',
        media: smilingPhotos[0],
        reason: '最高の笑顔'
      });
    }
    
    // 新しい動作を検出
    if (timeline) {
      const existingActions = new Set(
        timeline.milestones.map(m => m.type)
      );
      
      const newActions = mediaAnalyses
        .filter(m => m.actions?.some(a => 
          a.confidence > 0.85 && !existingActions.has(a.type)
        ));
      
      if (newActions.length > 0) {
        highlights.push({
          type: 'new_action',
          media: newActions[0],
          reason: '新しい動作の発見'
        });
      }
    }
    
    // 重要なシーンがある動画
    const importantVideos = mediaAnalyses
      .filter(m => m.type === 'video' && 
        m.importantScenes?.some(s => s.significance === 'high')
      );
    
    importantVideos.forEach(video => {
      highlights.push({
        type: 'important_moment',
        media: video,
        reason: video.importantScenes?.[0].description || '重要な瞬間'
      });
    });
    
    return highlights;
  }

  /**
   * セクションを生成
   */
  private async generateSections(
    params: GenerateParams,
    organizedMedia: Map<string, MediaAnalysis[]>,
    highlights: any[]
  ): Promise<NewsletterSection[]> {
    // デフォルトのセクション構成
    const sectionConfigs = [
      { id: 'weekly-interest', title: '今週の興味', type: 'photo-with-text' as const },
      { id: 'places-visited', title: '行った場所', type: 'text-only' as const },
      { id: 'first-time', title: '初めての体験', type: 'photo-caption' as const },
      { id: 'development', title: 'できるようになったこと', type: 'text-only' as const },
      { id: 'best-shot', title: '今週のベストショット', type: 'photo-caption' as const }
    ];

    const sections: NewsletterSection[] = [];
    
    for (let i = 0; i < sectionConfigs.length; i++) {
      const config = sectionConfigs[i];
      
      // セクション間に遅延を追加してレート制限を回避
      if (i > 0) {
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
      
      const content = await this.generateSectionContent(
        config,
        params,
        organizedMedia,
        highlights
      );
      
      sections.push({
        ...config,
        content,
        order: i + 1
      });
    }

    return sections;
  }

  /**
   * セクションのコンテンツを生成
   */
  private async generateSectionContent(
    config: any,
    params: GenerateParams,
    organizedMedia: Map<string, MediaAnalysis[]>,
    highlights: any[]
  ): Promise<any> {
    const allMedia = Array.from(organizedMedia.values()).flat();
    
    switch (config.id) {
      case 'weekly-interest': {
        // 今週の興味 - 物体認識から興味を分析
        const objectsDetected = allMedia
          .flatMap(m => m.objects || [])
          .filter(o => o.confidence > 0.8);
        
        const text = await this.vertexAI.generateSectionContent(
          config.title,
          params.childProfile,
          allMedia,
          params.timeline,
          '子供が興味を持った物や遊びについて、具体的なエピソードを交えて書いてください。'
        );
        
        // 最も多く検出された物体の写真を選択
        const mostFrequentObject = this.getMostFrequentObject(objectsDetected);
        const selectedMedia = allMedia.find(m => 
          m.objects?.some(o => o.name === mostFrequentObject)
        );
        
        return {
          text,
          photoUrl: selectedMedia?.filePath || 'placeholder.jpg',
          photoDescription: `${mostFrequentObject}で遊ぶ様子`
        };
      }
      
      case 'places-visited': {
        // 行った場所 - メタデータやシーンから場所を推測
        const text = await this.vertexAI.generateSectionContent(
          config.title,
          params.childProfile,
          allMedia,
          params.timeline,
          '写真や動画から推測される場所（公園、自宅、外出先など）について書いてください。'
        );
        
        return { text };
      }
      
      case 'first-time': {
        // 初めての体験
        const firstTimeHighlight = highlights.find(h => h.type === 'new_action');
        
        if (firstTimeHighlight) {
          // 写真選定をスキップして、ハイライトの理由をそのまま使用
          return {
            photoUrl: firstTimeHighlight.media.filePath,
            caption: firstTimeHighlight.reason
          };
        }
        
        // ハイライトがない場合は最新の写真を使用
        const latestMedia = allMedia[allMedia.length - 1];
        return {
          photoUrl: latestMedia?.filePath || 'placeholder.jpg',
          caption: '新しい発見の毎日'
        };
      }
      
      case 'development': {
        // できるようになったこと
        const text = await this.vertexAI.generateSectionContent(
          config.title,
          params.childProfile,
          allMedia,
          params.timeline,
          '動作認識の結果から、できるようになったことや成長の様子を具体的に書いてください。'
        );
        
        return { text };
      }
      
      case 'best-shot': {
        // 今週のベストショット
        const bestSmile = highlights.find(h => h.type === 'best_smile');
        const bestMedia = bestSmile?.media || allMedia[0];
        
        if (bestMedia) {
          // 写真選定をスキップして、事前に決められたキャプションを使用
          return {
            photoUrl: bestMedia.filePath,
            caption: bestSmile?.reason || '今週の素敵な笑顔'
          };
        }
        
        return {
          photoUrl: 'placeholder.jpg',
          caption: '素敵な瞬間'
        };
      }
      
      default:
        return {
          text: `${config.title}の内容`,
          photoUrl: 'placeholder.jpg',
          caption: 'キャプション'
        };
    }
  }
  
  /**
   * 最も頻出する物体を取得
   */
  private getMostFrequentObject(objects: DetectedObject[]): string {
    const frequency = objects.reduce((acc, obj) => {
      acc[obj.name] = (acc[obj.name] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    return Object.entries(frequency)
      .sort(([, a], [, b]) => b - a)[0]?.[0] || 'toy';
  }

  /**
   * セクションを再生成
   */
  private async regenerateSection(
    section: NewsletterSection,
    prompt: string
  ): Promise<NewsletterSection> {
    // テキストコンテンツがある場合のみ再生成
    if (section.content.text) {
      const regeneratedText = await this.vertexAI.regenerateContent(
        section.content.text,
        prompt
      );
      
      return {
        ...section,
        content: {
          ...section.content,
          text: regeneratedText
        }
      };
    }
    
    return section;
  }

  /**
   * タイトルを生成
   */
  private generateTitle(params: GenerateParams): string {
    const monthStr = format(params.period.start, 'M月', { locale: ja });
    return `${params.childProfile.name}ちゃんの${monthStr}の成長記録`;
  }

  /**
   * 使用したメディアIDを抽出
   */
  private extractUsedMediaIds(
    sections: NewsletterSection[],
    mediaAnalyses: MediaAnalysis[]
  ): string[] {
    const usedPaths = sections
      .map(s => s.content.photoUrl)
      .filter(url => url && url !== 'placeholder.jpg');
    
    return mediaAnalyses
      .filter(m => usedPaths.includes(m.filePath))
      .map(m => m.mediaId);
  }

  /**
   * IDを生成
   */
  private generateId(): string {
    return `newsletter_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}