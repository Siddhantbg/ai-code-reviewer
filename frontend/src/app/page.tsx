"use client"
import React, { useState, useCallback, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import CodeEditor from '@/components/CodeEditor'
import AnalysisResults from '@/components/AnalysisResults'
import EnhancedResults from '@/components/EnhancedResults'
import AnalysisConfig from '@/components/AnalysisConfig'
import AnalysisProgress from '@/components/AnalysisProgress'
import EpicLoader from '@/components/EpicLoader'
import CircuitBoardCity from '@/components/CircuitBoardCity'
import { apiClient, CodeAnalysisResponse } from '@/lib/api'
import { useSocket } from '@/lib/websocket'
import { useToast } from '@/hooks/use-toast'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Loader2, Play, AlertCircle, CheckCircle, Github, Settings, X, History, ChevronRight, Keyboard, Code, Zap, BarChart3, FileText, Moon, Sun } from 'lucide-react'
import { getLanguageFromFilename } from '@/lib/utils'
import { toast } from 'react-hot-toast'

// Register GSAP plugins
gsap.registerPlugin(ScrollTrigger)

interface Rule {
  id: string
  name: string
  description: string
  category: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  enabled: boolean
  tool: string
}

interface AnalysisConfigType {
  language: string
  rules: Rule[]
  selectedTools: string[]
  severityLevels: {
    critical: boolean
    high: boolean
    medium: boolean
    low: boolean
  }
  preset: string | null
}

type AnalysisMethod = 'quick' | 'comprehensive' | 'custom'

interface AnalysisHistoryItem {
  id: string
  timestamp: string
  language: string
  filename?: string
  score: number
  issueCount: number
}

export default function HomePage() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState('python')
  const [filename, setFilename] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<CodeAnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState<boolean | null>(null)
  const [configOpen, setConfigOpen] = useState(false)
  const [analysisMethod, setAnalysisMethod] = useState<AnalysisMethod>('comprehensive')
  const [analysisConfig, setAnalysisConfig] = useState<AnalysisConfigType | null>(null)
  const [currentAnalysisId, setCurrentAnalysisId] = useState<string | null>(null)
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisHistoryItem[]>([])
  const [historyOpen, setHistoryOpen] = useState(false)
  const [useEnhancedResults, setUseEnhancedResults] = useState(true)
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [showLoader, setShowLoader] = useState(true)
  const [showMainContent, setShowMainContent] = useState(false)
  const { toast: toastHook } = useToast()
  
  // Refs for animations
  const heroRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<HTMLDivElement>(null)
  
  // WebSocket connection
  const { socket, connected: wsConnected } = useSocket()
  
  // Keyboard shortcuts reference
  const [keyboardShortcutsOpen, setKeyboardShortcutsOpen] = useState(false)

  // Initialize animations and check connection
  useEffect(() => {
    // Initial setup - hide main content until loader completes
    if (containerRef.current) {
      gsap.set(containerRef.current, { opacity: 0 })
    }
    
    const checkConnection = async () => {
      try {
        await apiClient.healthCheck()
        setIsConnected(true)
      } catch (err) {
        setIsConnected(false)
        console.error('Backend connection failed:', err)
      }
    }
    
    checkConnection()
    
    // Setup interval to periodically check connection
    const interval = setInterval(checkConnection, 30000) // Check every 30 seconds
    
    return () => clearInterval(interval)
  }, [])
  
  const handleLoaderComplete = () => {
    setShowLoader(false)
    setShowMainContent(true)
    
    // Fade in main content with ref check
    if (containerRef.current) {
      gsap.fromTo(containerRef.current, 
        { opacity: 0, y: 50 },
        { opacity: 1, y: 0, duration: 0.8, ease: "power3.out" }
      )
    }

    // Initialize main page animations after loader
    setTimeout(() => {
      initializeMainAnimations()
    }, 100)
  }

  const initializeMainAnimations = () => {
    // Hero entrance animation
    const heroTitle = document.querySelector(".hero-title")
    const heroSubtitle = document.querySelector(".hero-subtitle") 
    const heroCta = document.querySelector(".hero-cta")
    
    if (heroTitle || heroSubtitle || heroCta) {
      const heroTl = gsap.timeline()
      
      if (heroTitle) {
        heroTl.from(heroTitle, {
          duration: 1.2,
          y: 100,
          opacity: 0,
          ease: "power3.out"
        })
      }
      
      if (heroSubtitle) {
        heroTl.from(heroSubtitle, {
          duration: 0.8,
          y: 50,
          opacity: 0,
          ease: "power2.out"
        }, "-=0.6")
      }
      
      if (heroCta) {
        heroTl.from(heroCta, {
          duration: 0.6,
          scale: 0,
          opacity: 0,
          ease: "back.out(1.7)"
        }, "-=0.4")
      }
    }

    // Floating animations for background elements
    const floatingElements = document.querySelectorAll(".floating-element")
    if (floatingElements.length > 0) {
      gsap.to(floatingElements, {
        y: -20,
        duration: 3,
        repeat: -1,
        yoyo: true,
        ease: "power1.inOut",
        stagger: 0.5
      })
    }

    // Scroll animations
    const revealSections = document.querySelectorAll(".reveal-section")
    revealSections.forEach((section) => {
      gsap.from(section, {
        y: 100,
        opacity: 0,
        duration: 1,
        scrollTrigger: {
          trigger: section,
          start: "top 80%",
          end: "bottom 20%",
          toggleActions: "play none none reverse"
        }
      })
    })
  }
  
  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode)
    // Theme transition animation
    gsap.to("body", {
      duration: 0.3,
      ease: "power2.inOut"
    })
  }

  const handleAnalyze = useCallback(async () => {
    if (!code.trim()) {
      setError('Please enter some code to analyze')
      return
    }

    setIsAnalyzing(true)
    setError(null)
    setAnalysis(null)
    
    // Generate a unique analysis ID
    const analysisId = `analysis-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
    setCurrentAnalysisId(analysisId)

    try {
      // Determine severity threshold based on analysis method
      let severityThreshold = 'low'
      let analysisType = 'comprehensive'
      
      if (analysisMethod === 'quick') {
        severityThreshold = 'medium'
        analysisType = 'quick'
      } else if (analysisMethod === 'comprehensive') {
        severityThreshold = 'low'
        analysisType = 'comprehensive'
      } else if (analysisMethod === 'custom') {
        // Use custom configuration - derive severity threshold from severityLevels
        if (analysisConfig?.severityLevels) {
          if (analysisConfig.severityLevels.critical) {
            severityThreshold = 'critical'
          } else if (analysisConfig.severityLevels.high) {
            severityThreshold = 'high'
          } else if (analysisConfig.severityLevels.medium) {
            severityThreshold = 'medium'
          } else {
            severityThreshold = 'low'
          }
        } else {
          severityThreshold = 'low'
        }
        analysisType = 'custom'
      }
      
      // If using WebSockets, emit analysis request
      if (socket && wsConnected) {
        socket.emit('start_analysis', {
          analysisId,
          code,
          language,
          filename: filename || undefined,
          analysis_type: analysisType,
          include_suggestions: true,
          include_explanations: true,
          severity_threshold: severityThreshold,
          config: analysisConfig
        })
        
        // Listen for completion
        const handleComplete = (data: { analysisId: string; result: CodeAnalysisResponse }) => {
          if (data.analysisId === analysisId) {
            setAnalysis(data.result)
            setIsAnalyzing(false)
            setCurrentAnalysisId(null)
            
            // Add to history
            const historyItem: AnalysisHistoryItem = {
              id: data.result.analysis_id,
              timestamp: new Date().toISOString(),
              language,
              filename: filename || undefined,
              score: data.result.summary.overall_score,
              issueCount: data.result.summary.total_issues
            }
            
            setAnalysisHistory(prev => [historyItem, ...prev.slice(0, 9)])
            
            // Clean up listener
            socket.off('analysis_complete', handleComplete)
          }
        }
        
        socket.on('analysis_complete', handleComplete)
      } else {
        // Fallback to REST API
        const response = await apiClient.analyzeCode({
          code,
          language,
          filename: filename || undefined,
          analysis_type: analysisType,
          include_suggestions: true,
          include_explanations: true,
          severity_threshold: severityThreshold,
          config: analysisConfig
        })

        setAnalysis(response)
        
        // Add to history
        const historyItem: AnalysisHistoryItem = {
          id: response.analysis_id,
          timestamp: new Date().toISOString(),
          language,
          filename: filename || undefined,
          score: response.summary.overall_score,
          issueCount: response.summary.total_issues
        }
        
        setAnalysisHistory(prev => [historyItem, ...prev.slice(0, 9)])
        setIsAnalyzing(false)
        setCurrentAnalysisId(null)
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to analyze code. Please try again.'
      setError(errorMessage)
      console.error('Analysis failed:', err)
      setIsAnalyzing(false)
      setCurrentAnalysisId(null)
      
      toast.error('Analysis failed: ' + errorMessage)
    }
  }, [code, language, filename, analysisMethod, analysisConfig, socket, wsConnected])

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + Enter to analyze
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        if (!isAnalyzing && code.trim() && isConnected) {
          handleAnalyze()
        }
      }
      
      // Ctrl/Cmd + / to toggle config panel
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault()
        setConfigOpen(prev => !prev)
      }
      
      // Escape to close panels
      if (e.key === 'Escape') {
        if (configOpen) setConfigOpen(false)
        if (historyOpen) setHistoryOpen(false)
        if (keyboardShortcutsOpen) setKeyboardShortcutsOpen(false)
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isAnalyzing, code, isConnected, configOpen, historyOpen, keyboardShortcutsOpen, handleAnalyze])

  const handleExportReport = useCallback((format: 'json' | 'pdf' | 'csv' = 'json') => {
    if (!analysis) return

    if (format === 'json') {
      const reportData = {
        analysis,
        exportedAt: new Date().toISOString(),
        code: code.substring(0, 1000) + (code.length > 1000 ? '...' : '') // Truncate for privacy
      }

      const blob = new Blob([JSON.stringify(reportData, null, 2)], {
        type: 'application/json'
      })
      
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `code-analysis-${analysis.analysis_id}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } else if (format === 'csv') {
      // Generate CSV content
      const headers = ['ID', 'Type', 'Severity', 'Line', 'Message', 'Suggestion']
      const rows = analysis.issues.map(issue => [
        issue.id,
        issue.type,
        issue.severity,
        issue.line_number || '',
        issue.description,
        issue.suggestion || ''
      ])
      
      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
      ].join('\n')
      
      const blob = new Blob([csvContent], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `code-analysis-${analysis.analysis_id}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } else {
      toast.error('PDF export is not implemented yet')
    }
  }, [analysis, code])

  const handleCodeChange = useCallback((newCode: string) => {
    setCode(newCode)
    setError(null)
    // Clear analysis when code changes significantly
    if (analysis && Math.abs(newCode.length - code.length) > 50) {
      setAnalysis(null)
    }
  }, [code, analysis])

  const handleLanguageChange = useCallback((newLanguage: string) => {
    setLanguage(newLanguage)
    setError(null)
    setAnalysis(null)
  }, [])

  const handleFilenameChange = useCallback((newFilename: string) => {
    setFilename(newFilename)
    
    // Auto-detect language from filename
    const detectedLanguage = getLanguageFromFilename(newFilename)
    if (detectedLanguage !== language) {
      setLanguage(detectedLanguage)
    }
  }, [language])
  
  const handleConfigChange = useCallback((config: AnalysisConfigType) => {
    setAnalysisConfig(config)
    // Automatically switch to custom analysis method when config changes
    setAnalysisMethod('custom')
  }, [])
  
  const handleCancelAnalysis = useCallback(() => {
    if (socket && wsConnected && currentAnalysisId) {
      socket.emit('cancel_analysis', { analysisId: currentAnalysisId })
    }
    
    setIsAnalyzing(false)
    setCurrentAnalysisId(null)
    toast.success('Analysis cancelled')
  }, [socket, wsConnected, currentAnalysisId])
  
  const loadAnalysisFromHistory = useCallback((historyItem: AnalysisHistoryItem) => {
    // In a real app, this would fetch the analysis from the server
    toast.success(`Loading analysis ${historyItem.id}`)
    setHistoryOpen(false)
  }, [])

  if (showLoader) {
    return <EpicLoader onComplete={handleLoaderComplete} />
  }

  return (
    <div ref={containerRef} className={`main-app min-h-screen ${isDarkMode ? 'dark' : ''}`}>
      {/* Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="floating-element absolute top-20 left-10 w-32 h-32 bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-full blur-xl"></div>
        <div className="floating-element absolute top-40 right-20 w-24 h-24 bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-full blur-lg"></div>
        <div className="floating-element absolute bottom-20 left-1/4 w-40 h-40 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-full blur-2xl"></div>
      </div>

      {/* Header */}
      <header className="fixed top-0 w-full z-50 backdrop-blur-lg bg-white/80 dark:bg-gray-900/80 border-b border-gray-200/20 dark:border-gray-700/20">
        <div className="container mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
              <Code className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              AI Code Reviewer
            </span>
          </div>
          
          <nav className="hidden md:flex items-center space-x-8">
            <a href="#circuit-city" className="text-gray-600 dark:text-gray-300 hover:text-blue-600 transition-colors">Features</a>
            <a href="#editor" className="text-gray-600 dark:text-gray-300 hover:text-blue-600 transition-colors">Analyzer</a>
            
            {/* Connection Status */}
            <div className="flex items-center gap-2">
              {isConnected === null ? (
                <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
              ) : isConnected ? (
                <>
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span className="text-sm text-green-600">Connected</span>
                </>
              ) : (
                <>
                  <AlertCircle className="h-4 w-4 text-red-500" />
                  <span className="text-sm text-red-600">Disconnected</span>
                </>
              )}
            </div>
            
            {/* WebSocket Status */}
            {isConnected && (
              <div className="flex items-center gap-2">
                {wsConnected ? (
                  <>
                    <span className="flex h-2 w-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                    </span>
                    <span className="text-xs text-green-600">Live</span>
                  </>
                ) : (
                  <>
                    <span className="flex h-2 w-2 relative">
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-gray-400"></span>
                    </span>
                    <span className="text-xs text-gray-600">Standard</span>
                  </>
                )}
              </div>
            )}
            
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setKeyboardShortcutsOpen(prev => !prev)}
              className="rounded-full"
            >
              <Keyboard className="w-5 h-5" />
            </Button>
            
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              className="rounded-full"
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </Button>
            
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-500 hover:text-gray-700"
            >
              <Github className="h-5 w-5" />
            </a>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section ref={heroRef} className="relative pt-32 pb-20 px-6 text-center overflow-hidden">
        <div className="container mx-auto max-w-6xl">
          <h1 className="hero-title text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-blue-600 via-purple-600 to-cyan-600 bg-clip-text text-transparent leading-tight">
            AI-Powered Code
            <br />
            Analysis & Bug Detection
          </h1>
          <p className="hero-subtitle text-xl md:text-2xl text-gray-600 dark:text-gray-300 mb-8 max-w-3xl mx-auto leading-relaxed">
            Detect bugs, security vulnerabilities, and performance issues in your code with advanced AI analysis. 
            Get instant feedback and improve your code quality.
          </p>
          <div className="hero-cta flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button 
              size="lg" 
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-8 py-4 text-lg rounded-xl shadow-lg hover:shadow-xl transition-all duration-300"
              onClick={() => document.getElementById('editor')?.scrollIntoView({ behavior: 'smooth' })}
            >
              <Play className="w-5 h-5 mr-2" />
              Try It Now
            </Button>
            <Button 
              variant="outline" 
              size="lg" 
              className="px-8 py-4 text-lg rounded-xl border-2 hover:bg-gray-50 dark:hover:bg-gray-800 transition-all duration-300"
              onClick={() => document.getElementById('circuit-city')?.scrollIntoView({ behavior: 'smooth' })}
            >
              Explore Features
            </Button>
          </div>
        </div>
      </section>

      {/* Circuit Board City Features Section */}
      <CircuitBoardCity />

      {/* Editor Section */}
      <section id="editor" ref={editorRef} className="reveal-section py-20 px-6">
        <div className="container mx-auto max-w-7xl">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Code Analysis Studio
            </h2>
            <p className="text-xl text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
              Paste your code below and get instant AI-powered analysis with detailed feedback
            </p>
          </div>

          <div className="grid lg:grid-cols-2 gap-8">
            {/* Code Editor */}
            <Card className="editor-container border-0 bg-white/70 dark:bg-gray-800/70 backdrop-blur-sm shadow-2xl">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Code className="w-5 h-5" />
                    Code Editor
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setConfigOpen(prev => !prev)}
                      className="flex items-center gap-2"
                    >
                      <Settings className="h-4 w-4" />
                      Config
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setHistoryOpen(prev => !prev)}
                      className="flex items-center gap-2"
                    >
                      <History className="h-4 w-4" />
                      History
                    </Button>
                  </div>
                </div>
                
                {/* Analysis Method Tabs */}
                <Tabs value={analysisMethod} onValueChange={(value) => setAnalysisMethod(value as AnalysisMethod)} className="w-full">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="quick">Quick</TabsTrigger>
                    <TabsTrigger value="comprehensive">Comprehensive</TabsTrigger>
                    <TabsTrigger value="custom">Custom</TabsTrigger>
                  </TabsList>
                </Tabs>
              </CardHeader>
              <CardContent className="p-0">
                {/* Configuration Panel */}
                {configOpen && (
                  <div className="p-6 border-t bg-gray-50/50 dark:bg-gray-700/50">
                    <AnalysisConfig
                      language={language}
                      onConfigChange={handleConfigChange}
                      defaultConfig={analysisConfig || undefined}
                    />
                  </div>
                )}
                
                {/* History Panel */}
                {historyOpen && (
                  <div className="p-6 border-t bg-gray-50/50 dark:bg-gray-700/50">
                    <div className="space-y-2">
                      <h4 className="font-medium mb-3">Analysis History</h4>
                      {analysisHistory.length > 0 ? (
                        <div className="space-y-2">
                          {analysisHistory.map((item) => (
                            <div 
                              key={item.id}
                              className="flex items-center justify-between p-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded cursor-pointer"
                              onClick={() => loadAnalysisFromHistory(item)}
                            >
                              <div>
                                <div className="font-medium">{item.filename || 'Untitled'}</div>
                                <div className="text-xs text-gray-500">
                                  {new Date(item.timestamp).toLocaleString()} • {item.language}
                                </div>
                              </div>
                              <div className="flex items-center gap-4">
                                <div className="text-sm">
                                  Score: <span className="font-medium">{item.score.toFixed(1)}</span>
                                </div>
                                <div className="text-sm">
                                  Issues: <span className="font-medium">{item.issueCount}</span>
                                </div>
                                <ChevronRight className="h-4 w-4 text-gray-400" />
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-4 text-gray-500">
                          No analysis history yet
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                <CodeEditor
                  code={code}
                  language={language}
                  filename={filename}
                  onChange={handleCodeChange}
                  onLanguageChange={handleLanguageChange}
                  onFilenameChange={handleFilenameChange}
                  disabled={isAnalyzing}
                />
                
                <div className="p-6 border-t bg-gray-50/50 dark:bg-gray-700/50">
                  <Button 
                    onClick={handleAnalyze}
                    disabled={isAnalyzing || !code.trim() || !isConnected}
                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white py-3 rounded-lg shadow-lg hover:shadow-xl transition-all duration-300"
                  >
                    {isAnalyzing ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Analyzing Code...
                      </>
                    ) : (
                      <>
                        <Zap className="w-4 h-4 mr-2" />
                        Analyze Code
                      </>
                    )}
                  </Button>
                  
                  {!isConnected && (
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded mt-3">
                      ⚠️ Backend is not connected. Please make sure the FastAPI server is running on port 8000.
                    </div>
                  )}
                  
                  {error && (
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded mt-3">
                      {error}
                    </div>
                  )}
                  
                  <div className="flex items-center justify-between mt-4">
                    <div className="text-xs text-gray-500">
                      <p>• Supports Python, JavaScript, TypeScript, Java, C++</p>
                      <p>• Detects bugs, security issues, and style problems</p>
                      <p>• Provides suggestions and explanations</p>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">Enhanced Results</span>
                      <button
                        onClick={() => setUseEnhancedResults(prev => !prev)}
                        className={`relative inline-flex h-5 w-10 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${useEnhancedResults ? 'bg-blue-600' : 'bg-gray-200'}`}
                      >
                        <span
                          className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${useEnhancedResults ? 'translate-x-5' : 'translate-x-0'}`}
                        />
                      </button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Results */}
            <Card className="results-container border-0 bg-white/70 dark:bg-gray-800/70 backdrop-blur-sm shadow-2xl">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Analysis Results
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isAnalyzing && currentAnalysisId ? (
                  <AnalysisProgress
                    analysisId={currentAnalysisId}
                    language={language}
                    codeSize={code.split('\n').length}
                    onCancel={handleCancelAnalysis}
                    onComplete={() => {
                      // This is handled by the WebSocket event listener
                    }}
                  />
                ) : analysis ? (
                  useEnhancedResults ? (
                    <EnhancedResults
                      analysis={analysis}
                      onExport={handleExportReport}
                    />
                  ) : (
                    <AnalysisResults
                      analysis={analysis}
                      onExport={handleExportReport}
                    />
                  )
                ) : (
                  <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                    <BarChart3 className="w-16 h-16 mx-auto mb-4 opacity-50" />
                    <p className="text-lg">Run analysis to see results here</p>
                    <p className="text-sm mt-2">Upload code or paste it in the editor to get started</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Keyboard Shortcuts Modal */}
      {keyboardShortcutsOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-md">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle>Keyboard Shortcuts</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setKeyboardShortcutsOpen(false)}
                  className="h-8 w-8 p-0"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-2 text-sm">
                <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                  <span>Analyze Code</span>
                  <kbd className="px-2 py-1 bg-gray-200 rounded text-xs">Ctrl+Enter</kbd>
                </div>
                <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                  <span>Toggle Configuration</span>
                  <kbd className="px-2 py-1 bg-gray-200 rounded text-xs">Ctrl+/</kbd>
                </div>
                <div className="flex items-center justify-between p-2 bg-gray-50 rounded">
                  <span>Close Panels</span>
                  <kbd className="px-2 py-1 bg-gray-200 rounded text-xs">Esc</kbd>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}