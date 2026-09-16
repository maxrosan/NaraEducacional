import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Lightbulb, TrendingDown } from 'lucide-react';

const COLORS = ['#8A63D2', '#A488E1', '#BEADF0', '#D7CDEB', '#C3ECD4', '#A9E2BF'];
const RADIAN = Math.PI / 180;

const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index, name }) => {
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  if (percent * 100 < 5) return null;

  return (
    <text x={x} y={y} fill="white" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" className="text-xs font-bold">
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-2 border border-gray-200 rounded-lg shadow-lg">
        <p className="font-bold text-gray-800">{`${payload[0].name}`}</p>
        <p className="text-sm text-purple-600">{`Registros: ${payload[0].value}`}</p>
      </div>
    );
  }
  return null;
};

const BnccUsageChart = ({ data }) => {
    const leastUsed = data.sort((a, b) => a.value - b.value).slice(0, 2);

    return (
        <Card className="h-full flex flex-col">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">Uso dos Campos da BNCC</CardTitle>
                <CardDescription>Frequência de marcação por campo de experiência.</CardDescription>
            </CardHeader>
            <CardContent className="flex-grow flex flex-col justify-center items-center">
                <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                        <Pie
                            data={data}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={renderCustomizedLabel}
                            outerRadius={110}
                            fill="#8884d8"
                            dataKey="value"
                            nameKey="name"
                        >
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                    </PieChart>
                </ResponsiveContainer>
                <div className="mt-4 w-full bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-r-lg">
                    <h4 className="font-bold text-yellow-800 flex items-center gap-2">
                        <TrendingDown className="h-5 w-5"/>
                        Atenção aos campos menos utilizados:
                    </h4>
                    <ul className="list-disc list-inside text-sm text-yellow-700 mt-1">
                        {leastUsed.map(item => <li key={item.name}>{item.name} ({item.value} {item.value === 1 ? 'registro' : 'registros'})</li>)}
                    </ul>
                </div>
            </CardContent>
        </Card>
    );
};

export default BnccUsageChart;
