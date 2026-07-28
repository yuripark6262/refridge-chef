"""냉장고 셰프 — Streamlit 웹 인터페이스 (Python 단일 프로세스).

기존 FastAPI 백엔드(main.py)의 모델 호출(`_chat`)·레시피 파싱과 db.py의
저장/인증 로직을 재사용한다. 별도 API 서버 없이 이 파일 하나로 동작한다.

1단계 입력은 두 가지: 파일 드래그앤드롭/클릭 업로드, 또는 이미지 URL.
이미지가 제공되면 즉시 AI가 재료(이름·수량·상태)를 자동 분석해 카드로 보여주고,
각 카드에서 수정·삭제할 수 있다.

실행:  cd backend && python -m streamlit run streamlit_app.py
"""
import base64
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from PIL import Image

import db
# 검증된 백엔드 로직 재사용 (import 시 서버가 뜨지 않음 — 함수/상수만 로드)
from main import RECIPE_PROMPT_TEMPLATE, _chat, _extract_json, _parse_recipes

st.set_page_config(page_title="냉장고 셰프", page_icon="🧊", layout="centered")
db.init_db()

# 수량·상태까지 추정하도록 지시하는 1단계 인식 프롬프트
RECOGNIZE_PROMPT_RICH = (
    "너는 냉장고 사진에서 식재료를 인식하는 도우미다. "
    "사진에 실제로 보이는 식재료마다 이름, 대략적인 수량, 신선도 상태를 추정해 "
    "아래 JSON 형식으로만 답하라. 설명 문장은 절대 쓰지 마라.\n"
    '{"ingredients": [{"name": "재료명(한국어)", '
    '"quantity": "수량(예: 2개, 1팩, 약간, 알수없음)", '
    '"state": "상태(신선함/보통/상함 의심 중 하나)"}]}\n'
    '식재료가 하나도 없으면 {"ingredients": []} 를 반환하라.'
)

DIETS = ["제한 없음", "채식", "비건", "저탄수화물"]
STATES = ["신선함", "보통", "상함 의심", "알수없음"]

# ---------- 상태 초기화 ----------
ss = st.session_state
ss.setdefault("user", None)          # {id, nickname, diet, allergies, default_servings} | None
ss.setdefault("ingredients", [])     # [{id, name, quantity, state}]
ss.setdefault("recipes", [])
ss.setdefault("img_sig", None)       # 마지막으로 분석한 이미지 서명 (중복 분석 방지)
ss.setdefault("_uid", 0)


# ---------- 헬퍼 ----------
def new_ing(name="", quantity="", state=""):
    ss._uid += 1
    return {"id": ss._uid, "name": name, "quantity": quantity, "state": state}


def bytes_to_data_url(data: bytes, max_size=1024, quality=85) -> str:
    """이미지 바이트를 긴 변 max_size로 리사이즈하고 JPEG data URL로 변환."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    if max(w, h) > max_size:
        if w >= h:
            img = img.resize((max_size, round(h * max_size / w)))
        else:
            img = img.resize((round(w * max_size / h), max_size))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def parse_rich_ingredients(text: str) -> list[dict]:
    obj = json.loads(_extract_json(text))
    out = []
    for it in obj.get("ingredients", []):
        if isinstance(it, dict) and it.get("name"):
            out.append(
                new_ing(
                    str(it["name"]).strip(),
                    str(it.get("quantity", "") or "").strip(),
                    str(it.get("state", "") or "").strip(),
                )
            )
        elif isinstance(it, str) and it.strip():
            out.append(new_ing(it.strip()))
    return out


def analyze_image(image_url: str):
    """image_url(data URL 또는 원격 URL)을 모델에 보내 재료를 인식하고 세션에 저장."""
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": RECOGNIZE_PROMPT_RICH},
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
    }]
    raw = _chat(messages)
    ss.ingredients = parse_rich_ingredients(raw)
    ss.recipes = []


def build_conditions(diet, allergies, max_minutes, servings):
    parts = []
    if diet and diet not in ("제한 없음", "none"):
        parts.append(f"식단은 '{diet}'을(를) 지킬 것")
    if allergies:
        parts.append(f"다음 알레르기 재료는 절대 사용 금지: {', '.join(allergies)}")
    if max_minutes:
        parts.append(f"총 조리 시간은 {max_minutes}분 이내")
    if servings:
        parts.append(f"{servings}인분 기준")
    return " / ".join(parts) if parts else "특별한 제약 없음"


def user_dict(row):
    return {
        "id": row["id"],
        "nickname": row["nickname"],
        "diet": row["diet"] or "제한 없음",
        "allergies": json.loads(row["allergies"] or "[]"),
        "default_servings": row["default_servings"] or 2,
    }


# ---------- 사이드바: 계정 ----------
with st.sidebar:
    st.header("👤 계정")
    if ss.user:
        st.success(f"{ss.user['nickname']} 님 로그인됨")
        if st.button("로그아웃"):
            ss.user = None
            st.rerun()
        st.divider()
        st.subheader("⭐ 내 선호 (프로필)")
        p_diet = st.selectbox("식단", DIETS, index=DIETS.index(ss.user["diet"]) if ss.user["diet"] in DIETS else 0)
        p_all = st.text_input("알레르기 (쉼표로 구분)", value=", ".join(ss.user["allergies"]))
        p_serv = st.number_input("기본 인분", min_value=1, max_value=20, value=int(ss.user["default_servings"]))
        if st.button("프로필 저장"):
            allergies = [s.strip() for s in p_all.split(",") if s.strip()]
            db.update_profile(ss.user["id"], p_diet, allergies, int(p_serv))
            ss.user.update(diet=p_diet, allergies=allergies, default_servings=int(p_serv))
            st.success("프로필이 저장되었어요 ✓")
    else:
        tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
        with tab_login:
            le = st.text_input("이메일", key="le")
            lp = st.text_input("비밀번호", type="password", key="lp")
            if st.button("로그인", key="login_btn"):
                row = db.get_user_by_email(le.strip().lower())
                if row and db.verify_password(lp, row["password_hash"]):
                    ss.user = user_dict(row)
                    st.rerun()
                else:
                    st.error("이메일 또는 비밀번호가 올바르지 않습니다.")
        with tab_signup:
            se = st.text_input("이메일", key="se")
            sp = st.text_input("비밀번호 (6자 이상)", type="password", key="sp")
            sn = st.text_input("닉네임", key="sn")
            if st.button("가입하기", key="signup_btn"):
                email = se.strip().lower()
                if "@" not in email:
                    st.error("유효한 이메일을 입력하세요.")
                elif len(sp) < 6:
                    st.error("비밀번호는 6자 이상이어야 합니다.")
                elif not sn.strip():
                    st.error("닉네임을 입력하세요.")
                elif db.get_user_by_email(email):
                    st.error("이미 가입된 이메일입니다.")
                else:
                    db.create_user(email, sp, sn.strip())
                    ss.user = user_dict(db.get_user_by_email(email))
                    st.rerun()


# ---------- 본문 ----------
st.title("🧊 냉장고 셰프")
st.caption("냉장고 사진 → 재료 자동 분석 → 레시피 추천 → 저장. (Streamlit 버전)")

# ── 1단계: 이미지 입력 (파일 업로드 / URL) ──
st.subheader("① 냉장고 사진 입력")
tab_file, tab_url = st.tabs(["📁 파일 업로드", "🔗 이미지 URL"])

image_url = None   # 분석에 사용할 URL (data URL 또는 원격 URL)
image_sig = None   # 중복 분석 방지용 서명
preview = None      # 미리보기용 (bytes 또는 url)

with tab_file:
    file = st.file_uploader(
        "냉장고 사진을 드래그앤드롭하거나 클릭해서 업로드",
        type=["png", "jpg", "jpeg", "webp"],
    )
    if file is not None:
        data = file.getvalue()
        image_url = bytes_to_data_url(data)
        image_sig = f"file:{file.name}:{len(data)}"
        preview = data

with tab_url:
    url = st.text_input("이미지 URL을 붙여넣으세요", placeholder="https://example.com/fridge.jpg")
    if url.strip() and file is None:  # 파일이 없을 때만 URL 사용
        image_url = url.strip()
        image_sig = f"url:{url.strip()}"
        preview = url.strip()

# 미리보기 + 업로드 즉시 자동 분석
if image_url:
    st.image(preview, caption="입력한 사진", use_container_width=True)
    col_a, col_b = st.columns([1, 3])
    reanalyze = col_a.button("🔄 다시 분석")
    if image_sig != ss.img_sig or reanalyze:
        ss.img_sig = image_sig
        with st.spinner("🤖 AI가 사진 속 재료를 자동 분석하고 있어요…"):
            try:
                analyze_image(image_url)
                if not ss.ingredients:
                    st.warning("재료를 찾지 못했어요. 아래에서 직접 추가해 주세요.")
            except Exception as e:  # noqa: BLE001
                st.error(f"분석 실패: {e}")

# ── 2단계 입력: 인식된 재료 카드 (수정·삭제) ──
if ss.ingredients:
    st.subheader(f"② 인식된 재료 ({len(ss.ingredients)})")
    st.caption("AI가 추정한 재료명·수량·상태입니다. 카드에서 직접 수정하거나 삭제하세요.")

    for ing in list(ss.ingredients):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1], vertical_alignment="bottom")
            ing["name"] = c1.text_input("재료명", ing["name"], key=f"name_{ing['id']}")
            ing["quantity"] = c2.text_input("수량", ing.get("quantity", ""), key=f"qty_{ing['id']}")
            state_val = ing.get("state") or "알수없음"
            if state_val not in STATES:
                STATES_OPT = STATES + [state_val]
            else:
                STATES_OPT = STATES
            ing["state"] = c3.selectbox(
                "상태", STATES_OPT, index=STATES_OPT.index(state_val), key=f"state_{ing['id']}"
            )
            if c4.button("🗑", key=f"del_{ing['id']}", help="이 재료 삭제"):
                ss.ingredients = [x for x in ss.ingredients if x["id"] != ing["id"]]
                st.rerun()

    if st.button("➕ 재료 추가"):
        ss.ingredients.append(new_ing("", "", "알수없음"))
        st.rerun()

# ── 3단계: 선호 조건 & 레시피 생성 ──
valid_names = [i["name"].strip() for i in ss.ingredients if i["name"].strip()]
if valid_names:
    st.subheader("③ 선호 조건 & 레시피 추천")
    c1, c2 = st.columns(2)
    default_diet = ss.user["diet"] if ss.user else "제한 없음"
    diet = c1.selectbox("식단", DIETS, index=DIETS.index(default_diet) if default_diet in DIETS else 0)
    max_min = c2.number_input("최대 조리시간(분, 0=제한없음)", min_value=0, max_value=240, value=0, step=5)
    c3, c4 = st.columns(2)
    servings = c3.number_input("인분", min_value=1, max_value=20, value=int(ss.user["default_servings"]) if ss.user else 2)
    allergies_str = c4.text_input("알레르기 (쉼표로 구분)", value=", ".join(ss.user["allergies"]) if ss.user else "")

    if st.button("🍳 레시피 추천 받기", type="primary"):
        allergies = [s.strip() for s in allergies_str.split(",") if s.strip()]
        conditions = build_conditions(diet, allergies, max_min or None, servings)
        prompt = RECIPE_PROMPT_TEMPLATE.format(
            count=3, conditions=conditions, ingredients=", ".join(valid_names)
        )
        with st.spinner("재료로 만들 수 있는 요리를 찾고 있어요…"):
            try:
                ss.recipes = _parse_recipes(_chat([{"role": "user", "content": prompt}]))
                if not ss.recipes:
                    st.warning("조건에 맞는 레시피를 만들지 못했어요. 재료나 조건을 조정해 보세요.")
            except Exception as e:  # noqa: BLE001
                st.error(f"레시피 생성 실패: {e}")

# 레시피 카드
if ss.recipes:
    st.subheader(f"추천 레시피 ({len(ss.recipes)})")
    for idx, r in enumerate(ss.recipes):
        meta = []
        if r.get("minutes") is not None:
            meta.append(f"⏱ {r['minutes']}분")
        if r.get("difficulty"):
            meta.append(f"📊 {r['difficulty']}")
        with st.expander(f"🍽 {r['title']}  ·  {' · '.join(meta)}", expanded=(idx == 0)):
            have = [i["name"] for i in r["ingredients"] if i.get("have", True)]
            missing = [i["name"] for i in r["ingredients"] if not i.get("have", True)]
            st.markdown("**보유 재료:** " + (", ".join(f"✅ {n}" for n in have) or "—"))
            if missing:
                st.markdown("**부족 재료:** " + ", ".join(f"🟡 {n}" for n in missing))
            st.markdown("**조리 단계:**")
            for i, s in enumerate(r["steps"], 1):
                st.markdown(f"{i}. {s}")
            if ss.user:
                if st.button("💾 저장", key=f"save_{idx}"):
                    db.save_recipe(ss.user["id"], r)
                    st.success("저장되었어요 ✓")
            else:
                st.info("🔒 저장하려면 왼쪽 사이드바에서 로그인하세요.")

# 내 레시피
if ss.user:
    st.divider()
    st.subheader("📚 내 레시피")
    rows = db.list_recipes(ss.user["id"])
    if not rows:
        st.caption("저장된 레시피가 없어요. 위 레시피 카드의 “저장”을 눌러보세요.")
    for row in rows:
        data = json.loads(row["data"])
        with st.expander(f"{data['title']}  ·  {row['created_at'][:10]}"):
            for i, s in enumerate(data.get("steps", []), 1):
                st.markdown(f"{i}. {s}")
            if st.button("🗑 삭제", key=f"delsaved_{row['id']}"):
                db.delete_recipe(ss.user["id"], row["id"])
                st.rerun()
