// frontend/src/hooks/useSafeApi.ts
import { useState, useCallback } from 'react'
import { api } from '../lib/api'

interface SafeApiState {
  loading: boolean
  error: string | null
  lastError: string | null
}

interface SafeApiOptions {
  retries?: number
  retryDelay?: number
  fallbackValue?: any
  suppressErrors?: boolean
}

export function useSafeApi() {
  const [state, setState] = useState<SafeApiState>({
    loading: false,
    error: null,
    lastError: null
  })

  const safeCall = useCallback(async <T>(
    apiCall: () => Promise<T>,
    options: SafeApiOptions = {}
  ): Promise<T | null> => {
    const {
      retries = 1,
      retryDelay = 1000,
      fallbackValue = null,
      suppressErrors = false
    } = options

    setState(prev => ({ ...prev, loading: true, error: null }))

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const result = await apiCall()
        setState(prev => ({ ...prev, loading: false, error: null }))
        return result
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error'
        
        // Check if this is a known non-critical error
        const isNonCritical = 
          errorMessage.includes('404') ||
          errorMessage.includes('Not Found') ||
          errorMessage.includes('Network error') ||
          errorMessage.includes('endpoint not found')

        if (isNonCritical && suppressErrors) {
          console.warn(`⚠️ API call failed (attempt ${attempt + 1}/${retries + 1}):`, errorMessage)
          setState(prev => ({ 
            ...prev, 
            loading: false, 
            error: null, 
            lastError: errorMessage 
          }))
          return fallbackValue
        }

        if (attempt === retries) {
          // Final attempt failed
          if (suppressErrors && isNonCritical) {
            console.warn('🔧 API endpoint unavailable, using fallback:', errorMessage)
            setState(prev => ({ 
              ...prev, 
              loading: false, 
              error: null, 
              lastError: errorMessage 
            }))
            return fallbackValue
          } else {
            console.error('❌ API call failed after all retries:', errorMessage)
            setState(prev => ({ 
              ...prev, 
              loading: false, 
              error: errorMessage, 
              lastError: errorMessage 
            }))
            return fallbackValue
          }
        }

        // Wait before retrying
        if (retryDelay > 0) {
          await new Promise(resolve => setTimeout(resolve, retryDelay))
        }
      }
    }

    return fallbackValue
  }, [])

  // Specific safe API methods
  const safeGetClientAnalyses = useCallback(async (
    clientSessionId: string, 
    limit: number = 20
  ) => {
    return safeCall(
      () => api.getClientAnalyses(clientSessionId, limit),
      {
        suppressErrors: true,
        fallbackValue: {
          success: false,
          analyses: [],
          count: 0,
          retrieved_at: new Date().toISOString()
        }
      }
    )
  }, [safeCall])

  const safeGetPersistenceStats = useCallback(async () => {
    return safeCall(
      () => api.getPersistenceStats(),
      {
        suppressErrors: true,
        fallbackValue: {
          success: false,
          stats: {
            total_results: 0,
            total_sessions: 0,
            storage_size_mb: 0.0
          }
        }
      }
    )
  }, [safeCall])

  const safeGetAnalysisResult = useCallback(async (
    analysisId: string, 
    clientSessionId?: string
  ) => {
    return safeCall(
      () => api.getAnalysisResult(analysisId, clientSessionId),
      {
        suppressErrors: true,
        fallbackValue: {
          success: false,
          analysis_id: analysisId,
          retrieved_at: new Date().toISOString()
        }
      }
    )
  }, [safeCall])

  const safeDeleteAnalysis = useCallback(async (
    analysisId: string, 
    clientSessionId?: string
  ) => {
    return safeCall(
      () => api.deleteAnalysisResult(analysisId, clientSessionId),
      {
        suppressErrors: true,
        fallbackValue: {
          success: false,
          message: 'Delete endpoint not available'
        }
      }
    )
  }, [safeCall])

  const safeTriggerCleanup = useCallback(async () => {
    return safeCall(
      () => api.triggerCleanup(),
      {
        suppressErrors: true,
        fallbackValue: {
          success: false,
          message: 'Cleanup endpoint not available'
        }
      }
    )
  }, [safeCall])

  const checkApiHealth = useCallback(async () => {
    return safeCall(
      () => api.healthCheck(),
      {
        suppressErrors: true,
        fallbackValue: {
          status: 'unavailable',
          message: 'Backend not reachable',
          version: 'unknown',
          ai_model_loaded: false
        }
      }
    )
  }, [safeCall])

  return {
    ...state,
    safeCall,
    safeGetClientAnalyses,
    safeGetPersistenceStats,
    safeGetAnalysisResult,
    safeDeleteAnalysis,
    safeTriggerCleanup,
    checkApiHealth,
    isApiAvailable: state.lastError === null
  }
}

// Hook specifically for persistence operations
export function useSafePersistence() {
  const {
    safeGetClientAnalyses,
    safeGetPersistenceStats,
    safeGetAnalysisResult,
    safeDeleteAnalysis,
    safeTriggerCleanup,
    loading,
    error,
    lastError,
    isApiAvailable
  } = useSafeApi()

  return {
    getClientAnalyses: safeGetClientAnalyses,
    getPersistenceStats: safeGetPersistenceStats,
    getAnalysisResult: safeGetAnalysisResult,
    deleteAnalysis: safeDeleteAnalysis,
    triggerCleanup: safeTriggerCleanup,
    loading,
    error,
    lastError,
    isAvailable: isApiAvailable,
    hasConnectivity: lastError === null || !lastError.includes('Network error')
  }
}