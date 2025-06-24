/**
 * Vertex AI統合サンプル
 * 
 * このサンプルを実行するには：
 * 1. GCPプロジェクトを設定
 * 2. Vertex AIのAPIを有効化
 * 3. 認証情報を設定
 *    - gcloud auth application-default login
 *    - または GOOGLE_APPLICATION_CREDENTIALS環境変数
 */

import { NewsletterGenerator, NewsletterRenderer } from '../src';
import type { GenerateParams, MediaAnalysis } from '../src/types';
import * as dotenv from 'dotenv';

// .envファイルを読み込み
dotenv.config();

// 実際の分析結果に近いサンプルデータを作成
const createRealisticData = (): GenerateParams => {
  const mediaAnalyses: MediaAnalysis[] = [
    {
      mediaId: 'photo-20240115-001',
      filePath: 'gs://ai-baby-journal/photos/2024/01/15/IMG_001.jpg',
      type: 'photo',
      capturedAt: new Date('2024-01-15T10:30:00'),
      expressions: [
        { type: 'smile', confidence: 0.96 },
        { type: 'laugh', confidence: 0.82 }
      ],
      actions: [
        { type: 'sitting', confidence: 0.91 },
        { type: 'playing', confidence: 0.88 }
      ],
      objects: [
        { name: 'wooden_blocks', category: 'toy', confidence: 0.94 },
        { name: 'teddy_bear', category: 'toy', confidence: 0.87 },
        { name: 'carpet', category: 'furniture', confidence: 0.79 }
      ]
    },
    {
      mediaId: 'photo-20240118-002', 
      filePath: 'gs://ai-baby-journal/photos/2024/01/18/IMG_002.jpg',
      type: 'photo',
      capturedAt: new Date('2024-01-18T15:45:00'),
      expressions: [
        { type: 'surprise', confidence: 0.85 }
      ],
      actions: [
        { type: 'standing', confidence: 0.93 },
        { type: 'reaching', confidence: 0.87 }
      ],
      objects: [
        { name: 'balloon', category: 'toy', confidence: 0.91 },
        { name: 'table', category: 'furniture', confidence: 0.88 }
      ]
    },
    {
      mediaId: 'video-20240120-001',
      filePath: 'gs://ai-baby-journal/videos/2024/01/20/VID_001.mp4', 
      type: 'video',
      capturedAt: new Date('2024-01-20T11:00:00'),
      expressions: [
        { type: 'smile', confidence: 0.88, timestamp: 2.5 },
        { type: 'laugh', confidence: 0.92, timestamp: 5.2 }
      ],
      actions: [
        { type: 'walking', confidence: 0.87, timestamp: 1.0 },
        { type: 'running', confidence: 0.79, timestamp: 4.5 },
        { type: 'jumping', confidence: 0.82, timestamp: 7.8 }
      ],
      objects: [
        { name: 'ball', category: 'toy', confidence: 0.95 },
        { name: 'playground', category: 'location', confidence: 0.89 }
      ],
      videoSummary: '公園でボール遊びを楽しんでいる様子。初めて上手にボールを蹴ることができ、とても嬉しそうな表情を見せています。',
      importantScenes: [
        {
          startTime: 3.0,
          endTime: 6.0,
          description: '初めてボールを上手に蹴れた瞬間',
          significance: 'high'
        },
        {
          startTime: 8.0,
          endTime: 10.0,
          description: 'ボールを追いかけて走り回る様子',
          significance: 'medium'
        }
      ]
    },
    {
      mediaId: 'photo-20240125-003',
      filePath: 'gs://ai-baby-journal/photos/2024/01/25/IMG_003.jpg',
      type: 'photo',
      capturedAt: new Date('2024-01-25T16:20:00'),
      expressions: [
        { type: 'neutral', confidence: 0.78 }
      ],
      actions: [
        { type: 'eating', confidence: 0.95 },
        { type: 'holding', confidence: 0.91 }
      ],
      objects: [
        { name: 'spoon', category: 'utensil', confidence: 0.96 },
        { name: 'bowl', category: 'utensil', confidence: 0.93 },
        { name: 'food', category: 'food', confidence: 0.88 }
      ]
    }
  ];

  return {
    childProfile: {
      id: 'child-456',
      name: 'ひなた',
      birthDate: new Date('2022-07-15'),
      gender: 'female',
      currentAge: {
        years: 1,
        months: 6
      }
    },
    period: {
      start: new Date('2024-01-01'),
      end: new Date('2024-01-31')
    },
    mediaAnalyses,
    timeline: {
      childId: 'child-456',
      milestones: [
        {
          id: 'milestone-001',
          type: 'first_stand',
          date: new Date('2023-11-20'),
          description: '初めてつかまり立ちをした',
          mediaIds: []
        },
        {
          id: 'milestone-002',
          type: 'first_walk',
          date: new Date('2023-12-25'),
          description: '初めて一人で3歩歩いた',
          mediaIds: []
        }
      ],
      preferences: [
        {
          category: 'toy',
          items: ['ブロック', 'ボール', 'ぬいぐるみ'],
          lastObserved: new Date('2024-01-20')
        },
        {
          category: 'food',
          items: ['バナナ', 'ヨーグルト', 'パン'],
          lastObserved: new Date('2024-01-25')
        }
      ],
      lastUpdated: new Date()
    },
    customPrompt: '元気いっぱいで活発な様子を中心に、食事の自立についても触れてください。'
  };
};

async function main() {
  console.log('🤖 Vertex AI統合サンプルを実行します...\n');

  const projectId = process.env.GCP_PROJECT_ID;
  const location = process.env.GCP_LOCATION || 'asia-northeast1';
  
  if (!projectId) {
    console.error('❌ GCP_PROJECT_IDが設定されていません。');
    console.log('\n設定方法:');
    console.log('\n1. .envファイルを作成（推奨）:');
    console.log('   cp .env.example .env');
    console.log('   # .envファイルを編集してGCP_PROJECT_IDを設定');
    console.log('   npm run example:integration');
    console.log('\n2. または環境変数で設定:');
    console.log('   export GCP_PROJECT_ID=your-project-id');
    console.log('   npm run example:integration\n');
    process.exit(1);
  }

  console.log(`📋 プロジェクトID: ${projectId}`);
  console.log(`🌏 ロケーション: ${location}`);

  try {
    // 生成器を初期化
    const generator = new NewsletterGenerator(projectId, location);
    const renderer = new NewsletterRenderer();

    // リアルなデータで連絡帳を生成
    console.log('\n📝 連絡帳を生成中...');
    const params = createRealisticData();
    const newsletter = await generator.generate(params);
    
    console.log('\n✅ 連絡帳が生成されました:');
    console.log(`- ID: ${newsletter.id}`);
    console.log(`- タイトル: ${newsletter.title}`);
    console.log(`- 期間: ${newsletter.period.start.toLocaleDateString()} ～ ${newsletter.period.end.toLocaleDateString()}`);
    console.log(`- 使用メディア数: ${newsletter.usedMediaIds.length}`);
    
    // セクションの内容を表示
    console.log('\n📑 生成されたセクション:');
    newsletter.sections.forEach((section, index) => {
      console.log(`\n${index + 1}. ${section.title}`);
      if (section.content.text) {
        console.log(`   ${section.content.text.substring(0, 50)}...`);
      }
      if (section.content.caption) {
        console.log(`   キャプション: ${section.content.caption}`);
      }
    });

    // ファイルとして出力
    const outputPath = './examples/output/integration';
    console.log('\n📄 ファイルを出力中...');
    const outputs = await renderer.renderAll(newsletter, outputPath);
    
    console.log('\n✅ 出力完了:');
    Object.entries(outputs).forEach(([format, path]) => {
      console.log(`- ${format.toUpperCase()}: ${path}`);
    });

    // 対話的な再生成のデモ
    console.log('\n🔄 対話的な再生成のデモ...');
    
    const prompts = [
      '成長の具体的な数値（歩数、時間など）を追加してください',
      '保護者へのアドバイスを含めてください',
      'もっとポエティックな表現にしてください'
    ];
    
    for (const prompt of prompts) {
      console.log(`\n💬 プロンプト: "${prompt}"`);
      
      const regenerated = await generator.regenerate({
        newsletter,
        prompt,
        sectionsToRegenerate: ['weekly-interest', 'development']
      });
      
      console.log(`✅ バージョン ${regenerated.version} を生成`);
      
      // 再生成されたセクションの一部を表示
      const interestSection = regenerated.sections.find(s => s.id === 'weekly-interest');
      if (interestSection?.content.text) {
        console.log(`   → ${interestSection.content.text.substring(0, 80)}...`);
      }
    }

    console.log('\n🎉 統合サンプルが正常に完了しました！');

  } catch (error) {
    console.error('\n❌ エラーが発生しました:', error);
    
    if (error instanceof Error) {
      if (error.message.includes('API not enabled')) {
        console.log('\nVertex AI APIを有効にしてください:');
        console.log('gcloud services enable aiplatform.googleapis.com');
      } else if (error.message.includes('PERMISSION_DENIED')) {
        console.log('\n権限エラーです。以下を確認してください:');
        console.log('1. プロジェクトIDが正しいか');
        console.log('2. Vertex AI APIが有効になっているか');
        console.log('3. 認証情報が正しく設定されているか');
      }
    }
  }
}

// スクリプトとして実行された場合
if (require.main === module) {
  main().catch(console.error);
}

export { main };