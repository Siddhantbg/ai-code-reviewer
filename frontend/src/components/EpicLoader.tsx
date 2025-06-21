
import React, { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { TextPlugin } from 'gsap/TextPlugin';
import { Code } from 'lucide-react';

gsap.registerPlugin(TextPlugin);

interface EpicLoaderProps {
  onComplete: () => void;
}

const EpicLoader: React.FC<EpicLoaderProps> = ({ onComplete }) => {
  const loaderRef = useRef<HTMLDivElement>(null);
  const logoRef = useRef<HTMLDivElement>(null);
  const progressFillRef = useRef<HTMLDivElement>(null);
  const progressPercentRef = useRef<HTMLDivElement>(null);
  const loadingTextRef = useRef<HTMLDivElement>(null);
  const particlesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const epicLoader = gsap.timeline({
      onComplete: () => {
        setTimeout(onComplete, 500);
      }
    });

    // Stage 1: Logo reveal with morphing (1s)
    epicLoader.from(logoRef.current, {
      scale: 0,
      rotation: 180,
      opacity: 0,
      duration: 1,
      ease: "back.out(1.7)"
    })

    // Stage 2: Progress bar with physics (2s) and percentage counter
    .fromTo(progressFillRef.current, 
      { width: "0%" },
      { 
        width: "100%", 
        duration: 2, 
        ease: "power2.out",
        onUpdate: function() {
          const progress = Math.round(this.progress() * 100);
          if (progressPercentRef.current) {
            progressPercentRef.current.textContent = `${progress}%`;
          }
        }
      }
    )

    // Loading text typewriter effect
    .to(loadingTextRef.current, {
      duration: 2,
      text: "Initializing AI Analysis Engine...",
      ease: "none"
    }, "-=2")

    // Stage 3: Particle explosion transition (1s)
    .to(particlesRef.current?.children || [], {
      scale: 3,
      opacity: 0,
      rotation: 360,
      duration: 0.8,
      ease: "power3.out",
      stagger: 0.1
    })

    // Stage 4: Smooth transition to main content
    .to(loaderRef.current, {
      y: "-100vh",
      duration: 1,
      ease: "power3.inOut"
    }, "-=0.3");

    // Floating particles animation
    gsap.to(particlesRef.current?.children || [], {
      y: -20,
      duration: 2,
      repeat: -1,
      yoyo: true,
      ease: "power1.inOut",
      stagger: 0.3
    });

    return () => {
      epicLoader.kill();
    };
  }, [onComplete]);

  return (
    <div 
      ref={loaderRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900 overflow-hidden"
    >
      {/* Animated code pattern background */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute top-10 left-10 text-green-400 font-mono text-sm animate-pulse">
          {`function analyzeCode() {`}
        </div>
        <div className="absolute top-20 right-20 text-blue-400 font-mono text-sm animate-pulse delay-500">
          {`const bugs = detector.scan();`}
        </div>
        <div className="absolute bottom-32 left-1/4 text-purple-400 font-mono text-sm animate-pulse delay-1000">
          {`return results.optimize();`}
        </div>
        <div className="absolute bottom-20 right-1/3 text-cyan-400 font-mono text-sm animate-pulse delay-1500">
          {`} // AI Analysis Complete`}
        </div>
      </div>

      <div className="loader-container text-center">
        {/* App Logo */}
        <div ref={logoRef} className="mb-8">
          <div className="w-24 h-24 mx-auto bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl flex items-center justify-center shadow-2xl">
            <Code className="w-12 h-12 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white mt-4 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            AI Code Reviewer
          </h1>
        </div>

        {/* Progress Container */}
        <div className="progress-container mb-6 w-80 mx-auto">
          <div className="progress-bar relative h-2 bg-gray-700 rounded-full overflow-hidden shadow-inner">
            <div 
              ref={progressFillRef}
              className="progress-bar-fill h-full bg-gradient-to-r from-blue-500 via-purple-500 to-cyan-500 rounded-full shadow-lg"
              style={{ width: '0%' }}
            />
          </div>
          <div 
            ref={progressPercentRef}
            className="progress-percentage text-white text-lg font-semibold mt-3"
          >
            0%
          </div>
        </div>

        {/* Loading Text */}
        <div 
          ref={loadingTextRef}
          className="loading-text text-gray-300 text-lg mb-8 min-h-[1.5rem]"
        />

        {/* Loader Particles */}
        <div ref={particlesRef} className="loader-particles flex justify-center space-x-4 text-2xl">
          <span className="text-yellow-400 font-mono">{`{`}</span>
          <span className="text-green-400 font-mono">{`}`}</span>
          <span className="text-blue-400 font-mono">[</span>
          <span className="text-purple-400 font-mono">]</span>
          <span className="text-cyan-400 font-mono">;</span>
        </div>
      </div>
    </div>
  );
};

export default EpicLoader;
