import React from 'react';
import { motion } from 'framer-motion';
import { MessageCircle, BrainCircuit } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useToast } from '@/components/ui/use-toast';

const ProfessorHeader = ({ professorName }) => {
  const { toast } = useToast();

  const handleNaraClick = () => {
    toast({
      title: "🚀 NARA em breve!",
      description: "A assistente virtual NARA está em desenvolvimento e será lançada em breve.",
    });
  };

  return (
    <div className="bg-gradient-to-r from-purple-50 to-indigo-50 p-6 sm:p-8 rounded-3xl mb-8 shadow-sm">
      <motion.div 
        className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <div className="flex-1">
          <h1 className="text-3xl md:text-4xl font-extrabold text-gray-800 tracking-tight">
            Olá, <span className="text-purple-600">{professorName || 'Professor(a)'}!</span>
          </h1>
          <p className="mt-2 text-md text-gray-600 max-w-lg">
            Que bom ter você aqui! Pronto para registrar as vivências e descobertas da sua turma?
          </p>
        </div>
        
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <Card className="bg-white/70 backdrop-blur-sm border-purple-200 rounded-2xl shadow-lg w-full md:w-auto">
            <CardContent className="p-4 flex flex-col sm:flex-row items-center gap-4">
              <div className="bg-purple-100 p-3 rounded-full">
                <BrainCircuit className="h-8 w-8 text-purple-600" />
              </div>
              <div className="text-center sm:text-left">
                <p className="font-bold text-lg text-gray-800">NARA TA AQUI.</p>
                <p className="text-sm text-gray-500">Sua assistente para devolutivas e sugestões.</p>
              </div>
              <Button onClick={handleNaraClick} className="nara-gradient text-white btn-hover mt-2 sm:mt-0 ml-0 sm:ml-4">
                <MessageCircle className="mr-2 h-4 w-4" />
                Conversar com NARA
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
    </div>
  );
};

export default ProfessorHeader;