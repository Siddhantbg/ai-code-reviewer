"use client"

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AlertTriangle, RefreshCw, Bug, Home } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)

    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    }
  }

  static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI
    return {
      hasError: true,
      error,
      errorInfo: null
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log the error to console and external services
    console.error('🚨 ErrorBoundary caught an error:', error)
    console.error('🚨 Error info:', errorInfo)
    
    // Update state with error details
    this.setState({
      error,
      errorInfo
    })

    // Call onError prop if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }

    // Log to external error reporting service (if available)
    // Example: Sentry.captureException(error, { contexts: { react: errorInfo } })
  }

  handleReload = () => {
    // Reset error state and reload the page
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    })
    window.location.reload()
  }

  handleReset = () => {
    // Reset error state without page reload
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    })
  }

  render() {
    if (this.state.hasError) {
      // Custom fallback UI provided
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default fallback UI
      return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
          <Card className="w-full max-w-2xl">
            <CardHeader className="text-center">
              <div className="flex justify-center mb-4">
                <div className="p-3 bg-red-100 rounded-full">
                  <AlertTriangle className="h-8 w-8 text-red-600" />
                </div>
              </div>
              <CardTitle className="text-2xl font-bold text-gray-900">
                Oops! Something went wrong
              </CardTitle>
            </CardHeader>
            
            <CardContent className="space-y-6">
              <div className="text-center">
                <p className="text-gray-600 mb-4">
                  The application encountered an unexpected error and crashed. 
                  Don't worry, this has been logged and we're working to fix it.
                </p>
                
                <div className="bg-gray-50 rounded-lg p-4 text-left">
                  <div className="flex items-center gap-2 mb-2">
                    <Bug className="h-4 w-4 text-gray-500" />
                    <span className="font-medium text-sm text-gray-700">Error Details:</span>
                  </div>
                  
                  {this.state.error && (
                    <div className="space-y-2">
                      <div>
                        <span className="text-xs font-medium text-gray-600">Message:</span>
                        <p className="text-sm text-red-600 font-mono bg-red-50 p-2 rounded mt-1">
                          {this.state.error.message}
                        </p>
                      </div>
                      
                      {this.state.error.stack && (
                        <details className="mt-2">
                          <summary className="text-xs font-medium text-gray-600 cursor-pointer hover:text-gray-800">
                            Stack Trace (click to expand)
                          </summary>
                          <pre className="text-xs text-gray-700 bg-gray-100 p-2 rounded mt-1 overflow-auto max-h-32">
                            {this.state.error.stack}
                          </pre>
                        </details>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <Button 
                  onClick={this.handleReset} 
                  variant="default"
                  className="flex items-center gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  Try Again
                </Button>
                
                <Button 
                  onClick={this.handleReload} 
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  <Home className="h-4 w-4" />
                  Reload Page
                </Button>
              </div>

              <div className="text-center text-sm text-gray-500">
                <p>
                  If this problem persists, please{' '}
                  <a 
                    href="https://github.com/anthropics/claude-code/issues" 
                    className="text-blue-600 hover:text-blue-800 underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    report this issue
                  </a>
                  {' '}or contact support.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}

// Hook-based error boundary for functional components
export function useErrorHandler() {
  return (error: Error, errorInfo?: ErrorInfo) => {
    console.error('🚨 useErrorHandler caught an error:', error)
    if (errorInfo) {
      console.error('🚨 Error info:', errorInfo)
    }
    // Could dispatch to error reporting service here
  }
}

// HOC for wrapping components with error boundary
export function withErrorBoundary<T extends object>(
  Component: React.ComponentType<T>,
  fallback?: ReactNode,
  onError?: (error: Error, errorInfo: ErrorInfo) => void
) {
  const WrappedComponent = (props: T) => (
    <ErrorBoundary fallback={fallback} onError={onError}>
      <Component {...props} />
    </ErrorBoundary>
  )

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`
  
  return WrappedComponent
}