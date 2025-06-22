"use client"

import React, { useState, useCallback } from 'react'
import Editor from '@monaco-editor/react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Upload, FileText, Code } from 'lucide-react'
import { getLanguageFromFilename, validateCode } from '@/lib/utils'
import { codeExamples } from '@/utils/codeExamples'

interface CodeEditorProps {
  code: string
  language: string
  filename?: string
  onChange: (code: string) => void
  onLanguageChange: (language: string) => void
  onFilenameChange: (filename: string) => void
  disabled?: boolean
}

const SUPPORTED_LANGUAGES = [
  { code: 'python', name: 'Python', monacoId: 'python' },
  { code: 'javascript', name: 'JavaScript', monacoId: 'javascript' },
  { code: 'typescript', name: 'TypeScript', monacoId: 'typescript' },
  { code: 'java', name: 'Java', monacoId: 'java' },
  { code: 'cpp', name: 'C++', monacoId: 'cpp' },
  { code: 'c', name: 'C', monacoId: 'c' },
  { code: 'go', name: 'Go', monacoId: 'go' },
  { code: 'rust', name: 'Rust', monacoId: 'rust' },
  { code: 'php', name: 'PHP', monacoId: 'php' },
  { code: 'ruby', name: 'Ruby', monacoId: 'ruby' },
]


export default function CodeEditor({
  code,
  language,
  filename,
  onChange,
  onLanguageChange,
  onFilenameChange,
  disabled = false
}: CodeEditorProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedLanguage = SUPPORTED_LANGUAGES.find(lang => lang.code === language) || SUPPORTED_LANGUAGES[0]

  const handleEditorChange = useCallback((value: string | undefined) => {
    const newCode = value || ''
    const validation = validateCode(newCode)
    
    if (!validation.isValid) {
      setError(validation.error || 'Invalid code')
    } else {
      setError(null)
    }
    
    onChange(newCode)
  }, [onChange])

  const handleLanguageChange = useCallback((newLanguage: string) => {
    onLanguageChange(newLanguage)
    setError(null)
    
    // Load example code if current code is empty
    if (!code.trim()) {
      const exampleCode = EXAMPLE_CODE[newLanguage as keyof typeof EXAMPLE_CODE]
      if (exampleCode) {
        onChange(exampleCode)
      }
    }
  }, [code, onChange, onLanguageChange])

  const handleFileUpload = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      const content = e.target?.result as string
      if (content) {
        onChange(content)
        onFilenameChange(file.name)
        
        // Auto-detect language from filename
        const detectedLanguage = getLanguageFromFilename(file.name)
        if (detectedLanguage !== language) {
          onLanguageChange(detectedLanguage)
        }
      }
    }
    reader.readAsText(file)
    
    // Reset the input
    event.target.value = ''
  }, [onChange, onFilenameChange, onLanguageChange, language])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    
    const files = Array.from(e.dataTransfer.files)
    const file = files[0]
    
    if (file && file.type.startsWith('text/')) {
      const reader = new FileReader()
      reader.onload = (event) => {
        const content = event.target?.result as string
        if (content) {
          onChange(content)
          onFilenameChange(file.name)
          
          // Auto-detect language from filename
          const detectedLanguage = getLanguageFromFilename(file.name)
          if (detectedLanguage !== language) {
            onLanguageChange(detectedLanguage)
          }
        }
      }
      reader.readAsText(file)
    }
  }, [onChange, onFilenameChange, onLanguageChange, language])

  const loadExample = useCallback(() => {
    const exampleCode = EXAMPLE_CODE[language as keyof typeof EXAMPLE_CODE]
    if (exampleCode) {
      onChange(exampleCode)
      onFilenameChange(`example.${language === 'cpp' ? 'cpp' : language === 'javascript' ? 'js' : language === 'typescript' ? 'ts' : language}`)
    }
  }, [language, onChange, onFilenameChange])

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Code className="h-5 w-5" />
            Code Editor
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadExample}
              disabled={disabled}
            >
              <FileText className="h-4 w-4 mr-2" />
              Load Example
            </Button>
            <label htmlFor="file-upload">
              <Button
                variant="outline"
                size="sm"
                asChild
                disabled={disabled}
              >
                <span>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload File
                </span>
              </Button>
            </label>
            <input
              id="file-upload"
              type="file"
              accept=".py,.js,.ts,.tsx,.jsx,.java,.cpp,.cxx,.cc,.c,.h,.hpp,.go,.rs,.php,.rb"
              onChange={handleFileUpload}
              className="hidden"
              disabled={disabled}
            />
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label htmlFor="language-select" className="text-sm font-medium">
              Language:
            </label>
            <Select
              value={language}
              onValueChange={handleLanguageChange}
              disabled={disabled}
            >
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Select language" />
              </SelectTrigger>
              <SelectContent>
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <SelectItem key={lang.code} value={lang.code}>
                    {lang.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          {filename && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <FileText className="h-4 w-4" />
              <span>{filename}</span>
            </div>
          )}
        </div>
        
        {error && (
          <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
            {error}
          </div>
        )}
      </CardHeader>
      
      <CardContent>
        <div
          className={`relative border rounded-lg overflow-hidden transition-colors ${
            isDragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {isDragOver && (
            <div className="absolute inset-0 bg-blue-100 bg-opacity-50 flex items-center justify-center z-10">
              <div className="text-blue-600 font-medium">
                Drop your code file here
              </div>
            </div>
          )}
          
          <Editor
            height="400px"
            language={selectedLanguage.monacoId}
            value={code}
            onChange={handleEditorChange}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              lineNumbers: 'on',
              roundedSelection: false,
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 2,
              insertSpaces: true,
              wordWrap: 'on',
              readOnly: disabled,
              theme: 'vs-light'
            }}
            loading={
              <div className="flex items-center justify-center h-96">
                <div className="text-gray-500">Loading editor...</div>
              </div>
            }
          />
        </div>
        
        <div className="mt-2 text-xs text-muted-foreground">
          {code.length} characters • {code.split('\n').length} lines
        </div>
      </CardContent>
    </Card>
  )
}