// frontend/src/hooks/useRobustAnalysisPersistence.ts
import { useState, useEffect, useCallback, useRef } from 'react'
import { useSafePersistence } from './useSafeApi'
import { AnalysisInfo, CodeAnalysisResponse } from '../lib/api'

interface UseRobustAnalysisPersistenceReturn {
  persistedAnalyses: AnalysisInfo[]
  loading: boolean
  error: string | null
  isAvailable: boolean
  hasConnectivity: boolean
  refreshAnalyses: () => Promise<void>
  getAnalysisResult: (analysisId: string) => Promise<CodeAnalysisResponse | null>
  deleteAnalysis: (analysisId: string) => Promise<boolean>
  clearExpiredAnalyses: () => Promise<void>
  stats: any
}

export function useRobustAnalysisPersistence(
  sessionId?: string,
  autoRefresh: boolean = true,
  refreshInterval: number = 30000 // 30 seconds
): UseRobustAnalysisPersistenceReturn {
  const [persistedAnalyses, setPersistedAnalyses] = useState<AnalysisInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<any>(null)
  
  const refreshTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const mountedRef = useRef(true)

  const safeApi = useSafePersistence()

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
      
      const response = await safeApi.getClientAnalyses(sessionId, 20)
      
      if (!mountedRef.current) return
      
      if (response && response.analyses) {
        setPersistedAnalyses(response.analyses)
        console.log(`📋 Found ${response.analyses.length} persisted analyses`)
      } else {
        setPersistedAnalyses([])
        console.log('📋 No persisted analyses found or endpoint unavailable')
      }
      
    } catch (err) {
      if (!mountedRef.current) return
      
      const errorMessage = err instanceof Error ? err.message : 'Failed to refresh analyses'
      console.warn('⚠️ Non-critical persistence error:', errorMessage)
      
      // Only set error for truly unexpected errors, not 404s or network issues
      if (!errorMessage.includes('404') && !errorMessage.includes('Network error')) {
        setError(errorMessage)
      }
      
    } finally {
      if (mountedRef.current) {
        setLoading(false)
      }
    }
  }, [sessionId, safeApi])

  const getAnalysisResult = useCallback(async (analysisId: string): Promise<CodeAnalysisResponse | null> => {
    if (!sessionId) {
      console.warn('⚠️ No session ID available for analysis retrieval')
      return null
    }

    try {
      console.log('📤 Retrieving analysis result:', analysisId)
      
      const response = await safeApi.getAnalysisResult(analysisId, sessionId)
      
      if (response && response.success && response.result) {
        console.log('✅ Analysis result retrieved successfully')
        return response.result
      } else {
        console.warn('⚠️ Analysis result not found or unavailable')
        return null
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to retrieve analysis'
      console.warn('⚠️ Analysis retrieval failed:', errorMessage)
      return null
    }
  }, [sessionId, safeApi])

  const deleteAnalysis = useCallback(async (analysisId: string): Promise<boolean> => {
    if (!sessionId) {
      console.warn('⚠️ No session ID available for analysis deletion')
      return false
    }

    try {
      console.log('🗑️ Deleting analysis:', analysisId)
      
      const response = await safeApi.deleteAnalysis(analysisId, sessionId)
      
      if (response && response.success) {
        // Remove from local state
        setPersistedAnalyses(prev => prev.filter(analysis => analysis.analysis_id !== analysisId))
        console.log('✅ Analysis deleted successfully')
        return true
      } else {
        console.warn('⚠️ Analysis deletion failed or endpoint unavailable')
        return false
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete analysis'
      console.warn('⚠️ Analysis deletion error:', errorMessage)
      return false
    }
  }, [sessionId, safeApi])

  const clearExpiredAnalyses = useCallback(async () => {
    try {
      console.log('🧹 Triggering cleanup of expired analyses')
      
      const response = await safeApi.triggerCleanup()
      
      if (response && response.success) {
        console.log('✅ Cleanup completed')
        // Refresh analyses to reflect changes
        await refreshAnalyses()
      } else {
        console.warn('⚠️ Cleanup endpoint unavailable')
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to clear expired analyses'
      console.warn('⚠️ Cleanup failed:', errorMessage)
    }
  }, [safeApi, refreshAnalyses])

  const refreshStats = useCallback(async () => {
    try {
      const response = await safeApi.getPersistenceStats()
      
      if (!mountedRef.current) return
      
      if (response && response.stats) {
        setStats(response.stats)
      } else {
        // Set default stats
        setStats({
          total_results: 0,
          total_sessions: 0,
          storage_size_mb: 0.0
        })
      }
      
    } catch (err) {
      console.warn('⚠️ Failed to refresh persistence stats:', err)
      // Set default stats on error
      if (mountedRef.current) {
        setStats({
          total_results: 0,
          total_sessions: 0,
          storage_size_mb: 0.0
        })
      }
    }
  }, [safeApi])

  // Initial load
  useEffect(() => {
    if (sessionId) {
      refreshAnalyses()
      refreshStats()
    }
  }, [sessionId, refreshAnalyses, refreshStats])

  // Auto-refresh setup (only if API is available)
  useEffect(() => {
    if (!autoRefresh || !sessionId || !safeApi.isAvailable) return

    const scheduleRefresh = () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }
      
      refreshTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current && safeApi.hasConnectivity) {
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
  }, [autoRefresh, sessionId, refreshInterval, refreshAnalyses, safeApi.isAvailable, safeApi.hasConnectivity])

  return {
    persistedAnalyses,
    loading: loading || safeApi.loading,
    error: error || safeApi.error,
    isAvailable: safeApi.isAvailable,
    hasConnectivity: safeApi.hasConnectivity,
    refreshAnalyses,
    getAnalysisResult,
    deleteAnalysis,
    clearExpiredAnalyses,
    stats
  }
}