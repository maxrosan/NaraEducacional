import React from 'react';
import { cn } from '@/lib/utils';

const NaraIaIcon = ({ className, isLogo = false }) => {
  const imageSrc = "/nara-logo.png";

  if (isLogo) {
    return <img-replace src={imageSrc} alt="Nara AI Logo" className={cn("h-12 w-auto sm:h-14", className)} />;
  }
  
  return <img-replace src={imageSrc} alt="Nara AI Icon" className={cn("h-5 w-5", className)} />;
};

export default NaraIaIcon;
