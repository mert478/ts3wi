type Props = {
  title: string
  poster?: string
  onClick?: () => void
}

export default function ContentCard({ title, poster, onClick }: Props) {
  return (
    <button
      className="flex flex-col bg-slate-900 rounded-lg overflow-hidden focus-visible:ring-2 ring-emerald-400 ring-offset-0 outline-none"
      onClick={onClick}
    >
      <div className="aspect-[2/3] bg-slate-800">
        {poster ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={poster} alt={title} className="w-full h-full object-cover" loading="lazy" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-500 text-sm">Poster yok</div>
        )}
      </div>
      <div className="p-2 text-left text-sm line-clamp-2 min-h-10">{title}</div>
    </button>
  )
}