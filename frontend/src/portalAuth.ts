/**
 * Auth SSO Albatros INTEGRADO.
 * En portal: usa window.AlbProtosPortal + localStorage albatros_token.
 * En local (VITE_AUTH_REQUIRED !== 'true'): bypass de desarrollo + selector de rol.
 */

export const APP_CLIENT_ID = 'biometrico'

export const ROLE_SERVICIOS = 'servicios_generales'
export const ROLE_GTH = 'gth'
export const ROLE_ADMIN = 'admin'

export type AppRole = typeof ROLE_SERVICIOS | typeof ROLE_GTH | typeof ROLE_ADMIN

const DEV_ROLE_KEY = 'biometrico_dev_role'

export type PortalUser = {
  id?: string
  email?: string
  full_name?: string
  is_superadmin?: boolean
  app_roles?: Record<string, string[]>
  enabled_modules?: string[]
}

type AlbPortal = {
  redirectIfNoToken: () => boolean
  getPortalUser: () => PortalUser | null
  getAppRoles: (clientId: string) => string[]
  hasAppAccess: (clientId: string) => boolean
  isAppAdmin: (clientId: string) => boolean
  backToHub: () => void
  logoutPortal: () => void
}

declare global {
  interface Window {
    AlbProtosPortal?: AlbPortal
  }
}

/** true solo cuando el módulo corre detrás del portal con JWT real */
export function isAuthRequired(): boolean {
  return import.meta.env.VITE_AUTH_REQUIRED === 'true'
}

export function getToken(): string | null {
  try {
    return localStorage.getItem('albatros_token')
  } catch {
    return null
  }
}

function readUserFromStorage(): PortalUser | null {
  try {
    const raw = localStorage.getItem('albatros_user')
    if (!raw) return null
    return JSON.parse(raw) as PortalUser
  } catch {
    return null
  }
}

export function getPortalUser(): PortalUser | null {
  if (window.AlbProtosPortal?.getPortalUser) {
    return window.AlbProtosPortal.getPortalUser()
  }
  return readUserFromStorage()
}

/** En desarrollo local: rol simulado para demos (GTH / SG / TI). */
export function getDevRole(): AppRole {
  try {
    const stored = sessionStorage.getItem(DEV_ROLE_KEY)
    if (stored === ROLE_SERVICIOS || stored === ROLE_GTH || stored === ROLE_ADMIN) {
      return stored
    }
  } catch {
    /* ignore */
  }
  return ROLE_ADMIN
}

export function setDevRole(role: AppRole): void {
  try {
    sessionStorage.setItem(DEV_ROLE_KEY, role)
  } catch {
    /* ignore */
  }
}

function normalizeRoles(raw: string[]): string[] {
  const out = new Set<string>()
  for (const r of raw) {
    if (r === 'consulta') out.add(ROLE_SERVICIOS)
    else if (r === 'operador') out.add(ROLE_GTH)
    else out.add(r)
  }
  return [...out]
}

export function getAppRoles(): string[] {
  if (!isAuthRequired()) {
    return [getDevRole()]
  }
  if (window.AlbProtosPortal?.getAppRoles) {
    return normalizeRoles(window.AlbProtosPortal.getAppRoles(APP_CLIENT_ID) || [])
  }
  const user = getPortalUser()
  if (user?.is_superadmin) {
    return [ROLE_ADMIN, ROLE_GTH, ROLE_SERVICIOS]
  }
  return normalizeRoles(user?.app_roles?.[APP_CLIENT_ID] || [])
}

function hasRole(...wanted: string[]): boolean {
  const roles = getAppRoles()
  return wanted.some((r) => roles.includes(r))
}

export function hasAppAccess(): boolean {
  if (!isAuthRequired()) return true
  if (window.AlbProtosPortal?.hasAppAccess) {
    return window.AlbProtosPortal.hasAppAccess(APP_CLIENT_ID)
  }
  const user = getPortalUser()
  if (user?.is_superadmin) return true
  return getAppRoles().length > 0
}

/** Ver listado / PDF de comedor (SG, GTH, admin). */
export function canAccessCafeteria(): boolean {
  if (!isAuthRequired()) return true
  const user = getPortalUser()
  if (user?.is_superadmin) return true
  return hasRole(ROLE_SERVICIOS, ROLE_GTH, ROLE_ADMIN)
}

/** Generar / refrescar listados (GTH, admin). SG solo imprime. */
export function canGenerateReports(): boolean {
  if (!isAuthRequired()) {
    return getDevRole() !== ROLE_SERVICIOS
  }
  const user = getPortalUser()
  if (user?.is_superadmin) return true
  return hasRole(ROLE_GTH, ROLE_ADMIN)
}

/** Asistencia (GTH, admin). */
export function canAccessAttendance(): boolean {
  if (!isAuthRequired()) {
    return getDevRole() !== ROLE_SERVICIOS
  }
  const user = getPortalUser()
  if (user?.is_superadmin) return true
  return hasRole(ROLE_GTH, ROLE_ADMIN)
}

/** Registrar / ver detalle de permisos GTH de excepción. */
export function canOperateGth(): boolean {
  if (!isAuthRequired()) {
    return getDevRole() === ROLE_GTH || getDevRole() === ROLE_ADMIN
  }
  const user = getPortalUser()
  if (user?.is_superadmin) return true
  if (window.AlbProtosPortal?.isAppAdmin?.(APP_CLIENT_ID)) return true
  return hasRole(ROLE_GTH, ROLE_ADMIN)
}

/** Servicios generales: solo listado limpio + PDF (sin excepciones visibles). */
export function isServiciosGeneralesOnly(): boolean {
  if (!isAuthRequired()) {
    return getDevRole() === ROLE_SERVICIOS
  }
  if (canOperateGth()) return false
  return hasRole(ROLE_SERVICIOS)
}

/** Administración de dispositivos biométricos (TI). */
export function canManageDevices(): boolean {
  if (!isAuthRequired()) {
    return getDevRole() === ROLE_ADMIN
  }
  const user = getPortalUser()
  if (user?.is_superadmin) return true
  if (window.AlbProtosPortal?.isAppAdmin?.(APP_CLIENT_ID)) return true
  return hasRole(ROLE_ADMIN)
}

export function authHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {
    ...(extra as Record<string, string> | undefined),
  }
  const token = getToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

/**
 * Guard de entrada. Devuelve false si redirige / bloquea.
 * Con VITE_AUTH_REQUIRED=false (default local) siempre pasa.
 */
export function ensureSession(): boolean {
  if (!isAuthRequired()) return true

  if (window.AlbProtosPortal?.redirectIfNoToken) {
    const ok = window.AlbProtosPortal.redirectIfNoToken()
    if (!ok) return false
  } else if (!getToken()) {
    console.warn('[biometrico] Sin albatros_token y sin AlbProtosPortal')
    return false
  }

  if (!hasAppAccess()) {
    alert('No tiene acceso a Control de Biométricos.')
    window.AlbProtosPortal?.backToHub?.()
    return false
  }
  return true
}

export function backToHub(): void {
  if (window.AlbProtosPortal?.backToHub) {
    window.AlbProtosPortal.backToHub()
    return
  }
  window.location.href = '/'
}

export function logoutPortal(): void {
  if (window.AlbProtosPortal?.logoutPortal) {
    window.AlbProtosPortal.logoutPortal()
    return
  }
  try {
    localStorage.removeItem('albatros_token')
    localStorage.removeItem('albatros_user')
  } catch {
    /* ignore */
  }
  window.location.href = '/'
}

export function displayName(): string {
  const u = getPortalUser()
  return u?.full_name || u?.email || (isAuthRequired() ? 'Usuario' : 'Desarrollo local')
}

export function roleLabel(role: string): string {
  switch (role) {
    case ROLE_SERVICIOS:
      return 'Servicios generales'
    case ROLE_GTH:
      return 'GTH'
    case ROLE_ADMIN:
      return 'Admin (TI)'
    default:
      return role
  }
}
