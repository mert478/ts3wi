import { useEffect, useState } from 'react'
import ChannelList from '../components/Content/ChannelList'
import VideoPlayer from '../components/Player/VideoPlayer'
import Loading from '../components/Common/Loading'
import { iptvService } from '../services/iptv'

export default function LiveTV() {
  const [items, setItems] = useState<{ id: number; name: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [playId, setPlayId] = useState<number | null>(null)
  const [streamUrl, setStreamUrl] = useState('')

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const channels = await iptvService.getChannels()
        if (mounted) setItems(channels)
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  const onPlay = async (id: number) => {
    setPlayId(id)
    const url = await iptvService.getStreamUrl(id, 'live')
    setStreamUrl(url)
  }

  if (loading) return <Loading />

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="md:col-span-1">
        <ChannelList items={items} onPlay={onPlay} />
      </div>
      <div className="md:col-span-2">
        {playId ? (
          <VideoPlayer src={streamUrl} />
        ) : (
          <div className="h-64 grid place-items-center bg-slate-900 rounded">Kanal seçiniz</div>
        )}
      </div>
    </div>
  )
}