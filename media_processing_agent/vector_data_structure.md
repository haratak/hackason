# ベクトル化データの構造

## 1. エピソードログの構造（highlight_identifier の出力）

```json
{
    "title": "アイスクリームタイム",
    "summary": "屋内、木製テーブルにて。アイスクリームを持ち、食べ、指で口を触る。楽しそう、満足そう。",
    "emotion": "楽しそう",
    "activities": ["アイスクリームを食べる", "指を口に入れる"],
    "development_milestones": ["食感の認識", "自己満足"],
    "vector_tags": ["アイスクリーム", "食べる", "屋内", "テーブル", "満足", "口", "指"]
}
```

## 2. ベクトル化される要素

### ベクトル化される内容（意味検索の対象）:
1. **summary** - ハイライトシーンの具体的な状況説明
2. **emotion** - 主な感情
3. **vector_tags** - 検索用の具体的なタグ
4. **activities** - 具体的な活動
5. **development_milestones** - 発達の兆候

### 結合されたテキスト例:
```
屋内、木製テーブルにて。アイスクリームを持ち、食べ、指で口を触る。楽しそう、満足そう。 楽しそう アイスクリーム 食べる 屋内 テーブル 満足 口 指 アイスクリームを食べる 指を口に入れる 食感の認識 自己満足
```

### ベクトル化のプロセス:
```python
text_for_embedding = " ".join([
    summary,                        # メインの説明文
    emotion,                        # 感情
    " ".join(tags),                # タグのリスト
    " ".join(activities),          # 活動のリスト
    " ".join(milestones),          # 発達マイルストーン
]).strip()

# text-embedding-004 モデルで768次元のベクトルに変換
embeddings = embedding_model.get_embeddings([text_for_embedding])
vector = embeddings[0].values  # [0.123, -0.456, 0.789, ...] (768個の数値)
```

## 3. ベクトル化されない要素（フィルタリング用）:

### カテゴリカルフィルタ:
- **child_id** - 子供のID（例: "demo"）

### 数値フィルタ:
- **created_at** - Unixタイムスタンプ（例: 1751162604）

### その他保存されるがベクトル化されない情報:
- **episode_id** - FirestoreのドキュメントID
- **title** - エピソードのタイトル
- **media_source_uri** - 元のメディアファイルのURI

## 4. Vertex AI Searchに保存される完全な構造:

```json
{
    "datapoint_id": "kYH4Fgmm28viySCQl4B6",  // ← エピソードID（Firestore文書ID）
    "feature_vector": [0.123, -0.456, ...],    // 768次元のベクトル
    "restricts": [
        {
            "namespace": "child_id",
            "allow_list": ["demo"]
        }
    ],
    "numeric_restricts": [
        {
            "namespace": "created_at",
            "value_int": 1751162604
        }
    ]
}
```

### エピソードIDの役割:
- **datapoint_id** として保存される
- ベクトル検索の結果として返される
- このIDを使ってFirestoreから完全なエピソード情報を取得できる

## 5. 検索時の動作:

### 意味検索（ベクトル類似度）:
- クエリ: "楽しい アイスクリーム"
- → text-embedding-004でベクトル化
- → 保存されているベクトルと比較して類似度を計算

### フィルタリング（正確な条件）:
- child_id = "demo"
- created_at が特定期間内（例: 過去7日間）

### 検索結果:
```json
{
  "nearestNeighbors": [{
    "neighbors": [
      {
        "datapoint": {
          "datapointId": "kYH4Fgmm28viySCQl4B6"  // ← エピソードID
        },
        "distance": 0.95  // 類似度スコア
      }
    ]
  }]
}
```

### エピソードIDを使った詳細取得:
```python
# ベクトル検索で取得したエピソードID
episode_id = "kYH4Fgmm28viySCQl4B6"

# Firestoreから完全な情報を取得
doc = db.collection("episodes").document(episode_id).get()
episode_data = doc.to_dict()
# → title, content, media_source_uri など全ての情報が取得できる
```

これにより、「特定の子供の、特定期間内の、意味的に関連するエピソード」を効率的に検索し、詳細情報を取得できます。