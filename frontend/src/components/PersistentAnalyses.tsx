// frontend/src/components/PersistentAnalyses.tsx
'use client'

import React, { useState } from 'react'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Badge } from './ui/badge'
import { Trash2, Download, RefreshCw, Clock, CheckCircle, AlertCircle, XCircle } from 'lucide-react'
import { useAnalysisPersistence } from '../hooks/useAnalysisPersistence'
import { AnalysisInfo, CodeAnalysisResponse } from '../lib/api'
import { toast } from 'react-hot-toast'

interface PersistentAnalysesProps {
  sessionId?: string
  onAnalysisRetrieved?: (analysis: CodeAnalysisResponse) => void
  className?: string
}

export function PersistentAnalyses({ 
  sessionId, 
  onAnalysisRetrieved,
  className = '' 
}: PersistentAnalysesProps) {
  const {
    persistedAnalyses,
    loading,
    error,
    refreshAnalyses,
    getAnalysisResult,
    deleteAnalysis,
    clearExpiredAnalyses,
    stats
  } = useAnalysisPersistence(sessionId, true, 30000)

  const [retrievingId, setRetrievingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const handleRetrieveAnalysis = async (analysisInfo: AnalysisInfo) => {
    if (!analysisInfo.has_result) {
      toast.error('Analysis result not available')
      return
    }

    setRetrievingId(analysisInfo.analysis_id)
    
    try {
      const result = await getAnalysisResult(analysisInfo.analysis_id)
      
      if (result) {
        onAnalysisRetrieved?.(result)
        toast.success(`Analysis ${analysisInfo.analysis_id.slice(0, 8)}... retrieved successfully`)
      } else {
        toast.error('Failed to retrieve analysis result')
      }
      
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to retrieve analysis'
      toast.error(message)
    } finally {
      setRetrievingId(null)
    }
  }

  const handleDeleteAnalysis = async (analysisInfo: AnalysisInfo) => {
    if (!confirm(`Are you sure you want to delete analysis ${analysisInfo.analysis_id.slice(0, 8)}...?`)) {
      return
    }

    setDeletingId(analysisInfo.analysis_id)
    
    try {
      const success = await deleteAnalysis(analysisInfo.analysis_id)
      
      if (success) {
        toast.success('Analysis deleted successfully')
      } else {
        toast.error('Failed to delete analysis')
      }
      
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete analysis'
      toast.error(message)
    } finally {
      setDeletingId(null)
    }
  }

  const handleClearExpired = async () => {
    try {
      await clearExpiredAnalyses()
      toast.success('Expired analyses cleared')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to clear expired analyses'
      toast.error(message)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'running':
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200'
      case 'running':
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString()
  }

  if (!sessionId) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground text-center">
            No session available for persistent analyses
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">Persistent Analyses</CardTitle>
            <CardDescription>
              Analysis results that survived disconnections
              {stats && (
                <span className="ml-2 text-xs">
                  ({stats.total_results} total, {stats.storage_size_mb}MB used)
                </span>
              )}
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={refreshAnalyses}
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearExpired}
              disabled={loading}
            >
              Clear Expired
            </Button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
            <p className="text-sm">{error}</p>
          </div>
        )}

        {loading && persistedAnalyses.length === 0 ? (
          <div className="text-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Loading persistent analyses...</p>
          </div>
        ) : persistedAnalyses.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-muted-foreground">No persistent analyses found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {persistedAnalyses.map((analysisInfo) => (
              <div
                key={analysisInfo.analysis_id}
                className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      {getStatusIcon(analysisInfo.status)}
                      <Badge className={getStatusColor(analysisInfo.status)}>
                        {analysisInfo.status}
                      </Badge>
                      <span className="text-sm font-mono text-muted-foreground">
                        {analysisInfo.analysis_id.slice(0, 8)}...
                      </span>
                    </div>
                    
                    <div className="text-xs text-muted-foreground space-y-1">
                      <p>Created: {formatDate(analysisInfo.created_at)}</p>
                      {analysisInfo.completed_at && (
                        <p>Completed: {formatDate(analysisInfo.completed_at)}</p>
                      )}
                      <p>Retrieved: {analysisInfo.retrieval_count} times</p>
                    </div>
                  </div>
                  
                  <div className="flex gap-2 ml-4">
                    {analysisInfo.has_result && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRetrieveAnalysis(analysisInfo)}
                        disabled={retrievingId === analysisInfo.analysis_id}
                      >
                        {retrievingId === analysisInfo.analysis_id ? (
                          <RefreshCw className="h-4 w-4 animate-spin" />
                        ) : (
                          <Download className="h-4 w-4" />
                        )}
                      </Button>
                    )}
                    
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDeleteAnalysis(analysisInfo)}
                      disabled={deletingId === analysisInfo.analysis_id}
                    >
                      {deletingId === analysisInfo.analysis_id ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}