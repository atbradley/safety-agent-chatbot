import asyncio
import logging
import os
import re
import sys
from datetime import date, datetime
from json import dumps as jdump
from logging.handlers import RotatingFileHandler
from urllib.parse import unquote_plus

import httpx
import pyodbc

# Handles memoization for async functions.
from async_lru import alru_cache
from bs4 import BeautifulSoup
from sanic import Sanic
from sanic.response import json
from smoltalk import Toolbox

from pwrdesk_tools import Pwrdesk_Tools
from settings import (
    AUTO_PREFIXES,
    AUTO_RELOAD,
    DEBUG,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LOG_LEVEL,
    POWERDESK_ROOT,
    api_base_url,
    api_key,
    base_url,
    cstring,
    lines_of_business,
    model_id,
    sock,
)


def json_serial(obj):
    """JSON serializer for datetime objects"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()


mssql = pyodbc.connect(cstring)

# Set up logging to a file
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# Create a rotating file handler
file_handler = RotatingFileHandler(
    "logs/agent-chatbot.log", maxBytes=1000000, backupCount=3
)

# Create a formatter and add it to the file handler
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

# Create a stream handler to log to stdout
# stream_handler = logging.StreamHandler(sys.stdout)
# stream_handler.setFormatter(formatter)
# logger.addHandler(stream_handler)

policy_match = re.compile(r"[a-z]{3}[0-9]{7}", re.IGNORECASE)
SCRIPT_DIR = "/var/www/apps/pwrdesk/"


logger.debug("Loading the system prompt.")
with open("system_prompt.md", "r") as f:
    system_prompt = f.read()

app = Sanic("Pwrdesk_Chat")


@app.before_server_start
async def on_before_server_start(app: Sanic):
    logger.info("Starting chatbot server.?")


@app.route(base_url + "/tools/policy_detail/<policy_number:[a-zA-Z]{3}[0-9]{7}>")
async def pwrdesk_detail(policy_number: str) -> dict:...


@app.route(base_url + "/tools/minifile/search/<s:str>")
async def minifile_search(request, s: str):...
    
@app.post(base_url + "/chat")
async def chat(request):
    logger.info("starting chat.")
    policy_number = request.headers.get("X-Policy-Number", False)
    cert = request.headers.get("ssl_client_s_dn")
    session = request.cookies.get("session_id_pwrdesk")
    
    msgs = request.json
    logger.info("Messages received: " + jdump(msgs))

    print(request.headers)

    pwrdesk_toolbox = Pwrdesk_Tools(request)

    toolbox = Toolbox(
        pwrdesk_toolbox,
        root_url=LLM_BASE_URL,
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        system_prompt=system_prompt,
        fail_on_tool_error=True,
    )


    if policy_number:
        msgs.insert(
            0,
            {
                "role": "assistant",
                "content": """The user is currently reviewing policy number %(policy_number)s on PowerDesk. If the user asks about "this policy", they are referring to that number.
Don't include a PowerDesk Link in your next response unless the user asks about a different policy.

The User ID for this chat is "%(cert)s", and the Session ID is "%(session)s". You will need these to call tools for this user.

Again, throughout this conversation, "this policy" refers to policy %(policy_number)s"""
                % {"policy_number": policy_number, "cert": cert, "session": session},
            },
        )

    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}

    payload = {
        "model": model_id,
        "messages": msgs,
        "tool_ids": ["policy_tools"],
    }

    logger.info("Chat payload: " + jdump(payload))

    async with httpx.AsyncClient() as client:
        response = await client.post(
            api_base_url + "/chat/completions",
            headers=headers,
            json=payload,
            timeout=300,
        )

    logger.info("Chat response: " + response.text)
    response = response.json()
    resp = request.json + [response["choices"][0]["message"]]
    return json(resp)


if __name__ == "__main__":
    try:
        from settings import sock
        app.run(unix=sock, debug=DEBUG, auto_reload=AUTO_RELOAD)
    except ImportError:
        from settings import host, port

        app.run(host=host, port=port, debug=DEBUG, auto_reload=AUTO_RELOAD)
