"use client"

import React, { useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import CodeEditor from '@/components/CodeEditor'
import AnalysisResults from '@/components/AnalysisResults'
import { apiClient, CodeAnalysisResponse } from '@/lib/api'
import { Loader2, Play, AlertCircle, CheckCircle, Github, Code2 } from 'lucide-react'
import { getLanguageFromFilename } from '@/lib/utils'

export default function HomePage() {
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState('python')
  const [filename, setFilename] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState<CodeAnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState<boolean | null>(null)

  // Check backend connection on component mount
  React.useEffect(() => {
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
  }, [])

  const handleAnalyze = useCallback(async () => {
    if (!code.trim()) {
      setError('Please enter some code to analyze')
      return
    }

    setIsAnalyzing(true)
    setError(null)
    setAnalysis(null)

    try {
      const response = await apiClient.analyzeCode({
        code,
        language,
        filename: filename || undefined,
        analysis_type: 'comprehensive',
        include_suggestions: true,
        include_explanations: true,
        severity_threshold: 'low'
      })

      setAnalysis(response)
    } catch (err: any) {
      setError(err.message || 'Failed to analyze code. Please try again.')
      console.error('Analysis failed:', err)
    } finally {
      setIsAnalyzing(false)
    }
  }, [code, language, filename])

  const handleExportReport = useCallback(() => {
    if (!analysis) return

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

  return (
    <div className="min-h-screen bg-gray-50">
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
                  Powered by AI • Sprint 1
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
          <div className="space-y-6">
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
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
                      ⚠️ Backend is not connected. Please make sure the FastAPI server is running on port 8000.
                    </div>
                  )}
                  
                  {error && (
                    <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
                      {error}
                    </div>
                  )}
                  
                  <div className="text-xs text-gray-500">
                    <p>• Supports Python, JavaScript, TypeScript, Java, C++</p>
                    <p>• Detects bugs, security issues, and style problems</p>
                    <p>• Provides suggestions and explanations</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Analysis Results */}
          <div className="space-y-6">
            {analysis ? (
              <AnalysisResults
                analysis={analysis}
                onExport={handleExportReport}
              />
            ) : (
              <Card className="h-96 flex items-center justify-center">
                <CardContent>
                  <div className="text-center text-gray-500">
                    <Code2 className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                    <h3 className="text-lg font-medium mb-2">No Analysis Yet</h3>
                    <p className="text-sm">
                      Enter your code in the editor and click "Analyze Code" to get started.
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
              AI Code Reviewer - Sprint 1 • Built with Next.js, FastAPI, and AI
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
