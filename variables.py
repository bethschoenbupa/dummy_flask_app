import os
project_dir = os.path.dirname(__file__)

# --- RequestLogging ---
cloud_save = True
local_data_dir = os.path.join(project_dir, 'data')
local_log_data_dir = os.path.join(local_data_dir, "logs")
input_requests_file = "input_requests.csv"
request_responses_file = "request_responses.csv"
request_error_file = "error_responses.csv"
metadata_file = "metadata.csv"
input_key = "input"
response_key = "response"
error_key = "error"
metadata_key = "metadata"
log_data_columns = ["TIMESTAMP", "REQUESTID", "PAYLOAD"]

# --- TextGeneration ---
generated_content_key = "generated_content"
token_key = "tokens"
models_key = "models"
total_token_count_key = "total_token_count"

# --- Tasks ---
haiku_prompt_name = "birthday_haiku"
haiku_task_str = "Birthday Haiku v1"
haiku_prompt_version_key = "haikuPromptVersion"

# GCP environment variables
vertex_model_name = "gemini-2.5-flash"
gcp_env_file = '.env.public'