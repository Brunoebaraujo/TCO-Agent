import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, MessageSquare, Trash2 } from 'lucide-react'

function formatDate(isoString) {
  const date = new Date(isoString)
  return date.toLocaleDateString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/tco/')
      .then(res => res.json())
      .then(data => setSessions(data.sessions ?? []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false))
  }, [])

  async function handleDelete(e, sessionId) {
    e.stopPropagation()
    if (!confirm('Excluir esta análise?')) return
    await fetch(`/api/tco/${sessionId}`, { method: 'DELETE' })
    setSessions(prev => prev.filter(s => s.id !== sessionId))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={20} className="animate-spin text-slate-400" />
      </div>
    )
  }

  return (
    <div className="px-6 py-8 max-w-3xl">
      <h1 className="text-lg font-semibold text-slate-800">TCO History</h1>
      <p className="text-sm text-slate-400 mt-1">All generated analyses appear here.</p>

      {sessions.length === 0 ? (
        <div className="mt-10 text-center text-slate-300 text-sm">
          No analyses yet — start a new TCO in the chat.
        </div>
      ) : (
        <div className="mt-6 space-y-2">
          {sessions.map(session => (
            <div
              key={session.id}
              onClick={() => navigate(`/chat/${session.id}`)}
              className="bg-white border border-slate-200 rounded-xl p-4 cursor-pointer hover:border-slate-300 transition-colors flex items-center justify-between gap-4"
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <MessageSquare size={16} className="text-slate-400 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm text-slate-700 truncate">{session.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {formatDate(session.updated_at)}
                    {session.tco_result && (
                      <span className="ml-2 text-emerald-600">
                        · {session.tco_result.customer_name} — saving {session.tco_result.saving_percentage}%
                      </span>
                    )}
                  </p>
                </div>
              </div>
              <button
                onClick={(e) => handleDelete(e, session.id)}
                className="text-slate-300 hover:text-red-500 transition-colors p-1"
                aria-label="Excluir"
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
