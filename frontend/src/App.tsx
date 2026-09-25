import { ShieldAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import type { Role } from './api/types'
import Layout from './components/Layout'
import { EmptyState } from './components/ui'
import { ROLE_LABEL } from './components/styles'
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
import { useViewer } from './viewas/context'

/** Pages hidden from a role in the sidebar are also blocked when opened by URL. */
function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { role } = useViewer()
  if (roles.includes(role)) return children
  return (
    <EmptyState icon={<ShieldAlert size={28} />} title="Not available for your role">
      This page is for {roles.map((r) => ROLE_LABEL[r]).join(' and ')}. You're viewing the app as {ROLE_LABEL[role]}.
    </EmptyState>
  )
}

const MANAGERS: Role[] = ['analyst', 'admin']
const ADMIN: Role[] = ['admin']

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<QueuePage />} />
        <Route path="tickets" element={<Navigate to="/" replace />} />
        <Route path="tickets/:ticketId" element={<TicketPage />} />
        <Route path="dashboard" element={<RequireRole roles={MANAGERS}><DashboardPage /></RequireRole>} />
        <Route path="team" element={<RequireRole roles={MANAGERS}><TeamPage /></RequireRole>} />
        <Route path="new" element={<RequireRole roles={MANAGERS}><NewTicketPage /></RequireRole>} />
        <Route path="knowledge" element={<RequireRole roles={ADMIN}><KnowledgePage /></RequireRole>} />
        <Route path="messages" element={<MessagesPage />} />
        <Route path="people" element={<PeoplePage />} />
        <Route path="assistant" element={<Navigate to="/" replace />} />
        <Route path="intake" element={<RequireRole roles={ADMIN}><ImportPage /></RequireRole>} />
        <Route path="import" element={<Navigate to="/intake" replace />} />
        <Route path="settings" element={<RequireRole roles={ADMIN}><SettingsPage /></RequireRole>} />
        <Route path="*" element={<p>Page not found.</p>} />
      </Route>
    </Routes>
  )
}
