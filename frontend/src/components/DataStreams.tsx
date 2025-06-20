
import React from 'react';

interface DataStreamsProps {
  circuitPathsRef: React.RefObject<HTMLDivElement | null>;
}

const DataStreams: React.FC<DataStreamsProps> = ({ circuitPathsRef }) => {
  return (
    <div ref={circuitPathsRef} className="absolute inset-0">
      {[...Array(8)].map((_, i) => (
        <div 
          key={i}
          className="data-stream absolute w-2 h-2 bg-cyan-400 rounded-full opacity-70"
          style={{
            top: `${20 + i * 10}%`,
            left: '-8px',
            animationDelay: `${i * 0.5}s`
          }}
        />
      ))}
      
      {[...Array(6)].map((_, i) => (
        <div 
          key={i}
          className="data-particle absolute w-1 h-1 bg-yellow-400 rounded-full"
          style={{
            left: `${10 + i * 15}%`,
            top: '25%',
            animationDelay: `${i * 0.3}s`
          }}
        />
      ))}
    </div>
  );
};

export default DataStreams;
