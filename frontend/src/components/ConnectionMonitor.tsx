"use client"
import React, { useEffect, useState } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { AlertCircle, CheckCircle, Wifi, WifiOff, RefreshCw } from 'lucide-react'

interface ConnectionMonitorProps {
  isConnected: boolean
  isAnalyzing: boolean
  analysisId?: string | null
  onReconnect?: () => void
  onRetryAnalysis?: () => void
}

export default function ConnectionMonitor({
  isConnected,
  isAnalyzing,
  analysisId,
  onReconnect,
  onRetryAnalysis
}: ConnectionMonitorProps) {
  const [showDisconnectionAlert, setShowDisconnectionAlert] = useState(false)
  const [wasConnectedDuringAnalysis, setWasConnectedDuringAnalysis] = useState(false)
  const [disconnectionStartTime, setDisconnectionStartTime] = useState<number | null>(null)
  const [reconnectionAttempts, setReconnectionAttempts] = useState(0)

  // Track connection state during analysis
  useEffect(() => {
    if (isAnalyzing && isConnected) {
      setWasConnectedDuringAnalysis(true)
      setShowDisconnectionAlert(false)
      setDisconnectionStartTime(null)
      setReconnectionAttempts(0)
    } else if (isAnalyzing && !isConnected && wasConnectedDuringAnalysis) {
      // Connection lost during analysis
      setShowDisconnectionAlert(true)
      if (!disconnectionStartTime) {
        setDisconnectionStartTime(Date.now())
      }
    } else if (!isAnalyzing) {
      setWasConnectedDuringAnalysis(false)
      setShowDisconnectionAlert(false)
      setDisconnectionStartTime(null)
      setReconnectionAttempts(0)
    }
  }, [isConnected, isAnalyzing, wasConnectedDuringAnalysis, disconnectionStartTime])

  // Auto-reconnect attempts
  useEffect(() => {
    if (showDisconnectionAlert && !isConnected && onReconnect && reconnectionAttempts < 3) {
      const timer = setTimeout(() => {
        console.log(`🔄 Auto-reconnect attempt ${reconnectionAttempts + 1}/3`)
        onReconnect()
        setReconnectionAttempts(prev => prev + 1)
      }, 2000 * (reconnectionAttempts + 1)) // Exponential backoff

      return () => clearTimeout(timer)
    }
  }, [showDisconnectionAlert, isConnected, onReconnect, reconnectionAttempts])

  // Calculate disconnection duration
  const getDisconnectionDuration = () => {
    if (!disconnectionStartTime) return 0
    return Math.floor((Date.now() - disconnectionStartTime) / 1000)
  }

  // Don't show anything if analysis is not running or if we never had a connection during analysis
  if (!isAnalyzing || !showDisconnectionAlert) {
    return null
  }

  const disconnectionDuration = getDisconnectionDuration()

  return (
    <div className="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 w-full max-w-md px-4">
      <Alert className="border-amber-200 bg-amber-50 text-amber-800 shadow-lg">
        <WifiOff className="h-4 w-4" />
        <AlertDescription className="flex flex-col gap-3">
          <div>
            <strong>Connection Lost During Analysis</strong>
            <p className="text-sm mt-1">
              Analysis "{analysisId?.slice(0, 8)}..." is still running on the server.
              {disconnectionDuration > 0 && (
                <span className="block text-xs text-amber-600 mt-1">
                  Disconnected for {disconnectionDuration}s
                </span>
              )}
            </p>
          </div>
          
          <div className="flex gap-2">
            {reconnectionAttempts < 3 ? (
              <div className="flex items-center gap-2 text-xs text-amber-600">
                <RefreshCw className="h-3 w-3 animate-spin" />
                Auto-reconnecting... (attempt {reconnectionAttempts + 1}/3)
              </div>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={onReconnect}
                className="text-amber-800 border-amber-300 hover:bg-amber-100"
              >
                <Wifi className="h-3 w-3 mr-1" />
                Reconnect
              </Button>
            )}
            
            {onRetryAnalysis && (
              <Button
                size="sm"
                variant="outline"
                onClick={onRetryAnalysis}
                className="text-amber-800 border-amber-300 hover:bg-amber-100"
              >
                <RefreshCw className="h-3 w-3 mr-1" />
                Retry Analysis
              </Button>
            )}
          </div>
          
          <div className="text-xs text-amber-600">
            💡 Your analysis will continue when the connection is restored
          </div>
        </AlertDescription>
      </Alert>
    </div>
  )
}

// Connection status indicator for the header
export function ConnectionStatus({ isConnected, isConnecting }: { isConnected: boolean; isConnecting: boolean }) {
  if (isConnecting) {
    return (
      <div className="flex items-center gap-2 text-sm text-blue-600">
        <RefreshCw className="h-4 w-4 animate-spin" />
        <span>Connecting...</span>
      </div>
    )
  }

  return (
    <div className={`flex items-center gap-2 text-sm ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
      {isConnected ? (
        <>
          <CheckCircle className="h-4 w-4" />
          <span>Connected</span>
        </>
      ) : (
        <>
          <AlertCircle className="h-4 w-4" />
          <span>Disconnected</span>
        </>
      )}
    </div>
  )
}