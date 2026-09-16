import React from 'react';
import { Inbox } from 'lucide-react';
import { motion } from 'framer-motion';

const EmptyContent = ({ message = "Ainda sem informações nesta seção." }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="flex flex-col items-center justify-center p-6 bg-gray-50 rounded-lg border border-dashed border-gray-300"
    >
      <Inbox className="w-8 h-8 text-gray-400 mb-2" />
      <p className="text-sm text-gray-500 font-medium text-center">
        {message}
      </p>
    </motion.div>
  );
};

export default EmptyContent;