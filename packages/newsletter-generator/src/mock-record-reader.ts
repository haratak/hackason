import { ChildcareRecord, ChildcareRecordReader } from './types';

/**
 * テスト用のモック育児記録リーダー
 */
export class MockRecordReader implements ChildcareRecordReader {
  private records: ChildcareRecord[] = [];

  constructor(records: ChildcareRecord[] = []) {
    this.records = records;
  }

  /**
   * モック記録を追加
   */
  addRecords(records: ChildcareRecord[]): void {
    this.records.push(...records);
  }

  /**
   * 記録を検索
   */
  async searchRecords(params: {
    childId: string;
    dateRange: { start: Date; end: Date };
    query?: string;
    tags?: string[];
    limit?: number;
  }): Promise<ChildcareRecord[]> {
    let filtered = this.records.filter(record => {
      // 子どもIDでフィルタ
      if (record.childId !== params.childId) return false;

      // 日付範囲でフィルタ
      const recordDate = new Date(record.timestamp);
      if (recordDate < params.dateRange.start || recordDate > params.dateRange.end) {
        return false;
      }

      // タグでフィルタ
      if (params.tags && params.tags.length > 0) {
        const hasMatchingTag = params.tags.some(tag => 
          record.tags.includes(tag)
        );
        if (!hasMatchingTag) return false;
      }

      // クエリでフィルタ（簡易的な文字列マッチング）
      if (params.query) {
        const searchText = [
          record.activity.type,
          record.activity.description,
          ...record.observations,
          ...(record.childState?.verbalExpressions || [])
        ].join(' ').toLowerCase();
        
        if (!searchText.includes(params.query.toLowerCase())) {
          return false;
        }
      }

      return true;
    });

    // 日付でソート（新しい順）
    filtered.sort((a, b) => 
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );

    // 件数制限
    if (params.limit) {
      filtered = filtered.slice(0, params.limit);
    }

    return filtered;
  }

  /**
   * IDで記録を取得
   */
  async getRecordsByIds(recordIds: string[]): Promise<ChildcareRecord[]> {
    return this.records.filter(record => 
      recordIds.includes(record.id)
    );
  }

  /**
   * 活動タイプで記録を検索
   */
  async getRecordsByActivityType(
    childId: string,
    activityType: string,
    dateRange: { start: Date; end: Date }
  ): Promise<ChildcareRecord[]> {
    return this.searchRecords({
      childId,
      dateRange,
      query: activityType
    });
  }
}

/**
 * サンプル育児記録データを生成
 */
export function createSampleChildcareRecords(): ChildcareRecord[] {
  return [
    {
      id: 'rec-001',
      timestamp: '2024-01-15T10:30:00+09:00',
      childId: 'child-123',
      recordedBy: '田中先生',
      activity: {
        type: '自由遊び',
        description: 'ブロック遊び',
        duration: 20,
        location: '保育室'
      },
      observations: [
        '赤と青のブロックを選んで遊んでいた',
        'ブロックを3つ重ねることに成功した',
        '崩れても何度も挑戦していた',
        '完成すると手を叩いて喜んでいた'
      ],
      childState: {
        mood: '集中していた',
        verbalExpressions: ['できた！', 'もっと']
      },
      mediaId: 'photo-001',
      tags: ['遊び', 'ブロック', '集中', '達成感']
    },
    {
      id: 'rec-002',
      timestamp: '2024-01-15T11:00:00+09:00',
      childId: 'child-123',
      recordedBy: '田中先生',
      activity: {
        type: 'お散歩',
        description: '園庭でのお散歩',
        duration: 30,
        location: '園庭'
      },
      observations: [
        '友達と手をつないで歩いた',
        '犬を見つけて指差しした',
        '「わんわん」と言葉を発した',
        '落ち葉を拾って観察していた'
      ],
      childState: {
        mood: '楽しそう',
        interactions: ['山田くんと手をつないだ'],
        verbalExpressions: ['わんわん', 'はっぱ']
      },
      mediaId: 'video-001',
      tags: ['お散歩', '社会性', '言葉', '自然']
    },
    {
      id: 'rec-003',
      timestamp: '2024-01-15T12:00:00+09:00',
      childId: 'child-123',
      recordedBy: '山田先生',
      activity: {
        type: '給食',
        description: '昼食の時間',
        duration: 40,
        location: '食堂'
      },
      observations: [
        'スプーンを使って自分で食べた',
        '野菜も残さず完食した',
        'お茶をこぼさずに飲めた',
        '「おいしい」と言った'
      ],
      childState: {
        mood: '満足そう',
        verbalExpressions: ['おいしい', 'もっと']
      },
      mediaId: 'photo-002',
      tags: ['給食', '自立', '食事']
    },
    {
      id: 'rec-004',
      timestamp: '2024-01-16T10:00:00+09:00',
      childId: 'child-123',
      recordedBy: '田中先生',
      activity: {
        type: '制作活動',
        description: 'お絵かき',
        duration: 25,
        location: '保育室'
      },
      observations: [
        'クレヨンで大きな円を描いた',
        '赤色を好んで使っていた',
        '「ママ」と言いながら描いていた',
        '完成した絵を嬉しそうに見せてくれた'
      ],
      childState: {
        mood: '楽しそう',
        verbalExpressions: ['ママ', 'あか']
      },
      mediaId: 'photo-003',
      tags: ['制作', 'お絵かき', '表現']
    },
    {
      id: 'rec-005',
      timestamp: '2024-01-20T14:30:00+09:00',
      childId: 'child-123',
      recordedBy: '山田先生',
      activity: {
        type: '自由遊び',
        description: 'ボール遊び',
        duration: 15,
        location: '園庭'
      },
      observations: [
        '初めてボールをキックできた',
        'ボールを追いかけて走った',
        '転んでも泣かずに立ち上がった',
        '友達にボールを渡そうとした'
      ],
      childState: {
        mood: '活発',
        interactions: ['佐藤くんとボールの受け渡しをした'],
        verbalExpressions: ['ボール', 'キック']
      },
      mediaId: 'video-002',
      tags: ['遊び', 'ボール', '運動', '初めて', '社会性']
    },
    {
      id: 'rec-006', 
      timestamp: '2024-01-25T15:00:00+09:00',
      childId: 'child-123',
      recordedBy: '田中先生',
      activity: {
        type: '読み聞かせ',
        description: '絵本の時間',
        duration: 20,
        location: '図書コーナー'
      },
      observations: [
        '絵本に集中して見入っていた',
        '動物の絵を指差した',
        '「にゃんにゃん」と猫の真似をした',
        '最後まで座って聞いていた'
      ],
      childState: {
        mood: '集中していた',
        verbalExpressions: ['にゃんにゃん', 'わんわん']
      },
      tags: ['読み聞かせ', '集中', '言葉']
    }
  ];
}