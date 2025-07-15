# Frontend Integration Guide for Audio Analysis API

## 🔧 **API Base URL**
```
http://localhost:8000
```

## 📋 **Required Headers**
```javascript
{
    'Content-Type': 'application/json'
}
```

## 🚀 **API Endpoints**

### 1. Health Check
```javascript
// GET /health
const response = await fetch('http://localhost:8000/health');
const data = await response.json();
// Expected response: { "status": "healthy", "timestamp": "...", "active_sessions": 0 }
```

### 2. Start Audio Analysis
```javascript
// POST /start-audio-analysis
const payload = {
    room_name: "your-room-name",        // Required
    participant_identity: "user-id"     // Optional, defaults to "unknown"
};

const response = await fetch('http://localhost:8000/start-audio-analysis', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
});

const data = await response.json();
// Expected response: { "success": true, "session_id": "...", "message": "..." }
```

### 3. Stop Audio Analysis
```javascript
// POST /stop-audio-analysis
const payload = {
    session_id: "session-id-from-start-response"  // Required
};

const response = await fetch('http://localhost:8000/stop-audio-analysis', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
});

const data = await response.json();
// Expected response: { "success": true, "message": "...", "session_info": {...} }
```

### 4. Get Active Sessions
```javascript
// GET /active-sessions
const response = await fetch('http://localhost:8000/active-sessions');
const data = await response.json();
// Expected response: { "active_sessions": {...} }
```

## 🛠 **Complete React Hook Example**

```javascript
import { useState, useCallback } from 'react';

export const useAudioAnalysis = () => {
    const [isRecording, setIsRecording] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const [error, setError] = useState(null);

    const API_BASE = 'http://localhost:8000';

    const startRecording = useCallback(async (roomName, participantId) => {
        try {
            setError(null);
            
            const response = await fetch(`${API_BASE}/start-audio-analysis`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    room_name: roomName,
                    participant_identity: participantId
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.success) {
                setSessionId(data.session_id);
                setIsRecording(true);
                return data;
            } else {
                throw new Error(data.error || 'Failed to start recording');
            }
        } catch (err) {
            const errorMessage = err.message || 'Failed to start recording';
            setError(errorMessage);
            console.error('Error starting recording:', errorMessage);
            throw err;
        }
    }, []);

    const stopRecording = useCallback(async () => {
        if (!sessionId) {
            throw new Error('No active recording session');
        }

        try {
            setError(null);
            
            const response = await fetch(`${API_BASE}/stop-audio-analysis`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.success) {
                setSessionId(null);
                setIsRecording(false);
                return data;
            } else {
                throw new Error(data.error || 'Failed to stop recording');
            }
        } catch (err) {
            const errorMessage = err.message || 'Failed to stop recording';
            setError(errorMessage);
            console.error('Error stopping recording:', errorMessage);
            throw err;
        }
    }, [sessionId]);

    const checkHealth = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE}/health`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (err) {
            console.error('Health check failed:', err.message);
            throw err;
        }
    }, []);

    return {
        isRecording,
        sessionId,
        error,
        startRecording,
        stopRecording,
        checkHealth
    };
};
```

## 🔍 **Troubleshooting Steps**

### 1. Check Server Status
```bash
# In terminal
python check_status.py
```

### 2. Test API Directly
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test start recording
curl -X POST http://localhost:8000/start-audio-analysis \
  -H "Content-Type: application/json" \
  -d '{"room_name":"test","participant_identity":"user"}'
```

### 3. Common Issues & Solutions

**Error: "Failed to start recording: undefined"**
- Check if audio analysis server is running on port 8000
- Verify CORS headers are properly configured
- Check browser console for detailed error messages
- Ensure request payload has required fields

**CORS Issues**
- Server is configured to allow `localhost:3000`
- Make sure you're accessing from the correct origin
- Check browser network tab for blocked requests

**Network Errors**
- Verify server is running: `netstat -ano | findstr :8000`
- Check firewall settings
- Ensure no other service is using port 8000

### 4. Debug Your Frontend Code

Add this debugging to your frontend:

```javascript
const startRecording = async () => {
    try {
        console.log('Starting recording...');
        
        const payload = {
            room_name: roomName,
            participant_identity: participantId
        };
        
        console.log('Payload:', payload);
        
        const response = await fetch('http://localhost:8000/start-audio-analysis', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });
        
        console.log('Response status:', response.status);
        console.log('Response headers:', response.headers);
        
        const data = await response.json();
        console.log('Response data:', data);
        
        if (data.success) {
            console.log('Recording started successfully:', data.session_id);
        } else {
            console.error('Recording failed:', data.error);
        }
        
    } catch (error) {
        console.error('Network error:', error);
    }
};
```

## 📊 **Expected Server Logs**

When your frontend makes requests, you should see logs like:
```
INFO:__main__:Received start analysis request: {'room_name': 'test-room', 'participant_identity': 'test-user'}
INFO:__main__:Started audio analysis session: test-room_test-user_20250715_110506
INFO:     127.0.0.1:55312 - "POST /start-audio-analysis HTTP/1.1" 200 OK
```

## 🧪 **Test Page**

Open the included `test_frontend.html` file in your browser to test the API endpoints directly.

## 🆘 **Still Having Issues?**

1. Share the exact error message from browser console
2. Check the network tab in browser dev tools
3. Verify the server logs when making requests
4. Ensure the payload structure matches the examples above
