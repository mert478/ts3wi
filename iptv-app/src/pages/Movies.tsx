import { useEffect, useState } from 'react'
import MovieGrid from '../components/Content/MovieGrid'
import VideoPlayer from '../components/Player/VideoPlayer'
import Loading from '../components/Common/Loading'
import { iptvService } from '../services/iptv'

export default function Movies() {
  const [items, setItems] = useState<{ id: number; name: string; poster?: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [playId, setPlayId] = useState<number | null>(null)
  const [streamUrl, setStreamUrl] = useState('')

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const movies = await iptvService.getMovies()
        if (mounted) setItems(movies)
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  const onPlay = async (id: number) => {
    setPlayId(id)
    const url = await iptvService.getStreamUrl(id, 'movie')
    setStreamUrl(url)
  }

  if (loading) return <Loading />

  return (
    <div>
      <MovieGrid items={items} onPlay={onPlay} />
      {playId && (
        <div className="fixed inset-0 bg-black/80 grid place-items-center p-4">
          <div className="w-full max-w-4xl">
            <VideoPlayer src={streamUrl} />
            <div className="text-right mt-2">
              <button className="px-3 py-1 bg-slate-800 rounded" onClick={() => setPlayId(null)}>Kapat</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}