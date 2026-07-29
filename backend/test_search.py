"""DeepSeek 레시피 생성 + 저장 레시피 검색/필터 통합 테스트."""
import json
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8000"


def req(path, method="GET", body=None, token=None):
    headers, data = {}, None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


for _ in range(10):
    try:
        urllib.request.urlopen(BASE + "/api/health", timeout=3); break
    except Exception:
        time.sleep(1)

# 로그인/가입
email = "search_tester@example.com"
st, body = req("/api/auth/signup", "POST", {"email": email, "password": "secret123", "nickname": "검색테스터"})
if st == 409:
    st, body = req("/api/auth/login", "POST", {"email": email, "password": "secret123"})
token = body["token"]
print(f"인증: HTTP {st}")

# 1) DeepSeek 레시피 생성 확인
print("\n[1] DeepSeek 레시피 생성 (deepseek/deepseek-chat)")
st, body = req("/api/recipes", "POST", {"ingredients": ["달걀", "밥", "김치"], "count": 2}, token)
print(f"   HTTP {st}, 생성된 레시피 {len(body.get('recipes', []))}개")
for r in body.get("recipes", []):
    print(f"     - {r['title']} ({r.get('minutes')}분/{r.get('difficulty')})")

# 2) 검색 필터 테스트용 레시피를 결정적으로 저장
print("\n[2] 테스트 레시피 저장")
samples = [
    {"title": "김치볶음밥", "ingredients": [{"name": "밥", "have": True}, {"name": "김치", "have": True}], "steps": ["볶기"], "minutes": 10, "difficulty": "쉬움"},
    {"title": "된장찌개", "ingredients": [{"name": "된장", "have": True}, {"name": "두부", "have": True}], "steps": ["끓이기"], "minutes": 25, "difficulty": "보통"},
    {"title": "소고기 스튜", "ingredients": [{"name": "소고기", "have": True}, {"name": "감자", "have": True}], "steps": ["오래 끓이기"], "minutes": 90, "difficulty": "어려움"},
]
for s in samples:
    st, _ = req("/api/recipes/save", "POST", {"recipe": s}, token)
print(f"   {len(samples)}개 저장 완료")

# 3) 검색/필터 검증
print("\n[3] 검색·필터")
tests = [
    ("전체", "/api/recipes/saved"),
    ("키워드 '김치'", "/api/recipes/saved?q=김치"),
    ("재료 '두부'", "/api/recipes/saved?q=두부"),
    ("난이도=쉬움", "/api/recipes/saved?difficulty=쉬움"),
    ("30분 이내", "/api/recipes/saved?max_minutes=30"),
    ("쉬움+30분", "/api/recipes/saved?difficulty=쉬움&max_minutes=30"),
]
import urllib.parse
for label, path in tests:
    # 한글 쿼리 인코딩
    if "?" in path:
        base, qs = path.split("?", 1)
        path = base + "?" + urllib.parse.quote(qs, safe="=&")
    st, body = req(path, token=token)
    titles = [i["recipe"]["title"] for i in body]
    print(f"   {label:14s} → {len(titles)}개: {titles}")
