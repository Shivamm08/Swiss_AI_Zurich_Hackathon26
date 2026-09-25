import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import CopilotProvider from './copilot/CopilotProvider.tsx'
import ModelProvider from './model/ModelProvider.tsx'
import ViewerProvider from './viewas/ViewerProvider.tsx'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ModelProvider>
        <ViewerProvider>
          <BrowserRouter>
            <CopilotProvider>
              <App />
            </CopilotProvider>
          </BrowserRouter>
        </ViewerProvider>
      </ModelProvider>
    </QueryClientProvider>
  </StrictMode>,
)
