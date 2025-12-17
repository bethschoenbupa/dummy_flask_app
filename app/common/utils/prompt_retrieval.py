#### PROMPT RETRIEVAL ####
# Author: Bethany Schoen
# Date: 24th July 2025
##########################
# To access prompts using
# version and task
##########################

import pandas as pd
from typing import Union
from flask import current_app

def access_prompt_data() -> pd.DataFrame:
    """
    Access the prompt data from storage

    Returns
    -------
    pd.DataFrame
        The prompt data if found
    """
    # this has been massively simplified for demo purposes
    # we might want to add 
    # - logic checking the file exists
    # - check the columns are as expected
    # - read the data from cloud storage
    # - save the file path as a variable
    df = pd.read_csv('data/birthday_prompts.csv')
    
    return df

def get_prompt(prompt_name: str, version: Union[str, float] = "latest") -> str:
    """
    Get a prompt by name and version
    Parameters
    ----------
    prompt_name : str
        The name of the prompt to retrieve
    version : str or float, optional
        The version of the prompt to retrieve, or "latest" (default is "latest")

    Returns
    -------
    str
        The prompt if found
    """
    # load prompt data
    try:
        # prompt data should have been loaded in the app context (at app startup)
        if hasattr(current_app, "prompt_data") and not current_app.prompt_data is None:
            df = current_app.prompt_data
        else:
            raise Exception("Prompt data not in app context.")
    except:
        print("WARNING: Prompt data is not available in the app context. Therefore, loading local prompt data before completing task - this can slow down runtime.")
        df = access_prompt_data(use_cloud_prompts=False)

    # filter for prompt name
    # (Exceptions have been simplified for demo purposes)
    df = df[df["TASK"] == prompt_name]
    if df.empty:
        raise Exception("Prompt data empty after filtering by TASK")

    # filter for version
    if version == "latest":
        version_to_find = df["VERSION"].max()
    elif isinstance(version, float) or isinstance(version, int):
        version_to_find = version
    else:
        raise Exception("Version parameter not recognised")
    
    df = df[df["VERSION"] == version_to_find]

    if df.empty:
        raise Exception("Prompt data empty after filtering by VERSION")
    elif len(df) > 1:
        raise Exception("Multiple prompts found")

    prompt = df["PROMPT"].iloc[0]
    
    return prompt