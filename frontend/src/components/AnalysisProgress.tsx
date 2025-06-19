"use client"

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { XCircle, Clock, AlertCircle, CheckCircle, Loader2 } from 'lucide-react'
import { useSocket } from '@/lib/websocket'

interface AnalysisProgressProps {
  analysisId: string
  language: string
  codeSize: number
  onCancel: () => void
  onComplete: (analysisId: string) => void
}

interface ToolProgress {
  tool: string
  status: 'pending' | 'running' | 'completed' | 'error'
  progress: number
  message?: string
  timeElapsed?: number
  timeRemaining?: number
}

interface AnalysisProgressState {
  status: 'initializing' | 'analyzing' | 'completed' | 'error'
  overallProgress: number
  startTime: number
  endTime?: number
  estimatedTimeRemaining?: number
  message?: string
  error?: string
  tools: ToolProgress[]
}

const TOOL_NAMES: Record<string, string> = {
  'eslint': 'ESLint',
  'pylint': 'Pylint',
  'bandit': 'Bandit',
  'jshint': 'JSHint',
  'flake8': 'Flake8',
  'rubocop': 'RuboCop',
  'phpcs': 'PHP_CodeSniffer',
  'checkstyle': 'Checkstyle',
  'stylelint': 'Stylelint',
  'shellcheck': 'ShellCheck',
  'golint': 'Golint',
  'tslint': 'TSLint',
}

const getToolDisplayName = (toolId: string): string => {
  return TOOL_NAMES[toolId.toLowerCase()] || toolId
}

const formatTime = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}m ${remainingSeconds}s`
}

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'completed': return 'text-green-600'
    case 'running': return 'text-blue-600'
    case 'pending': return 'text-gray-400'
    case 'error': return 'text-red-600'
    default: return 'text-gray-600'
  }
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className="h-4 w-4 text-green-600" />
    case 'running':
      return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
    case 'pending':
      return <Clock className="h-4 w-4 text-gray-400" />
    case 'error':
      return <XCircle className="h-4 w-4 text-red-600" />
    default:
      return <AlertCircle className="h-4 w-4 text-gray-600" />
  }
}

export default function AnalysisProgress({
  analysisId,
  language,
  codeSize,
  onCancel,
  onComplete
}: AnalysisProgressProps) {
  const [progress, setProgress] = useState<AnalysisProgressState>({
    status: 'initializing',
    overallProgress: 0,
    startTime: Date.now(),
    tools: []
  })

  const { socket, connected } = useSocket()

  // Calculate estimated time based on code size and language
  const getInitialEstimate = (): number => {
    // Base time in milliseconds
    const baseTime = 2000
    
    // Factor based on code size (lines or characters)
    const sizeFactor = Math.log(codeSize + 1) * 500
    
    // Language complexity factor
    const languageFactors: Record<string, number> = {
      'javascript': 1.2,
      'typescript': 1.3,
      'python': 1.0,
      'java': 1.5,
      'csharp': 1.4,
      'php': 1.1,
      'ruby': 1.0,
      'go': 0.9,
      'rust': 1.6,
      'c': 1.3,
      'cpp': 1.4
    }
    
    const langFactor = languageFactors[language.toLowerCase()] || 1.0
    
    return baseTime + (sizeFactor * langFactor)
  }

  useEffect(() => {
    if (!socket || !connected) return

    // Initialize with default tools based on language
    const initializeTools = () => {
      const defaultTools: ToolProgress[] = []
      
      // Add language-specific tools
      if (['javascript', 'typescript'].includes(language.toLowerCase())) {
        defaultTools.push(
          { tool: 'eslint', status: 'pending', progress: 0 },
          { tool: 'jshint', status: 'pending', progress: 0 }
        )
      } else if (language.toLowerCase() === 'python') {
        defaultTools.push(
          { tool: 'pylint', status: 'pending', progress: 0 },
          { tool: 'flake8', status: 'pending', progress: 0 },
          { tool: 'bandit', status: 'pending', progress: 0 }
        )
      } else if (language.toLowerCase() === 'java') {
        defaultTools.push(
          { tool: 'checkstyle', status: 'pending', progress: 0 }
        )
      } else if (language.toLowerCase() === 'ruby') {
        defaultTools.push(
          { tool: 'rubocop', status: 'pending', progress: 0 }
        )
      } else if (language.toLowerCase() === 'php') {
        defaultTools.push(
          { tool: 'phpcs', status: 'pending', progress: 0 }
        )
      } else if (language.toLowerCase() === 'go') {
        defaultTools.push(
          { tool: 'golint', status: 'pending', progress: 0 }
        )
      }
      
      // Add common tools for all languages
      defaultTools.push({ tool: 'common-analysis', status: 'pending', progress: 0 })
      
      setProgress(prev => ({
        ...prev,
        tools: defaultTools,
        estimatedTimeRemaining: getInitialEstimate()
      }))
    }

    initializeTools()

    // Listen for progress updates
    socket.on('analysis_progress', (data: any) => {
      if (data.analysisId !== analysisId) return

      setProgress(prev => {
        // Update the specific tool's progress
        const updatedTools = prev.tools.map(tool => {
          if (tool.tool === data.tool) {
            return {
              ...tool,
              status: data.status,
              progress: data.progress,
              message: data.message,
              timeElapsed: data.timeElapsed
            }
          }
          return tool
        })

        // Calculate overall progress as average of all tools
        const completedTools = updatedTools.filter(t => t.status === 'completed').length
        const totalTools = updatedTools.length
        const toolProgressSum = updatedTools.reduce((sum, tool) => sum + tool.progress, 0)
        const overallProgress = Math.min(
          99, // Cap at 99% until fully complete
          Math.round((toolProgressSum / totalTools) + (completedTools / totalTools * 10))
        )

        // Calculate estimated time remaining
        const elapsedTime = Date.now() - prev.startTime
        let estimatedTimeRemaining

        if (overallProgress > 0) {
          estimatedTimeRemaining = Math.max(
            1000, // At least 1 second
            Math.round((elapsedTime / overallProgress) * (100 - overallProgress))
          )
        }

        return {
          ...prev,
          status: data.overallStatus || prev.status,
          overallProgress,
          estimatedTimeRemaining,
          message: data.message,
          tools: updatedTools
        }
      })
    })

    // Listen for analysis completion
    socket.on('analysis_complete', (data: any) => {
      if (data.analysisId !== analysisId) return

      setProgress(prev => ({
        ...prev,
        status: 'completed',
        overallProgress: 100,
        endTime: Date.now(),
        estimatedTimeRemaining: 0,
        tools: prev.tools.map(tool => ({ ...tool, status: 'completed', progress: 100 }))
      }))

      // Notify parent component
      onComplete(analysisId)
    })

    // Listen for analysis errors
    socket.on('analysis_error', (data: any) => {
      if (data.analysisId !== analysisId) return

      setProgress(prev => ({
        ...prev,
        status: 'error',
        error: data.error,
        endTime: Date.now()
      }))
    })

    // Simulate progress for demo purposes
    // In a real app, this would be removed and rely on actual WebSocket events
    const simulateProgress = () => {
      let currentTool = 0
      const toolCount = progress.tools.length
      
      const interval = setInterval(() => {
        setProgress(prev => {
          if (prev.status === 'completed' || prev.status === 'error') {
            clearInterval(interval)
            return prev
          }
          
          const updatedTools = [...prev.tools]
          
          // Update current tool
          if (currentTool < toolCount) {
            const tool = updatedTools[currentTool]
            
            if (tool.progress < 100) {
              // Increment progress
              const increment = Math.floor(Math.random() * 10) + 1
              const newProgress = Math.min(100, tool.progress + increment)
              
              updatedTools[currentTool] = {
                ...tool,
                status: newProgress < 100 ? 'running' : 'completed',
                progress: newProgress,
                message: newProgress < 100 ? 'Analyzing code...' : 'Analysis complete'
              }
            } else {
              // Move to next tool
              currentTool++
              
              if (currentTool < toolCount) {
                updatedTools[currentTool] = {
                  ...updatedTools[currentTool],
                  status: 'running',
                  progress: 5,
                  message: 'Starting analysis...'
                }
              }
            }
          }
          
          // Calculate overall progress
          const toolProgressSum = updatedTools.reduce((sum, tool) => sum + tool.progress, 0)
          const overallProgress = Math.min(
            99,
            Math.round(toolProgressSum / toolCount)
          )
          
          // Check if all tools are complete
          const allComplete = updatedTools.every(tool => tool.progress === 100)
          
          if (allComplete) {
            clearInterval(interval)
            
            // Simulate a slight delay before marking as complete
            setTimeout(() => {
              setProgress(p => ({
                ...p,
                status: 'completed',
                overallProgress: 100,
                endTime: Date.now(),
                estimatedTimeRemaining: 0
              }))
              
              onComplete(analysisId)
            }, 500)
            
            return {
              ...prev,
              overallProgress,
              tools: updatedTools
            }
          }
          
          // Calculate estimated time remaining
          const elapsedTime = Date.now() - prev.startTime
          let estimatedTimeRemaining
          
          if (overallProgress > 0) {
            estimatedTimeRemaining = Math.round((elapsedTime / overallProgress) * (100 - overallProgress))
          }
          
          return {
            ...prev,
            status: 'analyzing',
            overallProgress,
            estimatedTimeRemaining,
            tools: updatedTools
          }
        })
      }, 300)
      
      return () => clearInterval(interval)
    }
    
    // Start simulation
    const cleanup = simulateProgress()
    
    // Cleanup function
    return () => {
      socket.off('analysis_progress')
      socket.off('analysis_complete')
      socket.off('analysis_error')
      cleanup()
    }
  }, [socket, connected, analysisId, language, codeSize, onComplete])

  const handleCancel = () => {
    // Send cancel event to server
    if (socket && connected) {
      socket.emit('cancel_analysis', { analysisId })
    }
    
    onCancel()
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Analysis Progress</CardTitle>
          <Button variant="outline" size="sm" onClick={handleCancel}>
            Cancel
          </Button>
        </div>
      </CardHeader>
      
      <CardContent>
        {/* Overall Progress */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {getStatusIcon(progress.status)}
              <span className="font-medium">
                {progress.status === 'initializing' && 'Initializing Analysis...'}
                {progress.status === 'analyzing' && 'Analyzing Code...'}
                {progress.status === 'completed' && 'Analysis Complete'}
                {progress.status === 'error' && 'Analysis Failed'}
              </span>
            </div>
            <span className="text-sm font-medium">{progress.overallProgress}%</span>
          </div>
          
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div 
              className={`h-2.5 rounded-full ${progress.status === 'error' ? 'bg-red-600' : 'bg-blue-600'}`}
              style={{ width: `${progress.overallProgress}%` }}
            ></div>
          </div>
          
          <div className="flex justify-between mt-2 text-xs text-gray-500">
            <div>
              {progress.startTime && (
                <span>Started: {new Date(progress.startTime).toLocaleTimeString()}</span>
              )}
            </div>
            <div>
              {progress.estimatedTimeRemaining !== undefined && progress.status !== 'completed' && progress.status !== 'error' && (
                <span>Estimated time remaining: {formatTime(progress.estimatedTimeRemaining)}</span>
              )}
              {progress.endTime && (
                <span>Completed in {formatTime(progress.endTime - progress.startTime)}</span>
              )}
            </div>
          </div>
          
          {progress.error && (
            <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">
              Error: {progress.error}
            </div>
          )}
        </div>
        
        {/* Tool-specific Progress */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium">Tool Progress</h3>
          
          {progress.tools.map((tool, index) => (
            <div key={index} className="border rounded p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {getStatusIcon(tool.status)}
                  <span className="font-medium">{getToolDisplayName(tool.tool)}</span>
                </div>
                <span className={`text-xs font-medium ${getStatusColor(tool.status)}`}>
                  {tool.status.charAt(0).toUpperCase() + tool.status.slice(1)} - {tool.progress}%
                </span>
              </div>
              
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div 
                  className={`h-1.5 rounded-full ${tool.status === 'error' ? 'bg-red-600' : 'bg-blue-600'}`}
                  style={{ width: `${tool.progress}%` }}
                ></div>
              </div>
              
              {tool.message && (
                <div className="mt-2 text-xs text-gray-600">
                  {tool.message}
                </div>
              )}
              
              {tool.timeElapsed && (
                <div className="mt-1 text-xs text-gray-500">
                  Time elapsed: {formatTime(tool.timeElapsed)}
                </div>
              )}
            </div>
          ))}
        </div>
        
        {/* Performance Metrics */}
        {progress.status === 'analyzing' && (
          <div className="mt-6 p-3 bg-gray-50 rounded border">
            <h3 className="text-sm font-medium mb-2">Performance Metrics</h3>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-gray-500">Code Size:</span>
                <span className="ml-2 font-medium">{codeSize} lines</span>
              </div>
              <div>
                <span className="text-gray-500">Language:</span>
                <span className="ml-2 font-medium">{language}</span>
              </div>
              <div>
                <span className="text-gray-500">Tools Running:</span>
                <span className="ml-2 font-medium">
                  {progress.tools.filter(t => t.status === 'running').length} / {progress.tools.length}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Analysis ID:</span>
                <span className="ml-2 font-medium">{analysisId.substring(0, 8)}...</span>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}