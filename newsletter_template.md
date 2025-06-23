# ベビータイムズ レイアウトテンプレート

## テンプレート仕様

```
Create a baby newsletter layout in Japanese with the following specifications:

**Header:**
- Title: "{NEWSLETTER_TITLE}" in large, bold black font
- Horizontal line separator
- Date: "{DATE}" centered below the line
- Another horizontal line separator

**Layout Structure:**
- Two-column layout with asymmetrical sections
- Clean, newspaper-style design with clear section divisions

**Main Sections:**

1. **{SECTION_1_TITLE}** (left column, top)
   - Large black and white portrait photo of {PHOTO_1_DESCRIPTION}
   - Subtitle: "{SECTION_1_SUBTITLE}"
   - Body text: "{SECTION_1_CONTENT}"

2. **{SECTION_2_TITLE}** (left column, bottom)
   - Text-only section
   - Content: "{SECTION_2_CONTENT}"

3. **{SECTION_3_TITLE}** (right column, top)
   - Small black and white photo of {PHOTO_2_DESCRIPTION}
   - Caption: "{SECTION_3_CAPTION}"

4. **{SECTION_4_TITLE}** (center)
   - Text about: "{SECTION_4_CONTENT}"

5. **{SECTION_5_TITLE}** (right column, bottom)
   - Medium-sized black and white photo of {PHOTO_3_DESCRIPTION}
   - Caption: "{SECTION_5_CAPTION}"

**Design Elements:**
- All photos in black and white/grayscale
- Clean, minimal typography
- Japanese text throughout
- Professional newsletter aesthetic
- Clear section headers in bold
- Consistent spacing and margins
- Family-friendly, warm tone
```

## 変数リスト

### ヘッダー部
- `{NEWSLETTER_TITLE}`: ニュースレターのタイトル（デフォルト: "ベビータイムズ"）
- `{DATE}`: 発行日

### セクション1（左列・上）
- `{SECTION_1_TITLE}`: セクションタイトル（例: "今週の興味"）
- `{PHOTO_1_DESCRIPTION}`: 写真の説明
- `{SECTION_1_SUBTITLE}`: サブタイトル
- `{SECTION_1_CONTENT}`: 本文コンテンツ

### セクション2（左列・下）
- `{SECTION_2_TITLE}`: セクションタイトル（例: "行った!場所"）
- `{SECTION_2_CONTENT}`: 本文コンテンツ（テキストのみ）

### セクション3（右列・上）
- `{SECTION_3_TITLE}`: セクションタイトル（例: "初めてのピクニック"）
- `{PHOTO_2_DESCRIPTION}`: 写真の説明
- `{SECTION_3_CAPTION}`: 写真キャプション

### セクション4（中央）
- `{SECTION_4_TITLE}`: セクションタイトル（例: "できるようになったこと"）
- `{SECTION_4_CONTENT}`: 本文コンテンツ

### セクション5（右列・下）
- `{SECTION_5_TITLE}`: セクションタイトル（例: "今週のベストショット"）
- `{PHOTO_3_DESCRIPTION}`: 写真の説明
- `{SECTION_5_CAPTION}`: 写真キャプション

## 使用例

```json
{
  "NEWSLETTER_TITLE": "〇〇ちゃんタイムズ",
  "DATE": "2024年6月10日",
  "SECTION_1_TITLE": "今週の興味",
  "PHOTO_1_DESCRIPTION": "笑顔の赤ちゃんのポートレート",
  "SECTION_1_SUBTITLE": "お気に入りの絵本",
  "SECTION_1_CONTENT": "『はらぺこあおむし』に夢中です。ページをめくるたびに...",
  // ... 以下省略
}
```