import axios from 'axios'
import { storage } from './storage'

type Item = { id: number; name: string; poster?: string }

function ensureCreds() {
  const creds = storage.getCredentials()
  if (!creds) throw new Error('Giriş gerekli')
  return creds
}

async function playerApi(path: string) {
  const { url, username, password } = ensureCreds()
  const base = url.replace(/\/?$/, '')
  const endpoint = `${base}/player_api.php?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}${path}`
  const res = await axios.get(endpoint, { timeout: 15000 })
  return res.data
}

async function getChannels(): Promise<Item[]> {
  const data = await playerApi('')
  const streams = data?.available_channels || data?.live_streams || []
  return streams.map((s: any) => ({ id: Number(s.stream_id), name: s.name }))
}

async function getMovies(): Promise<Item[]> {
  const data = await playerApi('&action=get_vod_streams')
  const list = data || []
  return list.map((s: any) => ({ id: Number(s.stream_id), name: s.name, poster: s.stream_icon }))
}

async function getSeries(): Promise<Item[]> {
  const data = await playerApi('&action=get_series')
  const list = data || []
  return list.map((s: any) => ({ id: Number(s.series_id), name: s.name, poster: s.cover }))
}

async function getEPG(_channelId: number) {
  // Placeholder: Xtream EPG: action=get_short_epg&stream_id=ID
  return []
}

async function getStreamUrl(streamId: number, type: 'live' | 'movie' | 'series'): Promise<string> {
  const { url, username, password } = ensureCreds()
  const base = url.replace(/\/?$/, '')
  if (type === 'live') return `${base}/live/${encodeURIComponent(username)}/${encodeURIComponent(password)}/${streamId}.m3u8`
  if (type === 'movie') return `${base}/movie/${encodeURIComponent(username)}/${encodeURIComponent(password)}/${streamId}.mp4`
  // series: need episode file; fallback to VOD stream style if available
  return `${base}/series/${encodeURIComponent(username)}/${encodeURIComponent(password)}/${streamId}.mp4`
}

// Basic M3U parser
function parseM3U(content: string) {
  const lines = content.split(/\r?\n/)
  const items: Item[] = []
  let current: any = {}
  for (const line of lines) {
    if (line.startsWith('#EXTINF')) {
      const nameMatch = line.match(/,(.*)$/)
      current = { name: nameMatch ? nameMatch[1].trim() : 'Kayıt', id: Date.now() + Math.random() }
    } else if (line && !line.startsWith('#')) {
      items.push({ id: current.id, name: current.name })
      current = {}
    }
  }
  return items
}

export const iptvService = { authenticate: async () => true, getChannels, getMovies, getSeries, getEPG, getStreamUrl, parseM3U }