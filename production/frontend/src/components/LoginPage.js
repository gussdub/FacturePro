import React, { useState } from 'react';
import { useAuth } from '../App';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card } from './ui/card';
import { Alert, AlertDescription } from './ui/alert';
import ForgotPasswordModal from './ForgotPasswordModal';
import { Eye, EyeOff, Receipt, Zap, Shield, Clock } from 'lucide-react';

const LoginPage = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    companyName: ''
  });

  const { login, register } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      let result;
      if (isLogin) {
        result = await login(formData.email, formData.password);
      } else {
        result = await register(formData.email, formData.password, formData.companyName);
      }

      if (!result.success) {
        setError(result.error);
      }
    } catch (err) {
      setError('Une erreur est survenue');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex">
      {/* Left side - Hero Section */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-indigo-600 via-purple-600 to-blue-700 relative overflow-hidden">
        <div className="absolute inset-0 bg-black/10"></div>
        
        {/* Decorative circles */}
        <div className="absolute top-20 left-20 w-72 h-72 bg-white/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-blue-400/20 rounded-full blur-3xl"></div>
        
        <div className="relative z-10 flex flex-col justify-center px-12 text-white">
          <div className="mb-8">
            <Receipt className="w-16 h-16 text-white/90 mb-6" />
            <h1 className="text-5xl font-bold mb-4 leading-tight">
              Simplifiez votre
              <span className="block text-blue-200">facturation</span>
            </h1>
            <p className="text-xl text-white/80 leading-relaxed">
              Gérez vos factures, devis et clients en toute simplicité avec notre solution complète et intuitive.
            </p>
          </div>

          <div className="space-y-6">
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                <Zap className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Facturation instantanée</h3>
                <p className="text-white/70">Créez et envoyez vos factures en quelques clics</p>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                <Clock className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Récurrence automatique</h3>
                <p className="text-white/70">Programmez vos factures récurrentes</p>
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                <Shield className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Sécurisé et fiable</h3>
                <p className="text-white/70">Vos données sont protégées et sauvegardées</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right side - Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="mb-6">
              {/* FacturePro Logo */}
              <div className="flex items-center justify-center mb-4">
                <div className="w-12 h-12 bg-teal-600 rounded-lg flex items-center justify-center mr-3">
                  <div className="relative">
                    <div className="w-8 h-8 bg-white rounded-md flex items-center justify-center">
                      <svg viewBox="0 0 24 24" className="w-5 h-5 text-teal-600" fill="currentColor">
                        <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                        <path d="M8,12H16V14H8V12M8,16H16V18H8V16Z" />
                      </svg>
                    </div>
                    <div className="absolute -top-1 -right-1 w-3 h-3 bg-gradient-to-br from-blue-400 to-purple-500 rounded-full"></div>
                  </div>
                </div>
                <span className="text-2xl font-bold text-gray-900 tracking-tight">FacturePro</span>
              </div>
            </div>
            <h2 className="text-3xl font-bold text-gray-900 mb-2">
              {isLogin ? 'Connexion' : 'Créer un compte'}
            </h2>
            <p className="text-gray-600">
              {isLogin 
                ? 'Accédez à votre tableau de bord' 
                : 'Démarrez votre essai gratuit aujourd\'hui'
              }
            </p>
          </div>

          <Card className="p-8 shadow-2xl border-0 glass">
            {error && (
              <Alert className="mb-6 border-red-200 bg-red-50">
                <AlertDescription className="text-red-800">
                  {error}
                </AlertDescription>
              </Alert>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              {!isLogin && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Nom de l'entreprise
                  </label>
                  <Input
                    type="text"
                    name="companyName"
                    value={formData.companyName}
                    onChange={handleChange}
                    placeholder="Mon Entreprise"
                    required
                    data-testid="company-name-input"
                    className="form-input h-12 text-base"
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Adresse email
                </label>
                <Input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="votre@email.com"
                  required
                  data-testid="email-input"
                  className="form-input h-12 text-base"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Mot de passe
                </label>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="••••••••"
                    required
                    data-testid="password-input"
                    className="form-input h-12 text-base pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700 transition-colors"
                    data-testid="toggle-password-btn"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                disabled={loading}
                data-testid="submit-btn"
                className="w-full h-12 text-base font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 transform hover:scale-[1.02] transition-all duration-200 btn-hover"
              >
                {loading ? (
                  <div className="flex items-center justify-center">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                    Chargement...
                  </div>
                ) : (
                  isLogin ? 'Se connecter' : 'Créer mon compte'
                )}
              </Button>
            </form>

            {/* Forgot Password Link */}
            {isLogin && (
              <div className="mt-4 text-center">
                <button
                  type="button"
                  onClick={() => setShowForgotPassword(true)}
                  className="text-sm text-indigo-600 hover:text-indigo-800 underline"
                >
                  Mot de passe oublié ?
                </button>
              </div>
            )}

            <div className="mt-6 text-center">
              <button
                type="button"
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                  setFormData({ email: '', password: '', companyName: '' });
                }}
                className="text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
                data-testid="toggle-mode-btn"
              >
                {isLogin 
                  ? "Pas encore de compte ? S'inscrire" 
                  : "Déjà un compte ? Se connecter"
                }
              </button>
            </div>
          </Card>

          {!isLogin && (
            <div className="mt-6 text-center text-sm text-gray-500">
              En créant un compte, vous acceptez nos{' '}
              <a href="#" className="text-indigo-600 hover:text-indigo-800">
                conditions d'utilisation
              </a>{' '}
              et notre{' '}
              <a href="#" className="text-indigo-600 hover:text-indigo-800">
                politique de confidentialité
              </a>
            </div>
          )}
        </div>
      </div>
      
      {/* Forgot Password Modal */}
      <ForgotPasswordModal 
        isOpen={showForgotPassword}
        onClose={() => setShowForgotPassword(false)}
      />
    </div>
  );
};

export default LoginPage;