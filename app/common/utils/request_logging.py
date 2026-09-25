#### REQUEST LOGGER ####
# Author: Bethany Schoen
# Date: 25th July 2025
########################
# To store incoming 
# requests, outgoing
# responses, errors, 
# and metadata
########################

from google.cloud import storage
import json
from datetime import datetime, timezone
import os
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, RetryCallState, retry_if_exception_type
from google.api_core.exceptions import (
    ServiceUnavailable,
    TooManyRequests,
    InternalServerError,
    GatewayTimeout,
    PreconditionFailed 
)
from requests.exceptions import Timeout, ConnectionError

from log import logger
import variables as vr
from app.common.exceptions import validate_internal_call
from app.common.schemas import RouteData, ErrorData, Metadata, Status

def log_retry(retry_state: RetryCallState):
    logger.warning(
        f"Retrying {retry_state.fn.__name__} due to {retry_state.outcome.exception()}. "
        f"Attempt {retry_state.attempt_number} will wait {retry_state.next_action.sleep} seconds."
    )

class RequestLogger:
    """
    Class to log information regarding requests: incoming requests, outgoing responses, errors, and metadata
    Data can be saved locally or to a cloud bucket
    """

    def __init__(self, path: str, request_id: str, api_version: str, cloud_save: bool=False):

        self.path = path
        self.request_id = request_id
        self.api_version = api_version
        self.cloud_save = cloud_save
        # if not cloud_save, save locally (for dev)
        if self.cloud_save:
            self.storage_client = storage.Client()
            self.bucket_name = os.getenv("GCP_BUCKET_NAME")
            if not self.bucket_name:
                logger.error("GCP_BUCKET_NAME environment variable not set, but cloud_save is True. Saving locally instead...")
                self.cloud_save = False

        # the information that will be logged
        self._log_event = {
            "request_id": request_id,
            "api_version": api_version,
            "api_path": path,
            "status": "IN_PROGRESS",
            vr.input_key: None,
            vr.metadata_key: None,
            vr.response_key: None,
            vr.error_key: None
        }

    def finalise_and_save_log(self):
        """
        Finalizes the log event and saves it as a single JSON file either
        locally or to a GCS bucket with Hive partitioning.

        This operation will not crash the app if the upload fails.
        """
        
        now = datetime.now(timezone.utc)        
        partition_path = now.strftime("year=%Y/month=%m/day=%d")
        # add route to the partition path
        partition_path = os.path.join(partition_path, os.path.basename(self.path))
        
        filename = f"{self.request_id}.json"

        # Serialize the entire log event to a JSON string
        json_data = json.dumps(self._log_event, indent=2, default=str)

        try:
            if self.cloud_save and hasattr(self, 'bucket_name'):
                blob_name = f"logs/{partition_path}/{filename}"
                self._upload_to_gcs_with_retry(blob_name, json_data)
            else:
                # Save locally for development
                local_path = Path(vr.local_log_data_dir) / partition_path
                local_path.mkdir(parents=True, exist_ok=True)
                full_local_path = local_path / filename
                with open(full_local_path, 'w') as f:
                    f.write(json_data)
                logger.info(f"Log saved locally to: {full_local_path}")
        
        except Exception as e:
            # - CHANGED: This is the crucial part for not crashing the app.
            # The retry decorator will raise the last exception if all attempts fail.
            # We catch it here, log it, and move on.
            logger.error(
                f"Failed to save log for request {self.request_id} after multiple retries. Error: {e}",
                exc_info=True # This adds traceback details to the log
            )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=0.5, max=5),
        retry=retry_if_exception_type((
            ServiceUnavailable,
            TooManyRequests,
            InternalServerError,
            GatewayTimeout,
            Timeout,
            ConnectionError,
            PreconditionFailed 
        )),
        before_sleep=log_retry,
        reraise=True
    )
    def _upload_to_gcs_with_retry(self, blob_name: str, json_data: str):
        
        logger.info(f"Attempting to upload log to gs://{self.bucket_name}/{blob_name}")
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(blob_name)
        
        blob.upload_from_string(
            data=json_data,
            content_type="application/json",
            timeout=15.0
        )
        logger.info(f"Successfully uploaded log for request {self.request_id}.")
    
    def log_input_data(self, request_input: dict):

        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        data_to_log = {
            "timestamp":timestamp,
            "data":request_input
        }
        self._log_event[vr.input_key] = data_to_log
    
    # validation completed in the route
    def log_response_data(self, response_body: dict):
    
        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        data_to_log = {
            "timestamp":timestamp,
            "data":response_body
        }
        self._log_event[vr.response_key] = data_to_log
        self._log_event["status"] = Status.Success
    
    @validate_internal_call
    def log_error_data(self, error_body: ErrorData):

        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        # convert pydantic model to dictionary for logging
        error_body_dict = error_body.model_dump(by_alias=True)
        data_to_log = {
            "timestamp":timestamp,
            "data":error_body_dict
        }
        self._log_event[vr.error_key] = data_to_log
        self._log_event["status"] = Status.Failed

    @validate_internal_call
    def log_response_metadata(self, metadata: Metadata):

        # convert pydantic model to dictionary for logging
        metadata_body_dict = metadata.model_dump(by_alias=True)
        self._log_event[vr.metadata_key] = metadata_body_dict

class NullRequestLogger:
    """
    A logger that does nothing, but has the same interface as RequestLogger.
    This is used in Testing to prevent us from saving logs but making sure code works
    """
    def __init__(self, path, request_id, api_version, cloud_save: bool=False, *args, **kwargs):
        # Accepting *args and **kwargs makes it robust to future changes.
        self.path = path
        self.request_id = request_id
        self.api_version = api_version
        self.cloud_save = cloud_save
        self._log_event = {
            "request_id": self.request_id,
            "api_version": api_version,
            "api_path": path,
            "status": "TESTING",
            vr.input_key: None,
            vr.metadata_key: None,
            vr.response_key: None,
            vr.error_key: None
        }

    def finalise_and_save_log(self):
        pass

    def _upload_to_gcs_with_retry(self, blob_name: str, json_data: str):
        pass

    def log_input_data(self, request_input: dict):

        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        data_to_log = {
            "timestamp":timestamp,
            "data":request_input
        }
        self._log_event[vr.input_key] = data_to_log
    
    def log_response_data(self, response_body: dict):
    
        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        data_to_log = {
            "timestamp":timestamp,
            "data":response_body
        }
        self._log_event[vr.response_key] = data_to_log
        self._log_event["status"] = Status.Success
    
    def log_error_data(self, error_body: ErrorData):

        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
        
        data_to_log = {
            "timestamp":timestamp,
            "data":error_body
        }
        self._log_event[vr.error_key] = data_to_log
        self._log_event["status"] = Status.Failed

    def log_response_metadata(self, metadata: Metadata):

        self._log_event[vr.metadata_key] = metadata