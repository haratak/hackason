import { NewsletterGenerator } from '../generator';
import { VertexAIClient } from '../vertex-ai-client';
import type { GenerateParams, MediaAnalysis } from '../types';

// Vertex AIクライアントをモック化
jest.mock('../vertex-ai-client');

describe('NewsletterGenerator', () => {
  let generator: NewsletterGenerator;
  let mockVertexAI: jest.Mocked<VertexAIClient>;

  beforeEach(() => {
    // モックをリセット
    jest.clearAllMocks();
    
    // Vertex AIクライアントのモックを設定
    mockVertexAI = {
      generateSectionContent: jest.fn().mockResolvedValue('生成されたコンテンツ'),
      selectPhotoWithCaption: jest.fn().mockResolvedValue({
        mediaId: 'photo-001',
        caption: '生成されたキャプション'
      }),
      regenerateContent: jest.fn().mockResolvedValue('再生成されたコンテンツ')
    } as any;
    
    (VertexAIClient as jest.MockedClass<typeof VertexAIClient>).mockImplementation(() => mockVertexAI);
    
    generator = new NewsletterGenerator('test-project-id');
  });

  describe('generate', () => {
    it('連絡帳を正常に生成できる', async () => {
      const params: GenerateParams = createTestParams();
      
      const newsletter = await generator.generate(params);
      
      expect(newsletter).toMatchObject({
        childId: 'child-123',
        title: '太郎ちゃんの1月の成長記録',
        period: params.period,
        version: 1
      });
      
      expect(newsletter.sections).toHaveLength(5);
      expect(newsletter.id).toBeTruthy();
      expect(newsletter.generatedAt).toBeInstanceOf(Date);
    });

    it('各セクションが正しく生成される', async () => {
      const params: GenerateParams = createTestParams();
      
      const newsletter = await generator.generate(params);
      
      const sectionTitles = newsletter.sections.map(s => s.title);
      expect(sectionTitles).toEqual([
        '今週の興味',
        '行った場所',
        '初めての体験',
        'できるようになったこと',
        '今週のベストショット'
      ]);
      
      // Vertex AIが呼ばれたことを確認
      expect(mockVertexAI.generateSectionContent).toHaveBeenCalled();
    });

    it('ハイライトを正しく抽出できる', async () => {
      const params: GenerateParams = createTestParams();
      // 笑顔の写真を追加
      params.mediaAnalyses[0].expressions = [
        { type: 'smile', confidence: 0.95 }
      ];
      
      const newsletter = await generator.generate(params);
      
      // ベストショットセクションに笑顔の写真が使われることを確認
      const bestShotSection = newsletter.sections.find(s => s.id === 'best-shot');
      expect(bestShotSection?.content.photoUrl).toBe('gs://bucket/photos/photo-001.jpg');
    });
  });

  describe('regenerate', () => {
    it('プロンプトで連絡帳を再生成できる', async () => {
      const params: GenerateParams = createTestParams();
      const original = await generator.generate(params);
      
      const regenerated = await generator.regenerate({
        newsletter: original,
        prompt: 'もっと詳しく'
      });
      
      expect(regenerated.version).toBe(2);
      expect(regenerated.generationPrompt).toBe('もっと詳しく');
      expect(mockVertexAI.regenerateContent).toHaveBeenCalled();
    });

    it('特定のセクションのみ再生成できる', async () => {
      const params: GenerateParams = createTestParams();
      const original = await generator.generate(params);
      
      const regenerated = await generator.regenerate({
        newsletter: original,
        prompt: 'もっと詳しく',
        sectionsToRegenerate: ['weekly-interest']
      });
      
      // 指定したセクションのみ再生成されることを確認
      expect(mockVertexAI.regenerateContent).toHaveBeenCalledTimes(1);
    });
  });
});

// テスト用のパラメータを作成
function createTestParams(): GenerateParams {
  const mediaAnalyses: MediaAnalysis[] = [
    {
      mediaId: 'photo-001',
      filePath: 'gs://bucket/photos/photo-001.jpg',
      type: 'photo',
      capturedAt: new Date('2024-01-15'),
      expressions: [{ type: 'smile', confidence: 0.9 }],
      actions: [{ type: 'sitting', confidence: 0.8 }],
      objects: [
        { name: 'toy_blocks', category: 'toy', confidence: 0.9 },
        { name: 'ball', category: 'toy', confidence: 0.7 }
      ]
    },
    {
      mediaId: 'video-001',
      filePath: 'gs://bucket/videos/video-001.mp4',
      type: 'video',
      capturedAt: new Date('2024-01-20'),
      videoSummary: 'ボール遊びを楽しむ様子',
      importantScenes: [{
        startTime: 2.0,
        endTime: 5.0,
        description: '初めてボールをキック',
        significance: 'high'
      }]
    }
  ];

  return {
    childProfile: {
      id: 'child-123',
      name: '太郎',
      birthDate: new Date('2022-06-01'),
      currentAge: { years: 1, months: 7 }
    },
    period: {
      start: new Date('2024-01-01'),
      end: new Date('2024-01-31')
    },
    mediaAnalyses,
    timeline: {
      childId: 'child-123',
      milestones: [{
        id: 'milestone-001',
        type: 'first_walk',
        date: new Date('2023-12-15'),
        description: '初めて歩いた',
        mediaIds: []
      }],
      preferences: [{
        category: 'toy',
        items: ['blocks', 'ball'],
        lastObserved: new Date('2024-01-15')
      }],
      lastUpdated: new Date()
    }
  };
}