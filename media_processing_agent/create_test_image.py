"""
テスト用の画像を作成してCloud Storageにアップロード
"""
from PIL import Image, ImageDraw, ImageFont
import io
from google.cloud import storage
import datetime

# テスト画像を作成
img = Image.new('RGB', (800, 600), color='lightblue')
draw = ImageDraw.Draw(img)

# テキストを描画
text = f"Test Image\n{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nFirestore Trigger Test"
try:
    # デフォルトフォントを使用
    font = ImageFont.load_default()
except:
    font = None

# テキストを中央に配置
draw.multiline_text((400, 300), text, fill='darkblue', anchor='mm', font=font)

# 画像をバイト列に変換
img_byte_arr = io.BytesIO()
img.save(img_byte_arr, format='JPEG')
img_byte_arr = img_byte_arr.getvalue()

# Cloud Storageにアップロード
client = storage.Client(project="hackason-464007")
bucket = client.bucket("hackason-464007.firebasestorage.app")
blob = bucket.blob("test/test_image_001.jpg")
blob.upload_from_string(img_byte_arr, content_type="image/jpeg")

print(f"✅ Test image uploaded to: gs://{bucket.name}/{blob.name}")
print(f"📏 Size: {len(img_byte_arr):,} bytes")