# AI連絡帳生成パッケージ (@ai-baby-journal/newsletter-generator)

## 概要

このパッケージは、AI連絡帳プロダクトの**コア機能**である「連絡帳生成」を担当するコンポーネントです。保育園で撮影された写真・動画の分析結果と子どもの成長記録（タイムライン）を基に、保育士視点の温かみのある連絡帳を自動生成します。

## プロダクト全体における位置づけ

```mermaid
graph TB
    subgraph "フロントエンド"
        A[保育士アプリ<br/>Next.js/PWA] 
        B[保護者アプリ<br/>Flutter]
    end
    
    subgraph "バックエンド - Cloud Run"
        C[写真アップロードAPI<br/>@ai-baby-journal/api]
        D[メディア分析API<br/>@ai-baby-journal/api]
        E[連絡帳生成API<br/>@ai-baby-journal/api]
    end
    
    subgraph "コアパッケージ"
        F[メディア分析<br/>@ai-baby-journal/media-analyzer]
        G[連絡帳生成<br/>@ai-baby-journal/newsletter-generator]
        H[タイムライン管理<br/>@ai-baby-journal/timeline-manager]
    end
    
    subgraph "ストレージ"
        I[Cloud Storage<br/>写真・動画]
        J[Firestore<br/>メタデータ・連絡帳]
    end
    
    subgraph "AI/ML"
        K[Vertex AI<br/>Gemini 1.5 Flash]
    end
    
    A -->|写真アップロード| C
    C -->|保存| I
    C -->|分析リクエスト| D
    D -->|使用| F
    F -->|画像認識・分析| K
    F -->|結果保存| J
    
    A -->|生成リクエスト| E
    E -->|使用| G
    G -->|分析結果取得| J
    G -->|タイムライン取得| H
    H -->|データ取得| J
    G -->|文章生成| K
    G -->|連絡帳保存| J
    
    B -->|連絡帳閲覧| J
    
    style G fill:#ff9999,stroke:#333,stroke-width:4px
    style K fill:#9999ff,stroke:#333,stroke-width:2px
```

## 主な機能

### 1. 連絡帳生成
- **入力**: メディア分析結果、子どものプロフィール、成長タイムライン、レイアウト設定
- **出力**: 構造化された連絡帳データ（セクション別）
- **特徴**: 
  - 保育士視点の温かい文章生成
  - 年齢に応じた発達視点の記述
  - 写真と連動したストーリー構成

### 2. コンテンツ再生成
- ユーザーからのフィードバックに基づく文章の再生成
- セクション単位での部分的な更新が可能
- バージョン管理機能

### 3. レンダリング
- HTML形式での出力
- 今後のPDF対応も考慮した拡張可能な設計

## 技術仕様

### 依存関係
- **Google Cloud Vertex AI**: テキスト生成エンジン（Gemini 1.5 Flash）
- **TypeScript**: 型安全な実装
- **@ai-baby-journal/shared**: 共通型定義

### セクションタイプ

| セクション | 説明 | コンテンツタイプ |
|----------|------|----------------|
| `overview` | 今週の様子（概要） | テキストのみ |
| `activities` | 今週の活動 | テキストのみ |
| `favorite-play` | お気に入りの遊び | 写真＋説明 |
| `growth-moment` | 成長の瞬間 | 写真＋説明 |
| `places-visited` | 行った場所 | テキストのみ |
| `first-time` | 初めての体験 | 写真＋キャプション |
| `development` | できるようになったこと | テキストのみ |
| `best-shot` | 今週のベストショット | 写真＋キャプション |

## インストールと使用方法

### インストール
```bash
npm install @ai-baby-journal/newsletter-generator
```

### 環境変数
```bash
# Google Cloud認証
export GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
```

## 使用方法

### 基本的な使用例

```typescript
import { NewsletterGenerator, VertexAIClient, HtmlRenderer } from '@ai-baby-journal/newsletter-generator';

// クライアントの初期化
const vertexAIClient = new VertexAIClient(
  'your-project-id',
  'asia-northeast1'
);

const renderer = new HtmlRenderer();
const generator = new NewsletterGenerator(vertexAIClient, renderer);

// 連絡帳生成
const newsletter = await generator.generate({
  childProfile: {
    id: 'child_123',
    name: '太郎',
    currentAge: { years: 3, months: 2 },
    className: 'ひまわり組'
  },
  mediaAnalyses: [...], // メディア分析結果
  timeline: {...},      // 成長記録
  layout: {
    sections: [
      { id: 'section_1', type: 'overview', order: 1 },
      { id: 'section_2', type: 'activities', order: 2 },
      { id: 'section_3', type: 'favorite-play', order: 3 },
      { id: 'section_4', type: 'first-time', order: 4 },
      { id: 'section_5', type: 'best-shot', order: 5 }
    ]
  }
});

// HTML出力
const outputs = await renderer.renderAll(
  newsletter,
  './output',
  ['html']
);
```

### コンテンツ再生成

```typescript
// プロンプトを使って再生成
const regenerated = await generator.regenerate({
  newsletter: newsletter,
  prompt: 'もっと具体的な成長の様子を詳しく記載してください'
});
```

## API仕様

### NewsletterGenerator

```typescript
class NewsletterGenerator {
  constructor(
    vertexAIClient: VertexAIClient,
    renderer: NewsletterRenderer
  )
  
  // 連絡帳を新規生成
  async generate(params: GenerateParams): Promise<Newsletter>
  
  // 既存の連絡帳を再生成
  async regenerate(params: RegenerateParams): Promise<Newsletter>
}
```

### 主要な型定義

```typescript
interface GenerateParams {
  childProfile: ChildProfile;
  mediaAnalyses: MediaAnalysis[];
  timeline?: Timeline;
  layout: NewsletterLayout;
  customPrompts?: Record<string, string>;
}

interface ChildProfile {
  id: string;
  name: string;
  currentAge: { years: number; months: number };
  className?: string;
}

interface MediaAnalysis {
  mediaId: string;
  type: 'photo' | 'video';
  filePath: string;
  capturedAt: Date;
  expressions?: Expression[];
  actions?: Action[];
  objects?: DetectedObject[];
  videoSummary?: string;
}

interface Newsletter {
  id: string;
  childId: string;
  title: string;
  period: { start: Date; end: Date };
  sections: NewsletterSection[];
  version: number;
  generatedAt: Date;
}
```

## パフォーマンスとレート制限対策

### API呼び出し最適化
- セクション間に2秒の遅延を設定
- 写真選定APIの呼び出しを最小化（事前分析結果を活用）
- リトライ時にexponential backoffとジッターを適用

### レート制限対策
- 最大5回のリトライ
- 基本遅延3秒
- API呼び出し間の最小間隔2秒
- 順次処理による同時実行数の制限

### 実装済みの最適化
```typescript
// vertex-ai-client.ts
private maxRetries = 5;
private baseDelay = 3000;
private minApiInterval = 2000;
```

## 開発状況

### 実装済み機能
- ✅ 基本的な連絡帳生成機能
- ✅ Vertex AI (Gemini 1.5 Flash) との統合
- ✅ HTML形式でのレンダリング
- ✅ コンテンツ再生成機能
- ✅ レート制限対策（リトライ、遅延処理）
- ✅ セクションタイプ別のコンテンツ生成

### 今後の実装予定
- 📋 PDF形式でのレンダリング
- 📋 より高度なレイアウトカスタマイズ
- 📋 多言語対応（英語、中国語など）
- 📋 テンプレート機能
- 📋 バッチ処理機能（複数の連絡帳を一括生成）

## 開発

```bash
# 依存関係のインストール
npm install

# サービスアカウントキーの配置
cp path/to/service-account-key.json ./

# ビルド
npm run build

# テスト
npm test

# 開発モード
npm run dev

# サンプルの実行
npm run example:basic  # 基本的なサンプル
```

## トラブルシューティング

### 429エラー（レート制限）が発生する場合
1. Vertex AIのクォータを確認してください
2. `minApiInterval`の値を増やしてください
3. リトライ回数を増やすか、基本遅延時間を延長してください

### モデルが見つからないエラー
- リージョンが`asia-northeast1`に設定されているか確認
- モデル名が`gemini-1.5-flash`になっているか確認

## ライセンス

プライベートパッケージ（ハッカソンプロジェクト）

## 貢献

このプロジェクトはハッカソンのために開発されています。

---

**注意**: このパッケージはAI連絡帳システムの一部であり、単独では動作しません。完全なシステムを構築するには、他の関連パッケージ（メディア分析、API、タイムライン管理など）も必要です。