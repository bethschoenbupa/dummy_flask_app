from enum import Enum
from functools import wraps
import hashlib
import os
import time
from typing import List, Type, Optional
from pydantic import BaseModel
from flask import g, request, current_app, has_request_context
import json

from app.extensions import cache # Flask-Caching instance
from app.v1.model_versions import VERTEX_PROVIDER_IDENTIFIER
from app.common.schemas import CacheOutcome, CacheMetadata

from log import logger

class CachePhase(str, Enum):
    DIRECT = "direct"
    SIMPLE = "simple"
    AFTER_LOCK = "after_lock"
    AFTER_WAIT = "after_wait"
    AFTER_WAIT_FALLBACK = "after_wait_fallback"

class CacheSummary(BaseModel):
    route_name: str
    request_start_ms: int
    outcome: CacheOutcome = CacheOutcome.BYPASS
    phase: CachePhase = CachePhase.DIRECT
    bypass_reason: Optional[str] = None
    wait_ms: Optional[int] = None

def now_ms() -> int:
    """Return current epoch time in milliseconds."""
    return int(time.time() * 1000)

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

def _parse_cached_content(cached_result: dict, result_model: Type[BaseModel]) -> tuple[str, BaseModel]:
    """
    Parses the cached content string into a Pydantic model.
    Expects the cached string to be in the format: "request_id::json_content".
    Returns a tuple of (original_request_id, service_result).
    """
    if not isinstance(cached_result, dict):
        raise ValueError("Cached result must be a dictionary containing 'original_request_id' and 'service_result'.")
    elif "original_request_id" not in cached_result or "service_result" not in cached_result:
        raise ValueError("Cached result format is unexpected. Expected keys 'original_request_id' and 'service_result'.")

    og_request_id = cached_result["original_request_id"]
    service_result_dict = cached_result["service_result"]
    
    # Validate and reconstruct the Pydantic model
    result_model.model_validate(service_result_dict)
    service_result = result_model(**service_result_dict)

    return og_request_id, service_result

def _try_get_cache(cache_key: str, result_model: Type[BaseModel], cache_summary: CacheSummary) -> BaseModel | None:
    """
    Using the key, check the cache to see if the content has already been created, if so, return it.
    If hit, update the cache_summary with outcome HIT and add cache details to the result's metadata.
    If nothing is found, return None to indicate a cache miss.
    Don't update cache_summary with outcome MISS here, as it returns None and the caller will handle the miss case.
    """
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        # CACHE HIT (don't include key as this has potential PII, and we don't want it in the logs)
        logger.info("CACHE HIT")        
        try:            
            og_request_id, service_result = _parse_cached_content(cached_result, result_model)
        except Exception as e:
            logger.error(f"Cached result found but failed to parse into the expected model: {e}. Cache key: {cache_key}. Proceeding with cache miss.")
            return None

        # Add cache details to the result's metadata  
        cache_summary.outcome = CacheOutcome.HIT      
        cache_metadata = CacheMetadata(
            outcome=cache_summary.outcome,
            original_request_id=og_request_id,
            cache_key=cache_key,
            phase=cache_summary.phase,
            wait_ms=cache_summary.wait_ms
        )
        service_result.metadata.cache_metadata = cache_metadata
        
        return service_result
    else:
        return None

def _execute_and_log(cache_summary: CacheSummary, service_func, validated_input, *args, **kwargs):
    """
    Execute the service function and log the result. Used when the cache is bypassed or missed (hence why it doesn't set the cache 'outcome')
    """
    service_result = service_func(validated_input, *args, **kwargs)

    # Add status to the result's metadata
    cache_metadata = CacheMetadata(
        outcome=cache_summary.outcome,
        phase=cache_summary.phase,
        bypass_reason=cache_summary.bypass_reason,
        wait_ms=cache_summary.wait_ms
    )
    service_result.metadata.cache_metadata = cache_metadata

    return service_result

def _cache_result(request_id, service_result, cache_key, timeout):
    """
    Having executed the service function, cache the result.
    """
    content_to_cache = {
        "original_request_id": request_id,
        "service_result": service_result.model_dump(
            mode="json",
            by_alias=True,
        ),
    }
    cache_write_success = cache.set(cache_key, content_to_cache, timeout=timeout)

    if cache_write_success:
        logger.info("Result cached")
        return True
    else:
        logger.warning("Result was not cached.")
        return False

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

            request_start_ms = now_ms()
            # initialise cache summary
            cache_summary = CacheSummary(
                route_name=route_name,
                request_start_ms=request_start_ms
            )

            # 0. If caching has been disabled via config, skip all caching logic and just execute the function.
            # Default values in cache summary assume cache is bypassed and phase is direct, unless overridden by later logic.
            cache_summary.outcome = CacheOutcome.BYPASS
            cache_summary.phase = CachePhase.DIRECT

            if not current_app.config.get('ENABLE_CACHING', True):
                logger.info("Caching is disabled via config. Skipping cache logic.")

                cache_summary.bypass_reason="config_disabled"
                service_result = _execute_and_log(cache_summary, service_func, validated_input, *args, **kwargs) 

                return service_result
            
            cache_backend = None
            try:
                cache_backend = cache.cache
            except (AttributeError, KeyError):                
                logger.warning(
                        "Cache backend is not available when checking disabled-cache state. "
                        "Continuing without cache backend access.",
                        exc_info=True,
                )
                cache_backend = None

            
            # If a previous request caused the Redis cache backend to disable itself,
            # bypass caching for this request and execute the service function directly.
            if cache_backend is not None and hasattr(cache_backend, "is_disabled") and cache_backend.is_disabled():
                logger.info("Caching has been disabled due to a previous Redis failure. Skipping cache logic.")

                cache_summary.bypass_reason="backend_disabled"
                service_result = _execute_and_log(cache_summary, service_func, validated_input, *args, **kwargs)

                return service_result

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

                cache_summary.bypass_reason="shadow_or_non_target_provider"
                service_result = _execute_and_log(cache_summary, service_func, validated_input, *args, **kwargs)  

                return service_result
              
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

                cache_summary.bypass_reason="cache_key_generation_failed"
                service_result = _execute_and_log(cache_summary, service_func, validated_input, *args, **kwargs) 

                return service_result

            # After this point, we no longer have logic for bypassing the cache - set default outcome to MISS, which will be updated to HIT if we find a cached result.
            cache_summary.outcome = CacheOutcome.MISS

            # 3. Check the cache to see if the content has already been created, if so, return it   
            cached_result = _try_get_cache(cache_key, result_model, cache_summary=cache_summary)  
            if cached_result is not None:

                return cached_result
            
            # if we're using redis, can use redis locks to prevent multiple processes from doing the same work while we compute and set the cache. 
            # If we're using simple cache (in-memory, for testing), we skip locking as it's not needed.
            if current_app.config.get('CACHE_TYPE', "simple") == "simple":
                logger.info("CACHE MISS")

                cache_summary.phase = CachePhase.SIMPLE
                service_result = _execute_and_log(cache_summary, service_func, validated_input, *args, **kwargs)
                cache_success = _cache_result(g.request_id, service_result, cache_key, timeout)

                return service_result

            
            # 4. Otherwise, compute content - lock key first to prevent other processes from doing the same work while we compute and set the cache
            lock_acquired = cache.cache.acquire_lock(cache_key, timeout=120)
            # If no one else has the lock, we proceed to check the cache and potentially execute the function.
            if lock_acquired:
                try:
                    # double-check the cache after acquiring the lock 

                    cache_summary.phase = CachePhase.AFTER_LOCK
                    cached_result = _try_get_cache(cache_key, result_model, cache_summary=cache_summary)

                    if cached_result is not None:   

                        return cached_result
                    
                    # still a miss => generate the content
                    logger.info("CACHE MISS")
                    service_result = _execute_and_log(cache_summary, service_func, validated_input, *args, **kwargs)
                    cache_success = _cache_result(g.request_id, service_result, cache_key, timeout)

                    return service_result

                finally:
                    # Always release the lock after checking the cache and executing
                    cache.cache.release_lock(cache_key)
                    
            else:
                logger.debug("Cache lock is held by another process. Retrying...")    
                lock_wait_start_ms = now_ms()
                
                emit_cache_event(
                    "cache_lock_wait_started",
                    route=route_name,
                )

                # wait for the content to be ready in the cache
                cache_summary.phase = CachePhase.AFTER_WAIT
                for _ in range(3): # Try to get result for a certain number of attempts (wait for the leader to finish)
                    time.sleep(10) # Sleep for 10s before retrying (sleep first to avoid redundant checks)
                    # double-check the cache after acquiring the lock 
                    cache_summary.wait_ms = now_ms() - lock_wait_start_ms
                    cached_result = _try_get_cache(cache_key, result_model, cache_summary=cache_summary)

                    if cached_result is not None:
                        emit_cache_event(
                            "cache_lock_wait_resolved",
                            route=route_name,
                            wait_ms=cache_summary.wait_ms,
                        )
                        
                        return cached_result            

            logger.warning("Could not acquire cache lock after multiple attempts. Proceeding without caching.")
            logger.info("CACHE MISS")    

            wait_ms = now_ms() - lock_wait_start_ms if 'lock_wait_start_ms' in locals() else 0

            emit_cache_event(
                "cache_lock_wait_fallback",
                route=route_name,
                wait_ms=wait_ms,
            )

            cache_summary.phase = CachePhase.AFTER_WAIT_FALLBACK
            cache_summary.wait_ms = wait_ms
            service_result = _execute_and_log(cache_summary, service_func, validated_input, *args, **kwargs)

            return service_result 
            
        return wrapper
    return decorator
