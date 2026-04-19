# Azure opentelemetry integration 

import os
import logging
from azure.monitor.opentelemetry import configure_azure_monitor

# create a dedicated logger
logger = logging.getLogger("youtube-add-compliance-checker-telemetry")

def setup_telemetry():
    '''
    Initializes Azure Monitor OpenTelemetry
    Tracks: HTTP Requests, Database Queries, errors, performance metrics, etc.
    Sends this data to Azure Monitor

    It Auto-Captures every API request
    No need to manually log each endpoint 
    '''

    # retrieve the connection string
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    # check if configured
    if not connection_string:
        logger.warning("Application Insights connection string (instrumentation key) not found. Telemetry is DISABLED.")
        return
    # configure the azure monitor
    try:
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="youtube-add-compliance-checker-tracer"
        )
        logger.info("Azure Monitor Tracking Enabled and Connected")
    except Exception as e:
        logger.error(f"Failed to initialize Azure Monitor {str(e)}")

