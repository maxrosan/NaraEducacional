import React from 'react';
import { motion } from 'framer-motion';
import { Camera } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import EmptyContent from '@/components/reports/EmptyContent';

const PortfolioGalleryBlock = ({ photos }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5, delay: 0.3 }}
    className="bg-white p-6 rounded-2xl shadow-md border border-gray-100"
  >
    <div className="flex items-center gap-3 mb-4">
      <div className="bg-lavanda-claro p-2 rounded-full"><Camera className="h-5 w-5 text-roxo-principal" /></div>
      <h3 className="text-lg font-bold text-texto-escuro">Portfólio</h3>
    </div>
    {photos.length === 0 ? <EmptyContent /> : (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {photos.slice(0, 4).map(photo => (
          <div key={photo.id} className="relative">
            <img src={photo.url} alt={photo.tag} className="w-full h-auto object-cover rounded-lg" />
            <Badge className="absolute bottom-2 left-2 bg-black/50 text-white border-none">{photo.tag}</Badge>
          </div>
        ))}
      </div>
    )}
  </motion.div>
);

export default PortfolioGalleryBlock;