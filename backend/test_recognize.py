"""백엔드 /api/recognize 엔드포인트 통합 테스트."""
import base64
import io
import json
import urllib.request

from PIL import Image, ImageDraw

# 냉장고 속 재료처럼 보이는 간단한 그림 생성: 토마토, 달걀, 당근
img = Image.new("RGB", (400, 300), "#e8e8e8")
d = ImageDraw.Draw(img)
# 토마토 (빨간 원 + 초록 꼭지)
d.ellipse([40, 120, 130, 210], fill="#e23b2e")
d.polygon([(80, 118), (70, 128), (90, 128)], fill="#2e8b57")
# 달걀 (흰 타원 + 노른자)
d.ellipse([170, 130, 250, 210], fill="#fdfcf5")
d.ellipse([195, 155, 225, 185], fill="#f2b705")
# 당근 (주황 삼각형 + 초록 잎)
d.polygon([(310, 130), (340, 130), (325, 220)], fill="#ef7d1a")
d.line([(325, 130), (315, 105)], fill="#2e8b57", width=6)
d.line([(325, 130), (335, 105)], fill="#2e8b57", width=6)

buf = io.BytesIO()
img.save(buf, format="PNG")
data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

payload = json.dumps({"image": data_url}).encode()
req = urllib.request.Request(
    "http://localhost:8000/api/recognize",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=90) as resp:
    result = json.loads(resp.read().decode())

print(json.dumps(result, ensure_ascii=False, indent=2))
