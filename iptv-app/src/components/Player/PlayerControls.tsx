type Props = {
  onSeek: (seconds: number) => void
  onToggleFullscreen: () => void
  onVolume: (v: number) => void
}

export default function PlayerControls({ onSeek, onToggleFullscreen, onVolume }: Props) {
  return (
    <div className="absolute bottom-2 left-2 right-2 flex items-center gap-2 bg-black/40 px-3 py-2 rounded">
      <button onClick={() => onSeek(-10)} className="px-2 py-1 bg-slate-800 rounded">-10s</button>
      <button onClick={() => onSeek(10)} className="px-2 py-1 bg-slate-800 rounded">+10s</button>
      <input type="range" min={0} max={1} step={0.05} onChange={(e) => onVolume(parseFloat(e.target.value))} className="flex-1" />
      <button onClick={onToggleFullscreen} className="px-2 py-1 bg-slate-800 rounded">Tam ekran</button>
    </div>
  )
}