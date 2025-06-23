// frontend/src/lib/api.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Types for API responses
export interface CodeIssue {
  id: string
  type: string  // Maps to IssueType enum: 'bug' | 'security' | 'performance' | 'style' | 'maintainability' | 'complexity'
  severity: 'critical' | 'high' | 'medium' | 'low'
  title: string
  description: string
  line_number?: number
  column_number?: number
  code_snippet?: string
  suggestion?: string
  explanation?: string
  confidence: number  // Required in backend with default 0.8
}

export interface CodeAnalysisResponse {
  analysis_id: string
  timestamp: string  // ISO datetime string from backend datetime serialization
  language: string
  filename?: string
  processing_time_ms: number
  summary: {
    total_issues: number
    critical_issues: number
    high_issues: number
    medium_issues: number
    low_issues: number
    overall_score: number  // 0-10 scale
    recommendation: string  // Required in backend
  }
  issues: CodeIssue[]
  metrics: {
    lines_of_code: number
    complexity_score: number
    maintainability_index: number  // 0-100 scale
    test_coverage?: number | null   // Optional in backend
    duplication_percentage: number
  }
  suggestions: string[]
}

export interface HealthResponse {
  status: string
  message: string
  version: string
  ai_model_loaded: boolean
  ai_model_path?: string
  websocket?: string
  active_analyses?: number
}

// Analysis persistence types
export interface AnalysisInfo {
  analysis_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: number
  completed_at?: number
  has_result: boolean
  retrieval_count: number
}

export interface PersistenceResponse {
  success: boolean
  session_id?: string
  analyses?: AnalysisInfo[]
  count?: number
  retrieved_at: string
}

export interface AnalysisResultResponse {
  success: boolean
  analysis_id: string
  result?: CodeAnalysisResponse
  retrieved_at: string
}

export interface AnalysisStatusResponse {
  success: boolean
  analysis_id: string
  available: boolean
  status: string
  created_at?: number
  completed_at?: number
  retrieval_count?: number
  max_retrievals?: number
  message: string
  websocket?: string
  active_analyses?: number
}

export interface AnalysisRequest {
  code: string
  language: string
  filename?: string
  analysis_type?: 'full' | 'bugs_only' | 'security_only' | 'performance_only' | 'style_only'
  include_suggestions?: boolean
  include_explanations?: boolean
  severity_threshold?: 'critical' | 'high' | 'medium' | 'low'
  config?: any
}

// API Client class
class APIClient {
  private baseURL: string

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      // Add timeout to prevent hanging requests
      signal: AbortSignal.timeout(10000), // 10 second timeout
      ...options,
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        // Handle specific HTTP status codes
        if (response.status === 404) {
          throw new Error(`Endpoint not found: ${endpoint}`)
        }
        if (response.status === 500) {
          throw new Error(`Server error: Internal server error`)
        }
        if (response.status === 503) {
          throw new Error(`Server unavailable: Service temporarily unavailable`)
        }
        
        const errorData = await response.json().catch(() => ({}))
        throw new Error(
          errorData.detail || 
          errorData.message || 
          `HTTP ${response.status}: ${response.statusText}`
        )
      }

      const data = await response.json()
      return data
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('Network error: Unable to connect to the server. Please check if the backend is running.')
      }
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Request timeout: The server took too long to respond.')
      }
      throw error
    }
  }

  // Health check endpoint
  async healthCheck(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health')
  }

  // Alternative health check
  async apiHealthCheck(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/api/health')
  }

  // Code analysis endpoint (REST API fallback)
  async analyzeCode(data: AnalysisRequest): Promise<CodeAnalysisResponse> {
    return this.request<CodeAnalysisResponse>('/api/v1/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Get supported languages
  async getSupportedLanguages(): Promise<string[]> {
    try {
      return this.request<string[]>('/api/v1/languages')
    } catch (error) {
      // Fallback to default languages if endpoint doesn't exist
      console.warn('Could not fetch supported languages, using defaults:', error)
      return ['python', 'javascript', 'typescript', 'java', 'cpp', 'c', 'go', 'rust', 'php']
    }
  }

  // Get analysis history (if implemented)
  async getAnalysisHistory(limit: number = 10): Promise<any[]> {
    try {
      return this.request<any[]>(`/api/v1/history?limit=${limit}`)
    } catch (error) {
      console.warn('Analysis history endpoint not available:', error)
      return []
    }
  }

  // Get analysis by ID (if implemented)
  async getAnalysis(analysisId: string): Promise<CodeAnalysisResponse> {
    return this.request<CodeAnalysisResponse>(`/api/v1/analysis/${analysisId}`)
  }

  // Export analysis report
  async exportAnalysis(analysisId: string, format: 'json' | 'pdf' | 'csv' = 'json'): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/api/v1/analysis/${analysisId}/export?format=${format}`, {
      method: 'GET',
      headers: {
        'Accept': format === 'json' ? 'application/json' : 
                 format === 'pdf' ? 'application/pdf' : 'text/csv'
      }
    })

    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`)
    }

    return response.blob()
  }

  // ====== ANALYSIS PERSISTENCE METHODS ======

  // Get all analysis results for a client session
  async getClientAnalyses(clientSessionId: string, limit: number = 20): Promise<PersistenceResponse> {
    try {
      return await this.request<PersistenceResponse>(`/api/v1/persistence/analyses/${clientSessionId}?limit=${limit}`)
    } catch (error) {
      // Fallback for 404 errors - return empty response to prevent crashes
      if (error instanceof Error && (error.message.includes('404') || error.message.includes('Not Found'))) {
        console.warn('⚠️ Client analyses endpoint not found, returning empty result')
        return {
          success: false,
          analyses: [],
          count: 0,
          retrieved_at: new Date().toISOString()
        }
      }
      throw error
    }
  }

  // Get a specific analysis result
  async getAnalysisResult(analysisId: string, clientSessionId?: string): Promise<AnalysisResultResponse> {
    const params = clientSessionId ? `?client_session_id=${clientSessionId}` : ''
    try {
      return await this.request<AnalysisResultResponse>(`/api/v1/persistence/analyses/${analysisId}${params}`)
    } catch (error) {
      // Fallback for 404 errors - return unsuccessful response instead of throwing
      if (error instanceof Error && (error.message.includes('404') || error.message.includes('Not Found'))) {
        console.warn(`⚠️ Analysis result not found: ${analysisId}`)
        return {
          success: false,
          analysis_id: analysisId,
          retrieved_at: new Date().toISOString()
        }
      }
      throw error
    }
  }

  // Check if an analysis result is available
  async checkAnalysisStatus(analysisId: string, clientSessionId?: string): Promise<AnalysisStatusResponse> {
    const params = clientSessionId ? `?client_session_id=${clientSessionId}` : ''
    try {
      return await this.request<AnalysisStatusResponse>(`/api/v1/persistence/analysis/${analysisId}/check${params}`, {
        method: 'POST'
      })
    } catch (error) {
      // Fallback for 404 errors
      if (error instanceof Error && (error.message.includes('404') || error.message.includes('Not Found'))) {
        console.warn(`⚠️ Analysis status check endpoint not found: ${analysisId}`)
        return {
          success: false,
          analysis_id: analysisId,
          available: false,
          status: 'not_found',
          message: 'Analysis status endpoint not available'
        }
      }
      throw error
    }
  }

  // Delete an analysis result
  async deleteAnalysisResult(analysisId: string, clientSessionId?: string): Promise<{success: boolean, message: string}> {
    const params = clientSessionId ? `?client_session_id=${clientSessionId}` : ''
    try {
      return await this.request<{success: boolean, message: string}>(`/api/v1/persistence/analysis/${analysisId}${params}`, {
        method: 'DELETE'
      })
    } catch (error) {
      // Fallback for 404 errors
      if (error instanceof Error && (error.message.includes('404') || error.message.includes('Not Found'))) {
        console.warn(`⚠️ Analysis deletion endpoint not found: ${analysisId}`)
        return {
          success: false,
          message: 'Analysis deletion endpoint not available'
        }
      }
      throw error
    }
  }

  // Get persistence stats
  async getPersistenceStats(): Promise<{success: boolean, stats: any}> {
    try {
      return await this.request<{success: boolean, stats: any}>('/api/v1/persistence/stats')
    } catch (error) {
      // Fallback for 404 errors - return empty stats to prevent crashes
      if (error instanceof Error && (error.message.includes('404') || error.message.includes('Not Found'))) {
        console.warn('⚠️ Persistence stats endpoint not found, returning empty stats')
        return {
          success: false,
          stats: {
            total_results: 0,
            total_sessions: 0,
            storage_size_bytes: 0,
            storage_size_mb: 0.0,
            storage_limit_mb: 500,
            status_counts: {},
            last_cleanup: 0
          }
        }
      }
      throw error
    }
  }

  // Trigger cleanup of expired results
  async triggerCleanup(): Promise<{success: boolean, message: string}> {
    try {
      return await this.request<{success: boolean, message: string}>('/api/v1/persistence/cleanup', {
        method: 'POST'
      })
    } catch (error) {
      // Fallback for 404 errors
      if (error instanceof Error && (error.message.includes('404') || error.message.includes('Not Found'))) {
        console.warn('⚠️ Cleanup endpoint not found')
        return {
          success: false,
          message: 'Cleanup endpoint not available'
        }
      }
      throw error
    }
  }

  // Test connection
  async testConnection(): Promise<boolean> {
    try {
      await this.healthCheck()
      return true
    } catch (error) {
      console.error('Connection test failed:', error)
      return false
    }
  }

  // Get server status
  async getServerStatus(): Promise<{
    online: boolean
    websocket: boolean
    aiModel: boolean
    activeAnalyses: number
  }> {
    try {
      const health = await this.healthCheck()
      return {
        online: health.status === 'healthy',
        websocket: health.websocket === 'enabled',
        aiModel: health.ai_model_loaded || false,
        activeAnalyses: health.active_analyses || 0
      }
    } catch (error) {
      return {
        online: false,
        websocket: false,
        aiModel: false,
        activeAnalyses: 0
      }
    }
  }
}

// Create and export the API client instance
export const apiClient = new APIClient()
export const api = apiClient // Export as 'api' for compatibility

// Export the class for custom instances
export default APIClient

// Utility function to check if backend is available
export async function checkBackendAvailability(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      // Add timeout
      signal: AbortSignal.timeout(5000)
    })
    return response.ok
  } catch (error) {
    console.error('Backend availability check failed:', error)
    return false
  }
}

// Utility function to get API base URL
export function getAPIBaseURL(): string {
  return API_BASE_URL
}

// Error types for better error handling
export class APIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public code?: string
  ) {
    super(message)
    this.name = 'APIError'
  }
}

export class NetworkError extends Error {
  constructor(message: string = 'Network connection failed') {
    super(message)
    this.name = 'NetworkError'
  }
}