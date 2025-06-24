import { VertexAI } from '@google-cloud/vertexai';
import { ChildcareRecord, ChildProfile, Timeline } from './types';

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
    records: ChildcareRecord[],
    timeline?: Timeline,
    customPrompt?: string
  ): Promise<string> {
    const prompt = this.buildPrompt(
      sectionType,
      childProfile,
      records,
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
   * 育児記録からキャプションを生成
   */
  async generateCaption(
    record: ChildcareRecord,
    sectionType: string
  ): Promise<string> {
    const prompt = `
以下の育児記録から、「${sectionType}」セクションの写真キャプションを生成してください。

【育児記録】
活動: ${record.activity.type} - ${record.activity.description}
観察記録:
${record.observations.map(o => `- ${o}`).join('\n')}
${record.childState ? `\n子どもの様子:
- 気分: ${record.childState.mood || '不明'}
${record.childState.verbalExpressions ? `- 発した言葉: ${record.childState.verbalExpressions.join(', ')}` : ''}` : ''}

【指示】
- 15-25文字程度の簡潔なキャプション
- 記録の内容を要約し、温かみのある表現で
- 記録にない情報は追加しない

キャプションのみを出力してください。`;

    return this.retryWithBackoff(async () => {
      const result = await this.model.generateContent(prompt);
      const response = result.response;
      return response.candidates[0].content.parts[0].text.trim();
    }, 'generateCaption');
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
    records: ChildcareRecord[],
    timeline?: Timeline,
    customPrompt?: string
  ): string {
    const ageText = `${childProfile.currentAge.years}歳${childProfile.currentAge.months}ヶ月`;

    let basePrompt = `
あなたは保育士の視点で、${childProfile.name}ちゃん（${ageText}）の連絡帳を作成するアシスタントです。

【重要な指示】
- 提供された育児記録のみを使用して文章を作成してください
- 記録にない情報を創作したり、推測したりしないでください
- 記録の内容を要約し、保護者に伝わりやすい形で表現してください

【セクション】${sectionType}

【育児記録】
${this.summarizeChildcareRecords(records)}

【過去の成長記録】
${timeline ? this.summarizeTimeline(timeline) : '初回のため過去データなし'}
`;

    if (customPrompt) {
      basePrompt += `\n【追加の指示】\n${customPrompt}`;
    }

    basePrompt += `

以下の点を考慮して、保護者が読んで嬉しくなるような文章を生成してください：
- 記録に基づいた事実のみを記載
- 客観的でありながら温かみのある表現
- 具体的な成長の様子（記録から読み取れる範囲で）
- 年齢に応じた発達の視点
- 200文字程度で簡潔に

文章のみを出力してください。`;

    return basePrompt;
  }

  /**
   * 育児記録をサマライズ
   */
  private summarizeChildcareRecords(records: ChildcareRecord[]): string {
    if (records.length === 0) {
      return '記録なし';
    }

    return records.map((record, index) => {
      const date = new Date(record.timestamp);
      const dateStr = `${date.getMonth() + 1}月${date.getDate()}日`;
      
      return `
【記録${index + 1}】${dateStr} - ${record.activity.type}
活動内容: ${record.activity.description}
観察記録:
${record.observations.map(o => `  - ${o}`).join('\n')}
${record.childState ? `子どもの様子:
  - 気分: ${record.childState.mood || '記録なし'}
${record.childState.verbalExpressions?.length ? `  - 発した言葉: ${record.childState.verbalExpressions.join(', ')}` : ''}
${record.childState.interactions?.length ? `  - 他児との関わり: ${record.childState.interactions.join(', ')}` : ''}` : ''}`;
    }).join('\n\n');
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
