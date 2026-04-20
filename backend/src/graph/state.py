import operator
from typing import Annotated, List, Dict, Optional, Any, TypedDict

# Define the schema for a single compliance result
# Error Report
class ComplianceIssue(TypedDict):
    category : str # eg : FTC Disclosure
    description : str # specific detail of violation
    severity : str # CRITICAL | WARNING
    timestamp: Optional[str]

# Define the global graph state
# this defines the state that gets passed around in the agentic workflow
class VideoAuditState(TypedDict):
    '''
    Defines the data schema for LangGraph execution content
    Main Container : Holds all the information about the audit 
    right from the initial URL given by the user to the final report.
    '''
    # input parameters
    video_url : str
    video_id : str
    source_type : str
    source_url : Optional[str]

    # ingestion and extraction data
    local_file_path : Optional[str]
    video_metadata : Dict[str,Any] # {"duration" : 15, "resolution" : "1080p"}
    transcript : Optional[str] # Fully extracted speech-to-text
    ocr_text : List[str]

    # analysis output
    # stores the list of all the violations found by AI
    compliance_results : Annotated[List[ComplianceIssue], operator.add]

    # final deliverables
    final_status : str # PASS or FAIL
    final_report : str # markdown format

    # system observability
    # errors : API timeout, system level errors
    # list of system level crashes
    errors : Annotated[List[str], operator.add]
