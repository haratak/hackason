import { VertexAI } from '@google-cloud/vertexai';
import { MediaAnalysis, ChildProfile, Timeline } from './types';

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export class VertexAIClient {
  private client: VertexAI;
  private model: any;
  private maxRetries = 5;  // リトライ回数を増やす
  private baseDelay = 3000;  // レート制限回避のため基本遅延を3秒に増加
  private lastApiCallTime = 0;  // 最後のAPI呼び出し時刻
  private minApiInterval = 2000;  // API呼び出し間の最小間隔（2秒）

  constructor(
    private projectId: string,
    private location: string
  ) {
    this.client = new VertexAI({
      project: projectId,
      location: location
    });

    // Gemini Pro Visionモデルを使用
    this.model = this.client.getGenerativeModel({
      model: 'gemini-1.5-flash',
    });
  }

  /**
   * 連絡帳のセクションコンテンツを生成
   */
  async generateSectionContent(
    sectionType: string,
    childProfile: ChildProfile,
    mediaAnalyses: MediaAnalysis[],
    timeline?: Timeline,
    customPrompt?: string
  ): Promise<string> {
    const prompt = this.buildPrompt(
      sectionType,
      childProfile,
      mediaAnalyses,
      timeline,
      customPrompt
    );

    return this.retryWithBackoff(async () => {
      const result = await this.model.generateContent(prompt);
      const response = result.response;
      return response.candidates[0].content.parts[0].text;
    }, 'generateSectionContent');
  }

  /**
   * 写真の選定とキャプション生成
   */
  async selectPhotoWithCaption(
    sectionType: string,
    mediaAnalyses: MediaAnalysis[],
    context: string
  ): Promise<{ mediaId: string; caption: string }> {
    const prompt = `
以下の写真・動画の分析結果から、「${sectionType}」セクションに最適な1枚を選んで、キャプションを生成してください。

コンテキスト: ${context}

分析結果:
${JSON.stringify(mediaAnalyses, null, 2)}

以下の形式で回答してください：
選択したメディアID: [media_id]
キャプション: [生成したキャプション]
`;

    try {
      const text = await this.retryWithBackoff(async () => {
        const result = await this.model.generateContent(prompt);
        const response = result.response;
        return response.candidates[0].content.parts[0].text;
      }, 'selectPhotoWithCaption');

      // レスポンスをパース（簡易実装）
      const mediaIdMatch = text.match(/選択したメディアID: (.+)/);
      const captionMatch = text.match(/キャプション: (.+)/);

      return {
        mediaId: mediaIdMatch?.[1] || mediaAnalyses[0].mediaId,
        caption: captionMatch?.[1] || ''
      };
    } catch (error) {
      console.error('Photo selection error:', error);
      // フォールバック
      return {
        mediaId: mediaAnalyses[0].mediaId,
        caption: ''
      };
    }
  }

  /**
   * コンテンツを再生成
   */
  async regenerateContent(
    originalContent: string,
    userPrompt: string
  ): Promise<string> {
    const prompt = `
以下の文章を、ユーザーからの指示に従って書き直してください。

【元の文章】
${originalContent}

【ユーザーからの指示】
${userPrompt}

保育士の温かい視点は保ちながら、指示に従った文章を生成してください。
文章のみを出力してください。`;

    return this.retryWithBackoff(async () => {
      const result = await this.model.generateContent(prompt);
      const response = result.response;
      return response.candidates[0].content.parts[0].text;
    }, 'regenerateContent');
  }

  /**
   * リトライロジック with exponential backoff
   */
  private async retryWithBackoff<T>(
    operation: () => Promise<T>,
    operationName: string
  ): Promise<T> {
    let lastError: any;
    
    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        // API呼び出し間隔を確保
        const now = Date.now();
        const timeSinceLastCall = now - this.lastApiCallTime;
        if (timeSinceLastCall < this.minApiInterval) {
          const waitTime = this.minApiInterval - timeSinceLastCall;
          console.log(`Waiting ${waitTime}ms before API call to avoid rate limit...`);
          await sleep(waitTime);
        }
        
        this.lastApiCallTime = Date.now();
        return await operation();
      } catch (error: any) {
        lastError = error;
        
        // 429エラー（レート制限）の場合のみリトライ
        if (error?.code === 429 || error?.status === 'RESOURCE_EXHAUSTED' || 
            (typeof error?.stackTrace === 'string' && error.stackTrace.includes('429')) || 
            error?.cause?.code === 429) {
          const delay = this.baseDelay * Math.pow(2, attempt) + Math.random() * 1000;  // ジッターを追加
          console.log(`Rate limit hit in ${operationName}, retrying in ${Math.round(delay)}ms... (attempt ${attempt + 1}/${this.maxRetries})`);
          await sleep(delay);
          continue;
        }
        
        // その他のエラーは即座に投げる
        console.error(`${operationName} error:`, error);
        throw error;
      }
    }
    
    // 最大リトライ回数に達した場合
    console.error(`${operationName} failed after ${this.maxRetries} attempts:`, lastError);
    throw lastError;
  }

  /**
   * プロンプトを構築
   */
  private buildPrompt(
    sectionType: string,
    childProfile: ChildProfile,
    mediaAnalyses: MediaAnalysis[],
    timeline?: Timeline,
    customPrompt?: string
  ): string {
    const ageText = `${childProfile.currentAge.years}歳${childProfile.currentAge.months}ヶ月`;

    let basePrompt = `
あなたは保育士の視点で、${childProfile.name}ちゃん（${ageText}）の成長記録を作成するアシスタントです。

【セクション】${sectionType}

【今週の写真・動画の分析結果】
${this.summarizeMediaAnalyses(mediaAnalyses)}

【過去の成長記録】
${timeline ? this.summarizeTimeline(timeline) : '初回のため過去データなし'}
`;

    if (customPrompt) {
      basePrompt += `\n【追加の指示】\n${customPrompt}`;
    }

    basePrompt += `

以下の点を考慮して、保護者が読んで嬉しくなるような文章を生成してください：
- 客観的でありながら温かみのある表現
- 具体的な成長の様子
- 年齢に応じた発達の視点
- 200文字程度で簡潔に

文章のみを出力してください。`;

    return basePrompt;
  }

  /**
   * メディア分析結果をサマライズ
   */
  private summarizeMediaAnalyses(mediaAnalyses: MediaAnalysis[]): string {
    return mediaAnalyses.map(media => {
      const expressions = media.expressions?.map(e => e.type).join(', ') || 'なし';
      const actions = media.actions?.map(a => a.type).join(', ') || 'なし';
      const objects = media.objects?.map(o => o.name).join(', ') || 'なし';

      return `
- ${media.type === 'photo' ? '写真' : '動画'} (${media.capturedAt.toLocaleDateString()})
  表情: ${expressions}
  動作: ${actions}
  物体: ${objects}
  ${media.videoSummary ? `サマリー: ${media.videoSummary}` : ''}`;
    }).join('\n');
  }

  /**
   * タイムラインをサマライズ
   */
  private summarizeTimeline(timeline: Timeline): string {
    const recentMilestones = timeline.milestones
      .slice(-5)
      .map(m => `- ${m.date.toLocaleDateString()}: ${m.description}`)
      .join('\n');

    const preferences = timeline.preferences
      .map(p => `- ${p.category}: ${p.items.join(', ')}`)
      .join('\n');

    return `
最近のマイルストーン:
${recentMilestones || 'なし'}

好み・興味:
${preferences || 'なし'}`;
  }
}
