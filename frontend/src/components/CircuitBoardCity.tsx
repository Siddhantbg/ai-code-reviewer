
import React from 'react';
import { useCityAnimations } from '../hooks/useCityAnimations';
import { districts } from '../constants/cityData';
import CircuitBackground from './CircuitBackground';
import DataStreams from './DataStreams';
import CityDistrict from './CityDistrict';
import CityStats from './CityStats';

const CircuitBoardCity: React.FC = () => {
  const { cityRef, circuitPathsRef } = useCityAnimations();

  return (
    <section id="circuit-city" className="py-20 px-6 bg-gradient-to-b from-gray-900 via-slate-800 to-gray-900 overflow-hidden">
      <div className="container mx-auto max-w-6xl">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold mb-4 bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
            Circuit Board City
          </h2>
          <p className="text-xl text-gray-300 max-w-2xl mx-auto">
            Explore our AI-powered analysis districts in this futuristic code city
          </p>
        </div>

        {/* Circuit Board City Container */}
        <div 
          ref={cityRef}
          className="relative h-96 bg-gradient-to-b from-green-900/20 to-green-800/30 rounded-2xl overflow-hidden border border-green-500/30 shadow-2xl"
          style={{
            background: `
              radial-gradient(circle at 20% 30%, rgba(34, 197, 94, 0.1) 0%, transparent 50%),
              radial-gradient(circle at 80% 70%, rgba(59, 130, 246, 0.1) 0%, transparent 50%),
              linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)
            `
          }}
        >
          {/* Circuit Board Background Pattern */}
          <CircuitBackground />

          {/* Data Streams */}
          <DataStreams circuitPathsRef={circuitPathsRef} />

          {/* City Districts */}
          {districts.map((district) => (
            <CityDistrict
              key={district.id}
              {...district}
            />
          ))}

          {/* Central AI Hub */}
          <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
            <div className="city-building w-20 h-24 bg-gradient-to-t from-indigo-600 via-purple-600 to-cyan-500 rounded-lg shadow-2xl border-2 border-white/30 backdrop-blur-sm">
              <div className="absolute inset-2 bg-white/10 rounded-lg flex items-center justify-center">
                <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center animate-pulse">
                  <div className="w-4 h-4 bg-cyan-400 rounded-full"></div>
                </div>
              </div>
              <div className="absolute -bottom-4 left-1/2 transform -translate-x-1/2 text-xs text-cyan-400 font-semibold whitespace-nowrap">
                AI Core
              </div>
            </div>
          </div>
        </div>

        {/* City Stats */}
        <CityStats />
      </div>
    </section>
  );
};

export default CircuitBoardCity;
