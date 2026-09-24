# Implementing a Redis Caching Layer for the Care Note Pre-processing Service 

## Problem Statement
The note pre-processing service, which redacts PII and profanity from care notes using LLMs, is experiencing high operational costs and slow response times. Upon initial, manual inspection, we noticed that many incoming requests are duplicates, containing the exact same observation text. Each duplicate request currently triggers expensive and time-consuming LLM calls, leading to unnecessary resource consumption and degraded performance.

## Problem Analysis
All requests made to the note pre-processing route on the 21st December were extracted from the JSON logs and transformed into CSV format for analysis. Data was pivoted: rows were filtered by log type (note pre-processing), original text (the data to be redacted) was selected as rows, and the request IDs were counted. Column B now contains the number of times each distinct text was processed. The transformed data was then aggregated:

| Metric | Formula | Value | 
| ------ | ------ | ------ |
| Total number of requests | =SUM(B:B) | 25,573 |
| Distinct count of texts only requested once | =SUMIF(B:B, 1) (or =COUNTIF(B:B, 1)) | 2,273 |
| Distinct count of texts that were requested more than once | =COUNTIF(B:B, ">1") | 1,700 |
| Total number of non-unique requests | =SUMIF(B:B, ">1") | 23,300 |
| Avoidable requests | =(Total number of non-unique requests)-(Distinct count of texts requested more than once) | 21,600 | 
| Percentage of requests avoidable | voidable requests)/(Total number of requests) | 84.5% |
 

In one day, a significant number of requests were made and most of these were duplicates. **We could save considerable time and money by implementing a caching solution.**

## Proposed Solution
We propose implementing a caching layer using Google Cloud Memorystore for Redis and the Flask-Caching library. This solution will store the results of successfully processed notes. When a new request arrives, the application will first check the Redis cache to see if the observation text has been processed before.

- **Cache Hit:** If the text exists in the cache, the stored (redacted) result will be returned immediately, bypassing the entire LLM processing pipeline.
- **Cache Miss:** If the text is not in the cache, the request will be processed by the LLM as normal, and the result will be stored in the cache before being returned to the user.

## Technical Implementation Details
The workflow of the caching system has been visualised below. This outlines the intialisation of the client, how the app works alongside caching, and ways in which caching can be disabled.

![Caching System Workflow](images/caching_workflow.png)

### Infrastructure (Request for DevOps/SRE):
- **Resource:** Provision a Google Cloud Memorystore for Redis instance.
- **Networking:** The instance must be provisioned on the same VPC network used by our Cloud Run services.
- **VPC Access:** A Serverless VPC Access Connector or Direct VPC egress must be configured to allow the Cloud Run service to connect to the Memorystore instance over its private IP.
- **Configuration:** The private IP address and port of the Redis instance should be exposed to the Cloud Run service as environment variables (CACHE_REDIS_HOST, CACHE_REDIS_PORT).
- **Security:** Memorystore for Redis allows you to require an authentication string (password) for connections. This provides an additional layer of security. You can pass the auth token to your Cloud Run service as a secret (e.g., via Secret Manager) and configure it in your Flask application's Redis connection settings.

### Application Code (Responsibility of Development Team):
- **Libraries:** Add Flask-Caching and Redis to the project's dependencies.
- **Authorisation:** Setup a code for instantiating a Redis client via common utilities. A custom class for using the database will be required so that we can use this authorisation method. 

```
# NEW FILE: app/common/redis_client.py
import os
import redis
import google.auth
from google.auth.transport.requests import Request
def get_access_token() -> str:
    """
    Get an OAuth access token.
    - Workbench: uses ADC / gcloud login
    - Cloud Run: uses metadata server automatically
    """
    credentials, _ = google.auth.default()
    credentials.refresh(Request())
    return credentials.token
def create_redis_client() -> redis.Redis:
    """
    Create a Redis client suitable for
    GCP Memorystore Redis Cluster with IAM.
    """
    return redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.environ.get("REDIS_PORT", 6379)),
        ssl=True,
        username="default",
        password=get_access_token(),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
        retry_on_timeout=True,
    )    
# NEW FILE: app/common/iam_redis_cache.py
from flask_caching.backends.base import BaseCache
from app.common.redis_client import create_redis_client
class IAMRedisCache(BaseCache):
    """
    Flask-Caching backend for Redis using IAM authentication.
    """
    def __init__(self, default_timeout=300):
        super().__init__(default_timeout=default_timeout)
        self.default_timeout = default_timeout
        # HERE: use function for authenticating DB access.
        self._client = create_redis_client()
    def get(self, key):
        return self._client.get(key)
    def set(self, key, value, timeout=None):
        ttl = timeout or self.default_timeout
        self._client.setex(key, ttl, value)
        return True
    def delete(self, key):
        return self._client.delete(key)
    def has(self, key):
        return bool(self._client.exists(key))
```

- **Configuration:** The Flask app will be configured in app/__init__.py to use the Redis instance via the environment variables.

```
# NEW FILE: app/extensions.py (to prevent circular imports)
from flask_caching import Cache
# App-level cache instance
cache = Cache()
# UPDATE FILE: app/__init__.py
from flask import Flask
from extensions import cache
from config import config_by_name
def create_app(config_name="default"):
    app = Flask(__name__)
    # In config include
    # - "ENABLE_CACHING" (True or False)
    # - "CACHE_TYPE" (e.g. "SimpleCache" or "app.common.iam_redis_cache.IAMRedisCache")
    # - "CACHE_DEFAULT_TIMEOUT" (e.g. 300)
    app.config.from_object(config_by_name[config_name])
    if app.config["ENABLE_CACHING"]:
        try:
            cache.init_app(app)
            logger.info(f"Caching enabled: {app.config['CACHE_TYPE']}")
        except Exception as e:
            logger.warning(f"CACHING ISSUE: failed to initialise cache: {e}")
    # ... other app setup ...
    return app
```

- **Custom Cache Key:** As Sapient’s requests will include fields unique to each input (e.g. Connection ID), using Flask-Caching logic to recognise duplicate requests will result in Cache Misses every time. Instead, search through a request input for a specific field that will be compared to historic requests. A custom function to extract the necessary field will be programmed in a new utils file. This function will hash the observation text, prompt versions, models, and app version to create a unique and consistent cache key. 

``
# NEW FILE: app/v1/utils/caching_decorator.py
from functools import wraps
import hashlib
from typing import List, Type
from pydantic import BaseModel
def _create_cache_string(
    route_name: str,
    app_version: str,
    prompt_versions: str,
    models_used: str,
    field_value: str
) -> str:
    """
    Combines a static version string with a dynamic field value to create a unique cache key string.
    This ensures that changes in either the logic (version) or the data (field value) will result in a different cache key.
    """
    key_string = f"{route_name}::{app_version}::{prompt_versions}::{models_used}::{field_value}"
    # Use SHA-256 for a robust, unique hash.
    return f"{route_name}::{hashlib.sha256(key_string.encode('utf-8')).hexdigest()}"
# The type hint 'Type[BaseModel]' means "a class that inherits from BaseModel"
def _make_cache_key_from_pydantic(
    route_name: str,
    pydantic_models: List[Type[BaseModel]], 
    field_name: str, 
    prompt_versions: str,
    models_used: str
):
    """
    Creates a function that generates a cache key from a specific field of a Pydantic model
    found within the decorated function's arguments.
    This version is flexible and can search for an instance from a list of possible Pydantic models.
    The key is a hash composed of a static version string and a dynamic value 
    from a Pydantic model field.
    """
    models_tuple = tuple(pydantic_models)
    def generate_key(*args, **kwargs):
        """ The actual function that Flask-Caching will call on each request. """
        model_instance = None
        # Search through positional arguments
        for arg in args:
            if isinstance(arg, models_tuple):
                model_instance = arg
                break
        # Search through keyword arguments if not found
        if not model_instance:
            for value in kwargs.values():
                if isinstance(value, models_tuple):
                    model_instance = value
                    break
        # If no matching Pydantic model is found, raise an error.
        if not model_instance:
            model_names = ', '.join(m.__name__ for m in pydantic_models)
            raise TypeError(
                f"Pydantic model of an expected type ('{model_names}') not found in function arguments."
            )
        # Get the value of the specified field.
        if not hasattr(model_instance, field_name):
            raise AttributeError(
                f"Pydantic model '{type(model_instance).__name__}' does not have the field '{field_name}'."
            )
        field_value = getattr(model_instance, field_name)
        # Ensure the field has a value to hash.
        if not field_value:
            raise ValueError(
                f"The field '{field_name}' in model '{type(model_instance).__name__}' is empty or None, which is not valid for cache key generation."
            )
        # Combine the static version string with the dynamic field value.
        # This ensures that a change in logic (version) or data (field_value) creates a new key.
        combined_key_string = _create_cache_string(
            route_name=route_name,
            app_version=os.environ.get('APP_VERSION', 'unknown'),
            prompt_versions=prompt_versions,
            models_used=models_used,
            field_value=field_value
        )
        return combined_key_string
    return generate_key
```

- **Caching Logic:** Flask-Caching's built-in @cache.cached decorator on the service function was considered, but it has a significant limitation: it makes tracking cache hits and misses within the application difficult, as the decorated function is bypassed entirely on a cache hit. This would prevent us from directly measuring the ROI of this project. Therefore, the recommended solution is to create a new, reusable @api_cached decorator. This decorator will be stacked with our existing @api_route decorator, allowing it to intercept requests, check the cache, and transparently add a cache_status field to the response metadata. This approach provides full control and observability while keeping our route and service logic clean.

```
# UPDATE FILE: app/v1/prompt_versions.py
# create a string that includes all prompt versions
NOTE_PREPROCESSING_PROMPT_VERSION_STRING = (
    f"pii-{pii_removal_prompt_version}_pii-validation-{pii_removal_validation_prompt_version}_pii-retry-{pii_removal_retry_prompt_version}" 
    f"profanity-{profanity_removal_prompt_version}_profanity-validation-{profanity_removal_validation_prompt_version}_profanity-retry-{profanity_removal_retry_prompt_version}"
)
# UPDATE FILE: v1/utils/route_decorator.py
# edit '@api_route' to save the request and service models in request context 'g'
...
g.request_models = [json_request_model, avro_request_model]
g.service_result_model = service_result_model
...
# UPDATE FILE: v1/utils/caching_decorator.py
from functools import wraps
from app import cache # Flask-Caching instance
from flask import g
def api_cached(
    timeout: int,
    route_name: str,
    field_name: str,
    prompt_versions: str,
    models_used: str
):
    """
    A decorator for caching API service function results.
    - Sits inside @api_route.
    - Expects to receive a validated Pydantic model as its first argument.
    - Checks cache before executing the function.
    - Sets cache on miss.
    - Modifies the service result metadata to include cache status.
    """
    def decorator(service_func):
        @wraps(service_func)
        def wrapper(validated_input, *args, **kwargs):
            # 0. If caching has been disabled via config, skip all caching logic and just execute the function.
            if not current_app.config.get('ENABLE_CACHING', True):
                logger.info("Caching is disabled via config. Skipping cache logic.")
                return service_func(validated_input, *args, **kwargs)
            # 1. Look up the models and request context from the `g` object.
            # This makes the decorator generic and dependent on the outer @api_route.    
            try:
                result_model = g.service_result_model
                request_models = g.request_models
                provider = g.provider
                shadow_mode = g.shadow_mode
            except AttributeError as e:
                # This provides a clear error if the decorators are stacked incorrectly.
                raise RuntimeError(
                    f"@api_cached is missing required context from @api_route. Details: {e}"
                )
            if shadow_mode or provider != VERTEX_PROVIDER_IDENTIFIER:
                # Don't cache if in shadow mode or not using the target provider
                logger.info(f"Caching skipped due to shadow mode or non-target provider ({provider}).")
                return service_func(validated_input, *args, **kwargs)
            # 2. Generate the cache key from the validated input
            key_generator = _make_cache_key_from_pydantic(
                route_name=route_name,
                pydantic_models=request_models,
                field_name=field_name,
                prompt_versions=prompt_versions,
                models_used=models_used
            )
            try:
                cache_key = key_generator(validated_input)
            except (TypeError, AttributeError, ValueError) as e:
                logger.error(f"Cache key generation failed: {e}. Proceeding without caching.")
                return service_func(validated_input, *args, **kwargs)
            # 3. Check the cache to see if the content has already been created, if so, return it     
            cached_result = _try_get_cache(cache_key, result_model)   
            if cached_result is not None:
                return cached_result
            # if we're using redis, can use redis locks to prevent multiple processes from doing the same work while we compute and set the cache. 
            # If we're using simple cache (in-memory, for testing), we skip locking as it's not needed.
            if current_app.config.get('CACHE_TYPE', "simple") == "simple":
                logger.info("CACHE MISS")
                return _execute_and_cache(service_func, validated_input, cache_key, timeout, *args, **kwargs)
            # 4. Otherwise, compute content - lock key first to prevent other processes from doing the same work while we compute and set the cache
            lock_acquired, lock_key = _acquire_lock(cache_key)
            # If no one else has the lock, we proceed to check the cache and potentially execute the function.
            if lock_acquired:
                try:
                    # double-check the cache after acquiring the lock 
                    cached_result = _try_get_cache(cache_key, result_model)   
                    if cached_result is not None:
                        return cached_result
                    # still a miss => generate the content
                    logger.info("CACHE MISS")
                    return _execute_and_cache(service_func, validated_input, cache_key, timeout, *args, **kwargs)
                finally:
                    # Always release the lock after checking the cache and executing
                    cache.cache._client.delete(lock_key)
            else:
                logger.debug("Cache lock is held by another process. Retrying...")
                # wait for the content to be ready in the cache
                for _ in range(3): # Try to get result for a certain number of attempts (wait for the leader to finish)
                    time.sleep(0.1) # Sleep for 100ms before retrying (sleep first to avoid redundant checks)
                    # double-check the cache after acquiring the lock 
                    cached_result = _try_get_cache(cache_key, result_model)   
                    if cached_result is not None:
                        return cached_result            
            logger.warning("Could not acquire cache lock after multiple attempts. Proceeding without caching.")
            logger.info("CACHE MISS")
            return service_func(validated_input, *args, **kwargs)
        return wrapper
    return decorator
```

- **Route Implementation:** The decorators are stacked on the route function, resulting in a clean and declarative implementation. With the latest shadow traffic refactor, the caching decorator is theoretically called within execute_service_logic inapp/v1/utils/route_decorator.py. In the api_route decorator, we’ve extracted data from the request, validated the request, and called to execute the service. At this point, api_cacheddecorator is used to check the caching DB, call the service, and return the output back to execute_service_logic which will validate the service structure.

```
@v1_bp.route(f"/notepreprocessing", methods=["POST"])
@api_route(
    http_request_model=NotePreprocessingRequestModel,
    avro_request_model=NotePreprocessingEvent,
    service_result_model=NotePreprocessingServiceResult,
    req_avro_schema_name='com.blua_family.ai.request.ObservationPIIEvent',      
    res_avro_schema_name='com.blua_family.ai.response.ObservationPIIResponseEvent',
    response_pubsub_topic_name="NOTE_PREPROCESS_RESPONSE_TOPIC"
)
@api_cached(
    timeout=os.environ.get('CACHE_DEFAULT_TIMEOUT', 24 * 60 * 60),  # default cache timeout of 24 hours, can be overridden by env var
    route_name="notepreprocessing",
    field_name='observation',
    prompt_versions=pv.NOTE_PREPROCESSING_PROMPT_VERSION_STRING,
    models_used=mv.NOTE_PREPROCESSING_MODEL_STRING
)
def preprocess(validated_input: NotePreprocessingEvent | NotePreprocessingRequestModel, get_generator: Callable[[str], TextGenerator]):
    """
    API Endpoint for pre-processing care notes
    """
    return note_preprocessing_service(validated_input, get_generator)
```

- **Schema Updates:** the Metadata, InferenceMetadata, and ApiResponse schemas would need to be updated to include the additional field. These would be optional for routes not using the new decorator.

This example can help with conceptually understanding the chaining of decorators:

```
from functools import wraps
# Second decorator applied => it will receive a string that already has @s around it, and will add *s around that
def star_decor(n_stars: int=None):
  def decorator(func):
    @wraps(func)
    def wrap(*args, **kwargs):
      s = func(*args, **kwargs)
      n = n_stars if n_stars is not None else len(s)
      new_s = "*" * n + "\n" + s + "\n" + "*" * n
      return new_s
    return wrap
  return decorator
# First decorator applied => The input string will be surrounded by @s
def at_decor(n_ats: int=None):
  def decorator(func):
    @wraps(func)
    def wrap(*args, **kwargs):
      s = func(*args, **kwargs)
      n = n_ats if n_ats is not None else len(s)
      new_s = "@" * n + "\n" + s + "\n" + "@" * n
      return new_s
    return wrap
  return decorator
@star_decor(10)
@at_decor()
def shout_something(s):
  return s.upper()
@star_decor()
@at_decor(3)
def whisper_something(s):
  return s.lower()
print(shout_something("Hello, World!"))
print('\n')
print(whisper_something("I REALLY hope this works"))
```

Returns

```
**********
@@@@@@@@@@@@@
HELLO, WORLD!
@@@@@@@@@@@@@
**********
********************************
@@@
i really hope this works
@@@
********************************
```

## Invalidation Strategy:
Should a service result be cached that contains unsatisfactory content (e.g., bad LLM response), we need to create a strategy for amending of removing these values.

1. **Flagging Mechanism:** Identify when an insufficient response has been created. This could be via:
	a. **End user** – PII or profanities are present in the front end so a user flags the bad content
	b. **QA Process** – an internal team periodically reviews a sample of processed notes and identifies bad responses
	c. **Local monitoring solution** – Our custom endpoints evaluate content, and the result doesn’t meet a certain threshold
2. **Logging:** the bad responses are logged with the original text, prompts used, and any relevant metadata
3. **Invalidation:** create a new script within the Flask application. Its sole job is to receive the original text of a bad entry and the prompts used, calculate its cache key, and delete it from Redis. The script will be run manually.
4. **Re-processing:** The next time the same care note is requested, it will be a cache miss, and the request will go to the LLM for a fresh attempt.
5. **Data Pipeline:** Create a QA tool that logs bad responses and automatically makes POST requests to the invalidate endpoint with the logged content. 

## Expected Benefits
- **Significant Cost Reduction:** By eliminating redundant LLM API calls, we will directly reduce our Vertex AI or other LLM provider costs.
- **Drastic Performance Improvement:** Latency for cached responses will drop from seconds to milliseconds, providing a vastly improved experience for API consumers.
- **Increased Scalability and Reliability:** Reducing the load on the core processing logic will make the service more resilient to traffic spikes and less likely to hit LLM rate limits.
- **Minimal Maintenance:** Using a fully managed service like Memorystore removes the operational overhead of maintaining a Redis server.

## KPIs
- **Cache Hit/Miss Ratio:** Prove the effectiveness and ROI of this implementation but seeing how frequently cached responses are used. This can be logged from the application.
- **Redis Memory Usage:** Set up alerts in Google Cloud Monitoring to be notified when memory usage on the Memorystore instance approaches its limit.
- **CPU Utilisation:** Monitor Redis CP5U to ensure resource-intensive commands aren't blocking the server.
- **End-to-End Latency:** Response times (this can be broken down by cache hits and misses to also prove ROI). 

## Next Steps
- **Infrastructure Team:** Provision the Memorystore for Redis instance and the Serverless VPC Access Connector as specified.
- **Development Team:** Implement the application-level caching logic in a feature branch.
- **Testing:** Deploy to a staging environment to validate caching behaviour and monitor cache hit/miss rates.
- **Production Rollout:** Deploy to production and monitor performance and cost metrics.