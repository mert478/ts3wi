import { useEffect, useState } from 'react'
import { authenticate } from '../../services/auth'
import { storage } from '../../services/storage'
import { isValidHttpUrl } from '../../utils/validators'
import { useNavigate } from 'react-router-dom'

export default function LoginForm() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const saved = storage.getCredentials()
    if (saved) {
      setUrl(saved.url)
      setUsername(saved.username)
      setPassword(saved.password)
      setRemember(true)
    }
  }, [])

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!isValidHttpUrl(url)) {
      setError('Geçerli bir URL giriniz')
      return
    }
    if (!username || !password) {
      setError('Kullanıcı adı ve şifre zorunludur')
      return
    }
    try {
      setLoading(true)
      const ok = await authenticate(url, username, password)
      if (ok) {
        if (remember) storage.saveCredentials({ url, username, password })
        else storage.clearCredentials()
        navigate('/')
      } else {
        setError('Giriş başarısız. Bilgilerinizi kontrol edin')
      }
    } catch (err: any) {
      setError(err?.message || 'Bağlantı sağlanamadı')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-md mx-auto p-6 bg-slate-900 rounded-xl shadow-xl space-y-4">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">IPTV Giriş</h1>
        <p className="text-slate-400 text-sm">Xtream Codes veya M3U desteklenir</p>
      </div>
      {error && (
        <div className="bg-red-500/10 text-red-300 px-3 py-2 rounded border border-red-500/30 text-sm">{error}</div>
      )}
      <div className="space-y-1">
        <label className="text-sm text-slate-300">Sunucu URL</label>
        <input
          className="w-full px-3 py-2 bg-slate-800 rounded outline-none focus:ring-2 ring-emerald-400"
          placeholder="http://example.com:8080"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          inputMode="url"
        />
      </div>
      <div className="space-y-1">
        <label className="text-sm text-slate-300">Kullanıcı Adı</label>
        <input
          className="w-full px-3 py-2 bg-slate-800 rounded outline-none focus:ring-2 ring-emerald-400"
          placeholder="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
      </div>
      <div className="space-y-1">
        <label className="text-sm text-slate-300">Şifre</label>
        <input
          className="w-full px-3 py-2 bg-slate-800 rounded outline-none focus:ring-2 ring-emerald-400"
          placeholder="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <div className="flex items-center justify-between">
        <label className="inline-flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          Beni hatırla
        </label>
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 rounded bg-emerald-500 hover:bg-emerald-400 text-black font-medium disabled:opacity-50"
        >
          {loading ? 'Giriş yapılıyor...' : 'Giriş Yap'}
        </button>
      </div>
      <div className="text-xs text-slate-500">
        Test: URL: http://paket7e.org:8080, Kullanıcı: Y9DgfVaDc328, Şifre: Mc7jxWXJT8sP
      </div>
    </form>
  )
}