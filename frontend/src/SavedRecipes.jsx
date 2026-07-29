import { useEffect, useState } from 'react'
import { api } from './api'

// 로그인 사용자의 저장된 레시피 목록 + 검색/필터 + 삭제.
// refreshKey가 바뀌면 목록을 다시 불러온다 (저장 직후 갱신용).
export default function SavedRecipes({ refreshKey }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0) // 필터 미적용 전체 개수(대략)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  // 검색·필터 상태
  const [q, setQ] = useState('')
  const [difficulty, setDifficulty] = useState('전체')
  const [maxMinutes, setMaxMinutes] = useState('')

  async function load() {
    setError('')
    try {
      const params = new URLSearchParams()
      if (q.trim()) params.set('q', q.trim())
      if (difficulty !== '전체') params.set('difficulty', difficulty)
      if (maxMinutes) params.set('max_minutes', String(maxMinutes))
      const qs = params.toString()
      const data = await api(`/api/recipes/saved${qs ? `?${qs}` : ''}`, { auth: true })
      setItems(data)
      // 필터가 없을 때의 결과를 전체 개수로 기억
      if (!qs) setTotal(data.length)
    } catch (e) {
      setError(e.message)
    }
  }

  // 저장 갱신 / 필터 변경 시 다시 로드
  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey, q, difficulty, maxMinutes])

  async function remove(id) {
    try {
      await api(`/api/recipes/saved/${id}`, { method: 'DELETE', auth: true })
      setItems((prev) => prev.filter((i) => i.id !== id))
    } catch (e) {
      setError(e.message)
    }
  }

  const hasFilter = q.trim() || difficulty !== '전체' || maxMinutes

  return (
    <section className="results saved">
      <h2 className="saved-head" onClick={() => setOpen((o) => !o)}>
        📚 내 레시피 <span className="count">{items.length}</span>
        <span className="toggle">{open ? '▲' : '▼'}</span>
      </h2>
      {error && <div className="error">⚠️ {error}</div>}
      {open && (
        <>
          <div className="saved-filters">
            <input
              className="search"
              placeholder="🔎 제목·재료로 검색"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
              <option value="전체">난이도 전체</option>
              <option value="쉬움">쉬움</option>
              <option value="보통">보통</option>
              <option value="어려움">어려움</option>
            </select>
            <input
              type="number"
              min="0"
              placeholder="최대 분"
              value={maxMinutes}
              onChange={(e) => setMaxMinutes(e.target.value)}
            />
          </div>

          {items.length === 0 ? (
            <p className="empty">
              {hasFilter
                ? '검색·필터 조건에 맞는 레시피가 없어요.'
                : '저장된 레시피가 없어요. 레시피 카드의 “저장”을 눌러보세요.'}
            </p>
          ) : (
            <>
              {hasFilter && <p className="empty">{items.length} / {total}개 표시</p>}
              <div className="recipe-list">
                {items.map((it) => (
                  <article className="recipe" key={it.id}>
                    <div className="recipe-head">
                      <h3>{it.recipe.title}</h3>
                      <div className="meta">
                        {it.recipe.minutes != null && <span>⏱ {it.recipe.minutes}분</span>}
                        {it.recipe.difficulty && <span>📊 {it.recipe.difficulty}</span>}
                        <span className="date">{it.created_at?.slice(0, 10)}</span>
                      </div>
                    </div>
                    <div className="recipe-ings">
                      {it.recipe.ingredients.map((ing, i) => (
                        <span className={`ing ${ing.have ? 'have' : 'missing'}`} key={i}>
                          {ing.have ? '✓' : '＋'} {ing.name}
                        </span>
                      ))}
                    </div>
                    <ol className="steps">
                      {it.recipe.steps.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ol>
                    <button className="ghost save" onClick={() => remove(it.id)}>
                      🗑 삭제
                    </button>
                  </article>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </section>
  )
}
