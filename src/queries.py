"""GraphQL queries for Litmus Chaos API."""

class LitmusGraphQLQueries:
  """Collection of GraphQL queries for Litmus ChaosCenter API."""
  
  # Query to list environments and return their IDs and names
  LIST_ENVIRONMENTS = """
    query listEnvironments($projectID: ID!, $request: ListEnvironmentRequest){
      listEnvironments(projectID: $projectID, request: $request){
        environments {
          environmentID
          name
        }
      }
    }
  """

  # Query to list infrastructures and return their IDs, names, and statuses
  LIST_CHAOS_INFRASTRUCTURES = """
    query listInfras($projectID: ID!, $request: ListInfraRequest){
      listInfras(projectID: $projectID, request: $request){
        infras {
          infraID
          name
          isActive
          isInfraConfirmed
        }
      }
    }
  """

  # Query to list experiments and return their IDs and names
  LIST_EXPERIMENTS = """
    query listExperiment($projectID: ID!, $request: ListExperimentRequest!){
      listExperiment(projectID: $projectID, request: $request){
        experiments {
          experimentID
          name
        }
      }
    }
  """

  # Mutation to save a chaos experiment
  SAVE_EXPERIMENT = """
    mutation saveChaosExperiment($projectID: ID!, $request: SaveChaosExperimentRequest!){
      saveChaosExperiment(projectID: $projectID, request: $request)
    }
  """

  # Mutation to run a chaos experiment and return the notifyID for the run
  RUN_EXPERIMENT = """
    mutation runChaosExperiment($projectID: ID!, $experimentID: String!){
      runChaosExperiment(projectID: $projectID, experimentID: $experimentID){
        notifyID
      }
    }
  """
