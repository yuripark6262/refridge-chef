"""백엔드 /api/recipes 엔드포인트 통합 테스트."""
import json
import time
import urllib.request

# 서버 기동 대기
for _ in range(10):
    try:
        urllib.request.urlopen("http://localhost:8000/api/health", timeout=3)
        break
    except Exception:
        time.sleep(1)

payload = json.dumps(
    {
        "ingredients": ["달걀", "대파", "밥", "김치"],
        "preferences": {"diet": "none", "allergies": [], "max_minutes": 20, "servings": 2},
        "count": 2,
    }
).encode()

req = urllib.request.Request(
    "http://localhost:8000/api/recipes",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=120) as resp:
    result = json.loads(resp.read().decode())

print(f"레시피 {len(result['recipes'])}개 생성됨\n")
for r in result["recipes"]:
    have = [i["name"] for i in r["ingredients"] if i["have"]]
    missing = [i["name"] for i in r["ingredients"] if not i["have"]]
    print(f"■ {r['title']}  ({r.get('minutes')}분 / {r.get('difficulty')})")
    print(f"   보유: {', '.join(have)}")
    if missing:
        print(f"   부족: {', '.join(missing)}")
    print(f"   단계: {len(r['steps'])}개")
    print()
