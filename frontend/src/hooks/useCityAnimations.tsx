
import { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export const useCityAnimations = () => {
  const cityRef = useRef<HTMLDivElement | null>(null);
  const circuitPathsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      // City initialization animation
      const cityTl = gsap.timeline({
        scrollTrigger: {
          trigger: cityRef.current,
          start: "top 80%",
          end: "bottom 20%",
          toggleActions: "play none none reverse"
        }
      });

      // Buildings rise from circuit board
      cityTl.from(".city-building", {
        y: 100,
        opacity: 0,
        scale: 0.5,
        duration: 1,
        stagger: 0.2,
        ease: "back.out(1.7)"
      })

      // Circuit pathways light up
      .from(".circuit-path", {
        scaleX: 0,
        duration: 2,
        stagger: 0.1,
        ease: "power2.out",
        transformOrigin: "left center"
      }, "-=0.5")

      // Data particles start flowing
      .fromTo(".data-particle", {
        opacity: 0,
        scale: 0
      }, {
        opacity: 1,
        scale: 1,
        duration: 0.5,
        stagger: 0.1,
        ease: "power2.out"
      }, "-=1");

      // Continuous background animations
      gsap.to(".power-indicator", {
        opacity: 0.3,
        duration: 1.5,
        repeat: -1,
        yoyo: true,
        stagger: 0.2,
        ease: "power1.inOut"
      });

      gsap.to(".data-stream", {
        x: "100%",
        duration: 3,
        repeat: -1,
        ease: "none",
        stagger: 0.5
      });

      // Data particles flowing animation
      gsap.to(".data-particle", {
        x: "+=400",
        duration: 4,
        repeat: -1,
        ease: "none",
        stagger: 0.3,
        modifiers: {
          x: gsap.utils.unitize(gsap.utils.wrap(-50, 450))
        }
      });

    }, cityRef);

    return () => ctx.revert();
  }, []);

  useEffect(() => {
    // Interactive hover effects for districts
    const districts = document.querySelectorAll('.city-district');
    districts.forEach(district => {
      const districtElement = district as HTMLElement;
      
      districtElement.addEventListener('mouseenter', () => {
        gsap.to(districtElement.querySelector('.city-building'), {
          y: -10,
          scale: 1.05,
          duration: 0.3,
          ease: "power2.out"
        });
        
        gsap.to(districtElement.querySelector('.district-glow'), {
          opacity: 1,
          scale: 1.2,
          duration: 0.3,
          ease: "power2.out"
        });

        gsap.to(districtElement.querySelector('.district-icon'), {
          rotation: 360,
          scale: 1.2,
          duration: 0.5,
          ease: "power2.out"
        });
      });
      
      districtElement.addEventListener('mouseleave', () => {
        gsap.to(districtElement.querySelector('.city-building'), {
          y: 0,
          scale: 1,
          duration: 0.3,
          ease: "power2.out"
        });
        
        gsap.to(districtElement.querySelector('.district-glow'), {
          opacity: 0.5,
          scale: 1,
          duration: 0.3,
          ease: "power2.out"
        });

        gsap.to(districtElement.querySelector('.district-icon'), {
          rotation: 0,
          scale: 1,
          duration: 0.3,
          ease: "power2.out"
        });
      });
    });
  }, []);

  return { cityRef, circuitPathsRef };
};
