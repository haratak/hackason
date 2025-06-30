# Multi-Faceted Analysis (多角的分析) アーキテクチャ

## 概要

メディア解析エージェントを、単一の「エピソードログ」を生成する方式から、月齢に基づいて動的に複数の視点で分析を行う「多角的分析」モデルへとリファクタリングしました。

## 主な変更点

### 1. 動的な視点決定

`perspective_determiner` 関数が、子供の月齢と観察された行動から、分析すべき視点を最大4つまで自動的に決定します。

```python
perspectives = perspective_determiner(facts, child_age_months)
# 返り値例:
{
    "perspectives": [
        {
            "type": "motor_development",
            "focus": "つかまり立ちと歩行の兆候",
            "reason": "10ヶ月で立位の動作が観察されたため",
            "observable_signs": ["ソファにつかまって立つ", "足を踏み出そうとする"]
        },
        {
            "type": "social_emotional",
            "focus": "親との相互作用",
            "reason": "親を見て笑う様子が観察されたため",
            "observable_signs": ["親を見て笑顔", "手を伸ばす"]
        }
    ],
    "analysis_note": "運動発達と社会性の両面で重要な兆候が見られる時期"
}
```

### 2. 並行分析処理

各視点に対して、`dynamic_multi_analyzer` が並行して分析を実行します。

```python
# 非同期で複数の視点を並行分析
tasks = []
for perspective in perspectives:
    task = analyze_perspective(facts, perspective, ...)
    tasks.append(task)

results = await asyncio.gather(*tasks)
```

### 3. 新しいFirestoreスキーマ

```
media/{mediaId}/
  ├─ metadata
  │   ├─ media_uri: string
  │   ├─ child_id: string
  │   ├─ child_age_months: number
  │   ├─ user_id: string
  │   └─ created_at: timestamp
  └─ analyses/{analysisId}/
      ├─ perspective_type: string (例: "motor_development")
      ├─ title: string
      ├─ summary: string
      ├─ significance: string
      ├─ future_outlook: string
      ├─ vector_tags: array
      └─ created_at: timestamp
```

### 4. Vector Search の拡張

- 各分析は独立してベクトル化され、インデックス化されます
- `perspective_type` をrestrictとして追加し、特定の視点の分析のみを検索可能
- データポイントIDは `{media_id}_{analysis_id}` 形式

## 使用方法

### 基本的な使用

```python
from agent import process_media_for_cloud_function

result = process_media_for_cloud_function(
    media_uri="gs://bucket/image.jpg",
    user_id="user123",
    child_id="child456",
    child_age_months=18  # 18ヶ月の子供として分析
)
```

### レスポンス形式

```json
{
    "status": "success",
    "media_id": "uuid",
    "child_age_months": 18,
    "objective_facts": {...},
    "perspectives_analyzed": 3,
    "successful_analyses": [
        {
            "perspective_type": "language_development",
            "analysis_id": "analysis_id_1",
            "indexed": true
        },
        {
            "perspective_type": "social_play",
            "analysis_id": "analysis_id_2",
            "indexed": true
        }
    ],
    "failed_analyses": [],
    "analysis_note": "言語発達と社会的遊びの重要な時期"
}
```

## テスト

```bash
# 基本テスト（異なる月齢での分析）
python test_multi_faceted_analysis.py

# Firestoreのデータ確認
python test_multi_faceted_analysis.py --check-firestore

# カスタムメディアでテスト
python test_multi_faceted_analysis.py --media-uri "https://example.com/image.jpg"
```

## Cloud Functions

HTTPトリガーとFirestoreトリガーの両方が新しいアーキテクチャに対応しています：

```bash
# デプロイ
cd cloud_functions
gcloud functions deploy process_media_upload \
    --runtime python312 \
    --trigger-http \
    --allow-unauthenticated
```

## 月齢による視点の例

### 0-6ヶ月
- 感覚発達（視線追従、音への反応）
- 基本的な運動（首すわり、寝返り）
- 親子の愛着形成

### 6-12ヶ月
- 運動発達（ハイハイ、つかまり立ち）
- 物の永続性理解
- 初期の言語理解

### 12-24ヶ月
- 歩行と運動技能
- 言語発達（初語、二語文）
- 社会性（他者への関心）

### 24ヶ月以上
- 複雑な遊び（ごっこ遊び）
- 感情の理解と表現
- 友達との関わり

## 利点

1. **柔軟性**: AIが月齢と観察内容から最適な視点を自動選択
2. **効率性**: 関連性の低い視点は分析しない
3. **多様性**: 1つのメディアから複数の価値ある洞察を生成
4. **検索性**: Vector Searchで特定の発達領域の記録を効率的に検索可能
5. **拡張性**: 新しい分析視点を簡単に追加可能