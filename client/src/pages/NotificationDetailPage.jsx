import React, { useEffect, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiService } from '@/services/api';

const NotificationDetailPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [alert, setAlert] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tipo = params.get('tipo');
    const chave = params.get('chave');

    if (!tipo || !chave) {
      setError('Parâmetros de alerta inválidos.');
      setLoading(false);
      return;
    }

    const fetchAlert = async () => {
      setLoading(true);
      try {
        const data = await apiService.buscarDetalheAlerta(tipo, chave);
        setAlert(data);
      } catch (err) {
        setError('Não foi possível carregar os detalhes do alerta.');
      } finally {
        setLoading(false);
      }
    };

    fetchAlert();
  }, [location.search]);

  return (
    <>
      <Helmet>
        <title>NARA - Detalhe do Alerta</title>
        <meta name="description" content="Detalhe completo do alerta de registros." />
      </Helmet>

      <div className="bg-[#F5F3FA] min-h-screen">
        <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-10 shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-6 w-6 text-gray-600" />
            </Button>
            <h1 className="text-xl font-bold text-gray-800">Detalhe do Alerta</h1>
          </div>
        </header>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {loading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Carregando alerta...</span>
            </div>
          ) : error ? (
            <p className="text-sm text-red-600">{error}</p>
          ) : (
            <div className="bg-white rounded-2xl shadow-md border border-gray-100 p-6 space-y-4">
              <div>
                <p className="text-sm text-gray-500">{alert?.tipo || 'Alerta'}</p>
                <h2 className="text-2xl font-bold text-gray-800">{alert?.titulo}</h2>
              </div>
              <p className="text-gray-700 whitespace-pre-line">{alert?.conteudo}</p>
            </div>
          )}
        </main>
      </div>
    </>
  );
};

export default NotificationDetailPage;
