import React, { useState, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../App';
import { Button } from './ui/button';
import NotificationsDropdown from './NotificationsDropdown';
import UserProfileModal from './UserProfileModal';
import {
  Receipt,
  Users,
  FileText,
  ScrollText,
  Settings,
  LogOut,
  Menu,
  X,
  Bell,
  Search,
  Package,
  BarChart3
} from 'lucide-react';

const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();

  const navigation = [
    { name: 'Tableau de bord', href: '/dashboard', icon: Receipt, current: location.pathname === '/dashboard' },
    { name: 'Clients', href: '/clients', icon: Users, current: location.pathname === '/clients' },
    { name: 'Produits', href: '/products', icon: Package, current: location.pathname === '/products' },
    { name: 'Factures', href: '/invoices', icon: FileText, current: location.pathname === '/invoices' },
    { name: 'Soumissions', href: '/quotes', icon: ScrollText, current: location.pathname === '/quotes' },
    { name: 'Exports', href: '/export', icon: BarChart3, current: location.pathname === '/export' },
    { name: 'Paramètres', href: '/settings', icon: Settings, current: location.pathname === '/settings' },
  ];

  const handleLogout = () => {
    logout();
  };

  // Close user menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuOpen && !event.target.closest('.relative')) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [userMenuOpen]);

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 lg:hidden modal-backdrop"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-xl transform transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between h-16 px-6 bg-gradient-to-r from-teal-600 to-teal-700">
            <div className="flex items-center">
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center mr-3 backdrop-blur-sm">
                <div className="relative">
                  <div className="w-6 h-6 bg-white rounded-md flex items-center justify-center">
                    <svg viewBox="0 0 24 24" className="w-4 h-4 text-teal-600" fill="currentColor">
                      <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                      <path d="M8,12H16V14H8V12M8,16H16V18H8V16Z" />
                    </svg>
                  </div>
                  <div className="absolute -top-1 -right-1 w-2 h-2 bg-gradient-to-br from-blue-400 to-purple-500 rounded-full"></div>
                </div>
              </div>
              <span className="text-xl font-bold text-white tracking-tight">FacturePro</span>
            </div>
            <button
              className="lg:hidden text-white hover:text-gray-200 transition-colors"
              onClick={() => setSidebarOpen(false)}
              data-testid="close-sidebar-btn"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-4 py-6 space-y-2">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  data-testid={`nav-${item.name.toLowerCase().replace(' ', '-')}`}
                  className={`
                    sidebar-item group flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200
                    ${item.current
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-gray-700 hover:bg-gray-50 hover:text-indigo-600'
                    }
                  `}
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon className={`
                    mr-3 h-5 w-5 transition-colors
                    ${item.current ? 'text-indigo-500' : 'text-gray-400 group-hover:text-indigo-500'}
                  `} />
                  {item.name}
                </Link>
              );
            })}
          </nav>

          {/* User section */}
          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center mb-4">
              <div className="w-10 h-10 bg-indigo-600 rounded-full flex items-center justify-center">
                <span className="text-sm font-bold text-white">
                  {user?.company_name?.charAt(0)?.toUpperCase() || 'U'}
                </span>
              </div>
              <div className="ml-3 overflow-hidden">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {user?.company_name || 'Entreprise'}
                </p>
                <p className="text-xs text-gray-500 truncate">
                  {user?.email}
                </p>
              </div>
            </div>
            <Button
              onClick={handleLogout}
              variant="ghost"
              data-testid="logout-btn"
              className="w-full justify-start text-red-600 hover:text-red-700 hover:bg-red-50"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Déconnexion
            </Button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 lg:ml-0">
        {/* Top navigation */}
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center">
                <button
                  className="lg:hidden text-gray-500 hover:text-gray-700 transition-colors mr-4"
                  onClick={() => setSidebarOpen(true)}
                  data-testid="open-sidebar-btn"
                >
                  <Menu className="w-6 h-6" />
                </button>
              </div>

              <div className="flex items-center space-x-4">
                {/* Search bar */}
                <div className="hidden sm:flex relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                  <input
                    type="text"
                    placeholder="Rechercher..."
                    className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                    data-testid="search-input"
                  />
                </div>

                {/* Notifications */}
                <div className="relative">
                  <button 
                    className="relative text-gray-500 hover:text-gray-700 transition-colors p-2 rounded-lg hover:bg-gray-100"
                    data-testid="notifications-btn"
                    onClick={() => setNotificationsOpen(!notificationsOpen)}
                    title="Notifications"
                  >
                    <Bell className="w-5 h-5" />
                    <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                  </button>

                  {/* Notifications Dropdown */}
                  <NotificationsDropdown
                    isOpen={notificationsOpen}
                    onClose={() => setNotificationsOpen(false)}
                  />
                </div>

                {/* User avatar with dropdown */}
                <div className="relative">
                  <button
                    className="w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center hover:bg-indigo-700 transition-colors"
                    onClick={() => setUserMenuOpen(!userMenuOpen)}
                    title="Menu utilisateur"
                  >
                    <span className="text-xs font-bold text-white">
                      {user?.company_name?.charAt(0)?.toUpperCase() || 'U'}
                    </span>
                  </button>

                  {/* Dropdown menu */}
                  {userMenuOpen && (
                    <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50 border">
                      <div className="px-4 py-2 border-b border-gray-200">
                        <p className="text-sm font-medium text-gray-900">
                          {user?.company_name || 'Entreprise'}
                        </p>
                        <p className="text-xs text-gray-500">{user?.email}</p>
                      </div>
                      <button
                        onClick={() => {
                          setUserMenuOpen(false);
                          setProfileOpen(true);
                        }}
                        className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                      >
                        Mon profil
                      </button>
                      <button
                        onClick={() => {
                          setUserMenuOpen(false);
                          // Navigate to settings
                          window.location.href = '/settings';
                        }}
                        className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                      >
                        Paramètres
                      </button>
                      <div className="border-t border-gray-200"></div>
                      <button
                        onClick={() => {
                          setUserMenuOpen(false);
                          logout();
                        }}
                        className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                      >
                        Se déconnecter
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 sm:p-6 lg:p-4">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Modals */}
      <UserProfileModal
        isOpen={profileOpen}
        onClose={() => setProfileOpen(false)}
      />
    </div>
  );
};

export default Layout;