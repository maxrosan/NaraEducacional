import React from 'react';
import { motion } from 'framer-motion';
import { Textarea } from '@/components/ui/textarea';

const ReportSection = ({ icon, title, content, onContentChange, delay }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100"
    >
      <div className="flex items-center gap-3 mb-4">
        <div className="bg-[#F5F3FA] p-2 rounded-full">
          {icon}
        </div>
        <h3 className="text-lg font-bold text-gray-800">{title}</h3>
      </div>
      <Textarea
        value={content}
        onChange={(e) => onContentChange(e.target.value)}
        className="min-h-[120px] text-base leading-relaxed"
        rows={6}
      />
    </motion.div>
  );
};

export default ReportSection;