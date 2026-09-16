import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { apiClient } from '@/lib/apiClient';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';
import { Loader2 } from 'lucide-react';

const AuditoriaTab = () => {
    const [auditLogs, setAuditLogs] = useState([]);
    const [loading, setLoading] = useState(true);

    const formatLogs = useCallback((logs, userMap) => {
        return logs.map(log => {
            const user = userMap[log.details?.actor_id] || {};
            return {
                id: log.details?.id,
                action: log.action,
                user_name: user.nome_completo || 'Usuário do Sistema',
                user_email: user.email || log.user_email || 'N/A',
                ip_address: log.details?.ip,
                created_at: log.timestamp
            };
        }).filter(log => log.action === 'login');
    }, []);

    const fetchAuditLogs = useCallback(async () => {
        setLoading(true);
        try {
            const { data: authLogs, error: authError } = await apiClient.rpc('get_audit_logs');

            if (authError) {
                throw authError;
            }

            const userIds = authLogs.map(log => log.details?.actor_id).filter(Boolean);
            
            let userMap = {};
            if (userIds.length > 0) {
                const { data: users, error: usersError } = await apiClient
                    .from('usuarios')
                    .select('id, nome_completo, email')
                    .in('id', userIds);
                
                if (usersError) {
                    throw usersError;
                }
                
                userMap = users.reduce((acc, user) => {
                    acc[user.id] = user;
                    return acc;
                }, {});
            }
            setAuditLogs(formatLogs(authLogs, userMap));
        } catch (error) {
            console.error('Erro ao buscar logs de auditoria:', error);
        } finally {
            setLoading(false);
        }
    }, [formatLogs]);

    useEffect(() => {
        fetchAuditLogs();
    }, [fetchAuditLogs]);


    const getActionBadge = (action) => {
        switch (action) {
            case 'login':
                return <Badge variant="secondary">Login</Badge>;
            default:
                return <Badge variant="outline">{action}</Badge>;
        }
    };

    return (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <Card>
                <CardHeader>
                    <CardTitle>Histórico de Atividades do Sistema</CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="flex justify-center items-center py-10">
                            <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
                            <p className="ml-2 text-gray-600">Carregando registros...</p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Usuário</TableHead>
                                        <TableHead>Ação</TableHead>
                                        <TableHead>Endereço IP</TableHead>
                                        <TableHead>Data e Hora</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {auditLogs.map((log) => (
                                        <TableRow key={log.id}>
                                            <TableCell>
                                                <div className="font-medium">{log.user_name}</div>
                                                <div className="text-sm text-muted-foreground">{log.user_email}</div>
                                            </TableCell>
                                            <TableCell>{getActionBadge(log.action)}</TableCell>
                                            <TableCell>{log.ip_address}</TableCell>
                                            <TableCell>
                                                {safeFormatDate(log.created_at, "dd/MM/yyyy 'às' HH:mm:ss", { locale: ptBR })}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                     {(!loading && auditLogs.length === 0) && (
                        <p className="text-center py-10 text-gray-500">Nenhum registro de atividade encontrado.</p>
                     )}
                </CardContent>
            </Card>
        </motion.div>
    );
};

export default AuditoriaTab;