import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ImportPage from './pages/ImportPage'
import KnowledgePage from './pages/KnowledgePage'
import MessagesPage from './pages/MessagesPage'
import NewTicketPage from './pages/NewTicketPage'
import PeoplePage from './pages/PeoplePage'
import QueuePage from './pages/QueuePage'
import SettingsPage from './pages/SettingsPage'
import TeamPage from './pages/TeamPage'
import TicketPage from './pages/TicketPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<QueuePage />} />
        <Route path="tickets" element={<Navigate to="/" replace />} />
        <Route path="tickets/:ticketId" element={<TicketPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="team" element={<TeamPage />} />
        <Route path="new" element={<NewTicketPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="people" element={<PeoplePage />} />
        <Route path="assistant" element={<Navigate to="/" replace />} />
        <Route path="intake" element={<ImportPage />} />
        <Route path="import" element={<Navigate to="/intake" replace />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<p>Page not found.</p>} />
      </Route>
    </Routes>
  )
}
