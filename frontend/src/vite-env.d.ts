/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AUTH_REQUIRED?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
