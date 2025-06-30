import firebase_admin
import json
from firebase_admin import credentials, firestore
from datetime import datetime

# サービスアカウントキーのパスを設定
SECRET_KEY_PATH = 'hackason-464007-firebase-adminsdk-fbsvc-5e846f6c78.json'

# 既存のアプリを削除
if len(firebase_admin._apps) > 0:
    firebase_admin.delete_app(firebase_admin.get_app())

# Firebase Admin SDK を初期化
cred = credentials.Certificate(SECRET_KEY_PATH)
firebase_admin.initialize_app(cred)

db = firestore.client()

# 新しいフォーマットのダミーデータ
notebook_data_001 = {
    "nickname": "たろうくん",
    "date": datetime.now(),
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
}

notebook_data_002 = {
    "nickname": "はなちゃん",
    "date": datetime.now(),
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
}

# Firestoreにデータを更新
print("Updating notebook_001...")
db.collection('notebooks').document('notebook_001').set(notebook_data_001)
print("Successfully updated notebook_001")

print("Updating notebook_002...")
db.collection('notebooks').document('notebook_002').set(notebook_data_002)
print("Successfully updated notebook_002")

print("All data updated successfully with new format!")