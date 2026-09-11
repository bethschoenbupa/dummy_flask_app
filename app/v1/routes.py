###### BIRTHDAY ROUTES ######
# Author: Bethany Schoen
# Date: 17th December 2025
#############################
# Endpoints for the dummy app
#############################

from flask import Blueprint
from typing import Callable

from app.v1.schemas import HaikuRequestModel, HaikuServiceResult
from app.v1.services import haiku_service

from app.common.clients.text_generation import TextGenerator
from app.v1.utils.route_decorator import api_route

# --- Blueprint setup --- #
v1_bp = Blueprint('v1', __name__)
api_version = 1
v1_bp.api_version = api_version 

# --- Routes --- #
@v1_bp.route(f"/birthdayhaiku", methods=["POST"])
@api_route(
    json_request_model=HaikuRequestModel, 
    service_result_model=HaikuServiceResult,
)
def birthday_haiku(validated_input: HaikuRequestModel, get_generator: Callable[[str], TextGenerator]):
    """
    API Endpoint for generating a birthday haiku.
    """
    return haiku_service(validated_input, get_generator)

# ================================= #
#       --- Next Year Route ---     #
# ================================= #

# Paste notebook code here