import { Outlet, NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'

export default function AppLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-[--bg] text-slate-100">
      <header className="sticky top-0 z-20 backdrop-blur bg-slate-900/60 border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="font-semibold">IPTV</div>
          <nav className="hidden md:flex gap-4 text-sm">
            <NavLink to="/" className={({ isActive }) => isActive ? 'text-emerald-400' : 'text-slate-300'}>Ana Sayfa</NavLink>
            <NavLink to="/movies" className={({ isActive }) => isActive ? 'text-emerald-400' : 'text-slate-300'}>Filmler</NavLink>
            <NavLink to="/series" className={({ isActive }) => isActive ? 'text-emerald-400' : 'text-slate-300'}>Diziler</NavLink>
            <NavLink to="/livetv" className={({ isActive }) => isActive ? 'text-emerald-400' : 'text-slate-300'}>Canlı TV</NavLink>
            <NavLink to="/settings" className={({ isActive }) => isActive ? 'text-emerald-400' : 'text-slate-300'}>Ayarlar</NavLink>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-4">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Outlet />
        </motion.div>
      </main>

      <footer className="md:hidden fixed bottom-0 inset-x-0 h-14 bg-slate-900/80 border-t border-slate-800">
        <div className="max-w-6xl mx-auto h-full grid grid-cols-5">
          <BottomTab to="/" label="Ana" />
          <BottomTab to="/movies" label="Filmler" />
          <BottomTab to="/series" label="Diziler" />
          <BottomTab to="/livetv" label="Canlı" />
          <BottomTab to="/settings" label="Ayarlar" />
        </div>
      </footer>
    </div>
  )
}

function BottomTab({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        'flex items-center justify-center text-xs ' + (isActive ? 'text-emerald-400' : 'text-slate-400')
      }
    >
      {label}
    </NavLink>
  )
}