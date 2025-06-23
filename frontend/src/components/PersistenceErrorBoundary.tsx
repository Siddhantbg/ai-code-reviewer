"use client"

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  AlertTriangle, 
  RefreshCw, 
  Database, 
  WifiOff, 
  Server, 
  Clock,
  Info,
  Home
} from 'lucide-react'

interface PersistenceErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  showRetry?: boolean
  retryText?: string
  componentName?: string
}

interface PersistenceErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  retryCount: number
  isRetrying: boolean
}

export class PersistenceErrorBoundary extends Component<
  PersistenceErrorBoundaryProps, 
  PersistenceErrorBoundaryState
> {
  private retryTimeout: NodeJS.Timeout | null = null

  constructor(props: PersistenceErrorBoundaryProps) {
    super(props)

    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: 0,
      isRetrying: false
    }
  }

  static getDerivedStateFromError(error: Error): Partial<PersistenceErrorBoundaryState> {
    return {
      hasError: true,
      error,
      errorInfo: null
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.warn('🔧 Persistence component error (non-critical):', error)
    console.warn('🔧 Component:', this.props.componentName || 'Unknown')
    console.warn('🔧 Error info:', errorInfo)
    
    this.setState({
      error,
      errorInfo
    })

    // Call onError prop if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }

    // Log to external error reporting (if available)
    // This is non-critical, so we don't want to crash the main app
    try {
      // Example: Sentry.captureException(error, { 
      //   tags: { component: 'persistence' },
      //   extra: errorInfo 
      // })
    } catch (reportingError) {
      console.warn('Failed to report persistence error:', reportingError)
    }
  }

  componentWillUnmount() {
    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout)
    }
  }

  handleRetry = () => {
    this.setState({ 
      isRetrying: true,
      retryCount: this.state.retryCount + 1 
    })

    // Add a small delay to show the retry state
    this.retryTimeout = setTimeout(() => {
      this.setState({
        hasError: false,
        error: null,
        errorInfo: null,
        isRetrying: false
      })
    }, 1000)
  }

  handleReload = () => {
    window.location.reload()
  }

  getErrorType(error: Error): {
    type: 'api' | 'network' | 'persistence' | 'component' | 'unknown'
    icon: ReactNode
    title: string
    description: string
    canRetry: boolean
  } {
    const message = error.message?.toLowerCase() || ''

    if (message.includes('404') || message.includes('not found')) {
      return {
        type: 'api',
        icon: <Server className="h-5 w-5 text-orange-600" />,
        title: 'Service Unavailable',
        description: 'The persistence service is not available right now. Your main analysis features will continue to work normally.',
        canRetry: true
      }
    }

    if (message.includes('network') || message.includes('fetch')) {
      return {
        type: 'network',
        icon: <WifiOff className="h-5 w-5 text-red-600" />,
        title: 'Connection Issue',
        description: 'Unable to connect to the persistence service. Check your internet connection.',
        canRetry: true
      }
    }

    if (message.includes('timeout') || message.includes('abort')) {
      return {
        type: 'network',
        icon: <Clock className="h-5 w-5 text-yellow-600" />,
        title: 'Request Timeout',
        description: 'The persistence service is taking too long to respond. It may be overloaded.',
        canRetry: true
      }
    }

    if (this.props.componentName?.toLowerCase().includes('persist')) {
      return {
        type: 'persistence',
        icon: <Database className="h-5 w-5 text-blue-600" />,
        title: 'Persistence Error',
        description: 'There was an issue with the analysis history feature. Your current analysis will still work.',
        canRetry: true
      }
    }

    return {
      type: 'component',
      icon: <AlertTriangle className="h-5 w-5 text-red-600" />,
      title: 'Component Error',
      description: 'This feature encountered an unexpected error. The rest of the application should continue working.',
      canRetry: true
    }
  }

  render() {
    if (this.state.hasError && this.state.error) {
      // Custom fallback UI provided
      if (this.props.fallback) {
        return this.props.fallback
      }

      const errorType = this.getErrorType(this.state.error)
      const { showRetry = true, retryText = 'Try Again', componentName } = this.props

      return (
        <div className="w-full">
          <Alert variant="destructive" className="mb-4">
            <div className="flex items-start gap-3">
              {errorType.icon}
              <div className="flex-1">
                <h4 className="font-semibold mb-1">{errorType.title}</h4>
                <AlertDescription className="text-sm">
                  {errorType.description}
                </AlertDescription>
              </div>
            </div>
          </Alert>

          <Card className="border-orange-200 bg-orange-50">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Info className="h-4 w-4 text-orange-600" />
                <CardTitle className="text-sm font-medium text-orange-800">
                  Feature Temporarily Unavailable
                </CardTitle>
              </div>
              {componentName && (
                <CardDescription className="text-xs text-orange-700">
                  Component: {componentName}
                </CardDescription>
              )}
            </CardHeader>
            
            <CardContent className="pt-0">
              <div className="space-y-3">
                <div className="text-sm text-orange-700">
                  <p className="mb-2">What you can do:</p>
                  <ul className="space-y-1 list-disc list-inside">
                    <li>Continue using the main analysis features</li>
                    <li>Try refreshing this component</li>
                    <li>Check back in a few minutes</li>
                  </ul>
                </div>

                {/* Error Details (Collapsible) */}
                <details className="bg-orange-100 rounded p-2">
                  <summary className="text-xs font-medium text-orange-800 cursor-pointer hover:text-orange-900">
                    Technical Details (click to expand)
                  </summary>
                  <div className="mt-2 space-y-1">
                    <div className="text-xs text-orange-700">
                      <strong>Error:</strong> {this.state.error.message}
                    </div>
                    {this.state.retryCount > 0 && (
                      <div className="text-xs text-orange-700">
                        <strong>Retry attempts:</strong> {this.state.retryCount}
                      </div>
                    )}
                    {this.state.error.stack && (
                      <details className="mt-1">
                        <summary className="text-xs cursor-pointer">Stack trace</summary>
                        <pre className="text-xs bg-orange-200 p-1 rounded mt-1 overflow-auto max-h-20">
                          {this.state.error.stack}
                        </pre>
                      </details>
                    )}
                  </div>
                </details>

                {/* Action Buttons */}
                <div className="flex gap-2">
                  {showRetry && errorType.canRetry && (
                    <Button
                      onClick={this.handleRetry}
                      disabled={this.state.isRetrying}
                      size="sm"
                      variant="outline"
                      className="border-orange-300 text-orange-800 hover:bg-orange-100"
                    >
                      {this.state.isRetrying ? (
                        <RefreshCw className="h-3 w-3 animate-spin mr-1" />
                      ) : (
                        <RefreshCw className="h-3 w-3 mr-1" />
                      )}
                      {this.state.isRetrying ? 'Retrying...' : retryText}
                    </Button>
                  )}

                  {this.state.retryCount > 2 && (
                    <Button
                      onClick={this.handleReload}
                      size="sm"
                      variant="outline"
                      className="border-orange-300 text-orange-800 hover:bg-orange-100"
                    >
                      <Home className="h-3 w-3 mr-1" />
                      Reload Page
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}

// Hook-based error handler for functional components
export function usePersistenceErrorHandler() {
  return (error: Error, errorInfo?: ErrorInfo) => {
    console.warn('🔧 Persistence error handler:', error)
    if (errorInfo) {
      console.warn('🔧 Error info:', errorInfo)
    }
    
    // Could dispatch to error reporting service here with persistence tag
    // analytics.track('persistence_error', { error: error.message, component: errorInfo?.componentStack })
  }
}

// HOC for wrapping persistence components with error boundary
export function withPersistenceErrorBoundary<T extends object>(
  Component: React.ComponentType<T>,
  options: {
    fallback?: ReactNode
    componentName?: string
    onError?: (error: Error, errorInfo: ErrorInfo) => void
    showRetry?: boolean
  } = {}
) {
  const WrappedComponent = (props: T) => (
    <PersistenceErrorBoundary
      fallback={options.fallback}
      onError={options.onError}
      showRetry={options.showRetry}
      componentName={options.componentName || Component.displayName || Component.name}
    >
      <Component {...props} />
    </PersistenceErrorBoundary>
  )

  WrappedComponent.displayName = `withPersistenceErrorBoundary(${Component.displayName || Component.name})`
  
  return WrappedComponent
}

// Specific error boundary for analysis persistence features
export function AnalysisPersistenceErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <PersistenceErrorBoundary
      componentName="AnalysisPersistence"
      onError={(error, errorInfo) => {
        // Log with specific context
        console.warn('🔧 Analysis persistence error:', {
          error: error.message,
          component: 'AnalysisPersistence',
          stack: error.stack
        })
      }}
    >
      {children}
    </PersistenceErrorBoundary>
  )
}

export default PersistenceErrorBoundary