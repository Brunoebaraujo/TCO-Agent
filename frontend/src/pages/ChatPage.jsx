import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Send, Loader2 } from 'lucide-react'
import TCODashboard from '../components/tco/TCODashboard'
import PendingPanel from '../components/tco/PendingPanel'
import ExpressForm from '../components/tco/ExpressForm'
import { formatOverridesBlock, formatPreviousAccessoriesBlock } from '../components/tco/dashboardCalc'

const WELCOME_MESSAGE = {
  role: 'assistant',
  content: `Olá! Sou o agente TCO da Goodpack — modo express: me dá esses 9 dados de uma vez e eu já calculo um TCO preliminar na hora.

• **SKU Goodpack** (ex: MB6)
• **SKU/embalagem concorrente** (ex: Octabin)
• **Produto** (ex: Orange FCOJ, Palm Oil)
• **Preço Goodpack** (por unidade)
• **Preço concorrente** (por unidade)
• **Origem** e **Destino**
• **Frete por container**
• **Volume total** (MT) e **Lease days**

Pode mandar tudo junto, num texto corrido — não precisa ser formatado. O que eu não souber, calculo com benchmark da base e já te aviso o que precisa confirmar com o cliente depois.`,
}

export default function ChatPage() {
  const { analysisId } = useParams()
  const navigate = useNavigate()

  const [messages, setMessages] = useState([WELCOME_MESSAGE])
  const [sessionId, setSessionId] = useState(analysisId ? Number(analysisId) : null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingSession, setLoadingSession] = useState(Boolean(analysisId))
  const [overrides, setOverrides] = useState({})
  const bottomRef = useRef(null)

  // key=null sinaliza "limpar tudo" (usado pelo botão Restaurar do dashboard)
  const handleOverrideChange = useCallback((key, value, label) => {
    if (key === null) {
      setOverrides({})
      return
    }
    setOverrides(prev => ({ ...prev, [key]: { value, label } }))
  }, [])

  useEffect(() => {
    if (!analysisId) {
      setMessages([WELCOME_MESSAGE])
      setSessionId(null)
      setOverrides({})
      return
    }

    setLoadingSession(true)
    setOverrides({})
    fetch(`/api/tco/${analysisId}`)
      .then(res => {
        if (!res.ok) throw new Error('Sessão não encontrada')
        return res.json()
      })
      .then(data => {
        setMessages([WELCOME_MESSAGE, ...data.messages])
        setSessionId(data.id)
      })
      .catch(() => {
        setMessages([WELCOME_MESSAGE])
        setSessionId(null)
        navigate('/chat', { replace: true })
      })
      .finally(() => setLoadingSession(false))
  }, [analysisId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const persistSession = useCallback(async (allMessages, currentSessionId) => {
    try {
      const res = await fetch('/api/tco/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: currentSessionId,
          messages: allMessages.slice(1).map(m => ({
            role: m.role,
            content: m.content,
            tco_result: m.tco_result ?? null,
            pending_text: m.pending_text ?? null,
          })),
        }),
      })
      const data = await res.json()
      if (!currentSessionId && data.session_id) {
        setSessionId(data.session_id)
        navigate(`/chat/${data.session_id}`, { replace: true })
      }
    } catch (err) {
      console.error('Falha ao salvar sessão:', err)
    }
  }, [navigate])

  const submitUserMessage = useCallback(async (text) => {
    if (!text.trim() || loading) return

    const userMessage = { role: 'user', content: text.trim() }
    const overridesBlock = formatOverridesBlock(overrides)
    const lastTcoResult = [...messages].reverse().find(m => m.tco_result)?.tco_result || null
    const accessoriesBlock = formatPreviousAccessoriesBlock(lastTcoResult)
    const apiUserMessage = { role: 'user', content: accessoriesBlock + overridesBlock + text.trim() }
    const messagesWithUser = [...messages, userMessage]
    setMessages(messagesWithUser)
    setLoading(true)

    try {
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [...messages.slice(1), apiUserMessage],
          opportunity_context: {},
        }),
      })
      const data = await res.json()
      const assistantMessage = {
        role: 'assistant',
        content: data.content,
        tco_result: data.tco_result ?? null,
        pending_text: data.pending_text ?? null,
      }
      const finalMessages = [...messagesWithUser, assistantMessage]
      setMessages(finalMessages)
      await persistSession(finalMessages, sessionId)
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Erro ao conectar com o agente. Verifique se o backend está rodando.',
      }])
    } finally {
      setLoading(false)
    }
  }, [messages, loading, sessionId, persistSession, overrides])

  async function sendMessage(e) {
    e.preventDefault()
    if (!input.trim() || loading) return
    const text = input
    setInput('')
    await submitUserMessage(text)
  }

  // Formulário express só aparece numa análise nova, antes de qualquer
  // mensagem trocada — depois da primeira resposta, segue como chat normal
  // (refinamento, perguntas de acompanhamento, customização completa via texto).
  const showExpressForm = !sessionId && messages.length === 1

  if (loadingSession) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={20} className="animate-spin text-slate-400" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">

      <div className="px-6 py-4 border-b border-slate-200 bg-white">
        <h1 className="text-base font-semibold text-slate-800">
          {sessionId ? 'TCO Analysis' : 'New TCO Analysis'}
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Talk to the agent to generate a competitive TCO
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {showExpressForm && (
          <ExpressForm onSubmit={submitUserMessage} loading={loading} />
        )}

        {messages.map((msg, i) => (
          <div key={i} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-[#1a3a5c] flex items-center justify-center mr-2 mt-1 flex-shrink-0">
                <span className="text-white text-xs font-bold">G</span>
              </div>
            )}
            <div className={msg.role === 'user' ? '' : 'flex flex-col gap-3'}>
              {msg.content && (
                <div className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-agent'}>
                  <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                </div>
              )}
              {msg.tco_result && (
                <TCODashboard
                  result={msg.tco_result}
                  sessionId={sessionId}
                  overrides={overrides}
                  onOverrideChange={handleOverrideChange}
                />
              )}
              {msg.pending_text && <PendingPanel text={msg.pending_text} />}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-full bg-[#1a3a5c] flex items-center justify-center mr-2 flex-shrink-0">
              <span className="text-white text-xs font-bold">G</span>
            </div>
            <div className="chat-bubble-agent flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-slate-400" />
              <span className="text-sm text-slate-400">Analisando...</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="px-6 py-3 border-t border-slate-200 bg-white">
        {messages.some(m => m.tco_result) && (
          <button
            onClick={() => submitUserMessage(
              'Finalizar análise. Revise todos os valores que confirmei nesta sessão e me pergunte quais são elegíveis pra atualizar a knowledge base.'
            )}
            disabled={loading}
            className="w-full mb-3 px-4 py-2 text-sm font-medium text-[#1a3a5c] border border-[#1a3a5c]/30 rounded-xl hover:bg-[#1a3a5c]/5 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Finalizar TCO
          </button>
        )}
        <form onSubmit={sendMessage} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ex: MB6 vs Octabin, Orange FCOJ, $85 GP / $20 concorrente, Santos-Rotterdam, frete $4200/container, 1000 MT, 180 lease days..."
            className="flex-1 px-4 py-2.5 text-sm border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1a3a5c]/20 focus:border-[#1a3a5c] bg-slate-50"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="px-4 py-2.5 bg-[#1a3a5c] text-white rounded-xl hover:bg-[#1a3a5c]/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <Send size={15} />
            <span className="text-sm font-medium">Send</span>
          </button>
        </form>
      </div>

    </div>
  )
}
