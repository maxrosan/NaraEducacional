import React from 'react';
import { motion } from 'framer-motion';

export const Step = ({ children, title, icon }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5 }}
    className="bg-white p-4 sm:p-6 rounded-2xl shadow-lg border border-gray-100 mb-6"
  >
    <div className="flex items-center mb-4">
      <div className="flex items-center justify-center h-8 w-8 rounded-full bg-[#D7CDEB] text-white font-bold mr-3">{icon}</div>
      <h2 className="text-lg sm:text-xl font-bold text-gray-800">{title}</h2>
    </div>
    {children}
  </motion.div>
);