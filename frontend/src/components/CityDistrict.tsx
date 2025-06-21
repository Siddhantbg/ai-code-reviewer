
import React from 'react';
import { LucideIcon } from 'lucide-react';

interface CityDistrictProps {
  id: string;
  name: string;
  icon: LucideIcon;
  color: string;
  glowColor: string;
  description: string;
  position: string;
}

const CityDistrict: React.FC<CityDistrictProps> = ({
  id,
  name,
  icon: IconComponent,
  color,
  glowColor,
  description,
  position
}) => {
  return (
    <div
      className={`city-district absolute ${position} cursor-pointer group`}
    >
      {/* District Glow */}
      <div className={`district-glow absolute inset-0 bg-gradient-to-r ${color} rounded-lg blur-lg opacity-50 scale-75 ${glowColor}`}></div>
      
      {/* City Building */}
      <div className={`city-building relative w-16 h-20 bg-gradient-to-t ${color} rounded-t-lg shadow-xl border border-white/20 backdrop-blur-sm`}>
        {/* Building Details */}
        <div className="absolute inset-x-0 top-2 flex justify-center">
          <div className={`district-icon w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center backdrop-blur-sm`}>
            <IconComponent className="w-4 h-4 text-white" />
          </div>
        </div>
        
        {/* Windows */}
        <div className="absolute bottom-2 left-1 w-2 h-2 bg-yellow-300 rounded-sm power-indicator"></div>
        <div className="absolute bottom-2 right-1 w-2 h-2 bg-blue-300 rounded-sm power-indicator"></div>
        <div className="absolute bottom-5 left-1 w-2 h-2 bg-green-300 rounded-sm power-indicator"></div>
        <div className="absolute bottom-5 right-1 w-2 h-2 bg-purple-300 rounded-sm power-indicator"></div>
      </div>

      {/* Tooltip */}
      <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-black/80 text-white px-3 py-1 rounded-lg text-sm whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-300 backdrop-blur-sm border border-white/20">
        <div className="font-semibold">{name}</div>
        <div className="text-xs text-gray-300">{description}</div>
        <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-black/80"></div>
      </div>
    </div>
  );
};

export default CityDistrict;
