import { useState, useRef, useEffect } from 'react'
import { Send, Loader2 } from 'lucide-react'
import ConfidenceBadge from '../components/ui/ConfidenceBadge'

const WELCOME_MESSAGE = {
  role: 'assistant',
  content: `Olá! Sou o agente TCO da Goodpack.

Para gerar uma análise, me informe:
• **Cliente** — nome da empresa
• **Produto** — o que será transportado (ex: Omega 3, Palm Oil, FCOJ)
• **Volume** — em Metric Tonnes
• **Concorrente atual** — qual embalagem o cliente usa hoje (ex: Octabin, Drum 200L)

Pode me dar essas informações de uma vez ou eu te guio passo a passo.`,
}

export default function ChatPage() {
  const [messages, setMessages] = useState([WELCOME_MESSAGE])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(e) {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = { role: 'user', content: input.trim() }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          // Não envia a mensagem de boas-vindas estática (índice 0) — só o histórico real da conversa
          messages: [...messages.slice(1), userMessage],
          opportunity_context: {},
        }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.content }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Erro ao conectar com o agente. Verifique se o backend está rodando.',
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">

      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 bg-white">
        <h1 className="text-base font-semibold text-slate-800">New TCO Analysis</h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Talk to the agent to generate a competitive TCO
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-[#1a3a5c] flex items-center justify-center mr-2 mt-1 flex-shrink-0">
                <span className="text-white text-xs font-bold">G</span>
              </div>
            )}
            <div className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-agent'}>
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
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

      {/* Input */}
      <div className="px-6 py-4 border-t border-slate-200 bg-white">
        <form onSubmit={sendMessage} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ex: Cliente Nestlé, 800 MT de Palm Oil, concorrente Octabin..."
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
