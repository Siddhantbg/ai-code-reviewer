"use client"
import React, { useState, useCallback, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import CodeEditor from '@/components/CodeEditor'
import AnalysisResults from '@/components/AnalysisResults'
import EnhancedResults from '@/components/EnhancedResults'
import AnalysisConfig from '@/components/AnalysisConfig'
import AnalysisProgress from '@/components/AnalysisProgress'
import { apiClient, CodeAnalysisResponse } from '@/lib/api'
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
import { useSocket } from '@/lib/websocket'
import { Loader2, Play, AlertCircle, CheckCircle, Github, Code2, Settings, X, History, ChevronRight, Keyboard } from 'lucide-react'
import { getLanguageFromFilename } from '@/lib/utils'
import { toast } from 'react-hot-toast'

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
  const containerRef = useRef<HTMLDivElement>(null);
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
  
  // WebSocket connection
  const { socket, connected: wsConnected } = useSocket()
  
  // Keyboard shortcuts reference
  const [keyboardShortcutsOpen, setKeyboardShortcutsOpen] = useState(false)
  
  // Refs for keyboard shortcuts
  const editorRef = useRef<HTMLDivElement>(null)

  // Check backend connection on component mount
  useEffect(() => {
<<<<<<< Updated upstream
=======
    // Initial setup - hide main content until loader completes
    if (containerRef.current) {
      gsap.set(containerRef.current, { opacity: 0 })
    }
    
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======
  
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
>>>>>>> Stashed changes

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

  return (
<<<<<<< Updated upstream
    <div className="min-h-screen bg-gray-50">
=======
    <div ref={containerRef} className={`main-app min-h-screen ${isDarkMode ? 'dark' : ''}`}>
      {/* Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="floating-element absolute top-20 left-10 w-32 h-32 bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-full blur-xl"></div>
        <div className="floating-element absolute top-40 right-20 w-24 h-24 bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-full blur-lg"></div>
        <div className="floating-element absolute bottom-20 left-1/4 w-40 h-40 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-full blur-2xl"></div>
      </div>

>>>>>>> Stashed changes
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-600 rounded-lg">
                <Code2 className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  AI Code Reviewer
                </h1>
                <p className="text-sm text-gray-500">
                  Powered by AI • Sprint 2
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
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
              
              {/* Keyboard Shortcuts Button */}
              <button 
                onClick={() => setKeyboardShortcutsOpen(prev => !prev)}
                className="text-gray-500 hover:text-gray-700"
              >
                <Keyboard className="h-5 w-5" />
              </button>
              
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-gray-700"
              >
                <Github className="h-5 w-5" />
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column - Code Editor */}
          <div className="space-y-6" ref={editorRef}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfigOpen(prev => !prev)}
                  className="flex items-center gap-2"
                >
                  <Settings className="h-4 w-4" />
                  {configOpen ? 'Hide Configuration' : 'Show Configuration'}
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
              
              <div className="flex items-center gap-2">
                <Button
                  variant={analysisMethod === 'quick' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setAnalysisMethod('quick')}
                >
                  Quick
                </Button>
                <Button
                  variant={analysisMethod === 'comprehensive' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setAnalysisMethod('comprehensive')}
                >
                  Comprehensive
                </Button>
                <Button
                  variant={analysisMethod === 'custom' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setAnalysisMethod('custom')
                    if (!configOpen) setConfigOpen(true)
                  }}
                >
                  Custom
                </Button>
              </div>
            </div>
            
            {/* Configuration Panel */}
            {configOpen && (
              <Card className="border-blue-100">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle>Analysis Configuration</CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setConfigOpen(false)}
                      className="h-8 w-8 p-0"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <AnalysisConfig
                    language={language}
                    onConfigChange={handleConfigChange}
                    defaultConfig={analysisConfig}
                  />
                </CardContent>
              </Card>
            )}
            
            {/* History Panel */}
            {historyOpen && (
              <Card className="border-blue-100">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle>Analysis History</CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setHistoryOpen(false)}
                      className="h-8 w-8 p-0"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {analysisHistory.length > 0 ? (
                    <div className="space-y-2">
                      {analysisHistory.map((item) => (
                        <div 
                          key={item.id}
                          className="flex items-center justify-between p-2 hover:bg-gray-50 rounded cursor-pointer"
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
                </CardContent>
              </Card>
            )}
            
            {/* Keyboard Shortcuts Panel */}
            {keyboardShortcutsOpen && (
              <Card className="border-blue-100">
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
                  <div className="grid grid-cols-2 gap-2 text-sm">
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
            
            {/* Analysis Controls */}
            <Card>
              <CardHeader>
                <CardTitle>Analysis Controls</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <Button
                    onClick={handleAnalyze}
                    disabled={isAnalyzing || !code.trim() || !isConnected}
                    className="w-full"
                    size="lg"
                  >
                    {isAnalyzing ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Analyzing Code...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-2" />
                        Analyze Code
                      </>
                    )}
                  </Button>
                  
                  {!isConnected && (
<<<<<<< Updated upstream
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
                      ⚠️ Backend is not connected. Please make sure the FastAPI server is running on port 5000.
=======
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded mt-3">
                      ⚠️ Backend is not connected. Please make sure the FastAPI server is running on port 8000.
>>>>>>> Stashed changes
                    </div>
                  )}
                  
                  {error && (
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
                      {error}
                    </div>
                  )}
                  
                  <div className="flex items-center justify-between">
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
          </div>

          {/* Right Column - Analysis Results */}
          <div className="space-y-6">
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
              <Card className="h-96 flex items-center justify-center">
                <CardContent>
                  <div className="text-center text-gray-500">
                    <Code2 className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                    <h3 className="text-lg font-medium mb-2">No Analysis Yet</h3>
                    <p className="text-sm">
                      Enter your code in the editor and click &quot;Analyze Code&quot; to get started.
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-gray-500">
            <p className="text-sm">
              AI Code Reviewer - Sprint 2 • Built with Next.js, FastAPI, and AI
            </p>
            <p className="text-xs mt-2">
              This is a development version. Analysis results are for demonstration purposes.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}