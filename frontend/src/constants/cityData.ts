
import { Shield, Zap, BarChart3, Search, Globe } from 'lucide-react';

export const districts = [
  {
    id: 'bug-detection',
    name: 'Bug Detection District',
    icon: Search,
    color: 'from-red-500 to-orange-500',
    glowColor: 'shadow-red-500/50',
    description: 'Scanning beams hunt down bugs with precision',
    position: 'top-8 left-8'
  },
  {
    id: 'security',
    name: 'Security Fortress',
    icon: Shield,
    color: 'from-blue-500 to-cyan-500',
    glowColor: 'shadow-blue-500/50',
    description: 'Protective energy barriers secure your code',
    position: 'top-8 right-8'
  },
  {
    id: 'performance',
    name: 'Performance Plaza',
    icon: Zap,
    color: 'from-yellow-500 to-orange-500',
    glowColor: 'shadow-yellow-500/50',
    description: 'Lightning-fast optimization engines',
    position: 'bottom-16 left-1/4'
  },
  {
    id: 'quality',
    name: 'Quality Control Quarter',
    icon: BarChart3,
    color: 'from-green-500 to-emerald-500',
    glowColor: 'shadow-green-500/50',
    description: 'Quality meters ensure code excellence',
    position: 'bottom-16 right-1/4'
  },
  {
    id: 'multilang',
    name: 'Multi-Language Gateway',
    icon: Globe,
    color: 'from-purple-500 to-pink-500',
    glowColor: 'shadow-purple-500/50',
    description: 'Universal language support hub',
    position: 'bottom-8 left-1/2 transform -translate-x-1/2'
  }
];
