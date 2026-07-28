"""1단계 백엔드: 냉장고 이미지에서 식재료를 인식하는 FastAPI 서버.

- POST /api/recognize : { image: "data:image/...;base64,..." } 를 받아
  OpenRouter의 google/gemma-4-26b-a4b-it:free 모델로 재료를 인식하고
  { ingredients: [{ name, confidence }] } 를 반환한다.

OpenRouter API 키는 프로젝트 루트의 .env(openrouter_api_key)에서 로드하며,
프론트엔드에는 절대 노출되지 않는다.
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db

# 프로젝트 루트(.env는 backend 상위 디렉터리에 있음)
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("openrouter_api_key")
MODEL = "google/gemma-4-26b-a4b-it:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

RECOGNIZE_PROMPT = (
    "너는 냉장고 사진에서 식재료를 인식하는 도우미다. "
    "사진에 실제로 보이는 식재료만 골라 아래 JSON 형식으로만 답하라. 설명 문장은 절대 쓰지 마라.\n"
    '{"ingredients": [{"name": "재료명(한국어)", "confidence": 0.0~1.0}]}\n'
    "식재료가 하나도 없으면 {\"ingredients\": []} 를 반환하라."
)

RECIPE_PROMPT_TEMPLATE = (
    "너는 요리 추천 도우미다. 아래 보유 재료로 만들 수 있는 레시피를 최대 {count}개 제안하라.\n"
    "가능한 한 보유 재료를 최대한 활용하고, 소금·후추·기름 등 기본 양념은 있다고 가정한다.\n"
    "각 레시피에서 필요한 재료 중 보유 목록에 없는 것은 have=false 로 표시한다.\n"
    "아래 조건을 반드시 반영하라: {conditions}\n"
    "설명 문장 없이 아래 JSON 형식으로만 답하라.\n"
    '{{"recipes":[{{"title":"요리 이름","ingredients":[{{"name":"재료명","have":true}}],'
    '"steps":["1단계 설명","2단계 설명"],"minutes":15,"difficulty":"쉬움"}}]}}\n'
    "difficulty 는 반드시 \"쉬움\", \"보통\", \"어려움\" 중 하나여야 한다.\n\n"
    "보유 재료: {ingredients}"
)

app = FastAPI(title="냉장고 재료 인식 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    db.init_db()


def current_user(authorization: str | None = Header(default=None)):
    """Authorization: Bearer <token> 로 인증. 실패 시 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "로그인이 필요합니다.")
    token = authorization.split(" ", 1)[1].strip()
    user = db.user_for_token(token)
    if not user:
        raise HTTPException(401, "세션이 만료되었거나 유효하지 않습니다.")
    return user


class RecognizeRequest(BaseModel):
    image: str  # data URL: "data:image/png;base64,...."


class Ingredient(BaseModel):
    name: str
    confidence: float | None = None


class RecognizeResponse(BaseModel):
    ingredients: list[Ingredient]


class Preferences(BaseModel):
    diet: str | None = None            # 예: "채식", "비건", "none"
    allergies: list[str] = []          # 예: ["땅콩", "우유"]
    max_minutes: int | None = None     # 최대 조리 시간(분)
    servings: int | None = None        # 인분


class RecipeRequest(BaseModel):
    ingredients: list[str]
    preferences: Preferences = Preferences()
    count: int = 3


class RecipeIngredient(BaseModel):
    name: str
    have: bool = True


class Recipe(BaseModel):
    title: str
    ingredients: list[RecipeIngredient]
    steps: list[str]
    minutes: int | None = None
    difficulty: str | None = None


class RecipeResponse(BaseModel):
    recipes: list[Recipe]


# --- 3단계: 인증 / 프로필 / 저장 ---
class SignupRequest(BaseModel):
    email: str
    password: str
    nickname: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    nickname: str


class ProfileData(BaseModel):
    email: str
    nickname: str
    diet: str
    allergies: list[str]
    default_servings: int


class ProfileUpdate(BaseModel):
    diet: str = "none"
    allergies: list[str] = []
    default_servings: int = 2


class SaveRecipeRequest(BaseModel):
    recipe: Recipe


class SavedRecipe(BaseModel):
    id: int
    title: str
    created_at: str
    recipe: Recipe


def _chat(messages: list[dict]) -> str:
    """OpenRouter chat completions 호출, 모델의 텍스트 응답을 반환."""
    payload = json.dumps({"model": MODEL, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _extract_json(text: str) -> str:
    """모델 응답 텍스트에서 JSON 객체 문자열을 추출 (코드펜스·잡음 방어)."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    return match.group(0) if match else cleaned


def _parse_ingredients(text: str) -> list[dict]:
    """모델 응답 텍스트에서 재료 배열을 추출/파싱. 코드펜스·잡음에 내성."""
    obj = json.loads(_extract_json(text))
    items = obj.get("ingredients", [])
    result = []
    for it in items:
        if isinstance(it, dict) and it.get("name"):
            conf = it.get("confidence")
            result.append(
                {"name": str(it["name"]).strip(), "confidence": conf}
            )
        elif isinstance(it, str) and it.strip():
            result.append({"name": it.strip(), "confidence": None})
    return result


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL, "key_loaded": bool(API_KEY)}


@app.post("/api/recognize", response_model=RecognizeResponse)
def recognize(req: RecognizeRequest):
    if not API_KEY:
        raise HTTPException(500, "서버에 openrouter_api_key가 설정되지 않았습니다 (.env 확인).")
    if not req.image.startswith("data:image/"):
        raise HTTPException(400, "image는 'data:image/...;base64,...' 형식의 data URL이어야 합니다.")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": RECOGNIZE_PROMPT},
                {"type": "image_url", "image_url": {"url": req.image}},
            ],
        }
    ]
    try:
        raw = _chat(messages)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise HTTPException(502, f"OpenRouter 오류 (HTTP {e.code}): {detail}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"모델 호출 실패: {type(e).__name__}: {e}")

    try:
        ingredients = _parse_ingredients(raw)
    except (json.JSONDecodeError, ValueError):
        # 파싱 실패 시 빈 목록으로 반환하되 원문을 힌트로 제공
        raise HTTPException(
            422,
            f"모델 응답을 재료 목록으로 파싱하지 못했습니다. 원문: {raw[:300]}",
        )

    return {"ingredients": ingredients}


def _build_conditions(pref: Preferences) -> str:
    """선호(Preferences)를 프롬프트에 넣을 조건 문장으로 변환."""
    parts = []
    if pref.diet and pref.diet.lower() not in ("none", "없음", ""):
        parts.append(f"식단은 '{pref.diet}'을(를) 지킬 것")
    if pref.allergies:
        parts.append(f"다음 알레르기 재료는 절대 사용 금지: {', '.join(pref.allergies)}")
    if pref.max_minutes:
        parts.append(f"총 조리 시간은 {pref.max_minutes}분 이내")
    if pref.servings:
        parts.append(f"{pref.servings}인분 기준")
    return " / ".join(parts) if parts else "특별한 제약 없음"


def _parse_recipes(text: str) -> list[dict]:
    obj = json.loads(_extract_json(text))
    recipes = []
    for r in obj.get("recipes", []):
        if not isinstance(r, dict) or not r.get("title"):
            continue
        ings = []
        for it in r.get("ingredients", []):
            if isinstance(it, dict) and it.get("name"):
                ings.append({"name": str(it["name"]).strip(), "have": bool(it.get("have", True))})
            elif isinstance(it, str) and it.strip():
                ings.append({"name": it.strip(), "have": True})
        steps = [str(s).strip() for s in r.get("steps", []) if str(s).strip()]
        recipes.append(
            {
                "title": str(r["title"]).strip(),
                "ingredients": ings,
                "steps": steps,
                "minutes": r.get("minutes"),
                "difficulty": r.get("difficulty"),
            }
        )
    return recipes


@app.post("/api/recipes", response_model=RecipeResponse)
def recipes(req: RecipeRequest):
    if not API_KEY:
        raise HTTPException(500, "서버에 openrouter_api_key가 설정되지 않았습니다 (.env 확인).")
    if not req.ingredients:
        raise HTTPException(400, "재료 목록이 비어 있습니다.")

    prompt = RECIPE_PROMPT_TEMPLATE.format(
        count=max(1, min(req.count, 5)),
        conditions=_build_conditions(req.preferences),
        ingredients=", ".join(req.ingredients),
    )
    try:
        raw = _chat([{"role": "user", "content": prompt}])
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise HTTPException(502, f"OpenRouter 오류 (HTTP {e.code}): {detail}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"모델 호출 실패: {type(e).__name__}: {e}")

    try:
        result = _parse_recipes(raw)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(422, f"모델 응답을 레시피로 파싱하지 못했습니다. 원문: {raw[:300]}")

    if not result:
        raise HTTPException(422, "조건에 맞는 레시피를 생성하지 못했습니다. 재료나 조건을 조정해 보세요.")

    return {"recipes": result}


# ============================================================
# 3단계: 인증 / 프로필 / 레시피 저장
# ============================================================
def _profile_dict(user) -> dict:
    return {
        "email": user["email"],
        "nickname": user["nickname"],
        "diet": user["diet"] or "none",
        "allergies": json.loads(user["allergies"] or "[]"),
        "default_servings": user["default_servings"] or 2,
    }


@app.post("/api/auth/signup", response_model=AuthResponse)
def signup(req: SignupRequest):
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "유효한 이메일을 입력하세요.")
    if len(req.password) < 6:
        raise HTTPException(400, "비밀번호는 6자 이상이어야 합니다.")
    if not req.nickname.strip():
        raise HTTPException(400, "닉네임을 입력하세요.")
    if db.get_user_by_email(email):
        raise HTTPException(409, "이미 가입된 이메일입니다.")

    user_id = db.create_user(email, req.password, req.nickname.strip())
    token = db.create_session(user_id)
    return {"token": token, "nickname": req.nickname.strip()}


@app.post("/api/auth/login", response_model=AuthResponse)
def login(req: LoginRequest):
    user = db.get_user_by_email(req.email.strip().lower())
    if not user or not db.verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다.")
    token = db.create_session(user["id"])
    return {"token": token, "nickname": user["nickname"]}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        db.delete_session(authorization.split(" ", 1)[1].strip())
    return {"ok": True}


@app.get("/api/profile", response_model=ProfileData)
def get_profile(user=Depends(current_user)):
    return _profile_dict(user)


@app.put("/api/profile", response_model=ProfileData)
def put_profile(req: ProfileUpdate, user=Depends(current_user)):
    db.update_profile(user["id"], req.diet, req.allergies, req.default_servings)
    return _profile_dict(db.get_user_by_email(user["email"]))


@app.post("/api/recipes/save", response_model=SavedRecipe)
def save_recipe(req: SaveRecipeRequest, user=Depends(current_user)):
    row = db.save_recipe(user["id"], req.recipe.model_dump())
    return {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "recipe": json.loads(row["data"]),
    }


@app.get("/api/recipes/saved", response_model=list[SavedRecipe])
def saved_recipes(user=Depends(current_user)):
    rows = db.list_recipes(user["id"])
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "created_at": r["created_at"],
            "recipe": json.loads(r["data"]),
        }
        for r in rows
    ]


@app.delete("/api/recipes/saved/{recipe_id}")
def delete_saved_recipe(recipe_id: int, user=Depends(current_user)):
    if not db.delete_recipe(user["id"], recipe_id):
        raise HTTPException(404, "레시피를 찾을 수 없거나 삭제 권한이 없습니다.")
    return {"ok": True}
