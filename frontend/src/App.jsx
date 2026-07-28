import { useEffect, useRef, useState } from 'react'
import { api, getToken, setToken } from './api'
import AuthBar from './AuthBar'
import SavedRecipes from './SavedRecipes'

// 이미지를 긴 변 기준 maxSize로 리사이즈하고 JPEG data URL로 반환 (업로드 용량 축소)
function fileToResizedDataURL(file, maxSize = 1024, quality = 0.85) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('파일 읽기 실패'))
    reader.onload = () => {
      const img = new Image()
      img.onerror = () => reject(new Error('이미지 디코딩 실패'))
      img.onload = () => {
        let { width, height } = img
        if (width > height && width > maxSize) {
          height = Math.round((height * maxSize) / width)
          width = maxSize
        } else if (height > maxSize) {
          width = Math.round((width * maxSize) / height)
          height = maxSize
        }
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        canvas.getContext('2d').drawImage(img, 0, 0, width, height)
        resolve(canvas.toDataURL('image/jpeg', quality))
      }
      img.src = reader.result
    }
    reader.readAsDataURL(file)
  })
}

export default function App() {
  const [preview, setPreview] = useState(null) // data URL (미리보기 + 전송용)
  const [ingredients, setIngredients] = useState([]) // [{name, confidence}]
  const [status, setStatus] = useState('idle') // idle | loading | done | error
  const [error, setError] = useState('')
  const [newItem, setNewItem] = useState('')
  const fileRef = useRef(null)

  // 2단계: 레시피 생성
  const [prefs, setPrefs] = useState({ diet: 'none', allergies: '', maxMinutes: '', servings: 2 })
  const [recipes, setRecipes] = useState([])
  const [recipeStatus, setRecipeStatus] = useState('idle') // idle | loading | done | error
  const [recipeError, setRecipeError] = useState('')

  // 3단계: 인증 / 프로필 / 저장
  const [user, setUser] = useState(null) // { nickname } | null
  const [savedKey, setSavedKey] = useState(0) // 저장 후 목록 갱신 트리거
  const [savedIds, setSavedIds] = useState(new Set()) // 방금 저장한 레시피 인덱스
  const [profileMsg, setProfileMsg] = useState('')

  // 앱 시작 시 토큰이 있으면 프로필을 불러와 로그인 상태 복원 + 선호 프리필
  useEffect(() => {
    if (!getToken()) return
    api('/api/profile', { auth: true })
      .then((p) => {
        setUser({ nickname: p.nickname })
        setPrefs((prev) => ({
          ...prev,
          diet: p.diet || 'none',
          allergies: (p.allergies || []).join(', '),
          servings: p.default_servings || 2,
        }))
      })
      .catch(() => setToken(null)) // 만료 토큰 정리
  }, [])

  function handleLogout() {
    api('/api/auth/logout', { method: 'POST', auth: true }).catch(() => {})
    setToken(null)
    setUser(null)
    setSavedIds(new Set())
  }

  async function handleAuth({ nickname }) {
    setUser({ nickname })
    // 로그인 직후 저장된 선호를 프리필
    try {
      const p = await api('/api/profile', { auth: true })
      setPrefs((prev) => ({
        ...prev,
        diet: p.diet || 'none',
        allergies: (p.allergies || []).join(', '),
        servings: p.default_servings || 2,
      }))
    } catch {
      /* 무시 */
    }
  }

  async function saveProfile() {
    setProfileMsg('')
    try {
      await api('/api/profile', {
        method: 'PUT',
        auth: true,
        body: {
          diet: prefs.diet,
          allergies: prefs.allergies
            ? prefs.allergies.split(',').map((s) => s.trim()).filter(Boolean)
            : [],
          default_servings: prefs.servings ? Number(prefs.servings) : 2,
        },
      })
      setProfileMsg('선호가 프로필에 저장되었어요 ✓')
    } catch (e) {
      setProfileMsg(e.message)
    }
  }

  async function saveRecipe(recipe, idx) {
    try {
      await api('/api/recipes/save', { method: 'POST', auth: true, body: { recipe } })
      setSavedIds((prev) => new Set(prev).add(idx))
      setSavedKey((k) => k + 1)
    } catch (e) {
      setRecipeError(e.message)
    }
  }

  async function getRecipes() {
    if (ingredients.length === 0) return
    setRecipeStatus('loading')
    setRecipeError('')
    setRecipes([])
    setSavedIds(new Set())
    try {
      const res = await fetch('/api/recipes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ingredients: ingredients.map((i) => i.name),
          preferences: {
            diet: prefs.diet,
            allergies: prefs.allergies
              ? prefs.allergies.split(',').map((s) => s.trim()).filter(Boolean)
              : [],
            max_minutes: prefs.maxMinutes ? Number(prefs.maxMinutes) : null,
            servings: prefs.servings ? Number(prefs.servings) : null,
          },
          count: 3,
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `요청 실패 (HTTP ${res.status})`)
      }
      const data = await res.json()
      setRecipes(data.recipes || [])
      setRecipeStatus('done')
    } catch (e) {
      setRecipeError(e.message)
      setRecipeStatus('error')
    }
  }

  async function handleFile(file) {
    if (!file) return
    setError('')
    setIngredients([])
    setStatus('idle')
    try {
      const dataUrl = await fileToResizedDataURL(file)
      setPreview(dataUrl)
    } catch (e) {
      setError(e.message)
      setStatus('error')
    }
  }

  async function recognize() {
    if (!preview) return
    setStatus('loading')
    setError('')
    try {
      const res = await fetch('/api/recognize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: preview }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `요청 실패 (HTTP ${res.status})`)
      }
      const data = await res.json()
      setIngredients(data.ingredients || [])
      setStatus('done')
    } catch (e) {
      setError(e.message)
      setStatus('error')
    }
  }

  function removeIngredient(idx) {
    setIngredients((prev) => prev.filter((_, i) => i !== idx))
  }

  function addIngredient() {
    const name = newItem.trim()
    if (!name) return
    if (ingredients.some((i) => i.name === name)) {
      setNewItem('')
      return
    }
    setIngredients((prev) => [...prev, { name, confidence: null }])
    setNewItem('')
  }

  function onDrop(e) {
    e.preventDefault()
    handleFile(e.dataTransfer.files?.[0])
  }

  return (
    <div className="wrap">
      <header>
        <div className="topbar">
          <h1>🧊 냉장고 셰프</h1>
          <AuthBar user={user} onAuth={handleAuth} onLogout={handleLogout} />
        </div>
        <p className="sub">냉장고 사진 → 재료 인식 → 레시피 추천, 그리고 저장까지.</p>
      </header>

      <section
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
      >
        {preview ? (
          <img className="preview" src={preview} alt="업로드한 냉장고 사진" />
        ) : (
          <div className="placeholder">
            <div className="big">📷</div>
            <div>사진을 드래그하거나 클릭해서 업로드</div>
            <div className="hint">모바일에서는 카메라 촬영도 가능해요</div>
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </section>

      <div className="actions">
        <button
          className="primary"
          disabled={!preview || status === 'loading'}
          onClick={recognize}
        >
          {status === 'loading' ? '인식 중…' : '재료 인식하기'}
        </button>
        {preview && (
          <button
            className="ghost"
            onClick={() => {
              setPreview(null)
              setIngredients([])
              setStatus('idle')
              setError('')
            }}
          >
            초기화
          </button>
        )}
      </div>

      {status === 'loading' && <div className="loading">🍳 모델이 사진을 분석하고 있어요…</div>}
      {error && <div className="error">⚠️ {error}</div>}

      {(ingredients.length > 0 || status === 'done') && (
        <section className="results">
          <h2>인식된 재료 {ingredients.length > 0 && <span className="count">{ingredients.length}</span>}</h2>
          {ingredients.length === 0 ? (
            <p className="empty">재료를 찾지 못했어요. 아래에서 직접 추가할 수 있어요.</p>
          ) : (
            <div className="chips">
              {ingredients.map((ing, idx) => (
                <span className="chip" key={`${ing.name}-${idx}`}>
                  {ing.name}
                  {typeof ing.confidence === 'number' && (
                    <em className="conf">{Math.round(ing.confidence * 100)}%</em>
                  )}
                  <button className="x" onClick={() => removeIngredient(idx)} aria-label="삭제">
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="add-row">
            <input
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addIngredient()}
              placeholder="빠진 재료 직접 추가 (예: 두부)"
            />
            <button onClick={addIngredient}>추가</button>
          </div>

          {ingredients.length > 0 && (
            <div className="prefs">
              <h3>선호 조건 <span className="opt">(선택)</span></h3>
              <div className="prefs-grid">
                <label>
                  식단
                  <select
                    value={prefs.diet}
                    onChange={(e) => setPrefs({ ...prefs, diet: e.target.value })}
                  >
                    <option value="none">제한 없음</option>
                    <option value="채식">채식</option>
                    <option value="비건">비건</option>
                    <option value="저탄수화물">저탄수화물</option>
                  </select>
                </label>
                <label>
                  최대 조리시간(분)
                  <input
                    type="number"
                    min="1"
                    placeholder="예: 30"
                    value={prefs.maxMinutes}
                    onChange={(e) => setPrefs({ ...prefs, maxMinutes: e.target.value })}
                  />
                </label>
                <label>
                  인분
                  <input
                    type="number"
                    min="1"
                    value={prefs.servings}
                    onChange={(e) => setPrefs({ ...prefs, servings: e.target.value })}
                  />
                </label>
                <label className="wide">
                  알레르기 (쉼표로 구분)
                  <input
                    placeholder="예: 땅콩, 우유"
                    value={prefs.allergies}
                    onChange={(e) => setPrefs({ ...prefs, allergies: e.target.value })}
                  />
                </label>
              </div>
              <button
                className="primary next"
                onClick={getRecipes}
                disabled={recipeStatus === 'loading'}
              >
                {recipeStatus === 'loading' ? '레시피 생성 중…' : '🍳 레시피 추천 받기'}
              </button>
              {user && (
                <div className="profile-save">
                  <button className="ghost small" onClick={saveProfile}>
                    ⭐ 이 선호를 내 프로필에 저장
                  </button>
                  {profileMsg && <span className="profile-msg">{profileMsg}</span>}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {recipeStatus === 'loading' && (
        <div className="loading">👨‍🍳 재료로 만들 수 있는 요리를 찾고 있어요…</div>
      )}
      {recipeError && <div className="error">⚠️ {recipeError}</div>}

      {recipes.length > 0 && (
        <section className="results">
          <h2>추천 레시피 <span className="count">{recipes.length}</span></h2>
          <div className="recipe-list">
            {recipes.map((r, idx) => (
              <article className="recipe" key={`${r.title}-${idx}`}>
                <div className="recipe-head">
                  <h3>{r.title}</h3>
                  <div className="meta">
                    {r.minutes != null && <span>⏱ {r.minutes}분</span>}
                    {r.difficulty && <span>📊 {r.difficulty}</span>}
                  </div>
                </div>
                <div className="recipe-ings">
                  {r.ingredients.map((ing, i) => (
                    <span className={`ing ${ing.have ? 'have' : 'missing'}`} key={i}>
                      {ing.have ? '✓' : '＋'} {ing.name}
                    </span>
                  ))}
                </div>
                <ol className="steps">
                  {r.steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
                {user ? (
                  <button
                    className="ghost save"
                    onClick={() => saveRecipe(r, idx)}
                    disabled={savedIds.has(idx)}
                  >
                    {savedIds.has(idx) ? '✓ 저장됨' : '💾 저장'}
                  </button>
                ) : (
                  <button className="ghost save" disabled title="로그인하면 저장할 수 있어요">
                    🔒 저장하려면 로그인
                  </button>
                )}
              </article>
            ))}
          </div>
          <button
            className="ghost"
            onClick={getRecipes}
            disabled={recipeStatus === 'loading'}
          >
            🔄 다른 레시피 보기
          </button>
        </section>
      )}

      {user && <SavedRecipes refreshKey={savedKey} />}
    </div>
  )
}
