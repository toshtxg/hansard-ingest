import { Link, useLocation } from 'react-router-dom'
import { Home, Users, BookOpen, TrendingUp, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

const navLinks = [
  { to: '/', label: 'Overview' },
  { to: '/mp', label: 'MPs' },
  { to: '/topics', label: 'Topics' },
  { to: '/trends', label: 'Trends' },
  { to: '/about', label: 'About' },
]

const mobileNav = [
  { to: '/', label: 'Home', icon: Home },
  { to: '/mp', label: 'MPs', icon: Users },
  { to: '/topics', label: 'Topics', icon: BookOpen },
  { to: '/trends', label: 'Trends', icon: TrendingUp },
  { to: '/about', label: 'About', icon: Info },
]

export function Header() {
  const location = useLocation()

  const isActive = (to: string) => {
    if (to === '/') return location.pathname === '/'
    return location.pathname.startsWith(to)
  }

  return (
    <header style={{ backgroundColor: '#1e2a3a' }} className="text-white sticky top-0 z-50 shadow-lg">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo + Title */}
          <Link to="/" className="flex items-center gap-2 text-white hover:text-teal-300 transition-colors">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <rect x="2" y="20" width="24" height="4" rx="1" fill="#0d9488" />
              <rect x="6" y="10" width="3" height="10" fill="white" opacity="0.9" />
              <rect x="12.5" y="10" width="3" height="10" fill="white" opacity="0.9" />
              <rect x="19" y="10" width="3" height="10" fill="white" opacity="0.9" />
              <path d="M14 2 L26 10 H2 L14 2Z" fill="#0d9488" />
            </svg>
            <span className="font-semibold text-lg tracking-tight whitespace-nowrap">SG Hansard Explorer</span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={cn(
                  'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  isActive(to)
                    ? 'bg-teal text-white'
                    : 'text-gray-300 hover:bg-white/10 hover:text-white'
                )}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>

        {/* Mobile icon nav strip */}
        <nav className="md:hidden flex border-t border-white/10">
          {mobileNav.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                'flex-1 flex flex-col items-center gap-1 py-2.5 text-xs font-medium transition-colors',
                isActive(to) ? 'text-teal' : 'text-gray-400 hover:text-white'
              )}
            >
              <Icon size={20} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
      </div>
    </header>
  )
}
