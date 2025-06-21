
import React from 'react';

const CircuitBackground: React.FC = () => {
  return (
    <div className="absolute inset-0 opacity-30">
      {/* Horizontal circuit traces */}
      <div className="circuit-path absolute top-1/4 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-green-400 to-transparent"></div>
      <div className="circuit-path absolute top-1/2 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-blue-400 to-transparent"></div>
      <div className="circuit-path absolute top-3/4 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-purple-400 to-transparent"></div>
      
      {/* Vertical circuit traces */}
      <div className="circuit-path absolute left-1/4 top-0 w-0.5 h-full bg-gradient-to-b from-transparent via-cyan-400 to-transparent"></div>
      <div className="circuit-path absolute left-1/2 top-0 w-0.5 h-full bg-gradient-to-b from-transparent via-yellow-400 to-transparent"></div>
      <div className="circuit-path absolute left-3/4 top-0 w-0.5 h-full bg-gradient-to-b from-transparent via-pink-400 to-transparent"></div>
    </div>
  );
};

export default CircuitBackground;
