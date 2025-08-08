import { storage } from '../services/storage'
import { useNavigate } from 'react-router-dom'

export default function Settings() {
  const creds = storage.getCredentials()
  const navigate = useNavigate()

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Ayarlar</h2>
      <div className="bg-slate-900 rounded p-4">
        <div className="text-sm text-slate-400">Sunucu</div>
        <div className="font-mono break-all">{creds?.url ?? '-'}</div>
        <div className="text-sm text-slate-400 mt-2">Kullanıcı</div>
        <div className="font-mono">{creds?.username ?? '-'}</div>
      </div>
      <div className="flex gap-2">
        <button className="px-3 py-2 bg-slate-800 rounded" onClick={() => { storage.clearCredentials(); navigate('/login') }}>Çıkış Yap</button>
        <button className="px-3 py-2 bg-slate-800 rounded" onClick={() => { caches.keys().then(keys => keys.forEach(k => caches.delete(k))) }}>Önbelleği Temizle</button>
      </div>
    </div>
  )
}