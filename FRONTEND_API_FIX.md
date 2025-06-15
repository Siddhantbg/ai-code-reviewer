# Frontend API Call Fix

The frontend is sending the wrong data format to the `/analyze` endpoint.

## Current Issue:
Frontend is sending:
```json
{
  "code": "...",
  "language": "python"
}
```

But backend expects:
```json
{
  "analysis_type": "full",
  "code": "...",
  "filename": "code.py",
  "include_explanations": true,
  "include_suggestions": true,
  "language": "python",
  "severity_threshold": "low"
}
```

## Fix Required:
Update the frontend API call in `frontend/src/lib/api.ts` or wherever the analyze call is made.

### Before:
```typescript
const response = await fetch('/api/v1/analyze', {
  method: 'POST',
  body: JSON.stringify({
    code: code,
    language: language
  })
});
```

### After:
```typescript
const response = await fetch('/api/v1/analyze', {
  method: 'POST',
  body: JSON.stringify({
    analysis_type: "full",
    code: code,
    filename: `code.${getFileExtension(language)}`,
    include_explanations: true,
    include_suggestions: true,
    language: language,
    severity_threshold: "low"
  })
});
```

This will match the backend schema and allow the AI analysis to work from the frontend.
