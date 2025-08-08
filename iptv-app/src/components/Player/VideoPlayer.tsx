import Hls from 'hls.js'
import { useEffect, useRef, useState } from 'react'
import PlayerControls from './PlayerControls'

type Props = { src: string; autoPlay?: boolean }

export default function VideoPlayer({ src, autoPlay = true }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const hlsRef = useRef<Hls | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const video = videoRef.current!
    if (Hls.isSupported() && src.endsWith('.m3u8')) {
      const hls = new Hls({ autoStartLoad: true })
      hlsRef.current = hls
      hls.loadSource(src)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => setReady(true))
    } else {
      video.src = src
      video.oncanplay = () => setReady(true)
    }
    if (autoPlay) video.autoplay = true
    return () => {
      hlsRef.current?.destroy()
      hlsRef.current = null
    }
  }, [src, autoPlay])

  const onSeek = (seconds: number) => {
    if (videoRef.current) videoRef.current.currentTime += seconds
  }
  const onVolume = (v: number) => { if (videoRef.current) videoRef.current.volume = v }

  const onToggleFullscreen = () => {
    const el = videoRef.current?.parentElement
    if (!el) return
    if (document.fullscreenElement) document.exitFullscreen()
    else el.requestFullscreen()
  }

  return (
    <div className="relative bg-black">
      <video ref={videoRef} controls className="w-full h-auto" playsInline />
      {ready && (
        <PlayerControls onSeek={onSeek} onToggleFullscreen={onToggleFullscreen} onVolume={onVolume} />
      )}
    </div>
  )
}