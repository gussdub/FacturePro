import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Bell, CheckCircle, AlertCircle, Info, X } from 'lucide-react';

const NotificationsModal = ({ isOpen, onClose }) => {
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
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'warning':
        return <AlertCircle className="w-5 h-5 text-orange-500" />;
      case 'info':
        return <Info className="w-5 h-5 text-blue-500" />;
      default:
        return <Bell className="w-5 h-5 text-gray-500" />;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <Bell className="w-5 h-5 mr-2" />
            Notifications
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="text-center py-6 text-gray-500">
              <Bell className="w-12 h-12 mx-auto mb-2 text-gray-300" />
              <p>Aucune notification</p>
            </div>
          ) : (
            notifications.map((notification) => (
              <div
                key={notification.id}
                className={`p-3 rounded-lg border transition-colors ${
                  !notification.read
                    ? 'bg-blue-50 border-blue-200'
                    : 'bg-gray-50 border-gray-200'
                }`}
              >
                <div className="flex items-start space-x-3">
                  {getIcon(notification.type)}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium text-gray-900">
                        {notification.title}
                      </h4>
                      <span className="text-xs text-gray-500">
                        Il y a {notification.time}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">
                      {notification.message}
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
        
        <div className="flex justify-between items-center pt-4 border-t">
          <Button variant="outline" size="sm">
            Marquer tout comme lu
          </Button>
          <Button onClick={onClose} size="sm">
            Fermer
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default NotificationsModal;