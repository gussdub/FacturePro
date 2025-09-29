import React from 'react';
import { Bell, CheckCircle, AlertCircle, Info, X } from 'lucide-react';

const NotificationsDropdown = ({ isOpen, onClose }) => {
  // Notifications simulées pour la démonstration
  const notifications = [
    {
      id: 1,
      type: 'success',
      title: 'Facture payée',
      message: 'La facture #FAC-001 a été marquée comme payée',
      time: '2 minutes',
      read: false
    },
    {
      id: 2,
      type: 'warning',
      title: 'Facture en retard',
      message: 'La facture #FAC-003 est échue depuis 5 jours',
      time: '1 heure',
      read: false
    },
    {
      id: 3,
      type: 'info',
      title: 'Nouveau client',
      message: 'Un nouveau client a été ajouté à votre base',
      time: '3 heures',
      read: true
    }
  ];

  const getIcon = (type) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'warning':
        return <AlertCircle className="w-4 h-4 text-orange-500" />;
      case 'info':
        return <Info className="w-4 h-4 text-blue-500" />;
      default:
        return <Bell className="w-4 h-4 text-gray-500" />;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50 max-h-96 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center">
          <Bell className="w-5 h-5 text-gray-600 mr-2" />
          <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Notifications List */}
      <div className="max-h-80 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            <Bell className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            <p className="text-sm">Aucune notification</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {notifications.map((notification) => (
              <div
                key={notification.id}
                className={`p-4 hover:bg-gray-50 transition-colors cursor-pointer ${
                  !notification.read ? 'bg-blue-50' : ''
                }`}
              >
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 mt-0.5">
                    {getIcon(notification.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="text-sm font-medium text-gray-900 truncate">
                        {notification.title}
                      </h4>
                      <span className="text-xs text-gray-500 ml-2">
                        {notification.time}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 line-clamp-2">
                      {notification.message}
                    </p>
                    {!notification.read && (
                      <div className="w-2 h-2 bg-blue-500 rounded-full mt-2"></div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      {notifications.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center">
            <button className="text-sm text-blue-600 hover:text-blue-800 font-medium">
              Marquer tout comme lu
            </button>
            <button className="text-sm text-gray-600 hover:text-gray-800">
              Voir tout
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationsDropdown;