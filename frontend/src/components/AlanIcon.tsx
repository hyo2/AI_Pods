// src/components/AlanIcon.tsx
import React from 'react';

interface AlanIconProps {
  className?: string;
  width?: number;
  height?: number;
}

const AlanIcon: React.FC<AlanIconProps> = ({ 
  className = '', 
  width = 15, 
  height = 20 
}) => {
  return (
    <svg 
      width={width} 
      height={height} 
      viewBox="0 0 23 20" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
      role="presentation"
      className={className}
    >
      <path 
        d="M23.0946 19.5984H18.8098L16.8157 15.743H6.19808L4.25781 19.5984H0L9.70035 0.910309H13.1777L23.0946 19.5984ZM11.453 5.38153L7.70718 12.7711H15.2796L11.453 5.38153Z" 
        fill="currentColor"
      />
    </svg>
  );
};

export default AlanIcon;