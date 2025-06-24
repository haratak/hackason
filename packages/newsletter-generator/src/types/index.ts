// 基本的な型定義

// 子供のプロファイル
export interface ChildProfile {
  id: string;
  name: string;
  birthDate: Date;
  gender?: 'male' | 'female' | 'other';
  currentAge: {
    years: number;
    months: number;
  };
}

// 育児記録
export interface ChildcareRecord {
  id: string;
  timestamp: string; // ISO 8601形式
  childId: string;
  recordedBy?: string; // 記録者（保育士名）
  
  // 活動情報
  activity: {
    type: string; // "自由遊び", "お散歩", "給食" など
    description: string;
    duration?: number; // 分単位
    location?: string; // "園庭", "保育室" など
  };
  
  // 観察記録（事実のみ）
  observations: string[];
  
  // 子どもの様子
  childState?: {
    mood?: string; // "楽しそう", "集中していた" など
    interactions?: string[]; // 他の子との関わり
    verbalExpressions?: string[]; // 発した言葉
  };
  
  // メタ情報
  mediaId?: string; // 関連する写真・動画ID
  tags: string[]; // 検索用タグ
}

// 育児記録リーダーインターフェース
export interface ChildcareRecordReader {
  // 記録を検索
  searchRecords(params: {
    childId: string;
    dateRange: {
      start: Date;
      end: Date;
    };
    query?: string;
    tags?: string[];
    limit?: number;
  }): Promise<ChildcareRecord[]>;
  
  // 特定の記録を取得
  getRecordsByIds(recordIds: string[]): Promise<ChildcareRecord[]>;
  
  // 特定の活動タイプで検索
  getRecordsByActivityType(
    childId: string,
    activityType: string,
    dateRange: { start: Date; end: Date }
  ): Promise<ChildcareRecord[]>;
}

// メディア分析結果
export interface MediaAnalysis {
  mediaId: string;
  filePath: string;
  type: 'photo' | 'video';
  capturedAt: Date;
  
  // 分析結果
  expressions?: Expression[];
  actions?: Action[];
  objects?: DetectedObject[];
  
  // 動画の場合のサマリー
  videoSummary?: string;
  importantScenes?: Scene[];
}

export interface Expression {
  type: 'smile' | 'cry' | 'surprise' | 'neutral' | 'laugh';
  confidence: number;
  timestamp?: number; // 動画の場合
}

export interface Action {
  type: string; // 'sitting', 'standing', 'walking', 'crawling', etc.
  confidence: number;
  timestamp?: number;
}

export interface DetectedObject {
  name: string;
  category: string;
  confidence: number;
  boundingBox?: BoundingBox;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Scene {
  startTime: number;
  endTime: number;
  description: string;
  significance: 'high' | 'medium' | 'low';
}

// タイムライン情報
export interface Timeline {
  childId: string;
  milestones: Milestone[];
  preferences: Preference[];
  lastUpdated: Date;
}

export interface Milestone {
  id: string;
  type: string;
  date: Date;
  description: string;
  mediaIds: string[];
}

export interface Preference {
  category: string;
  items: string[];
  lastObserved: Date;
}

// 連絡帳生成パラメータ
export interface GenerateParams {
  childProfile: ChildProfile;
  period: {
    start: Date;
    end: Date;
  };
  recordReader: ChildcareRecordReader; // 育児記録リーダー
  timeline?: Timeline;
  layout?: NewsletterLayout; // レイアウト設定
  customPrompt?: string;
}

// 連絡帳テンプレート
export interface NewsletterTemplate {
  title: string;
  sections: Section[];
}

export interface Section {
  id: string;
  title: string;
  type: 'photo-with-text' | 'text-only' | 'photo-caption';
  order: number;
}

// 生成された連絡帳
export interface Newsletter {
  id: string;
  childId: string;
  period: {
    start: Date;
    end: Date;
  };
  generatedAt: Date;
  version: number;
  
  // コンテンツ
  title: string;
  sections: NewsletterSection[];
  
  // メタデータ
  usedMediaIds: string[];
  generationPrompt?: string;
  metadata?: Record<string, any>;
}

export interface NewsletterSection {
  id: string;
  title: string;
  type: string;
  content: SectionContent;
  order: number;
  metadata?: any;
}

export interface SectionContent {
  text?: string;
  photoUrl?: string;
  photoDescription?: string;
  caption?: string;
  metadata?: {
    recordCount: number;
    recordIds?: string[];
    selectedRecordId?: string;
  };
}

// 再生成パラメータ
export interface RegenerateParams {
  newsletter: Newsletter;
  prompt: string;
  sectionsToRegenerate?: string[]; // 特定のセクションのみ再生成
}

// レンダリングオプション
export interface RenderOptions {
  format: 'pdf' | 'png' | 'jpeg';
  quality?: number;
  width?: number;
  height?: number;
}

// レイアウト設定
export interface NewsletterLayout {
  id: string;
  name: string;
  sections: NewsletterSectionConfig[];
}

export interface NewsletterSectionConfig {
  id: string;
  type: string;
  title?: string;
  order: number;
}

// エラー型
export class NewsletterGenerationError extends Error {
  constructor(
    message: string,
    public code: string,
    public details?: any
  ) {
    super(message);
    this.name = 'NewsletterGenerationError';
  }
}