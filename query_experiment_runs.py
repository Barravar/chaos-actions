#!/usr/bin/env python3
"""Temporary script to query experiment runs using Litmus GraphQL API."""

import os
import sys
import json
from datetime import datetime

# Add parent directory to path to import src package
sys.path.insert(0, os.path.dirname(__file__))

from src.config import LitmusConfig, LoggerConfig, RetryConfig
from src.client import LitmusClient
from src.queries import LitmusGraphQLQueries
from src.exceptions import LitmusGraphQLError

# Initialize logger
logger = LoggerConfig.setup_logger()

# Load configuration from environment variables
# For querying, we only need basic auth info - use dummy values for optional fields
config = LitmusConfig(
    litmus_url=os.getenv("LITMUS_URL", ""),
    litmus_username=os.getenv("LITMUS_USERNAME", ""),
    litmus_password=os.getenv("LITMUS_PASSWORD", ""),
    litmus_project=os.getenv("LITMUS_PROJECT", ""),
    litmus_environment=os.getenv("LITMUS_ENVIRONMENT", "dummy-env"),  # Not needed for query
    litmus_infra=os.getenv("LITMUS_INFRA", "dummy-infra"),  # Not needed for query
    experiment_name=os.getenv("EXPERIMENT_NAME", ""),
    experiment_manifest=os.getenv("EXPERIMENT_MANIFEST", "dummy-manifest"),  # Not needed for query
    run_experiment=False
)

# Retry configuration
retry_config = RetryConfig()


def get_project_id(client: LitmusClient, project_name: str) -> str:
    """Retrieve the project ID for a given project name."""
    try:
        response = client._rest_call(method="GET", path="/list_projects")
        projects = response.json()
        
        if "data" not in projects or "projects" not in projects.get("data", {}):
            raise Exception("Invalid response structure from Litmus REST API")
        
        project_data = projects.get("data", {}).get("projects", [])
        project_info = next((p for p in project_data if p.get("name") == project_name), None)
        
        if not project_info or "projectID" not in project_info:
            raise Exception(f"Project {project_name} not found")
        
        return project_info.get("projectID")
    except Exception as e:
        logger.error(f"Error retrieving project ID: {e}")
        raise


def list_experiment_runs(client: LitmusClient, project_id: str, experiment_id: str = None, limit: int = 10):
    """
    List experiment runs with optional filtering.
    
    Args:
        client: LitmusClient instance
        project_id: Project ID
        experiment_id: Optional experiment ID to filter runs
        limit: Maximum number of runs to retrieve (default: 10)
    """
    # Build request variables
    request = {
        "sort": {"field": "TIME", "ascending": False},
        "pagination": {"page": 0, "limit": limit}
    }
    
    # Add experiment ID filter if provided
    if experiment_id:
        request["experimentIDs"] = [experiment_id]
    
    variables = {
        "projectID": project_id,
        "request": request
    }
    
    try:
        logger.info(f"Querying experiment runs for project {project_id}...")
        response = client._graphql_call(
            query=LitmusGraphQLQueries.LIST_EXPERIMENT_RUN,
            variables=variables
        )
        
        experiment_runs = response.get("listExperimentRun", {}).get("experimentRuns", [])
        total_runs = response.get("listExperimentRun", {}).get("totalNoOfExperimentRuns", 0)
        
        logger.info(f"Found {total_runs} total experiment runs. Showing {len(experiment_runs)} most recent:")
        print("\n" + "="*100)
        
        if not experiment_runs:
            print("No experiment runs found.")
            return
        
        for idx, run in enumerate(experiment_runs, 1):
            run_id = run.get("experimentRunID", "N/A")
            exp_name = run.get("experimentName", "N/A")
            phase = run.get("phase", "N/A")
            score = run.get("resiliencyScore", "N/A")
            updated_at = run.get("updatedAt", "N/A")
            
            # Convert timestamp if present
            if updated_at != "N/A":
                try:
                    dt = datetime.fromtimestamp(int(updated_at) / 1000)
                    updated_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            print(f"\n{idx}. Experiment Run ID: {run_id}")
            print(f"   Experiment Name: {exp_name}")
            print(f"   Phase: {phase}")
            print(f"   Resiliency Score: {score}")
            print(f"   Updated At: {updated_at}")
            print("-"*100)
        
        return experiment_runs
        
    except LitmusGraphQLError as e:
        logger.error(f"GraphQL error querying experiment runs: {e}")
        raise
    except Exception as e:
        logger.error(f"Error querying experiment runs: {e}")
        raise


def get_experiment_run_details(client: LitmusClient, project_id: str, experiment_run_id: str):
    """
    Get detailed information about a specific experiment run.
    
    Args:
        client: LitmusClient instance
        project_id: Project ID
        experiment_run_id: Experiment run ID to query
    """
    variables = {
        "projectID": project_id,
        "experimentRunID": experiment_run_id,
        "notifyID": ""  # Empty notifyID for general query
    }
    
    try:
        logger.info(f"Querying details for experiment run {experiment_run_id}...")
        response = client._graphql_call(
            query=LitmusGraphQLQueries.GET_EXPERIMENT_RUN,
            variables=variables
        )
        
        run = response.get("getExperimentRun", {})
        
        if not run:
            logger.error(f"Experiment run {experiment_run_id} not found")
            return
        
        print("\n" + "="*100)
        print("EXPERIMENT RUN DETAILS")
        print("="*100)
        print(f"Run ID: {run.get('experimentRunID', 'N/A')}")
        print(f"Experiment ID: {run.get('experimentID', 'N/A')}")
        print(f"Experiment Name: {run.get('experimentName', 'N/A')}")
        print(f"Phase: {run.get('phase', 'N/A')}")
        print(f"Resiliency Score: {run.get('resiliencyScore', 'N/A')}")
        
        # Execution data
        execution_data = run.get("executionData", "")
        if execution_data:
            print(f"\nExecution Data (truncated): {execution_data[:200]}...")

            chaos_nodes = json.loads(execution_data).get("nodes", {})
            for node_id, node_data in chaos_nodes.items():
                if node_data.get("type") == "ChaosEngine":
                    chaos_data = node_data.get("chaosData", {})
                    chaos_result = chaos_data.get("chaosResult", {})
                    fault_name = node_data.get('name', 'N/A')
                    fault_phase = node_data.get('phase', 'N/A')
                    fault_status = chaos_result.get('status', 'N/A')
                    print(f"Fault Name: {fault_name}")
                    print(f"Fault Phase: {fault_phase}")
                    print(f"Fault Status: {fault_status}")
                    print("-"*100)

        
        # Timestamps
        updated_at = run.get("updatedAt", "N/A")
        if updated_at != "N/A":
            try:
                dt = datetime.fromtimestamp(int(updated_at) / 1000)
                print(f"Updated At: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                print(f"Updated At: {updated_at}")
        
        print("="*100 + "\n")
        
        return run
        
    except LitmusGraphQLError as e:
        logger.error(f"GraphQL error querying experiment run details: {e}")
        raise
    except Exception as e:
        logger.error(f"Error querying experiment run details: {e}")
        raise


def main():
    """Main function to query experiment runs."""
    # Validate required config
    if not config.litmus_url or not config.litmus_username or not config.litmus_password:
        logger.error("Missing required environment variables: LITMUS_URL, LITMUS_USERNAME, LITMUS_PASSWORD")
        sys.exit(1)
    
    if not config.litmus_project:
        logger.error("Missing required environment variable: LITMUS_PROJECT")
        sys.exit(1)
    
    # Create Litmus client
    with LitmusClient(config, logger, retry_config) as client:
        # Authenticate
        logger.info(f"Authenticating with Litmus at {config.litmus_url}")
        client.authenticate()
        
        # Get project ID
        logger.info(f"Retrieving project ID for {config.litmus_project}")
        project_id = get_project_id(client, config.litmus_project)
        logger.info(f"Project ID: {project_id}")
        
        # Query experiment runs
        # You can modify these parameters as needed
        experiment_id = os.getenv("QUERY_EXPERIMENT_ID", None)  # Optional: filter by experiment ID
        limit = int(os.getenv("QUERY_LIMIT", "10"))  # Number of runs to retrieve
        
        runs = list_experiment_runs(
            client=client,
            project_id=project_id,
            experiment_id=experiment_id,
            limit=limit
        )
        
        # Optional: Get details for the first run
        if runs and os.getenv("QUERY_DETAILS", "false").lower() == "true":
            first_run_id = runs[0].get("experimentRunID")
            if first_run_id:
                get_experiment_run_details(
                    client=client,
                    project_id=project_id,
                    experiment_run_id=first_run_id
                )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)
