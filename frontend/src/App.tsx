import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import AssistantPage from './pages/AssistantPage'
import DashboardPage from './pages/DashboardPage'
import ImportPage from './pages/ImportPage'
import KnowledgePage from './pages/KnowledgePage'
import TicketPage from './pages/TicketPage'
import TicketsPage from './pages/TicketsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="tickets" element={<TicketsPage />} />
        <Route path="tickets/:ticketId" element={<TicketPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="assistant" element={<AssistantPage />} />
        <Route path="import" element={<ImportPage />} />
        <Route path="*" element={<p>Page not found.</p>} />
      </Route>
    </Routes>
  )
}
