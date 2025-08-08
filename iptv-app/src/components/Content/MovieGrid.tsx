import { useMemo, useState } from 'react'
import ContentCard from './ContentCard'
import SearchBar from '../Common/SearchBar'

type Item = { id: number; name: string; poster?: string }

export default function MovieGrid({ items, onPlay }: { items: Item[]; onPlay: (id: number) => void }) {
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<'az' | 'za'>('az')

  const filtered = useMemo(() => {
    const list = items.filter(i => i.name.toLowerCase().includes(query.toLowerCase()))
    return list.sort((a, b) => sort === 'az' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name))
  }, [items, query, sort])

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <SearchBar onChange={setQuery} />
        <select
          value={sort}
          onChange={e => setSort(e.target.value as any)}
          className="px-3 py-2 bg-slate-800 rounded"
        >
          <option value="az">A-Z</option>
          <option value="za">Z-A</option>
        </select>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
        {filtered.map(i => (
          <ContentCard key={i.id} title={i.name} poster={i.poster} onClick={() => onPlay(i.id)} />
        ))}
      </div>
    </div>
  )
}