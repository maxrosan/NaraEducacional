import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Map, TrendingDown } from 'lucide-react';
import { campoExperienciaMap } from '@/lib/observationUtils';

const COLORS = ['#8A63D2', '#A488E1', '#60A5FA', '#34D399', '#FBBF24', '#F87171'];

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-2 border border-gray-200 rounded-lg shadow-lg">
        <p className="font-bold text-gray-800">{`${payload[0].payload.name}`}</p>
        <p className="text-sm" style={{ color: payload[0].fill }}>{`Registros: ${payload[0].value}`}</p>
      </div>
    );
  }
  return null;
};

const BnccUsageMap = ({ data }) => {
    
    const chartData = Object.entries(campoExperienciaMap).map(([key, value]) => {
        const entry = data.find(d => d.campo_experiencia === key);
        return {
            name: value.name,
            registros: entry ? entry.count : 0,
        };
    }).sort((a,b) => b.registros - a.registros);

    const leastUsed = chartData.filter(item => item.registros > 0).sort((a, b) => a.registros - b.registros).slice(0, 2);

    return (
        <Card className="shadow-lg h-full">
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Map className="h-5 w-5 text-indigo-500" />
                    Mapa de Utilização dos Campos da BNCC
                </CardTitle>
                <CardDescription>Veja quais aspectos do desenvolvimento infantil estão sendo mais registrados.</CardDescription>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                        <XAxis type="number" hide />
                        <YAxis 
                            type="category" 
                            dataKey="name" 
                            tickLine={false} 
                            axisLine={false} 
                            tick={{ fontSize: 12, width: 120, fill: '#6b7280' }}
                            width={110}
                         />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#F5F3FA' }} />
                        <Bar dataKey="registros" radius={[0, 4, 4, 0]}>
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
                {leastUsed.length > 0 && (
                     <div className="mt-4 w-full bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-r-lg">
                        <h4 className="font-bold text-yellow-800 flex items-center gap-2 text-sm">
                            <TrendingDown className="h-5 w-5"/>
                            Atenção aos campos menos utilizados:
                        </h4>
                        <ul className="list-disc list-inside text-xs text-yellow-700 mt-1">
                            {leastUsed.map(item => <li key={item.name}>{item.name} ({item.registros} {item.registros === 1 ? 'registro' : 'registros'})</li>)}
                        </ul>
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

export default BnccUsageMap;