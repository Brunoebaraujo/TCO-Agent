import { Routes, Route, Navigate } from 'react-router-dom'
import ChatPage from './pages/ChatPage'
import HistoryPage from './pages/HistoryPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import Layout from './components/ui/Layout'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Página principal: chat com o agente */}
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/chat/:analysisId" element={<ChatPage />} />

        {/* Histórico de TCOs gerados */}
        <Route path="/history" element={<HistoryPage />} />

        {/* Admin: gerenciar base de benchmarks */}
        <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
      </Route>
    </Routes>
  )
}
