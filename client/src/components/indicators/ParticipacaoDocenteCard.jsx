import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Users, Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { authFetch } from '@/services/api';

const ParticipacaoDocenteCard = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    const fetchData = async () => {
      const instituicaoId = user?.instituicao_id || user?.user_metadata?.instituicao_id;
      if (!instituicaoId) return;

      setLoading(true);
      try {
        const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '').trim();
        // authFetch: leva credenciais, CSRF e o header que evita a interstitial
        // do ngrok (que devolveria HTML no lugar do JSON quando servido por túnel).
        const response = await authFetch(
          `${API_BASE_URL}/api/indicadores/participacao-docente/?instituicao_id=${instituicaoId}`
        );
        if (!response.ok) throw new Error(`Erro: ${response.status}`);
        const participationData = await response.json();
        setData(Array.isArray(participationData) ? participationData : []);
      } catch (error) {
        console.error("Erro ao buscar dados de participação docente:", error);
        setData([]);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [user]);

  return (
    <Card className="h-full flex flex-col">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Users className="h-5 w-5 text-purple-600" />
          Indicadores de Participação Docente nos últimos 30 dias
        </CardTitle>
        <CardDescription>Acompanhe o engajamento e as entregas feitas pelos professores.</CardDescription>
      </CardHeader>
      <CardContent className="flex-grow">
        {loading ? (
          <div className="flex justify-center items-center h-full">
            <Loader2 className="h-8 w-8 animate-spin text-roxo-principal" />
          </div>
        ) : (
          <div className="overflow-x-auto overflow-y-auto max-h-80">
            <Table>
              <TableHeader className="sticky top-0 bg-white z-10">
                <TableRow>
                  <TableHead className="font-bold text-gray-700">Professor(a)</TableHead>
                  <TableHead className="text-center font-bold text-gray-700">Registros</TableHead>
                  <TableHead className="text-center font-bold text-gray-700">Relatórios</TableHead>
                  <TableHead className="text-center font-bold text-gray-700">Planejamentos</TableHead>
                  <TableHead className="text-center font-bold text-gray-700">Portfólios</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(Array.isArray(data) ? [...data].sort((a, b) => {
                  const totalA = (a.registros_pedagogicos || 0) + (a.relatorios_entregues || 0) + (a.planejamentos_realizados || 0) + (a.portfolio_itens || 0);
                  const totalB = (b.registros_pedagogicos || 0) + (b.relatorios_entregues || 0) + (b.planejamentos_realizados || 0) + (b.portfolio_itens || 0);
                  return totalB - totalA;
                }) : []).map((teacher) => (
                  <TableRow key={teacher.professor_id}>
                    <TableCell className="font-medium text-gray-800">{teacher.professor_nome}</TableCell>
                    <TableCell className="text-center">{teacher.registros_pedagogicos}</TableCell>
                    <TableCell className="text-center">{teacher.relatorios_entregues}</TableCell>
                    <TableCell className="text-center">{teacher.planejamentos_realizados}</TableCell>
                    <TableCell className="text-center">{teacher.portfolio_itens}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ParticipacaoDocenteCard;
