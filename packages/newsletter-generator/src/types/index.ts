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
  mediaAnalyses: MediaAnalysis[];
  timeline?: Timeline;
  template?: NewsletterTemplate;
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
  type: 'photo-with-text' | 'text-only' | 'photo-caption';
  content: {
    text?: string;
    photoUrl?: string;
    photoDescription?: string;
    caption?: string;
  };
  order: number;
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