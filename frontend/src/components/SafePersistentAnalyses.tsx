// frontend/src/components/SafePersistentAnalyses.tsx
'use client'

import React from 'react'
import { PersistentAnalyses } from './PersistentAnalyses'
import { PersistenceErrorBoundary, AnalysisPersistenceErrorBoundary } from './PersistenceErrorBoundary'

interface SafePersistentAnalysesProps {
  sessionId?: string
  onAnalysisRetrieved?: (analysis: any) => void
  className?: string
}

export function SafePersistentAnalyses(props: SafePersistentAnalysesProps) {
  return (
    <AnalysisPersistenceErrorBoundary>
      <PersistentAnalyses {...props} />
    </AnalysisPersistenceErrorBoundary>
  )
}

// Alternative with custom error boundary
export function PersistentAnalysesWithErrorBoundary(props: SafePersistentAnalysesProps) {
  return (
    <PersistenceErrorBoundary
      componentName="PersistentAnalyses"
      onError={(error, errorInfo) => {
        console.warn('🔧 PersistentAnalyses error:', error)
        
        // Send to analytics if available
        // analytics.track('persistence_component_error', {
        //   component: 'PersistentAnalyses',
        //   error: error.message,
        //   sessionId: props.sessionId
        // })
      }}
    >
      <PersistentAnalyses {...props} />
    </PersistenceErrorBoundary>
  )
}

// Export both components for flexibility
export { PersistentAnalyses }
export default SafePersistentAnalyses