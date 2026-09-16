import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckCircle, AlertCircle, XCircle } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

const getStatus = (records) => {
    if (records === 0) return { icon: <XCircle className="h-5 w-5 text-red-500" />, text: 'Sem registro', color: 'bg-red-50 text-red-700' };
    if (records < 3) return { icon: <AlertCircle className="h-5 w-5 text-yellow-500" />, text: 'Poucos registros', color: 'bg-yellow-50 text-yellow-700' };
    return { icon: <CheckCircle className="h-5 w-5 text-green-500" />, text: 'Registros em dia', color: 'bg-green-50 text-green-700' };
};

const StudentRecordsSummary = ({ data }) => {
    const studentsWithZeroRecords = data.filter(s => s.records === 0).length;

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">Resumo por Criança</CardTitle>
                <CardDescription>
                    Registros feitos nos últimos 15 dias. 
                    {studentsWithZeroRecords > 0 && 
                        <span className="font-bold text-red-600 ml-1">
                           ({studentsWithZeroRecords} {studentsWithZeroRecords > 1 ? 'crianças' : 'criança'} sem registro!)
                        </span>
                    }
                </CardDescription>
            </CardHeader>
            <CardContent>
                <ScrollArea className="h-[280px] pr-4">
                    <div className="space-y-2">
                        {data.map(student => {
                            const status = getStatus(student.records);
                            return (
                                <div key={student.id} className={`flex justify-between items-center p-3 rounded-lg ${status.color}`}>
                                    <span className="font-medium">{student.name}</span>
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold">{student.records}</span>
                                        {status.icon}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </ScrollArea>
            </CardContent>
        </Card>
    );
};

export default StudentRecordsSummary;