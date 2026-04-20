import json
import os
import logging
import re
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, List

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

# import state schema
from backend.src.graph.state import VideoAuditState, ComplianceIssue

# import service
from backend.src.services.video_indexer import VideoIndexerService

# Load the .env file
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# configure the logger
logger = logging.getLogger("youtube-add-compliance-checker")
logging.basicConfig(level=logging.INFO)

# NODE 1 : Indexer
# Function responsible for converting video to text
def index_video_node(state:VideoAuditState) -> Dict[str, Any]:
    '''
    Downloads the youtube video from the url
    Uploads to the Azure Video Indexer
    Extracts the insights
    '''
    video_url = state.get("video_url")
    source_type = state.get("source_type", "youtube")
    source_url = state.get("source_url") or video_url
    local_file_path = state.get("local_file_path")
    video_id_input = state.get("video_id","vid_demo")

    logger.info(f"---[Node:Indexer] Processing : {source_type} -> {source_url}")

    try:
        vi_service = VideoIndexerService()
        cleanup_paths = []
        if source_type == "upload":
            if not local_file_path or not os.path.exists(local_file_path):
                raise Exception("Uploaded file could not be found for this audit job.")
            local_path = local_file_path
            cleanup_paths.append(local_path)
            azure_video_id = vi_service.upload_video(local_path, video_name=video_id_input)
        elif source_type == "media_url":
            if not source_url:
                raise Exception("Please provide a valid media URL for this audit.")
            azure_video_id = vi_service.upload_video_url(source_url, video_name=video_id_input)
        elif source_type == "youtube":
            local_filename = "temp_audit_video.mp4"
            if not source_url or ("youtube.com" not in source_url and "youtu.be" not in source_url):
                raise Exception("Please provide a valid YouTube URL for this audit.")
            local_path = vi_service.download_youtube_video(source_url, output_path=local_filename)
            cleanup_paths.append(local_path)
            azure_video_id = vi_service.upload_video(local_path, video_name=video_id_input)
        else:
            raise Exception("Unsupported audit source type.")

        logger.info(f"Upload Success. Azure ID : {azure_video_id}")
        # wait
        raw_insights = vi_service.wait_for_processing(azure_video_id)
        # extract
        clean_data = vi_service.extract_data(raw_insights)
        logger.info("---[NODE: Indexer] Extraction Complete ----------------")
        return clean_data

    except Exception as e:
        logger.error(f"Video Indexer Failed : {e}")
        return {
            "errors" : [str(e)],
            "final_status" : "FAIL",
            "transcript" : "",
            "ocr_text" : []
        }
    finally:
        for cleanup_path in locals().get("cleanup_paths", []):
            if cleanup_path and os.path.exists(cleanup_path):
                os.remove(cleanup_path)
    
# Node 2 : Compliance Auditor
def audit_content_node(state:VideoAuditState) -> Dict[str, Any]:
    '''
    Performs Retreival Augmented Generation to audit the content - brand video
    '''
    logger.info("---[Node: Auditor] querying Knowledge Base and LLM")
    transcript = state.get("transcript","")
    if not transcript:
        logger.warning("No transcript available. Skipping audit......")
        return {
            "final_status" : "FAIL",
            "final_report" : "Audit Skipped because video processing failed (No Transcript)."
        }
    
    # initialize azure clients
    llm = AzureChatOpenAI(
        azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature = 0.0
    )

    embeddings = AzureOpenAIEmbeddings(
        azure_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION"),
    )

    vector_store = AzureSearch(
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key = os.getenv("AZURE_SEARCH_API_KEY"),
        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME"),
        embedding_function = embeddings.embed_query
    )

    # RAG Retrieval
    ocr_text = state.get("ocr_text", [])
    query_text = f"{transcript} {''.join(ocr_text)}"
    docs = vector_store.similarity_search(query_text,k=3)
    retrieved_rules = "\n\n".join([doc.page_content for doc in docs])

    #
    system_prompt = f"""
    You are a Senior Brand Compliance Auditor.
    
    OFFICIAL REGULATORY RULES:
    {retrieved_rules}
    
    INSTRUCTIONS:
    1. Analyze the Transcript and OCR text below.
    2. Identify ANY violations of the rules.
    3. Return strictly JSON in the following format:
    
    {{
        "compliance_results": [
            {{
                "category": "Claim Validation",
                "severity": "CRITICAL",
                "description": "Explanation of the violation..."
            }}
        ],
        "status": "FAIL", 
        "final_report": "Summary of findings..."
    }}

    If no violations are found, set "status" to "PASS" and "compliance_results" to [].    
    """

    user_message = f"""
                    VIDEO_METADATA : {state.get('video_metadata',{})}
                    TRANSCRIPT : {transcript}
                    ON-SCREEN TEXT (OCR) : {ocr_text} 
                    """
    
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])
        content = response.content
        if "```" in content:
            content = re.search(r"```(?:json)?(.*?)```", content, re.DOTALL).group(1)
        audit_data = json.loads(content.strip())
        return {
            "compliance_results" : audit_data.get("compliance_results",[]),
            "final_status" : audit_data.get("status","FAIL"),
            "final_report" : audit_data.get("final_report","No report generated")
        }
    except Exception as e:
        logger.error(f"System Error in Auditor Node : {str(e)}")
        # logging the raw response
        logger.error(f"Raw LLM Response : {response.content if 'response' in locals() else 'None'}")
        return {
            "errors" : [str(e)],
            "final_status" : "FAIL",
            "final_report" : "No report generated"
        }
