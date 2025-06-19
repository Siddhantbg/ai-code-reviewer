import os
from celery import Celery

# Configure Celery
celery = Celery(
    'app.worker',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
)

# Configure Celery settings
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes
    worker_max_tasks_per_child=200,
    worker_prefetch_multiplier=4
)

# Import tasks to ensure they're registered
from app.services.static_analysis_service import analyze_code_task

# Define tasks that can be called from the application
@celery.task(name='app.worker.analyze_code_background')
def analyze_code_background(code: str, language: str, rules_config: dict = None):
    """Background task for code analysis."""
    from app.services.static_analysis_service import StaticAnalysisOrchestrator
    
    # Create orchestrator instance
    orchestrator = StaticAnalysisOrchestrator()
    
    # Run analysis synchronously in the background
    import asyncio
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        orchestrator.analyze_code(code, language, rules_config)
    )
    
    return result