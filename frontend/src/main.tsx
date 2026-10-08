import './index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './app.tsx'

const ROOT_ELEMENT = document.getElementById('root')
if (ROOT_ELEMENT === null) {
  throw new Error('index.html is missing the #root element')
}

createRoot(ROOT_ELEMENT).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
