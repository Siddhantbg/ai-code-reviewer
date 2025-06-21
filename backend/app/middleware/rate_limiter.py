# backend/app/middleware/rate_limiter.py
import time
import asyncio
import logging
from typing import Dict, Any, Optional
from collections import defaultdict, deque
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiting middleware for API endpoints and WebSocket connections"""
    
    def __init__(self):
        # Rate limiting configurations
        self.api_limits = {
            'default': {'requests': 60, 'window': 60},  # 60 requests per minute
            'analysis': {'requests': 10, 'window': 60},  # 10 analyses per minute
            'health': {'requests': 120, 'window': 60},   # Health checks more permissive
        }
        
        self.websocket_limits = {
            'connect': {'requests': 5, 'window': 60},    # 5 connections per minute
            'analysis': {'requests': 15, 'window': 300}, # 15 analyses per 5 minutes
        }
        
        # Storage for request tracking
        self.api_requests = defaultdict(lambda: deque())
        self.websocket_requests = defaultdict(lambda: deque())
        
        # Connection tracking
        self.connection_attempts = defaultdict(lambda: deque())
        self.blocked_ips = {}
        
        # Cleanup settings
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
        
    def get_client_id(self, request: Request) -> str:
        """Extract client identifier from request"""
        # Try to get real IP from headers (for reverse proxy setups)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
            
        # Fallback to client host
        client_host = getattr(request.client, 'host', 'unknown')
        return client_host
        
    def is_ip_blocked(self, client_id: str) -> bool:
        """Check if IP is temporarily blocked"""
        if client_id in self.blocked_ips:
            block_until = self.blocked_ips[client_id]
            if time.time() < block_until:
                return True
            else:
                # Block expired, remove it
                del self.blocked_ips[client_id]
        return False
        
    def block_ip(self, client_id: str, duration: int = 300):
        """Temporarily block an IP for specified duration (seconds)"""
        block_until = time.time() + duration
        self.blocked_ips[client_id] = block_until
        logger.warning(f"🚫 Temporarily blocked IP {client_id} for {duration} seconds")
        
    def check_api_rate_limit(self, request: Request, endpoint_type: str = 'default') -> bool:
        """Check if API request is within rate limits"""
        client_id = self.get_client_id(request)
        
        # Check if IP is blocked
        if self.is_ip_blocked(client_id):
            raise HTTPException(
                status_code=429,
                detail="IP temporarily blocked due to rate limit violations"
            )
        
        current_time = time.time()
        limits = self.api_limits.get(endpoint_type, self.api_limits['default'])
        window_size = limits['window']
        max_requests = limits['requests']
        
        # Get request history for this client
        request_times = self.api_requests[client_id]
        
        # Remove old requests outside the window
        while request_times and current_time - request_times[0] > window_size:
            request_times.popleft()
            
        # Check if limit exceeded
        if len(request_times) >= max_requests:
            logger.warning(f"⚠️ Rate limit exceeded for {client_id} on {endpoint_type}: {len(request_times)}/{max_requests}")
            
            # Block IP if severely violating limits
            if len(request_times) > max_requests * 1.5:
                self.block_ip(client_id, duration=600)  # 10 minute block
                
            return False
            
        # Add current request
        request_times.append(current_time)
        return True
        
    def check_websocket_rate_limit(self, client_id: str, operation: str = 'connect') -> bool:
        """Check if WebSocket operation is within rate limits"""
        # Check if IP is blocked
        if self.is_ip_blocked(client_id):
            logger.warning(f"🚫 WebSocket operation blocked for {client_id}: IP is blocked")
            return False
            
        current_time = time.time()
        limits = self.websocket_limits.get(operation, self.websocket_limits['connect'])
        window_size = limits['window']
        max_requests = limits['requests']
        
        # Get request history for this client and operation
        request_key = f"{client_id}_{operation}"
        request_times = self.websocket_requests[request_key]
        
        # Remove old requests outside the window
        while request_times and current_time - request_times[0] > window_size:
            request_times.popleft()
            
        # Check if limit exceeded
        if len(request_times) >= max_requests:
            logger.warning(f"⚠️ WebSocket rate limit exceeded for {client_id} on {operation}: {len(request_times)}/{max_requests}")
            
            # Block IP for repeated violations
            if len(request_times) > max_requests * 2:
                self.block_ip(client_id, duration=900)  # 15 minute block
                
            return False
            
        # Add current request
        request_times.append(current_time)
        return True
        
    def track_connection_attempt(self, client_id: str) -> bool:
        """Track connection attempts and detect abuse"""
        current_time = time.time()
        attempts = self.connection_attempts[client_id]
        
        # Remove old attempts (last 5 minutes)
        while attempts and current_time - attempts[0] > 300:
            attempts.popleft()
            
        # Check for connection flooding
        if len(attempts) > 20:  # More than 20 connection attempts in 5 minutes
            logger.warning(f"🚨 Connection flooding detected from {client_id}: {len(attempts)} attempts")
            self.block_ip(client_id, duration=1800)  # 30 minute block
            return False
            
        attempts.append(current_time)
        return True
        
    async def cleanup_old_data(self):
        """Clean up old tracking data"""
        current_time = time.time()
        
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
            
        logger.debug("🧹 Cleaning up old rate limit data")
        
        # Clean API requests
        for client_id in list(self.api_requests.keys()):
            request_times = self.api_requests[client_id]
            # Remove requests older than 1 hour
            while request_times and current_time - request_times[0] > 3600:
                request_times.popleft()
            # Remove empty entries
            if not request_times:
                del self.api_requests[client_id]
                
        # Clean WebSocket requests
        for request_key in list(self.websocket_requests.keys()):
            request_times = self.websocket_requests[request_key]
            while request_times and current_time - request_times[0] > 3600:
                request_times.popleft()
            if not request_times:
                del self.websocket_requests[request_key]
                
        # Clean connection attempts
        for client_id in list(self.connection_attempts.keys()):
            attempts = self.connection_attempts[client_id]
            while attempts and current_time - attempts[0] > 3600:
                attempts.popleft()
            if not attempts:
                del self.connection_attempts[client_id]
                
        # Clean expired IP blocks
        for client_id in list(self.blocked_ips.keys()):
            if current_time >= self.blocked_ips[client_id]:
                del self.blocked_ips[client_id]
                logger.info(f"✅ Unblocked IP {client_id}")
                
        self.last_cleanup = current_time
        
    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics"""
        current_time = time.time()
        
        # Count active clients
        active_api_clients = len([k for k, v in self.api_requests.items() if v])
        active_ws_clients = len([k for k, v in self.websocket_requests.items() if v])
        
        # Count blocked IPs
        active_blocks = len([ip for ip, block_time in self.blocked_ips.items() if current_time < block_time])
        
        return {
            'timestamp': current_time,
            'limits': {
                'api_limits': self.api_limits,
                'websocket_limits': self.websocket_limits
            },
            'active_tracking': {
                'api_clients': active_api_clients,
                'websocket_clients': active_ws_clients,
                'total_tracked_api_requests': sum(len(v) for v in self.api_requests.values()),
                'total_tracked_ws_requests': sum(len(v) for v in self.websocket_requests.values())
            },
            'security': {
                'blocked_ips': active_blocks,
                'blocked_ip_list': [ip for ip, block_time in self.blocked_ips.items() if current_time < block_time]
            },
            'last_cleanup': self.last_cleanup
        }

# Global rate limiter instance
rate_limiter = RateLimiter()

# Middleware function for FastAPI
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware for FastAPI"""
    try:
        # Clean up old data periodically
        await rate_limiter.cleanup_old_data()
        
        # Determine endpoint type for rate limiting
        path = request.url.path
        if '/api/v1/analysis' in path:
            endpoint_type = 'analysis'
        elif '/health' in path or '/api/health' in path:
            endpoint_type = 'health'
        else:
            endpoint_type = 'default'
            
        # Check rate limits
        if not rate_limiter.check_api_rate_limit(request, endpoint_type):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )
            
        # Process request
        response = await call_next(request)
        return response
        
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail}
        )
    except Exception as e:
        logger.error(f"❌ Error in rate limiting middleware: {e}")
        # Allow request to proceed if rate limiting fails
        return await call_next(request)