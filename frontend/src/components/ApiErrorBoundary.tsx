"use client"

import React, { ReactNode } from 'react'
import { PersistenceErrorBoundary, withPersistenceErrorBoundary } from './PersistenceErrorBoundary'
import ErrorBoundary from './ErrorBoundary'

interface ApiErrorBoundaryProps {
  children: ReactNode
  apiType?: 'persistence' | 'analysis' | 'general'
  componentName?: string
  fallbackMessage?: string
  showRetry?: boolean
  onError?: (error: Error, errorInfo: any) => void
}

// Centralized API error boundary that routes to appropriate handlers
export function ApiErrorBoundary({
  children,
  apiType = 'general',
  componentName,
  fallbackMessage,
  showRetry = true,
  onError
}: ApiErrorBoundaryProps) {
  
  if (apiType === 'persistence') {
    return (
      <PersistenceErrorBoundary
        componentName={componentName}
        showRetry={showRetry}
        onError={onError}
      >
        {children}
      </PersistenceErrorBoundary>
    )
  }

  // For general API errors, use the main error boundary
  return (
    <ErrorBoundary
      onError={onError}
      fallback={
        fallbackMessage ? (
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm text-yellow-800">{fallbackMessage}</p>
          </div>
        ) : undefined
      }
    >
      {children}
    </ErrorBoundary>
  )
}

// HOCs for different API types
export const withApiErrorBoundary = (
  Component: React.ComponentType<any>,
  options: Omit<ApiErrorBoundaryProps, 'children'> = {}
) => {
  const WrappedComponent = (props: any) => (
    <ApiErrorBoundary {...options}>
      <Component {...props} />
    </ApiErrorBoundary>
  )

  WrappedComponent.displayName = `withApiErrorBoundary(${Component.displayName || Component.name})`
  return WrappedComponent
}

// Specialized HOCs
export const withPersistenceErrorHandling = (Component: React.ComponentType<any>) =>
  withApiErrorBoundary(Component, { 
    apiType: 'persistence',
    componentName: Component.displayName || Component.name 
  })

export const withAnalysisErrorHandling = (Component: React.ComponentType<any>) =>
  withApiErrorBoundary(Component, { 
    apiType: 'analysis',
    componentName: Component.displayName || Component.name 
  })

// Pre-configured error boundary components
export function PersistenceFeature({ children }: { children: ReactNode }) {
  return (
    <ApiErrorBoundary 
      apiType="persistence" 
      componentName="PersistenceFeature"
      showRetry={true}
    >
      {children}
    </ApiErrorBoundary>
  )
}

export function AnalysisFeature({ children }: { children: ReactNode }) {
  return (
    <ApiErrorBoundary 
      apiType="analysis" 
      componentName="AnalysisFeature"
      fallbackMessage="Analysis feature temporarily unavailable. Please try again."
    >
      {children}
    </ApiErrorBoundary>
  )
}

// Error boundary for critical features that should show user-friendly messages
export function CriticalFeature({ 
  children, 
  featureName = "This feature" 
}: { 
  children: ReactNode
  featureName?: string 
}) {
  return (
    <ErrorBoundary
      fallback={
        <div className="p-6 bg-red-50 border border-red-200 rounded-lg text-center">
          <h3 className="text-lg font-semibold text-red-800 mb-2">
            {featureName} is temporarily unavailable
          </h3>
          <p className="text-sm text-red-700 mb-4">
            We're working to fix this issue. Please try refreshing the page.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm"
          >
            Refresh Page
          </button>
        </div>
      }
      onError={(error, errorInfo) => {
        console.error(`🚨 Critical feature error in ${featureName}:`, error)
        
        // Report critical errors to monitoring service
        // errorReporting.captureException(error, {
        //   tags: { feature: featureName, critical: true },
        //   extra: errorInfo
        // })
      }}
    >
      {children}
    </ErrorBoundary>
  )
}

export default ApiErrorBoundary