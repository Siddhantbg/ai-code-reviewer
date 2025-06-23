"use client"

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  AlertCircle,
  Info,
  Clock,
  BarChart3,
  FileText,
  Lightbulb,
  Download,
  RefreshCw,
  Play
} from 'lucide-react'
import { CodeAnalysisResponse, CodeIssue } from '@/lib/api'

interface AnalysisResultsProps {
  analysis: CodeAnalysisResponse
  onExport?: () => void
  onTryAgain?: () => void
  onAnalyzeAgain?: () => void
  isRetrying?: boolean
}

const getSeverityIcon = (severity: string) => {
  switch (severity.toLowerCase()) {
    case 'critical':
      return <XCircle className="h-4 w-4 text-red-600" />
    case 'high':
      return <AlertTriangle className="h-4 w-4 text-red-500" />
    case 'medium':
      return <AlertCircle className="h-4 w-4 text-yellow-500" />
    case 'low':
      return <Info className="h-4 w-4 text-blue-500" />
    default:
      return <Info className="h-4 w-4 text-gray-500" />
  }
}

const getSeverityBadgeVariant = (severity: string) => {
  switch (severity.toLowerCase()) {
    case 'critical':
      return 'critical'
    case 'high':
      return 'error'
    case 'medium':
      return 'warning'
    case 'low':
      return 'secondary'
    default:
      return 'outline'
  }
}

const getTypeIcon = (type: string) => {
  switch (type.toLowerCase()) {
    case 'bug':
      return <XCircle className="h-4 w-4 text-red-500" />
    case 'security':
      return <AlertTriangle className="h-4 w-4 text-red-600" />
    case 'performance':
      return <BarChart3 className="h-4 w-4 text-orange-500" />
    case 'style':
      return <FileText className="h-4 w-4 text-blue-500" />
    case 'maintainability':
      return <Lightbulb className="h-4 w-4 text-green-500" />
    default:
      return <Info className="h-4 w-4 text-gray-500" />
  }
}

const getScoreColor = (score: number) => {
  if (score >= 8) return 'text-green-600'
  if (score >= 6) return 'text-yellow-600'
  if (score >= 4) return 'text-orange-600'
  return 'text-red-600'
}

const getScoreBackground = (score: number) => {
  if (score >= 8) return 'bg-green-100'
  if (score >= 6) return 'bg-yellow-100'
  if (score >= 4) return 'bg-orange-100'
  return 'bg-red-100'
}

function IssueCard({ issue }: { issue: CodeIssue }) {
  return (
    <Card className="mb-4">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            {getSeverityIcon(issue.severity)}
            <div>
              <h4 className="font-semibold text-sm">{issue.title}</h4>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant={getSeverityBadgeVariant(issue.severity) as 'default' | 'secondary' | 'destructive' | 'outline' | 'warning' | 'error' | 'critical' | 'success'}>
                  {issue.severity.toUpperCase()}
                </Badge>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  {getTypeIcon(issue.type)}
                  <span>{issue.type.charAt(0).toUpperCase() + issue.type.slice(1)}</span>
                </div>
                {issue.line_number && (
                  <span className="text-xs text-muted-foreground">
                    Line {issue.line_number}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="text-xs text-muted-foreground">
            {Math.round(issue.confidence * 100)}% confidence
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        <p className="text-sm text-gray-700 mb-3">{issue.description}</p>
        
        {issue.code_snippet && (
          <div className="mb-3">
            <h5 className="text-xs font-medium text-gray-600 mb-1">Code:</h5>
            <pre className="bg-gray-100 p-2 rounded text-xs overflow-x-auto">
              <code>{issue.code_snippet}</code>
            </pre>
          </div>
        )}
        
        {issue.suggestion && (
          <div className="mb-3">
            <h5 className="text-xs font-medium text-gray-600 mb-1">Suggestion:</h5>
            <p className="text-sm text-green-700 bg-green-50 p-2 rounded">
              {issue.suggestion}
            </p>
          </div>
        )}
        
        {issue.explanation && (
          <div>
            <h5 className="text-xs font-medium text-gray-600 mb-1">Explanation:</h5>
            <p className="text-sm text-gray-600">{issue.explanation}</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function AnalysisResults({ analysis, onExport, onTryAgain, onAnalyzeAgain, isRetrying }: AnalysisResultsProps) {
  // Debug logging to track component rendering
  console.log('🔍 AnalysisResults component rendered with analysis:', !!analysis, analysis?.analysis_id)
  
  // Early return with error state if analysis is missing
  if (!analysis) {
    return (
      <div className="space-y-6">
        <Card>
          <CardContent className="p-8">
            <div className="text-center">
              <AlertTriangle className="h-12 w-12 mx-auto mb-4 text-yellow-500" />
              <h3 className="text-lg font-medium mb-2">No Analysis Data</h3>
              <p className="text-sm text-gray-500">
                Analysis data is not available. Please try running the analysis again.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Safe destructuring with fallbacks matching backend structure
  const {
    summary = {
      total_issues: 0,
      critical_issues: 0,
      high_issues: 0,
      medium_issues: 0,
      low_issues: 0,
      overall_score: 0,
      recommendation: 'No recommendation available'
    },
    metrics = {
      lines_of_code: 0,
      complexity_score: 0,
      maintainability_index: 0,
      test_coverage: null,
      duplication_percentage: 0
    },
    issues = [],
    suggestions = [],
    processing_time_ms = 0
  } = analysis

  // Ensure processing_time_ms is a valid number
  const safeProcessingTime = typeof processing_time_ms === 'number' && !isNaN(processing_time_ms) ? processing_time_ms : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Analysis Results</h2>
          <p className="text-muted-foreground">
            Analysis completed in {safeProcessingTime.toFixed(1)}ms
          </p>
        </div>
        <div className="flex items-center gap-2">
          {onTryAgain && (
            <Button 
              variant="outline" 
              onClick={onTryAgain}
              disabled={isRetrying}
              className="flex items-center gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${isRetrying ? 'animate-spin' : ''}`} />
              Try Again
            </Button>
          )}
          {/* Removed the Analyze Again button as requested */}
          {onExport && (
            <Button variant="outline" onClick={onExport}>
              <Download className="h-4 w-4 mr-2" />
              Export Report
            </Button>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Overall Score</p>
                <p className={`text-2xl font-bold ${getScoreColor(summary?.overall_score || 0)}`}>
                  {(summary?.overall_score || 0).toFixed(1)}/10
                </p>
              </div>
              <div className={`p-2 rounded-full ${getScoreBackground(summary?.overall_score || 0)}`}>
                {(summary?.overall_score || 0) >= 7 ? (
                  <CheckCircle className={`h-6 w-6 ${getScoreColor(summary?.overall_score || 0)}`} />
                ) : (
                  <AlertTriangle className={`h-6 w-6 ${getScoreColor(summary?.overall_score || 0)}`} />
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Issues</p>
                <p className="text-2xl font-bold">{summary?.total_issues || 0}</p>
              </div>
              <div className="p-2 rounded-full bg-blue-100">
                <AlertCircle className="h-6 w-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Lines of Code</p>
                <p className="text-2xl font-bold">{metrics?.lines_of_code || 0}</p>
              </div>
              <div className="p-2 rounded-full bg-green-100">
                <FileText className="h-6 w-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Complexity</p>
                <p className="text-2xl font-bold">{(metrics?.complexity_score || 0).toFixed(1)}</p>
              </div>
              <div className="p-2 rounded-full bg-purple-100">
                <BarChart3 className="h-6 w-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Issue Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Issue Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{summary?.critical_issues || 0}</div>
              <div className="text-sm text-muted-foreground">Critical</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-500">{summary?.high_issues || 0}</div>
              <div className="text-sm text-muted-foreground">High</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-500">{summary?.medium_issues || 0}</div>
              <div className="text-sm text-muted-foreground">Medium</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-500">{summary?.low_issues || 0}</div>
              <div className="text-sm text-muted-foreground">Low</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recommendation */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Recommendation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-700">{summary?.recommendation || 'No recommendation available'}</p>
        </CardContent>
      </Card>

      {/* Code Metrics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Code Metrics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="text-sm font-medium text-muted-foreground">Maintainability Index</div>
              <div className="text-xl font-semibold">{(metrics?.maintainability_index || 0).toFixed(1)}/100</div>
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Complexity Score</div>
              <div className="text-xl font-semibold">{(metrics?.complexity_score || 0).toFixed(1)}</div>
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">Code Duplication</div>
              <div className="text-xl font-semibold">{(metrics?.duplication_percentage || 0).toFixed(1)}%</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Issues List */}
      {Array.isArray(issues) && issues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Issues Found ({issues.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {issues.map((issue) => (
                issue && issue.id ? <IssueCard key={issue.id} issue={issue} /> : null
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Suggestions */}
      {Array.isArray(suggestions) && suggestions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5" />
              Improvement Suggestions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {suggestions.map((suggestion, index) => (
                suggestion && typeof suggestion === 'string' ? (
                  <li key={index} className="flex items-start gap-2">
                    <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0" />
                    <span className="text-sm text-gray-700">{suggestion}</span>
                  </li>
                ) : null
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Analysis Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="h-5 w-5" />
            Analysis Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium">Analysis ID:</span> {analysis?.analysis_id || 'N/A'}
            </div>
            <div>
              <span className="font-medium">Language:</span> {analysis?.language || 'Unknown'}
            </div>
            <div>
              <span className="font-medium">Timestamp:</span> {analysis?.timestamp ? new Date(analysis.timestamp).toLocaleString() : 'N/A'}
            </div>
            <div>
              <span className="font-medium">Processing Time:</span> {safeProcessingTime.toFixed(1)}ms
            </div>
            {analysis?.filename && (
              <div>
                <span className="font-medium">Filename:</span> {analysis.filename}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}