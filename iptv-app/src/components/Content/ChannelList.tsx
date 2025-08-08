type Channel = { id: number; name: string }

export default function ChannelList({ items, onPlay }: { items: Channel[]; onPlay: (id: number) => void }) {
  return (
    <div className="divide-y divide-slate-800 rounded-lg overflow-hidden bg-slate-900">
      {items.map(ch => (
        <button key={ch.id} onClick={() => onPlay(ch.id)} className="w-full text-left px-3 py-2 hover:bg-slate-800 focus-visible:bg-slate-800">
          {ch.name}
        </button>
      ))}
    </div>
  )
}