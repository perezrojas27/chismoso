import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ensureSession } from './portalAuth'
import './styles/tokens-diseno-albatros.css'
import './styles/admin-shell.css'

if (!ensureSession()) {
  // redirectIfNoToken / sin acceso ya manejó la salida
} else {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
