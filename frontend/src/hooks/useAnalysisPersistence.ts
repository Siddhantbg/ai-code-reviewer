// frontend/src/hooks/useAnalysisPersistence.ts
import { useState, useEffect, useCallback, useRef } from 'react'
import { api, AnalysisInfo, CodeAnalysisResponse } from '../lib/api'

interface UseAnalysisPersistenceReturn {
  persistedAnalyses: AnalysisInfo[]
  loading: boolean
  error: string | null
  refreshAnalyses: () => Promise<void>
  getAnalysisResult: (analysisId: string) => Promise<CodeAnalysisResponse | null>
  deleteAnalysis: (analysisId: string) => Promise<boolean>
  clearExpiredAnalyses: () => Promise<void>
  stats: any
}

export function useAnalysisPersistence(
  sessionId?: string,
  autoRefresh: boolean = false, // Changed default to false to prevent re-render loops
  refreshInterval: number = 30000 // 30 seconds
): UseAnalysisPersistenceReturn {
  const [persistedAnalyses, setPersistedAnalyses] = useState<AnalysisInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<any>(null)
  
  const refreshTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const mountedRef = useRef(true)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }
    }
  }, [])

  const refreshAnalyses = useCallback(async () => {
    if (!sessionId || !mountedRef.current) return

    try {
      setLoading(true)
      setError(null)
      
      console.log('🔄 Refreshing persisted analyses for session:', sessionId)
      
      const response = await api.getClientAnalyses(sessionId, 20)
      
      if (!mountedRef.current) return
      
      if (response.success && response.analyses) {
        setPersistedAnalyses(response.analyses)
        console.log(`📋 Found ${response.analyses.length} persisted analyses`)
      } else {
        // Handle unsuccessful response gracefully - don't treat as error
        setPersistedAnalyses([])
        console.log('📋 No persisted analyses found or endpoint unavailable')
      }
      
    } catch (err) {
      if (!mountedRef.current) return
      
      const errorMessage = err instanceof Error ? err.message : 'Failed to refresh analyses'
      console.warn('⚠️ Failed to refresh persisted analyses:', errorMessage)
      
      // Don't set error for 404 or network issues - just log and continue
      if (errorMessage.includes('404') || errorMessage.includes('Not Found') || errorMessage.includes('Network error')) {
        console.log('📋 Persistence endpoint not available, continuing without persistence features')
        setPersistedAnalyses([])
        setError(null) // Ensure no error state is set
      } else {
        setError(errorMessage)
      }
      
    } finally {
      if (mountedRef.current) {
        setLoading(false)
      }
    }
  }, [sessionId])

  const getAnalysisResult = useCallback(async (analysisId: string): Promise<CodeAnalysisResponse | null> => {
    if (!sessionId) {
      console.warn('⚠️ No session ID available for analysis retrieval')
      return null
    }

    try {
      console.log('📤 Retrieving analysis result:', analysisId)
      
      const response = await api.getAnalysisResult(analysisId, sessionId)
      
      if (response.success && response.result) {
        console.log('✅ Analysis result retrieved successfully')
        return response.result
      } else {
        console.warn('⚠️ Analysis result not found or unavailable')
        return null
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to retrieve analysis'
      console.error('❌ Failed to retrieve analysis result:', errorMessage)
      throw new Error(errorMessage)
    }
  }, [sessionId])

  const deleteAnalysis = useCallback(async (analysisId: string): Promise<boolean> => {
    if (!sessionId) {
      console.warn('⚠️ No session ID available for analysis deletion')
      return false
    }

    try {
      console.log('🗑️ Deleting analysis:', analysisId)
      
      const response = await api.deleteAnalysisResult(analysisId, sessionId)
      
      if (response.success) {
        // Remove from local state
        setPersistedAnalyses(prev => prev.filter(analysis => analysis.analysis_id !== analysisId))
        console.log('✅ Analysis deleted successfully')
        return true
      } else {
        console.warn('⚠️ Analysis deletion failed')
        return false
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete analysis'
      console.error('❌ Failed to delete analysis:', errorMessage)
      throw new Error(errorMessage)
    }
  }, [sessionId])

  const clearExpiredAnalyses = useCallback(async () => {
    try {
      console.log('🧹 Triggering cleanup of expired analyses')
      
      const response = await api.triggerCleanup()
      
      if (response.success) {
        console.log('✅ Cleanup completed')
        // Refresh analyses to reflect changes
        await refreshAnalyses()
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to clear expired analyses'
      console.error('❌ Failed to clear expired analyses:', errorMessage)
      throw new Error(errorMessage)
    }
  }, [refreshAnalyses])

  const refreshStats = useCallback(async () => {
    try {
      const response = await api.getPersistenceStats()
      
      if (!mountedRef.current) return
      
      if (response.success) {
        setStats(response.stats)
      } else {
        // Set default stats if unsuccessful
        setStats({
          total_results: 0,
          total_sessions: 0,
          storage_size_mb: 0.0
        })
      }
      
    } catch (err) {
      console.warn('⚠️ Failed to refresh persistence stats:', err)
      // Don't crash on stats failure - just set empty stats
      if (mountedRef.current) {
        setStats({
          total_results: 0,
          total_sessions: 0,
          storage_size_mb: 0.0
        })
      }
    }
  }, [])

  // Initial load - remove function dependencies to prevent infinite loops
  useEffect(() => {
    if (sessionId) {
      refreshAnalyses()
      refreshStats()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  // Auto-refresh setup
  useEffect(() => {
    if (!autoRefresh || !sessionId) return

    const scheduleRefresh = () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }
      
      refreshTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current) {
          refreshAnalyses().finally(() => {
            if (mountedRef.current) {
              scheduleRefresh()
            }
          })
        }
      }, refreshInterval)
    }

    scheduleRefresh()

    return () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
        refreshTimeoutRef.current = null
      }
    }
  }, [autoRefresh, sessionId, refreshInterval, refreshAnalyses])

  return {
    persistedAnalyses,
    loading,
    error,
    refreshAnalyses,
    getAnalysisResult,
    deleteAnalysis,
    clearExpiredAnalyses,
    stats
  }
}

// Hook for checking a specific analysis
export function useAnalysisStatus(analysisId: string, sessionId?: string) {
  const [status, setStatus] = useState<{
    available: boolean
    status: string
    message: string
    loading: boolean
    error: string | null
  }>({
    available: false,
    status: 'unknown',
    message: '',
    loading: false,
    error: null
  })

  const checkStatus = useCallback(async () => {
    if (!analysisId) return

    setStatus(prev => ({ ...prev, loading: true, error: null }))

    try {
      const response = await api.checkAnalysisStatus(analysisId, sessionId)
      
      setStatus({
        available: response.available,
        status: response.status,
        message: response.message,
        loading: false,
        error: null
      })
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to check status'
      setStatus({
        available: false,
        status: 'error',
        message: errorMessage,
        loading: false,
        error: errorMessage
      })
    }
  }, [analysisId, sessionId])

  useEffect(() => {
    checkStatus()
  }, [checkStatus])

  return {
    ...status,
    refresh: checkStatus
  }
}