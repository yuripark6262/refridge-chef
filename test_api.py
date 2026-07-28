"""OpenRouter + Gemma API 동작 테스트: 텍스트 인식 / 이미지 인식."""
import base64
import io
import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()

API_KEY = os.environ["openrouter_api_key"]
MODEL = "google/gemma-4-26b-a4b-it:free"
URL = "https://openrouter.ai/api/v1/chat/completions"


def call(messages):
    """OpenRouter chat completions 호출."""
    payload = json.dumps({"model": MODEL, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return f"[HTTP {e.code}] {e.read().decode('utf-8', 'replace')}"
    except Exception as e:  # noqa: BLE001
        return f"[ERROR] {type(e).__name__}: {e}"


def make_test_image_data_url():
    """빨간 원 하나가 그려진 간단한 이미지를 만들어 data URL로 반환."""
    img = Image.new("RGB", (200, 200), "white")
    d = ImageDraw.Draw(img)
    d.ellipse([50, 50, 150, 150], fill="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


print("=" * 60)
print("1) 텍스트 인식 테스트")
print("=" * 60)
text_result = call([
    {"role": "user", "content": "한 문장으로 답해줘: 대한민국의 수도는 어디야?"}
])
print(text_result)

print()
print("=" * 60)
print("2) 이미지 인식 테스트")
print("=" * 60)
image_result = call([
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "이 이미지에 무엇이 보여? 색과 도형을 말해줘."},
            {"type": "image_url", "image_url": {"url": make_test_image_data_url()}},
        ],
    }
])
print(image_result)
