import { useEffect, useMemo, useState } from 'react'

export default function SearchBar({ placeholder = 'Ara...', onChange }: { placeholder?: string; onChange: (q: string) => void }) {
  const [value, setValue] = useState('')

  const debounced = useMemo(() => {
    let timer: any
    return (v: string) => {
      clearTimeout(timer)
      timer = setTimeout(() => onChange(v), 300)
    }
  }, [onChange])

  useEffect(() => { debounced(value) }, [value, debounced])

  return (
    <div className="w-full">
      <input
        className="w-full px-3 py-2 bg-slate-800 rounded outline-none focus:ring-2 ring-emerald-400"
        placeholder={placeholder}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
    </div>
  )
}