import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Camera, Edit3, Users, BookOpen } from 'lucide-react';

const SummaryItem = ({ icon, value, label, color }) => (
    <div className={`flex items-center p-3 rounded-xl gap-3 ${color}`}>
        <div className="p-2 bg-white/50 rounded-full">
            {icon}
        </div>
        <div>
            <p className="font-bold text-xl text-gray-800">{value}</p>
            <p className="text-sm text-gray-700">{label}</p>
        </div>
    </div>
);

const ObservationTypesSummary = ({ data }) => {
    return (
        <Card className="h-full">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">Tipos de Observações</CardTitle>
                <CardDescription>Distribuição dos seus registros e atividades.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
                <SummaryItem
                    icon={<Edit3 className="h-5 w-5 text-blue-600" />}
                    value={data.withIA}
                    label="Registros com IA"
                    color="bg-blue-100"
                />
                <SummaryItem
                    icon={<Camera className="h-5 w-5 text-green-600" />}
                    value={data.withMedia}
                    label="Com Foto/Vídeo"
                    color="bg-green-100"
                />
                 <SummaryItem
                    icon={<BookOpen className="h-5 w-5 text-purple-600" />}
                    value={data.plannings}
                    label="Planejamentos"
                    color="bg-purple-100"
                />
                <SummaryItem
                    icon={<Users className="h-5 w-5 text-orange-600" />}
                    value={data.specialists}
                    label="Contribuições de Especialistas"
                    color="bg-orange-100"
                />
            </CardContent>
        </Card>
    );
};

export default ObservationTypesSummary;