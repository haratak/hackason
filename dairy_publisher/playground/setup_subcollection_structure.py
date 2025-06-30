import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

# サービスアカウントキーのパスを設定
SECRET_KEY_PATH = 'hackason-464007-firebase-adminsdk-fbsvc-5e846f6c78.json'

# 既存のアプリを削除
if len(firebase_admin._apps) > 0:
    firebase_admin.delete_app(firebase_admin.get_app())

# Firebase Admin SDK を初期化
cred = credentials.Certificate(SECRET_KEY_PATH)
firebase_admin.initialize_app(cred)

db = firestore.client()

# 子供の基本情報
children_info = {
    "taro_2020": {
        "name": "田中太郎",
        "nickname": "たろうくん",
        "birthdate": "2020-06-15",
        "gender": "male"
    },
    "hana_2022": {
        "name": "山田花子",
        "nickname": "はなちゃん",
        "birthdate": "2022-03-20",
        "gender": "female"
    }
}

# 各子供のノートブックデータ
notebooks_data = {
    "taro_2020": {
        "2024_06_week1": {
            "date": datetime.now() - timedelta(days=7),
            "title": "2024年6月第1週",
            "topics": [
                {
                    "title": "今週の興味",
                    "subtitle": "お気に入りの絵本",
                    "content": "今週は「はらぺこあおむし」の絵本に夢中です。カラフルな色彩と優しいイラストに目を輝かせて、ページをめくるたびに嬉しそうな声を出しています。特に果物のページがお気に入りで、指でさしながら「あー、あー」と一生懸命お話ししようとしています。読み聞かせの時間が親子のかけがえのない時間になっています。",
                    "photo": "https://via.placeholder.com/400x200/FFB6C1/333333?text=絵本を読むたろうくん"
                },
                {
                    "title": "行った！場所",
                    "content": "今週は近所の桜並木公園に初めて行きました。ベビーカーでのお散歩デビューです。青空の下で気持ちよさそうにしていて、風に揺れる木々を不思議そうに見上げていました。公園のベンチでひと休みしながら、鳥のさえずりや子どもたちの遊ぶ声を聞いて、とても楽しそうでした。来週はもう少し足を伸ばして、池のある大きな公園にも行ってみたいと思います。"
                },
                {
                    "title": "初めてのピクニック",
                    "caption": "初めての公園に行って",
                    "content": "天気の良い日曜日、家族でピクニックに行きました。レジャーシートの上でみんなでお弁当を食べて、とても気持ちの良い時間を過ごしました。外の空気を吸いながら、ご機嫌でした。",
                    "photo": "https://via.placeholder.com/300x120/98FB98/333333?text=ピクニック"
                },
                {
                    "title": "今週のベストショット",
                    "caption": "今週一番の笑顔",
                    "photo": "https://via.placeholder.com/300x150/87CEEB/333333?text=最高の笑顔"
                },
                {
                    "title": "できるようになったこと",
                    "content": "この一週間で、うつ伏せの時間が長くなりました。首がしっかりしてきて、周りを見回すのが上手になってきています。また、手をじっと見つめる「ハンドリガード」もよく見られるようになりました。指を動かしたり、手を口に持っていったりと、自分の体への興味が高まっているようです。夜もまとまって眠るようになり、生活リズムが整ってきています。毎日小さな成長が見られて、とても嬉しい毎日です。"
                }
            ]
        },
        "2024_06_week2": {
            "date": datetime.now(),
            "title": "2024年6月第2週",
            "topics": [
                {
                    "title": "今週の興味",
                    "subtitle": "積み木遊び",
                    "content": "今週は積み木に興味を持ち始めました。まだ上手に積むことはできませんが、カラフルな積み木を手に取って、不思議そうに眺めています。時々、積み木同士をカチカチと打ち合わせて音を楽しんでいます。これから積み木で遊ぶのが上手になっていくのが楽しみです。",
                    "photo": "https://via.placeholder.com/400x200/FFE5CC/333333?text=積み木で遊ぶたろうくん"
                },
                {
                    "title": "行った！場所",
                    "content": "今週は水族館デビューをしました！大きな水槽の前で、泳ぐ魚たちをじっと見つめていました。特にカラフルな熱帯魚に興味を示して、指をさしながら「あっあっ」と声を出していました。イルカショーでは、水しぶきに少し驚いていましたが、最後は楽しそうに拍手をしていました。"
                },
                {
                    "title": "水族館デビュー",
                    "caption": "大きな水槽に夢中",
                    "content": "初めての水族館で、たくさんの魚たちに出会いました。キラキラ光る魚の群れを追いかけるように目で追っていて、とても興味深そうでした。",
                    "photo": "https://via.placeholder.com/300x120/87CEFA/333333?text=水族館"
                },
                {
                    "title": "今週のベストショット",
                    "caption": "お魚さんにバイバイ",
                    "photo": "https://via.placeholder.com/300x150/FFB6C1/333333?text=お魚にバイバイ"
                },
                {
                    "title": "できるようになったこと",
                    "content": "今週は「ママ」という言葉がはっきり言えるようになりました！まだ意味を完全に理解しているわけではないかもしれませんが、嬉しそうに「ママ、ママ」と繰り返しています。また、おもちゃを「どうぞ」と渡してくれるようになりました。人とのやり取りを楽しんでいる様子が見られて、成長を感じます。"
                }
            ]
        }
    },
    "hana_2022": {
        "2024_06_week1": {
            "date": datetime.now() - timedelta(days=7),
            "title": "2024年6月第1週",
            "topics": [
                {
                    "title": "今週の興味",
                    "subtitle": "音楽が大好き！",
                    "content": "最近は音楽に合わせて体を動かすのが大好きです。特に「おもちゃのチャチャチャ」が流れると、手をたたいたり、体を左右に揺らしたりして踊っています。リズム感が良くて、音楽が止まると「もっと！」とおねだりするようになりました。毎日の音楽タイムが楽しみです。",
                    "photo": "https://via.placeholder.com/400x200/FFA07A/333333?text=踊るはなちゃん"
                },
                {
                    "title": "行った！場所",
                    "content": "今週は初めて動物園に行きました！キリンを見て「おおきい！」と大興奮。ゾウさんにも会えて、長い鼻に興味津々でした。ふれあいコーナーでは、うさぎさんを優しくなでなでできました。帰りの車では疲れてぐっすり。とても充実した一日でした。"
                },
                {
                    "title": "初めての動物園",
                    "caption": "うさぎさんと仲良し",
                    "content": "ふれあいコーナーでうさぎさんと初対面。最初は恐る恐るでしたが、優しくなでることができました。「ふわふわ」と言いながら、とても嬉しそうでした。",
                    "photo": "https://via.placeholder.com/300x120/DDA0DD/333333?text=うさぎとはなちゃん"
                },
                {
                    "title": "今週のベストショット",
                    "caption": "満面の笑みでバイバイ",
                    "photo": "https://via.placeholder.com/300x150/F0E68C/333333?text=バイバイする姿"
                },
                {
                    "title": "できるようになったこと",
                    "content": "今週は「バイバイ」が上手にできるようになりました！手を振りながら「ばいばーい」と言えるようになって、お出かけの時やお客さんが帰る時に披露しています。また、スプーンを使ってご飯を食べるのも上達しました。こぼすことも減って、自分で食べる喜びを感じているようです。言葉も増えて、「わんわん」「にゃんにゃん」「ぶーぶー」など、いろいろな単語を話すようになりました。"
                }
            ]
        },
        "2024_06_week2": {
            "date": datetime.now(),
            "title": "2024年6月第2週",
            "topics": [
                {
                    "title": "今週の興味",
                    "subtitle": "お絵かきデビュー",
                    "content": "今週はクレヨンでお絵かきデビューしました！まだぐるぐると円を描くだけですが、色とりどりのクレヨンを使って楽しそうに描いています。特に赤と黄色がお気に入りで、「あか！」「きいろ！」と言いながら描いています。紙からはみ出すこともありますが、それも含めて楽しい芸術作品です。",
                    "photo": "https://via.placeholder.com/400x200/FFE5CC/333333?text=お絵かきするはなちゃん"
                },
                {
                    "title": "行った！場所",
                    "content": "今週は児童館の親子イベントに参加しました。同じくらいの年齢のお友達がたくさんいて、最初は恥ずかしがっていましたが、徐々に慣れてきました。手遊び歌の時間では、先生の真似をして一生懸命手を動かしていました。新しいお友達もできて、とても良い経験になりました。"
                },
                {
                    "title": "児童館デビュー",
                    "caption": "新しいお友達と一緒に",
                    "content": "児童館で開催された親子リトミックに参加。音楽に合わせてみんなで体を動かしました。最初は緊張していましたが、だんだん笑顔が増えてきました。",
                    "photo": "https://via.placeholder.com/300x120/98FB98/333333?text=児童館"
                },
                {
                    "title": "今週のベストショット",
                    "caption": "お友達と手をつないで",
                    "photo": "https://via.placeholder.com/300x150/FFB6C1/333333?text=お友達と一緒"
                },
                {
                    "title": "できるようになったこと",
                    "content": "今週は2語文が話せるようになりました！「ママ、だっこ」「パパ、いた」など、単語を組み合わせて気持ちを伝えられるようになってきました。また、色の名前も覚え始めて、「あか」「あお」「きいろ」が言えるようになりました。絵本を見ながら「これ、あか！」と指さして教えてくれます。言葉の成長が著しく、毎日新しい発見があります。"
                }
            ]
        }
    }
}

print("Setting up new data structure with subcollections...")

# 1. 子供の基本情報を保存
for child_id, child_info in children_info.items():
    print(f"\nCreating child document: {child_id}")
    db.collection('children').document(child_id).set(child_info)
    
    # 2. 各子供のノートブックをサブコレクションとして保存
    if child_id in notebooks_data:
        for notebook_id, notebook_data in notebooks_data[child_id].items():
            print(f"  Adding notebook: {notebook_id}")
            # nicknameを各ノートブックにも含める（表示用）
            notebook_data['nickname'] = child_info['nickname']
            db.collection('children').document(child_id).collection('notebooks').document(notebook_id).set(notebook_data)

print("\nData structure setup complete!")
print("\nNew URLs will be:")
print("- https://hackason-464007.web.app/children/taro_2020/notebooks/2024_06_week1")
print("- https://hackason-464007.web.app/children/taro_2020/notebooks/2024_06_week2")
print("- https://hackason-464007.web.app/children/hana_2022/notebooks/2024_06_week1")
print("- https://hackason-464007.web.app/children/hana_2022/notebooks/2024_06_week2")