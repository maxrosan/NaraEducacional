
import React from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Users, Filter, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import StudentRecordsSummary from '@/components/indicators/StudentRecordsSummary';
import BnccUsageChart from '@/components/indicators/BnccUsageChart';
import WeeklyActivityChart from '@/components/indicators/WeeklyActivityChart';
import ObservationTypesSummary from '@/components/indicators/ObservationTypesSummary';
import LowFrequencySkills from '@/components/indicators/LowFrequencySkills';
import ParticipacaoDocenteCard from '@/components/indicators/ParticipacaoDocenteCard';

const bnccSkills = [
    { id: 'bncc01', description: 'Expressar-se por meio da linguagem corporal em brincadeiras e demais situações.' },
    { id: 'bncc02', description: 'Demonstrar interesse por contagens orais e registros escritos de quantidades.' },
    { id: 'bncc03', description: 'Participar de contação de histórias e reconto com criatividade.' },
    { id: 'bncc04', description: 'Explorar diferentes fontes sonoras e materiais para acompanhar brincadeiras cantadas, canções, músicas e melodias.' },
    { id: 'bncc05', description: 'Coordenar suas habilidades manuais no atendimento adequado a seus interesses e necessidades em situações diversas.'},
    { id: 'bncc06', description: 'Comunicar suas ideias e sentimentos a pessoas e grupos diversos.'}
];

const indicatorsData = {
  studentRecords: [
    { id: 1, name: 'Ana Clara', records: 5 },
    { id: 2, name: 'Lucas Gabriel', records: 8 },
    { id: 3, name: 'Beatriz Santos', records: 4 },
    { id: 4, name: 'Davi Lucca', records: 2 },
    { id: 5, name: 'Helena Maria', records: 0 },
    { id: 6, name: 'Miguel Oliveira', records: 6 },
    { id: 7, name: 'Laura Sofia', records: 3 },
    { id: 8, name: 'Arthur Costa', records: 0 },
    { id: 9, name: 'Júlia Rodrigues', records: 7 },
  ],
  bnccUsage: [
    { name: 'Corpo, gestos...', value: 12 },
    { name: 'Linguagens', value: 18 },
    { name: 'Espaços, tempos...', value: 5 },
    { name: 'O eu, o outro...', value: 8 },
    { name: 'Traços, sons...', value: 15 },
    { name: 'Natureza', value: 2 },
  ],
  weeklyActivity: [
    { name: '01-05 Jul', registros: 10 },
    { name: '08-12 Jul', registros: 15 },
    { name: '15-19 Jul', registros: 8 },
    { name: '22-26 Jul', registros: 12 },
  ],
  observationTypes: {
    withIA: 25,
    withMedia: 18,
    plannings: 4,
    specialists: 6
  },
  lowFrequencySkillsData: [
    {
        id: 1, name: 'Ana Clara', skills: [
            { id: 'bncc01', count: 0 },
            { id: 'bncc02', count: 0 },
            { id: 'bncc03', count: 2 },
            { id: 'bncc04', count: 4 },
            { id: 'bncc05', count: 5 },
            { id: 'bncc06', count: 3 },
        ]
    },
    {
        id: 2, name: 'Lucas Gabriel', skills: [
            { id: 'bncc01', count: 5 },
            { id: 'bncc02', count: 4 },
            { id: 'bncc03', count: 6 },
            { id: 'bncc04', count: 3 },
            { id: 'bncc05', count: 5 },
            { id: 'bncc06', count: 4 },
        ]
    },
    {
        id: 4, name: 'Davi Lucca', skills: [
            { id: 'bncc01', count: 1 },
            { id: 'bncc02', count: 0 },
            { id: 'bncc03', count: 1 },
            { id: 'bncc04', count: 0 },
            { id: 'bncc05', count: 2 },
            { id: 'bncc06', count: 0 },
        ]
    }
  ]
};


function IndicatorsPage() {
    const navigate = useNavigate();

    return (
        <>
            <Helmet>
                <title>NARA - Meus Indicadores</title>
                <meta name="description" content="Acompanhe seus indicadores de prática pedagógica." />
            </Helmet>
            <div className="bg-[#F5F3FA] min-h-screen">
                <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-20 shadow-sm">
                    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-y-3">
                        <div className="flex items-center gap-2 sm:gap-4">
                            <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                                <ArrowLeft className="h-6 w-6 text-gray-600" />
                            </Button>
                            <h1 className="text-lg sm:text-xl font-bold text-gray-800">Meus Indicadores</h1>
                        </div>
                        <div className="flex items-center gap-2 sm:gap-4 w-full sm:w-auto">
                            <div className="flex items-center gap-2 flex-1">
                                <Filter className="h-4 w-4 text-gray-500 hidden sm:block" />
                                <Select defaultValue="turma-a">
                                    <SelectTrigger className="w-full sm:w-[180px]">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="turma-a">Turma Nível 4 - A</SelectItem>
                                        <SelectItem value="turma-b">Turma Nível 4 - B</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="flex items-center gap-2 flex-1">
                                <Calendar className="h-4 w-4 text-gray-500 hidden sm:block" />
                                <Select defaultValue="bimestre">
                                    <SelectTrigger className="w-full sm:w-[150px]">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="15dias">Últimos 15 dias</SelectItem>
                                        <SelectItem value="mes">Mês</SelectItem>
                                        <SelectItem value="bimestre">Bimestre</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </div>
                </header>
                <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
                    <motion.div 
                        className="grid grid-cols-1 lg:grid-cols-3 gap-6"
                        initial="hidden"
                        animate="visible"
                        variants={{
                            visible: { transition: { staggerChildren: 0.1 } }
                        }}
                    >
                         <motion.div className="lg:col-span-3" variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 }}}>
                           <ParticipacaoDocenteCard />
                        </motion.div>
                         <motion.div className="lg:col-span-3" variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 }}}>
                           <LowFrequencySkills data={indicatorsData.lowFrequencySkillsData} skills={bnccSkills} />
                        </motion.div>
                        <motion.div className="lg:col-span-1" variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 }}}>
                           <StudentRecordsSummary data={indicatorsData.studentRecords} />
                        </motion.div>
                        <motion.div className="lg:col-span-2" variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 }}}>
                            <BnccUsageChart data={indicatorsData.bnccUsage} />
                        </motion.div>
                         <motion.div className="lg:col-span-2" variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 }}}>
                            <WeeklyActivityChart data={indicatorsData.weeklyActivity} />
                        </motion.div>
                         <motion.div className="lg:col-span-1" variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0 }}}>
                            <ObservationTypesSummary data={indicatorsData.observationTypes} />
                        </motion.div>
                    </motion.div>
                </main>
            </div>
        </>
    );
}

export default IndicatorsPage;
