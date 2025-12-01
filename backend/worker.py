#!/usr/bin/env python
"""
RQ Worker script for processing background jobs.
Run this script to start a worker that processes agent runs from the queue.
"""
import logging
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq import Worker
from app.queue import get_redis_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    redis_conn = get_redis_connection()
    
    logger.info("Starting RQ worker...")
    logger.info("Listening for jobs on 'default' queue")
    
    # RQ new API: pass connection directly to Worker
    worker = Worker(['default'], connection=redis_conn)
    worker.work()

