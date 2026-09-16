import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, XCircle, Music, ToyBrick, Languages } from 'lucide-react';
import { cn } from '@/lib/utils';

const specialistIcons = {
  'Música': <Music className="h-5 w-5" />,
  'Psicomotricidade': <ToyBrick className="h-5 w-5" />,
  'Inglês': <Languages className="h-5 w-5" />,
};

const SpecialistContributionStatus = ({ contributions, delay }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100"
    >
      <h3 className="text-lg font-bold text-gray-800 mb-4">Contribuições dos Especialistas</h3>
      <div className="flex flex-wrap gap-4">
        {Object.entries(contributions).map(([specialist, status]) => (
          <div
            key={specialist}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all",
              status ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
            )}
          >
            {status ? <CheckCircle className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
            {specialistIcons[specialist]}
            <span>{specialist}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
};

export default SpecialistContributionStatus;