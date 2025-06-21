
import React from 'react';
import { districts } from '../constants/cityData';

const CityStats: React.FC = () => {
  return (
    <div className="mt-12 grid grid-cols-2 md:grid-cols-5 gap-6">
      {districts.map((district) => (
        <div key={district.id} className="text-center">
          <div className={`w-12 h-12 mx-auto bg-gradient-to-r ${district.color} rounded-xl flex items-center justify-center mb-3 shadow-lg ${district.glowColor}`}>
            <district.icon className="w-6 h-6 text-white" />
          </div>
          <h3 className="text-sm font-semibold text-white mb-1">{district.name}</h3>
          <p className="text-xs text-gray-400">{district.description}</p>
        </div>
      ))}
    </div>
  );
};

export default CityStats;
