const CREDENTIALS_KEY = 'iptv.credentials.v1'

export type Credentials = { url: string; username: string; password: string }

function saveCredentials(creds: Credentials) {
  localStorage.setItem(CREDENTIALS_KEY, JSON.stringify(creds))
}
function getCredentials(): Credentials | null {
  const raw = localStorage.getItem(CREDENTIALS_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) as Credentials } catch { return null }
}
function clearCredentials() { localStorage.removeItem(CREDENTIALS_KEY) }

export const storage = { saveCredentials, getCredentials, clearCredentials }