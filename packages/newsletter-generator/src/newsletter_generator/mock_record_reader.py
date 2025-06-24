"""Mock childcare record reader for testing."""

from datetime import datetime
from typing import Dict, List, Optional

from .types import ChildcareRecord


class MockRecordReader:
    """テスト用のモック育児記録リーダー."""
    
    def __init__(self, records: Optional[List[ChildcareRecord]] = None):
        """Initialize with optional records."""
        self.records = records or []
    
    def add_records(self, records: List[ChildcareRecord]) -> None:
        """モック記録を追加する."""
        self.records.extend(records)
    
    async def search_records(
        self,
        child_id: str,
        date_range: Dict[str, datetime],
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[ChildcareRecord]:
        """記録を検索する."""
        filtered = []
        
        for record in self.records:
            # 子どもIDでフィルタ
            if record.child_id != child_id:
                continue
            
            # 日付範囲でフィルタ
            # タイムゾーン情報を除去して比較
            record_date = datetime.fromisoformat(record.timestamp.replace("+09:00", ""))
            start_date = date_range["start"].replace(tzinfo=None) if date_range["start"].tzinfo else date_range["start"]
            end_date = date_range["end"].replace(tzinfo=None) if date_range["end"].tzinfo else date_range["end"]
            
            if record_date < start_date or record_date > end_date:
                continue
            
            # タグでフィルタ
            if tags and not any(tag in record.tags for tag in tags):
                continue
            
            # クエリでフィルタ（簡易的な文字列マッチング）
            if query:
                search_text = " ".join(
                    [
                        record.activity.get("type", ""),
                        record.activity.get("description", ""),
                        *record.observations,
                        *(record.child_state.get("verbal_expressions", [])
                          if record.child_state
                          else []),
                    ]
                ).lower()
                
                if query.lower() not in search_text:
                    continue
            
            filtered.append(record)
        
        # 日付でソート（新しい順）
        filtered.sort(
            key=lambda r: datetime.fromisoformat(r.timestamp.replace("+09:00", "")),
            reverse=True,
        )
        
        # 件数制限
        if limit:
            filtered = filtered[:limit]
        
        return filtered
    
    async def get_records_by_ids(self, record_ids: List[str]) -> List[ChildcareRecord]:
        """IDで記録を取得する."""
        return [r for r in self.records if r.id in record_ids]
    
    async def get_records_by_activity_type(
        self,
        child_id: str,
        activity_type: str,
        date_range: Dict[str, datetime],
    ) -> List[ChildcareRecord]:
        """活動タイプで記録を検索する."""
        return await self.search_records(
            child_id=child_id, date_range=date_range, query=activity_type
        )


def create_sample_childcare_records() -> List[ChildcareRecord]:
    """サンプル育児記録データを生成する - 1ヶ月分（1日1記録程度）."""
    records = []
    
    # 1月の各日に記録を作成
    daily_activities = [
        # 1月1日
        {
            "day": 1, "time": "10:30", "type": "自由遊び", "desc": "お正月の飾り作り",
            "obs": ["折り紙で鶴を折ろうとした", "赤い紙を選んで作業した", "完成すると嬉しそうに飾った"],
            "mood": "楽しそう", "words": ["きれい", "あか"], "tags": ["制作", "季節行事"]
        },
        # 1月2日
        {
            "day": 2, "time": "11:00", "type": "お散歩", "desc": "初詣ごっこ",
            "obs": ["手を合わせる真似をした", "お賽銭箱に興味を示した", "「ぱんぱん」と言いながら拍手した"],
            "mood": "興味深そう", "words": ["ぱんぱん"], "tags": ["お散歩", "季節行事"]
        },
        # 1月3日
        {
            "day": 3, "time": "14:00", "type": "自由遊び", "desc": "コマ回し",
            "obs": ["コマを回そうと挑戦した", "3回目で成功した", "友達のコマも見て拍手した"],
            "mood": "集中していた", "words": ["くるくる", "できた"], "tags": ["遊び", "お正月"]
        },
        # 1月4日
        {
            "day": 4, "time": "10:00", "type": "制作活動", "desc": "凧作り",
            "obs": ["ビニール袋に絵を描いた", "紐を付けるのを手伝ってもらった", "完成した凧を大事に持っていた"],
            "mood": "真剣", "words": ["たこ", "とぶ"], "tags": ["制作", "お正月"]
        },
        # 1月5日
        {
            "day": 5, "time": "11:30", "type": "音楽活動", "desc": "お正月の歌",
            "obs": ["「お正月」の歌に合わせて体を揺らした", "手拍子でリズムを取った", "「もういっかい」とリクエストした"],
            "mood": "楽しそう", "words": ["もういっかい", "うた"], "tags": ["音楽", "季節行事"]
        },
        # 1月6日
        {
            "day": 6, "time": "10:00", "type": "自由遊び", "desc": "ブロック遊び",
            "obs": ["高いタワーを作ろうとした", "10個まで積み上げた", "崩れても笑って再挑戦した"],
            "mood": "楽しそう", "words": ["たかい", "もっと"], "tags": ["遊び", "ブロック"]
        },
        # 1月7日
        {
            "day": 7, "time": "12:00", "type": "給食", "desc": "七草がゆ",
            "obs": ["初めての七草がゆを食べた", "「おいしい」と言った", "おかわりを求めた"],
            "mood": "満足そう", "words": ["おいしい", "もっと"], "tags": ["給食", "季節行事"]
        },
        # 1月8日
        {
            "day": 8, "time": "14:30", "type": "お散歩", "desc": "園庭で凧揚げ",
            "obs": ["自分で作った凧を飛ばした", "風を感じて喜んだ", "走りながら凧を引っ張った"],
            "mood": "活発", "words": ["とんだ", "かぜ"], "tags": ["お散歩", "運動"]
        },
        # 1月9日
        {
            "day": 9, "time": "10:30", "type": "読み聞かせ", "desc": "干支の絵本",
            "obs": ["辰の絵を指差した", "「がおー」と真似をした", "最後まで集中して聞いた"],
            "mood": "集中していた", "words": ["がおー", "りゅう"], "tags": ["読み聞かせ", "言葉"]
        },
        # 1月10日
        {
            "day": 10, "time": "11:00", "type": "体操", "desc": "リズム体操",
            "obs": ["音楽に合わせてジャンプした", "手足を大きく動かした", "笑顔で参加した"],
            "mood": "活発", "words": ["ジャンプ", "たのしい"], "tags": ["運動", "音楽"]
        },
        # 1月11日
        {
            "day": 11, "time": "14:00", "type": "自由遊び", "desc": "粘土遊び",
            "obs": ["粘土で団子を作った", "「おだんご」と言った", "友達に見せて回った"],
            "mood": "得意そう", "words": ["おだんご", "みて"], "tags": ["遊び", "制作"]
        },
        # 1月12日
        {
            "day": 12, "time": "10:00", "type": "制作活動", "desc": "雪だるま作り",
            "obs": ["白い紙を丸く切った", "目と口を描いた", "「ゆきだるま」と言いながら作った"],
            "mood": "楽しそう", "words": ["ゆきだるま", "しろ"], "tags": ["制作", "季節"]
        },
        # 1月13日
        {
            "day": 13, "time": "11:30", "type": "給食", "desc": "温かいうどん",
            "obs": ["フーフーして冷ました", "箸を使って食べようとした", "「あったかい」と言った"],
            "mood": "満足そう", "words": ["あったかい", "おいしい"], "tags": ["給食", "自立"]
        },
        # 1月14日
        {
            "day": 14, "time": "15:00", "type": "お散歩", "desc": "近所の公園",
            "obs": ["滑り台を何度も滑った", "ブランコに乗りたがった", "「もっと」と言った"],
            "mood": "活発", "words": ["もっと", "たのしい"], "tags": ["お散歩", "運動"]
        },
        # 1月15日
        {
            "day": 15, "time": "10:30", "type": "自由遊び", "desc": "ブロック遊び",
            "obs": ["赤と青のブロックを選んで遊んだ", "ブロックを3つ重ねることに成功", "崩れても何度も挑戦した"],
            "mood": "集中していた", "words": ["できた！", "もっと"], "tags": ["遊び", "ブロック", "達成感"]
        },
        # 1月16日
        {
            "day": 16, "time": "10:00", "type": "制作活動", "desc": "お絵かき",
            "obs": ["クレヨンで大きな円を描いた", "赤色を好んで使った", "「ママ」と言いながら描いた"],
            "mood": "楽しそう", "words": ["ママ", "あか"], "tags": ["制作", "お絵かき"]
        },
        # 1月17日
        {
            "day": 17, "time": "11:00", "type": "音楽活動", "desc": "楽器遊び",
            "obs": ["タンバリンを叩いた", "リズムに合わせて動いた", "「シャンシャン」と言った"],
            "mood": "楽しそう", "words": ["シャンシャン"], "tags": ["音楽", "楽器"]
        },
        # 1月18日
        {
            "day": 18, "time": "14:30", "type": "自由遊び", "desc": "ままごと",
            "obs": ["お皿に食べ物を並べた", "「どうぞ」と友達に渡した", "エプロンを着けたがった"],
            "mood": "楽しそう", "words": ["どうぞ", "おいしい"], "tags": ["遊び", "社会性"]
        },
        # 1月19日
        {
            "day": 19, "time": "10:00", "type": "体操", "desc": "マット運動",
            "obs": ["でんぐり返しに挑戦した", "先生に手伝ってもらった", "できた時に拍手した"],
            "mood": "挑戦的", "words": ["できた", "もういっかい"], "tags": ["運動", "挑戦"]
        },
        # 1月20日
        {
            "day": 20, "time": "14:30", "type": "自由遊び", "desc": "ボール遊び",
            "obs": ["初めてボールをキックできた", "ボールを追いかけて走った", "友達にボールを渡そうとした"],
            "mood": "活発", "words": ["ボール", "キック"], "tags": ["遊び", "運動", "初めて"]
        },
        # 1月21日
        {
            "day": 21, "time": "11:00", "type": "お散歩", "desc": "商店街散歩",
            "obs": ["お店の人に手を振った", "「こんにちは」と挨拶した", "パン屋さんの匂いに反応した"],
            "mood": "社交的", "words": ["こんにちは", "パン"], "tags": ["お散歩", "挨拶"]
        },
        # 1月22日
        {
            "day": 22, "time": "10:30", "type": "制作活動", "desc": "節分の鬼作り",
            "obs": ["赤い紙で鬼を作った", "角を2本付けた", "「おに」と言いながら作った"],
            "mood": "楽しそう", "words": ["おに", "こわい"], "tags": ["制作", "季節行事"]
        },
        # 1月23日
        {
            "day": 23, "time": "14:00", "type": "自由遊び", "desc": "パズル",
            "obs": ["6ピースパズルに挑戦した", "動物の絵を完成させた", "「できた」と喜んだ"],
            "mood": "集中していた", "words": ["できた", "どうぶつ"], "tags": ["遊び", "パズル"]
        },
        # 1月24日
        {
            "day": 24, "time": "11:30", "type": "給食", "desc": "カレーライス",
            "obs": ["スプーンで上手に食べた", "「からい」と言いながらも完食", "お水をたくさん飲んだ"],
            "mood": "頑張った", "words": ["からい", "おいしい"], "tags": ["給食", "成長"]
        },
        # 1月25日
        {
            "day": 25, "time": "15:00", "type": "読み聞かせ", "desc": "絵本の時間",
            "obs": ["絵本に集中して見入った", "動物の絵を指差した", "「にゃんにゃん」と猫の真似をした"],
            "mood": "集中していた", "words": ["にゃんにゃん", "わんわん"], "tags": ["読み聞かせ", "言葉"]
        },
        # 1月26日
        {
            "day": 26, "time": "10:00", "type": "音楽活動", "desc": "歌の時間",
            "obs": ["「きらきら星」を歌った", "手をキラキラさせた", "最後まで歌い切った"],
            "mood": "楽しそう", "words": ["きらきら", "ほし"], "tags": ["音楽", "歌"]
        },
        # 1月27日
        {
            "day": 27, "time": "14:30", "type": "自由遊び", "desc": "砂場遊び",
            "obs": ["砂でケーキを作った", "型抜きを使った", "「ケーキ」と言って見せた"],
            "mood": "創造的", "words": ["ケーキ", "つくった"], "tags": ["遊び", "砂場"]
        },
        # 1月28日
        {
            "day": 28, "time": "11:00", "type": "体操", "desc": "かけっこ",
            "obs": ["一生懸命走った", "転んでも泣かなかった", "ゴールで手を上げた"],
            "mood": "頑張り屋", "words": ["はしる", "がんばる"], "tags": ["運動", "成長"]
        },
        # 1月29日
        {
            "day": 29, "time": "10:30", "type": "制作活動", "desc": "豆まきの豆入れ作り",
            "obs": ["紙コップに絵を描いた", "シールを貼った", "「まめまき」と言った"],
            "mood": "楽しそう", "words": ["まめまき", "おに"], "tags": ["制作", "節分"]
        },
        # 1月30日
        {
            "day": 30, "time": "14:00", "type": "自由遊び", "desc": "電車ごっこ",
            "obs": ["椅子を並べて電車を作った", "「しゅっぱつ」と言った", "友達を乗せた"],
            "mood": "リーダーシップ", "words": ["しゅっぱつ", "でんしゃ"], "tags": ["遊び", "想像力"]
        },
        # 1月31日
        {
            "day": 31, "time": "11:00", "type": "お誕生会", "desc": "1月生まれのお誕生会",
            "obs": ["お友達に「おめでとう」と言った", "ケーキの歌を歌った", "拍手で祝った"],
            "mood": "お祝いムード", "words": ["おめでとう", "ケーキ"], "tags": ["行事", "社会性"]
        },
    ]
    
    # 各日の活動データから ChildcareRecord を生成
    for i, activity in enumerate(daily_activities):
        record = ChildcareRecord(
            id=f"rec-{i+1:03d}",
            timestamp=f"2024-01-{activity['day']:02d}T{activity['time']}:00+09:00",
            child_id="child-123",
            recorded_by="田中先生" if i % 2 == 0 else "山田先生",
            activity={
                "type": activity["type"],
                "description": activity["desc"],
                "duration": 30,
                "location": "保育室" if "制作" in activity["type"] or "自由遊び" in activity["type"] else "園庭",
            },
            observations=activity["obs"],
            child_state={
                "mood": activity["mood"],
                "verbal_expressions": activity["words"],
            },
            media_id=f"photo-{i+1:03d}" if i % 3 != 2 else f"video-{i+1:03d}",
            tags=activity["tags"],
        )
        records.append(record)
    
    return records