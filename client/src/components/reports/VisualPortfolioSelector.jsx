import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, Circle } from 'lucide-react';
import { cn } from '@/lib/utils';

const VisualPortfolioSelector = ({ records, selected, onToggle, delay }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100"
    >
      <h3 className="text-lg font-bold text-gray-800 mb-4">Portfólio Visual (selecione até 3)</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {records.map(record => {
          const isSelected = selected.includes(record.id);
          return (
            <div
              key={record.id}
              onClick={() => onToggle(record.id)}
              className="relative cursor-pointer group"
            >
              <img
                src={record.mediaUrl}
                alt={record.title}
                className={cn(
                  "rounded-lg w-full h-32 object-cover border-4 transition-all",
                  isSelected ? "border-[#8A63D2]" : "border-transparent group-hover:border-gray-200"
                )}
              />
              <div className="absolute top-2 right-2 bg-white/80 rounded-full">
                {isSelected ? (
                  <CheckCircle className="h-6 w-6 text-[#8A63D2]" />
                ) : (
                  <Circle className="h-6 w-6 text-gray-400 group-hover:text-gray-600" />
                )}
              </div>
              <p className="text-xs text-center mt-1 font-medium text-gray-600">{record.title}</p>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
};

export default VisualPortfolioSelector;