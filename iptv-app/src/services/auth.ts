import axios from 'axios'
import { storage } from './storage'

export async function authenticate(url: string, username: string, password: string): Promise<boolean> {
  const base = url.replace(/\/?$/, '')
  const endpoint = `${base}/player_api.php?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
  const res = await axios.get(endpoint, { timeout: 12000 })
  const ok = !!res.data && (res.data.auth || res.data.user_info)
  if (ok) {
    storage.saveCredentials({ url: base, username, password })
  }
  return ok
}