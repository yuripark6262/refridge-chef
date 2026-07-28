"""3단계 통합 테스트: 회원가입 → 프로필 → 레시피 저장/조회/삭제 + 권한 검사."""
import json
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8000"


def req(path, method="GET", body=None, token=None):
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


# 서버 대기
for _ in range(10):
    try:
        urllib.request.urlopen(BASE + "/api/health", timeout=3)
        break
    except Exception:
        time.sleep(1)

# 고유 이메일 (DB에 이미 있으면 로그인으로 대체)
email = "tester_step3@example.com"
ok = True

# 1) 회원가입 (이미 있으면 409 → 로그인)
st, body = req("/api/auth/signup", "POST", {"email": email, "password": "secret123", "nickname": "테스터"})
if st == 409:
    st, body = req("/api/auth/login", "POST", {"email": email, "password": "secret123"})
print(f"1) 인증: HTTP {st}, nickname={body.get('nickname')}")
token = body["token"]

# 2) 잘못된 비밀번호 로그인 → 401 기대
st, _ = req("/api/auth/login", "POST", {"email": email, "password": "wrong"})
print(f"2) 잘못된 비밀번호: HTTP {st} (401 기대) {'OK' if st == 401 else 'FAIL'}")
ok &= st == 401

# 3) 인증 없이 프로필 접근 → 401 기대
st, _ = req("/api/profile")
print(f"3) 무인증 프로필: HTTP {st} (401 기대) {'OK' if st == 401 else 'FAIL'}")
ok &= st == 401

# 4) 프로필 수정
st, body = req("/api/profile", "PUT", {"diet": "채식", "allergies": ["땅콩"], "default_servings": 3}, token)
print(f"4) 프로필 수정: HTTP {st}, diet={body.get('diet')}, allergies={body.get('allergies')}, servings={body.get('default_servings')}")
ok &= st == 200 and body.get("diet") == "채식"

# 5) 레시피 저장
recipe = {
    "title": "채식 김치볶음밥",
    "ingredients": [{"name": "밥", "have": True}, {"name": "김치", "have": True}],
    "steps": ["팬을 달군다", "재료를 볶는다"],
    "minutes": 15,
    "difficulty": "쉬움",
}
st, saved = req("/api/recipes/save", "POST", {"recipe": recipe}, token)
print(f"5) 레시피 저장: HTTP {st}, id={saved.get('id')}, title={saved.get('title')}")
ok &= st == 200
saved_id = saved.get("id")

# 6) 저장 목록 조회
st, items = req("/api/recipes/saved", token=token)
print(f"6) 저장 목록: HTTP {st}, 개수={len(items)}")
ok &= st == 200 and len(items) >= 1

# 7) 다른 사용자가 삭제 시도 → 404 기대 (권한 격리)
st2, other = req("/api/auth/signup", "POST", {"email": "intruder_step3@example.com", "password": "secret123", "nickname": "침입자"})
if st2 == 409:
    st2, other = req("/api/auth/login", "POST", {"email": "intruder_step3@example.com", "password": "secret123"})
st, _ = req(f"/api/recipes/saved/{saved_id}", "DELETE", token=other["token"])
print(f"7) 타인 레시피 삭제 차단: HTTP {st} (404 기대) {'OK' if st == 404 else 'FAIL'}")
ok &= st == 404

# 8) 본인 삭제
st, _ = req(f"/api/recipes/saved/{saved_id}", "DELETE", token=token)
print(f"8) 본인 레시피 삭제: HTTP {st} (200 기대) {'OK' if st == 200 else 'FAIL'}")
ok &= st == 200

print("\n=== 전체 결과:", "모두 통과 ✅" if ok else "실패 항목 있음 ❌", "===")
