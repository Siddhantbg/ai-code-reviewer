// frontend/src/lib/websocket.ts
import { useEffect, useState, useRef, useCallback } from 'react'
import { io, Socket } from 'socket.io-client'

interface UseSocketReturn {
  socket: Socket | null
  connected: boolean
  error: string | null
  connecting: boolean
}

interface AnalysisProgress {
  analysisId: string
  progress: number
  message: string
  stage: string
}

interface AnalysisComplete {
  analysisId: string
  result: any
}

interface AnalysisError {
  analysisId: string
  error: string
}

export function useSocket(url?: string): UseSocketReturn {
  const [connected, setConnected] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const socketRef = useRef<Socket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const maxReconnectAttempts = 3
  const reconnectAttemptsRef = useRef(0)
  const isManualDisconnect = useRef(false)

  const getSocketUrl = useCallback(() => {
    const baseUrl = url || process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8000'
    
    if (baseUrl.startsWith('https://')) {
      return baseUrl.replace('https://', 'wss://') 
    } else if (baseUrl.startsWith('http://')) {
      return baseUrl.replace('http://', 'ws://')
    }
    
    return baseUrl
  }, [url])

  const connect = useCallback(() => {
    if (socketRef.current?.connected) {
      console.log('🔌 Socket already connected')
      return
    }

    if (connecting) {
      console.log('🔌 Connection already in progress')
      return
    }

    setConnecting(true)
    setError(null)
    isManualDisconnect.current = false

    const socketUrl = getSocketUrl()
    console.log('🚀 Attempting to connect to:', socketUrl)
    
    try {
      socketRef.current = io(socketUrl, {
        transports: ['websocket', 'polling'],
        upgrade: true,
        timeout: 10000,
        forceNew: false,
        autoConnect: true,
        reconnection: false,
        pingTimeout: 30000,
        pingInterval: 10000,
        closeOnBeforeunload: false,
        query: {
          clientType: 'react-frontend',
          timestamp: Date.now()
        }
      })

      const socket = socketRef.current

      socket.on('connect', () => {
        console.log('✅ WebSocket connected successfully:', socket.id)
        setConnected(true)
        setConnecting(false)
        setError(null)
        reconnectAttemptsRef.current = 0
        
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
      })

      socket.on('disconnect', (reason, details) => {
        console.log('🔌 WebSocket disconnected:', reason, details)
        setConnected(false)
        setConnecting(false)
        
        if (reason === 'io client disconnect' || isManualDisconnect.current) {
          console.log('🛑 Manual disconnect - not reconnecting')
          return
        }
        
        if (reason === 'transport close' && process.env.NODE_ENV === 'development') {
          console.log('🔧 Development mode - reduced reconnection attempts')
          return
        }
        
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(2000 * Math.pow(1.5, reconnectAttemptsRef.current), 10000)
          console.log(`🔄 Scheduling reconnection attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts} in ${delay}ms`)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++
            connect()
          }, delay)
        } else {
          setError('Connection lost. Please refresh the page to reconnect.')
        }
      })

      socket.on('connect_error', (err) => {
        console.error('❌ WebSocket connection error:', err)
        
        let errorMessage = 'Connection failed'
        
        if (err.message.includes('ECONNREFUSED')) {
          errorMessage = 'Backend server is not running. Please start the server and try again.'
        } else if (err.message.includes('CORS')) {
          errorMessage = 'CORS error: Check backend CORS configuration.'
        } else if (err.message.includes('timeout')) {
          errorMessage = 'Connection timeout: Server might be overloaded.'
        } else {
          errorMessage = `Connection error: ${err.message}`
        }
        
        setError(errorMessage)
        setConnected(false)
        setConnecting(false)
        
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(3000 * Math.pow(1.5, reconnectAttemptsRef.current), 15000)
          console.log(`🔄 Scheduling reconnection due to error in ${delay}ms`)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++
            connect()
          }, delay)
        }
      })

      socket.on('error', (err) => {
        console.error('❌ WebSocket error:', err)
        setError(`Socket error: ${err.message || err}`)
      })

      socket.on('ping', () => {
        socket.emit('pong')
      })

      socket.on('notification', (data) => {
        console.log('📢 Notification:', data)
      })

    } catch (err) {
      console.error('❌ Failed to create WebSocket connection:', err)
      setError('Failed to initialize WebSocket connection')
      setConnecting(false)
    }
  }, [getSocketUrl])

  const disconnect = useCallback(() => {
    console.log('🛑 Manually disconnecting WebSocket')
    isManualDisconnect.current = true
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    if (socketRef.current) {
      socketRef.current.disconnect()
      socketRef.current = null
    }
    
    setConnected(false)
    setConnecting(false)
    setError(null)
    reconnectAttemptsRef.current = 0
  }, [])

  useEffect(() => {
    const connectionDelay = process.env.NODE_ENV === 'development' ? 500 : 0
    
    const timeoutId = setTimeout(() => {
      connect()
    }, connectionDelay)

    return () => {
      clearTimeout(timeoutId)
      isManualDisconnect.current = true
      disconnect()
    }
  }, [connect, disconnect])

  return {
    socket: socketRef.current,
    connected,
    error,
    connecting
  }
}

// Analysis-specific hook with progress tracking
export function useAnalysisSocket() {
  const { socket, connected, error, connecting } = useSocket()
  const [analysisStatus, setAnalysisStatus] = useState<{
    [analysisId: string]: {
      status: 'pending' | 'running' | 'completed' | 'error' | 'cancelled'
      progress?: number
      message?: string
      stage?: string
      startTime?: number
    }
  }>({})

  useEffect(() => {
    if (!socket) return

    const handleProgress = (data: AnalysisProgress) => {
      console.log('📊 Analysis progress:', data)
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'running',
          progress: data.progress,
          message: data.message,
          stage: data.stage
        }
      }))
    }

    const handleComplete = (data: AnalysisComplete) => {
      console.log('✅ Analysis complete:', data.analysisId)
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'completed',
          progress: 100,
          message: 'Analysis completed successfully'
        }
      }))
    }

    const handleError = (data: AnalysisError) => {
      console.error('❌ Analysis error:', data)
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'error',
          message: data.error
        }
      }))
    }

    const handleCancelled = (data: { analysisId: string }) => {
      console.log('🛑 Analysis cancelled:', data.analysisId)
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'cancelled',
          message: 'Analysis was cancelled'
        }
      }))
    }

    socket.on('analysis_progress', handleProgress)
    socket.on('analysis_complete', handleComplete)
    socket.on('analysis_error', handleError)
    socket.on('analysis_cancelled', handleCancelled)

    return () => {
      socket.off('analysis_progress', handleProgress)
      socket.off('analysis_complete', handleComplete)
      socket.off('analysis_error', handleError)
      socket.off('analysis_cancelled', handleCancelled)
    }
  }, [socket])

  const startAnalysis = useCallback((analysisData: any) => {
    if (socket && connected) {
      console.log('🚀 Starting analysis:', analysisData.analysisId)
      socket.emit('start_analysis', analysisData)
      setAnalysisStatus(prev => ({
        ...prev,
        [analysisData.analysisId]: {
          status: 'pending',
          progress: 0,
          message: 'Initializing analysis...',
          stage: 'initialization',
          startTime: Date.now()
        }
      }))
      return true
    } else {
      console.warn('⚠️ Cannot start analysis: WebSocket not connected')
      return false
    }
  }, [socket, connected])

  const cancelAnalysis = useCallback((analysisId: string) => {
    if (socket && connected) {
      console.log('🛑 Cancelling analysis:', analysisId)
      socket.emit('cancel_analysis', { analysisId })
      
      setAnalysisStatus(prev => ({
        ...prev,
        [analysisId]: {
          ...prev[analysisId],
          status: 'cancelled',
          message: 'Cancelling analysis...'
        }
      }))
      return true
    } else {
      console.warn('⚠️ Cannot cancel analysis: WebSocket not connected')
      return false
    }
  }, [socket, connected])

  const clearAnalysisStatus = useCallback((analysisId: string) => {
    setAnalysisStatus(prev => {
      const newStatus = { ...prev }
      delete newStatus[analysisId]
      return newStatus
    })
  }, [])

  const getAnalysisStatus = useCallback((analysisId: string) => {
    return analysisStatus[analysisId] || null
  }, [analysisStatus])

  return {
    socket,
    connected,
    error,
    connecting,
    analysisStatus,
    startAnalysis,
    cancelAnalysis,
    clearAnalysisStatus,
    getAnalysisStatus
  }
}