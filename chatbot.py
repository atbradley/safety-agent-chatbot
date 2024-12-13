import httpx
import openai
from sanic import Sanic
from sanic.response import json
from json import dumps as jsondump, loads as jsonloads

import logging
from logging.handlers import RotatingFileHandler


from settings import api_key, base_url, model_id

# Set up logging to a file
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a rotating file handler
file_handler = RotatingFileHandler('app.log', maxBytes=1000000, backupCount=3)
file_handler.setLevel(logging.DEBUG)

# Create a formatter and add it to the file handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

app = Sanic("ChatProxy")


@app.post("/chat")
async def chat(request):
    prod = False # TODO: Need a way to check this. Referer? Or does the script need to tell me?
    policy_number = request.headers.get("X-Policy-Number", False)
    #policy_year = request.headers.get("X-Policy-Year")

    with open('powerdesk_assistant_prompt.md', 'r') as f:
        assistant_prompt = f.read()
    print(request.json)
    msgs = [{"role": "assistant", "content": assistant_prompt}]+request.json

    if policy_number:
        msgs.insert(-1, {"role": "assistant", "content": "The user is currently reviewing policy %s on PowerDesk. Don't include a PowerDesk Link in your next response." % policy_number})

    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer '+api_key}

    payload = {
        "model": model_id,
        "messages": msgs,
        "tool_ids": ["policy_tools"],
    }

    response = httpx.post(base_url + "/chat/completions", headers=headers, json=payload, timeout=60)

    logger.debug(response.text)
    response = response.json()
    resp = request.json + [response['choices'][0]['message']]
    return json(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000, debug=True, auto_reload=True)
