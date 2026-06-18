import { useState } from 'react'
import { ClipboardCopy, Check, Clock } from 'lucide-react'

/**
 * Painel de pendências — exibido quando o agente emite um bloco <<<PENDING>>>.
 *
 * Mostra o texto corrido que o vendedor pode copiar e enviar ao cliente
 * para buscar as informações que faltam para concluir a análise de TCO.
 */
export default function PendingPanel({ text }) {
  const [copied, setCopied] = useState(false)

  if (!text) return null

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch {
      // Fallback para browsers sem Clipboard API
      const el = document.createElement('textarea')
      el.value = text
      el.style.position = 'fixed'
      el.style.opacity = '0'
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    }
  }

  return (
    <div className="border border-amber-200 rounded-xl bg-amber-50 p-4 max-w-2xl">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Clock size={15} className="text-amber-600" />
          <p className="text-xs font-medium text-amber-800">Pendências — aguardando informações do cliente</p>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md border border-amber-300 text-amber-700 hover:bg-amber-100 transition-colors"
        >
          {copied
            ? <><Check size={13} />Copiado</>
            : <><ClipboardCopy size={13} />Copiar texto</>
          }
        </button>
      </div>
      <pre className="text-xs text-amber-900 whitespace-pre-wrap leading-relaxed font-sans">
        {text}
      </pre>
    </div>
  )
}
