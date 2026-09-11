from flask import Flask, request, g
import uuid

from config import config_by_name
from app.extensions import cache

from app.common.utils.error_handling import register_error_handlers
from app.common.utils.prompt_retrieval import access_prompt_data
from app.common.utils.request_logging import RequestLogger, NullRequestLogger

from app.v1.routes import v1_bp

from log import logger

def create_app(config_name="default"):
    """
    Setup Flask app
    1. Load prompt data
    2. Pre request hook
     - Create a request ID
     - Store request ID and api version
    3. Register blueprints
    4. Register error handlers
    """

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # 0. Setup caching
    if app.config["ENABLE_CACHING"]:
        try:
            cache.init_app(app)
            logger.info(f"Caching enabled: {app.config['CACHE_TYPE']}")
        except Exception as e:
            logger.warning(f"CACHING ISSUE: failed to initialise cache: {e}")


    # 1. Load prompt data
    # no try except here - if we can't access prompt data, there is a critical issue and the app shouldn't start
    app.prompt_data = access_prompt_data()
    print("PROMPTS: data successfully loaded into app context")

    # 2. Pre-request hook
    @app.before_request
    def setup_request_context():
        # This code runs before every request, after a route has been matched.
        g.request_id = str(uuid.uuid4())
        
        # Determine API version from the blueprint being used for this request
        g.api_version = "unknown"
        if request.blueprint and request.blueprint in app.blueprints:
            blueprint_object = app.blueprints[request.blueprint]
            g.api_version = str(getattr(blueprint_object, 'api_version', g.api_version))

        # Create and store the logger for this specific request on 'g'
        LoggerClass = RequestLogger if app.config['ENABLE_REQUEST_LOGGING'] else NullRequestLogger
        g.request_logger = LoggerClass(
            path=request.path,
            request_id=g.request_id,
            api_version=g.api_version,
            cloud_save=app.config['CLOUD_SAVE_LOGGING']
        )

        print(f"ID {g.request_id}: ## New Request to v{g.api_version}. Path: {request.path}")


    # 3. Register blueprints with URL prefixes
    app.register_blueprint(v1_bp, url_prefix='/api/v1')

    # 4. Register error handlers
    register_error_handlers(app)

    return app