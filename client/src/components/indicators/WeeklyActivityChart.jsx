import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, Activity } from 'lucide-react';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-2 border border-gray-200 rounded-lg shadow-lg">
        <p className="font-bold text-gray-800">{`Semana: ${label}`}</p>
        <p className="text-sm text-purple-600">{`Registros: ${payload[0].value}`}</p>
      </div>
    );
  }

  return null;
};

const WeeklyActivityChart = ({ data }) => {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">Registros por Semana</CardTitle>
                <CardDescription>Acompanhe a sua constância nos registros.</CardDescription>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                    <BarChart
                        data={data}
                        margin={{
                            top: 5,
                            right: 20,
                            left: -10,
                            bottom: 5,
                        }}
                    >
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis allowDecimals={false} fontSize={12} tickLine={false} axisLine={false} />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#F5F3FA' }} />
                        <Bar dataKey="registros" fill="#8A63D2" name="Registros" radius={[4, 4, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
};

export default WeeklyActivityChart;
