import { NewsletterGenerator, NewsletterRenderer } from '../src';
import type { GenerateParams, MediaAnalysis } from '../src/types';
import * as dotenv from 'dotenv';

// .envファイルを読み込み
dotenv.config();

// サンプルデータを作成
const createSampleData = (): GenerateParams => {
  const now = new Date();
  const mediaAnalyses: MediaAnalysis[] = [
    {
      mediaId: 'photo-001',
      filePath: 'gs://bucket/photos/photo-001.jpg',
      type: 'photo',
      capturedAt: new Date('2024-01-15'),
      expressions: [
        { type: 'smile', confidence: 0.95 }
      ],
      actions: [
        { type: 'sitting', confidence: 0.88 }
      ],
      objects: [
        { name: 'toy_blocks', category: 'toy', confidence: 0.92 }
      ]
    },
    {
      mediaId: 'photo-002',
      filePath: 'gs://bucket/photos/photo-002.jpg',
      type: 'photo',
      capturedAt: new Date('2024-01-20'),
      expressions: [
        { type: 'laugh', confidence: 0.90 }
      ],
      actions: [
        { type: 'standing', confidence: 0.85 }
      ],
      objects: [
        { name: 'ball', category: 'toy', confidence: 0.88 }
      ]
    },
    {
      mediaId: 'video-001',
      filePath: 'gs://bucket/videos/video-001.mp4',
      type: 'video',
      capturedAt: new Date('2024-01-25'),
      expressions: [
        { type: 'smile', confidence: 0.87, timestamp: 2.5 }
      ],
      actions: [
        { type: 'walking', confidence: 0.92, timestamp: 5.0 }
      ],
      videoSummary: '公園でボール遊びを楽しんでいる様子',
      importantScenes: [
        {
          startTime: 3.0,
          endTime: 7.0,
          description: '初めてボールをキックできた瞬間',
          significance: 'high'
        }
      ]
    }
  ];

  return {
    childProfile: {
      id: 'child-123',
      name: '太郎',
      birthDate: new Date('2022-06-01'),
      gender: 'male',
      currentAge: {
        years: 1,
        months: 7
      }
    },
    period: {
      start: new Date('2024-01-01'),
      end: new Date('2024-01-31')
    },
    mediaAnalyses,
    timeline: {
      childId: 'child-123',
      milestones: [
        {
          id: 'milestone-001',
          type: 'first_walk',
          date: new Date('2023-12-15'),
          description: '初めて一人で歩いた',
          mediaIds: []
        }
      ],
      preferences: [
        {
          category: 'toy',
          items: ['ブロック', 'ボール'],
          lastObserved: new Date('2024-01-20')
        }
      ],
      lastUpdated: new Date()
    }
  };
};

async function main() {
  console.log('連絡帳生成のサンプルを実行します...\n');

  // .envファイルまたは環境変数からプロジェクトIDを取得
  const projectId = process.env.GCP_PROJECT_ID || 'your-project-id';
  const location = process.env.GCP_LOCATION || 'asia-northeast1';
  
  if (projectId === 'your-project-id') {
    console.warn('⚠️  GCP_PROJECT_IDが設定されていません。');
    console.log('\n設定方法:');
    console.log('1. .envファイルを作成（推奨）:');
    console.log('   cp .env.example .env');
    console.log('   # .envファイルを編集してGCP_PROJECT_IDを設定');
    console.log('\n2. または環境変数で設定:');
    console.log('   export GCP_PROJECT_ID=your-actual-project-id\n');
  }

  try {
    // 生成器を初期化
    const generator = new NewsletterGenerator(projectId, location);
    const renderer = new NewsletterRenderer();

    // サンプルデータを作成
    const params = createSampleData();

    console.log('📝 連絡帳を生成中...');
    const newsletter = await generator.generate(params);
    
    console.log('\n✅ 連絡帳が生成されました:');
    console.log(`- ID: ${newsletter.id}`);
    console.log(`- タイトル: ${newsletter.title}`);
    console.log(`- セクション数: ${newsletter.sections.length}`);
    console.log(`- 期間: ${newsletter.period.start.toLocaleDateString()} ～ ${newsletter.period.end.toLocaleDateString()}`);

    // HTMLとして出力
    const outputPath = './examples/output';
    console.log('\n📄 ファイルを出力中...');
    const outputs = await renderer.renderAll(newsletter, outputPath, ['html']);
    
    console.log('\n✅ 出力完了:');
    Object.entries(outputs).forEach(([format, path]) => {
      console.log(`- ${format.toUpperCase()}: ${path}`);
    });

    // 再生成のサンプル
    console.log('\n🔄 プロンプトで再生成中...');
    
    // 初回生成から少し間隔を空ける
    console.log('⏳ レート制限回避のため5秒待機中...');
    await new Promise(resolve => setTimeout(resolve, 5000));
    
    const regenerated = await generator.regenerate({
      newsletter,
      prompt: 'もっと具体的な成長の様子を詳しく記載してください'
    });
    
    console.log('✅ 再生成完了 (バージョン: ' + regenerated.version + ')');

  } catch (error) {
    console.error('\n❌ エラーが発生しました:', error);
    if (error instanceof Error && error.message.includes('Application Default Credentials')) {
      console.log('\nGCP認証の設定が必要です。以下のいずれかの方法で設定してください:');
      console.log('1. gcloud auth application-default login');
      console.log('2. サービスアカウントキーを使用');
      console.log('   export GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json');
    }
  }
}

// 実行
main().catch(console.error);