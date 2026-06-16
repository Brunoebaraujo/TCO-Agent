import { Outlet, NavLink } from 'react-router-dom'
import { MessageSquare, Clock, Database, ChevronRight } from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { to: '/chat',           label: 'New TCO',        icon: MessageSquare },
  { to: '/history',        label: 'History',         icon: Clock },
  { to: '/knowledge-base', label: 'Knowledge Base',  icon: Database },
]

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">

      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-[#1a3a5c] flex flex-col">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-white/10">
          <span className="text-white font-semibold text-sm tracking-wide">
            TCO Engine
          </span>
          <span className="block text-white/40 text-xs mt-0.5">by Goodpack</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                  isActive
                    ? 'bg-white/10 text-white font-medium'
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-white/10">
          <span className="text-white/30 text-xs">v0.1.0 — Phase 1</span>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>

    </div>
  )
}
