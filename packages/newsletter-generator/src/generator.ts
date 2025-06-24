import {
  GenerateParams,
  Newsletter,
  NewsletterSection,
  NewsletterSectionConfig,
  NewsletterLayout,
  SectionContent,
  RegenerateParams,
  NewsletterGenerationError,
  ChildcareRecord,
  Timeline
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
      // 1. セクションごとのコンテンツを生成
      const sections = await this.generateSections(params);
      
      // 2. 使用した記録のメディアIDを収集
      const usedMediaIds = await this.collectUsedMediaIds(params, sections);
      
      // 3. 連絡帳オブジェクトを構築
      const newsletter: Newsletter = {
        id: this.generateId(),
        childId: params.childProfile.id,
        period: params.period,
        generatedAt: new Date(),
        version: 1,
        title: this.generateTitle(params),
        sections,
        usedMediaIds,
        generationPrompt: params.customPrompt,
        metadata: {
          childAge: params.childProfile.currentAge,
          recordCount: sections.reduce((acc, section) => 
            acc + (section.metadata?.recordCount || 0), 0
          )
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
   * セクションを生成
   */
  private async generateSections(
    params: GenerateParams
  ): Promise<NewsletterSection[]> {
    // レイアウト設定を取得
    const layout = params.layout || this.getDefaultLayout();
    const sections: NewsletterSection[] = [];
    
    for (let i = 0; i < layout.sections.length; i++) {
      const config = layout.sections[i];
      
      // セクション間に遅延を追加してレート制限を回避
      if (i > 0) {
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
      
      const content = await this.generateSectionContent(
        config,
        params
      );
      
      sections.push({
        id: config.id,
        type: config.type,
        title: config.title || this.getSectionTitle(config.type),
        content,
        order: config.order,
        metadata: content.metadata
      });
    }

    return sections;
  }

  /**
   * セクションのコンテンツを生成
   */
  private async generateSectionContent(
    config: NewsletterSectionConfig,
    params: GenerateParams
  ): Promise<SectionContent> {
    // セクションタイプに応じた検索クエリを構築
    const searchQuery = this.buildSearchQuery(config.type);
    
    // 育児記録を検索
    const records = await params.recordReader.searchRecords({
      childId: params.childProfile.id,
      dateRange: params.period,
      query: searchQuery,
      tags: this.getSearchTags(config.type),
      limit: 30
    });
    
    // 記録がない場合の処理
    if (records.length === 0) {
      return this.generateEmptyContent(config.type);
    }
    
    // セクションタイプに応じたコンテンツ生成
    switch (config.type) {
      case 'overview':
      case 'activities':
      case 'places-visited':
      case 'development': {
        // テキストのみのセクション
        const text = await this.vertexAI.generateSectionContent(
          config.type,
          params.childProfile,
          records,
          params.timeline,
          this.getSectionInstruction(config.type)
        );
        
        return {
          text,
          metadata: {
            recordCount: records.length,
            recordIds: records.map(r => r.id)
          }
        };
      }
      
      case 'favorite-play':
      case 'growth-moment': {
        // 写真＋説明のセクション
        const text = await this.vertexAI.generateSectionContent(
          config.type,
          params.childProfile,
          records,
          params.timeline,
          this.getSectionInstruction(config.type)
        );
        
        // 最も関連性の高い記録の写真を選択
        const selectedRecord = this.selectBestRecord(records, config.type);
        
        return {
          text,
          photoUrl: selectedRecord?.mediaId ? 
            `gs://bucket/photos/${selectedRecord.mediaId}.jpg` : 'placeholder.jpg',
          photoDescription: selectedRecord?.activity.description || '',
          metadata: {
            recordCount: records.length,
            recordIds: records.map(r => r.id),
            selectedRecordId: selectedRecord?.id
          }
        };
      }
      
      case 'first-time':
      case 'best-shot': {
        // 写真＋キャプションのセクション
        const selectedRecord = this.selectBestRecord(records, config.type);
        
        if (!selectedRecord) {
          return {
            photoUrl: 'placeholder.jpg',
            caption: '素敵な瞬間',
            metadata: { recordCount: 0 }
          };
        }
        
        // 記録からキャプションを生成
        const caption = await this.vertexAI.generateCaption(
          selectedRecord,
          config.type
        );
        
        return {
          photoUrl: selectedRecord.mediaId ? 
            `gs://bucket/photos/${selectedRecord.mediaId}.jpg` : 'placeholder.jpg',
          caption,
          metadata: {
            recordCount: records.length,
            recordIds: records.map(r => r.id),
            selectedRecordId: selectedRecord.id
          }
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
   * 使用したメディアIDを収集
   */
  private async collectUsedMediaIds(
    params: GenerateParams,
    sections: NewsletterSection[]
  ): Promise<string[]> {
    const mediaIds: string[] = [];
    
    for (const section of sections) {
      if (section.metadata?.selectedRecordId) {
        const records = await params.recordReader.getRecordsByIds([section.metadata.selectedRecordId]);
        if (records[0]?.mediaId) {
          mediaIds.push(records[0].mediaId);
        }
      }
    }
    
    return [...new Set(mediaIds)]; // 重複を除去
  }

  /**
   * IDを生成
   */
  private generateId(): string {
    return `newsletter_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * セクションタイプに応じた検索クエリを構築
   */
  private buildSearchQuery(sectionType: string): string {
    const queryMap: Record<string, string> = {
      'overview': '',
      'activities': '活動 遊び',
      'favorite-play': '遊び 楽しい 好き',
      'growth-moment': '成長 できた 初めて',
      'places-visited': '場所 お散歩 外出',
      'first-time': '初めて 新しい 挑戦',
      'development': 'できた 成長 発達',
      'best-shot': '笑顔 楽しい 素敵'
    };
    return queryMap[sectionType] || '';
  }

  /**
   * セクションタイプに応じた検索タグを取得
   */
  private getSearchTags(sectionType: string): string[] {
    const tagMap: Record<string, string[]> = {
      'overview': [],
      'activities': ['遊び', '活動'],
      'favorite-play': ['遊び', '楽しい'],
      'growth-moment': ['成長', '達成感'],
      'places-visited': ['お散歩', '外出'],
      'first-time': ['初めて', '新しい'],
      'development': ['成長', '発達'],
      'best-shot': ['笑顔', '楽しい']
    };
    return tagMap[sectionType] || [];
  }

  /**
   * セクションタイプに応じた生成指示を取得
   */
  private getSectionInstruction(sectionType: string): string {
    const instructionMap: Record<string, string> = {
      'overview': '今週の全体的な様子を要約してください。提供された記録のみを使用し、新しい情報を追加しないでください。',
      'activities': '今週行った活動について、記録から抽出して記述してください。',
      'favorite-play': '子どもが特に楽しんでいた遊びについて、具体的な様子を記録から記述してください。',
      'growth-moment': '成長が見られた瞬間について、記録から具体的に記述してください。',
      'places-visited': '訪れた場所について、記録に基づいて記述してください。',
      'first-time': '初めての体験について、記録から抽出して記述してください。',
      'development': 'できるようになったことについて、記録から具体的に記述してください。',
      'best-shot': '素敵な瞬間について簡潔に記述してください。'
    };
    return instructionMap[sectionType] || '記録に基づいて記述してください。';
  }

  /**
   * 最適な記録を選択
   */
  private selectBestRecord(records: ChildcareRecord[], sectionType: string): ChildcareRecord | undefined {
    if (records.length === 0) return undefined;
    
    // セクションタイプに応じた優先順位で選択
    if (sectionType === 'first-time') {
      // "初めて"タグがある記録を優先
      const firstTimeRecord = records.find(r => r.tags.includes('初めて'));
      if (firstTimeRecord) return firstTimeRecord;
    }
    
    if (sectionType === 'best-shot') {
      // "笑顔"タグがある記録を優先
      const smileRecord = records.find(r => r.tags.includes('笑顔'));
      if (smileRecord) return smileRecord;
    }
    
    // メディアIDがある記録を優先
    const withMedia = records.filter(r => r.mediaId);
    if (withMedia.length > 0) return withMedia[0];
    
    // 最新の記録を返す
    return records[0];
  }

  /**
   * 空のコンテンツを生成
   */
  private generateEmptyContent(sectionType: string): SectionContent {
    const emptyContentMap: Record<string, SectionContent> = {
      'overview': { text: '今週の記録はありません。' },
      'activities': { text: '今週の活動記録はありません。' },
      'favorite-play': {
        text: '今週の遊びの記録はありません。',
        photoUrl: 'placeholder.jpg',
        photoDescription: ''
      },
      'growth-moment': {
        text: '今週の成長記録はありません。',
        photoUrl: 'placeholder.jpg',
        photoDescription: ''
      },
      'places-visited': { text: '今週の外出記録はありません。' },
      'first-time': {
        photoUrl: 'placeholder.jpg',
        caption: '新しい体験の記録はありません。'
      },
      'development': { text: '今週の発達記録はありません。' },
      'best-shot': {
        photoUrl: 'placeholder.jpg',
        caption: '今週の写真記録はありません。'
      }
    };
    
    return {
      ...emptyContentMap[sectionType],
      metadata: { recordCount: 0 }
    };
  }

  /**
   * セクションタイトルを取得
   */
  private getSectionTitle(sectionType: string): string {
    const titleMap: Record<string, string> = {
      'overview': '今週の様子',
      'activities': '今週の活動',
      'favorite-play': 'お気に入りの遊び',
      'growth-moment': '成長の瞬間',
      'places-visited': '行った場所',
      'first-time': '初めての体験',
      'development': 'できるようになったこと',
      'best-shot': '今週のベストショット'
    };
    return titleMap[sectionType] || sectionType;
  }

  /**
   * デフォルトレイアウトを取得
   */
  private getDefaultLayout(): NewsletterLayout {
    return {
      id: 'default',
      name: 'デフォルトレイアウト',
      sections: [
        { id: 'sec-1', type: 'overview', order: 1 },
        { id: 'sec-2', type: 'activities', order: 2 },
        { id: 'sec-3', type: 'favorite-play', order: 3 },
        { id: 'sec-4', type: 'first-time', order: 4 },
        { id: 'sec-5', type: 'best-shot', order: 5 }
      ]
    };
  }
}