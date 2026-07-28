import { useEffect, useState } from 'react'
import { api } from './api'

// 로그인 사용자의 저장된 레시피 목록 + 삭제.
// refreshKey가 바뀌면 목록을 다시 불러온다 (저장 직후 갱신용).
export default function SavedRecipes({ refreshKey }) {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  async function load() {
    setError('')
    try {
      setItems(await api('/api/recipes/saved', { auth: true }))
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    load()
  }, [refreshKey])

  async function remove(id) {
    try {
      await api(`/api/recipes/saved/${id}`, { method: 'DELETE', auth: true })
      setItems((prev) => prev.filter((i) => i.id !== id))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <section className="results saved">
      <h2 className="saved-head" onClick={() => setOpen((o) => !o)}>
        📚 내 레시피 <span className="count">{items.length}</span>
        <span className="toggle">{open ? '▲' : '▼'}</span>
      </h2>
      {error && <div className="error">⚠️ {error}</div>}
      {open && (
        items.length === 0 ? (
          <p className="empty">저장된 레시피가 없어요. 레시피 카드의 “저장”을 눌러보세요.</p>
        ) : (
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
        )
      )}
    </section>
  )
}
