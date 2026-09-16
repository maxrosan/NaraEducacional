import React from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { BookCopy } from 'lucide-react';

const PlaceholderTab = ({ title }) => (
    <Card>
        <CardHeader>
            <CardTitle>{title}</CardTitle>
            <CardDescription>Esta funcionalidade será implementada em breve.</CardDescription>
        </CardHeader>
        <CardContent>
            <div className="flex flex-col items-center justify-center text-center text-gray-500 h-64">
                <motion.div initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 20 }}>
                    <BookCopy className="w-16 h-16 mb-4 text-gray-300" />
                </motion.div>
                <p className="font-semibold">🚧 Em Construção 🚧</p>
                <p className="text-sm">Estamos trabalhando para trazer esta funcionalidade para você!</p>
            </div>
        </CardContent>
    </Card>
);

export default PlaceholderTab;