import React, { useState, useCallback } from 'react';
import { Button } from './ui/button';
import { Alert, AlertDescription } from './ui/alert';
import { Upload, FileText, Image, Eye, Trash2, CheckCircle } from 'lucide-react';
import axios from 'axios';

const FileUpload = ({ expenseId, currentReceiptUrl, onUploadComplete, onError }) => {
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(currentReceiptUrl || null);

  const handleFiles = async (files) => {
    const file = files[0];
    if (!file) return;

    // Validate file size (10 MB)
    if (file.size > 10 * 1024 * 1024) {
      onError('Le fichier doit faire moins de 10 MB');
      return;
    }

    // Validate file type
    const allowedTypes = [
      'image/jpeg', 'image/jpg', 'image/png', 'image/heic',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ];

    if (!allowedTypes.includes(file.type)) {
      onError('Type de fichier non autorisé. Utilisez JPG, PNG, HEIC, PDF, DOC, DOCX ou XLSX');
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(
        `${process.env.REACT_APP_BACKEND_URL}/api/expenses/${expenseId}/upload-receipt`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      setUploadedFile(response.data.receipt_url);
      onUploadComplete(response.data.receipt_url, response.data.filename);
    } catch (error) {
      onError(error.response?.data?.detail || 'Erreur lors de l\'upload');
    } finally {
      setUploading(false);
    }
  };

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files);
    }
  }, []);

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFiles(e.target.files);
    }
  };

  const openReceipt = () => {
    if (uploadedFile) {
      const url = `${process.env.REACT_APP_BACKEND_URL}/api/expenses/${expenseId}/receipt`;
      window.open(url, '_blank');
    }
  };

  const getFileIcon = (filename) => {
    if (!filename) return <FileText className="w-6 h-6" />;
    
    const ext = filename.toLowerCase().split('.').pop();
    if (['jpg', 'jpeg', 'png', 'heic'].includes(ext)) {
      return <Image className="w-6 h-6 text-blue-500" />;
    }
    return <FileText className="w-6 h-6 text-red-500" />;
  };

  return (
    <div className="space-y-4">
      {!uploadedFile && (
        <div
          className={`
            border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
            ${dragActive 
              ? 'border-indigo-500 bg-indigo-50' 
              : 'border-gray-300 hover:border-indigo-400 hover:bg-gray-50'
            }
            ${uploading ? 'opacity-50 cursor-not-allowed' : ''}
          `}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => !uploading && document.getElementById('file-input')?.click()}
        >
          <input
            id="file-input"
            type="file"
            accept=".jpg,.jpeg,.png,.heic,.pdf,.doc,.docx,.xlsx"
            onChange={handleFileInput}
            className="hidden"
            disabled={uploading}
          />
          
          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          
          {uploading ? (
            <div className="space-y-2">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-500 mx-auto"></div>
              <p className="text-sm text-gray-600">Upload en cours...</p>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-lg font-medium text-gray-700">
                Glissez votre justificatif ici
              </p>
              <p className="text-sm text-gray-500">
                ou <span className="text-indigo-600 font-medium">parcourez vos fichiers</span>
              </p>
              <p className="text-xs text-gray-400">
                JPG, PNG, HEIC, PDF, DOC, XLSX • Max 10 MB
              </p>
            </div>
          )}
        </div>
      )}

      {uploadedFile && (
        <div className="border rounded-lg p-4 bg-green-50 border-green-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <CheckCircle className="w-5 h-5 text-green-600" />
              {getFileIcon(uploadedFile)}
              <div>
                <p className="text-sm font-medium text-green-800">
                  Justificatif uploadé
                </p>
                <p className="text-xs text-green-600">
                  Fichier sauvegardé avec succès
                </p>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={openReceipt}
                className="text-blue-600 border-blue-200"
              >
                <Eye className="w-4 h-4 mr-1" />
                Voir
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setUploadedFile(null);
                  onUploadComplete(null, null);
                }}
                className="text-red-600 border-red-200"
              >
                <Trash2 className="w-4 h-4 mr-1" />
                Supprimer
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUpload;