import asyncio
import logging
import re
from logging.handlers import RotatingFileHandler
from os import chdir, getcwd

import httpx
from bs4 import BeautifulSoup
from sanic import Sanic
from sanic.response import json

from settings import api_key, api_base_url, host, model_id, port, DEBUG, AUTO_RELOAD

# Set up logging to a file
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a rotating file handler
file_handler = RotatingFileHandler("app.log", maxBytes=1000000, backupCount=3)
file_handler.setLevel(logging.DEBUG)

# Create a formatter and add it to the file handler
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

policy_match = re.compile(r"[a-z]{3}[0-9]{7}", re.IGNORECASE)

app = Sanic("ChatProxy")


@app.post("/chat")
async def chat(request):
    # prod = False  # TODO: Need a way to check this. Referer? X-Forwarded-For? Or does the script need to tell me?
    policy_number = request.headers.get("X-Policy-Number", False)
    # policy_year = request.headers.get("X-Policy-Year")

    with open("powerdesk_assistant_prompt.md", "r") as f:
        assistant_prompt = f.read()
    print(request.json)
    msgs = [{"role": "assistant", "content": assistant_prompt}] + request.json

    if policy_number:
        msgs.insert(
            -1,
            {
                "role": "assistant",
                "content": "The user is currently reviewing policy %s on PowerDesk. Don't include a PowerDesk Link in your next response."
                % policy_number,
            },
        )

    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}

    payload = {
        "model": model_id,
        "messages": msgs,
        "tool_ids": ["policy_tools"],
    }

    response = httpx.post(
        api_base_url + "/chat/completions", headers=headers, json=payload, timeout=60
    )

    logger.debug(response.text)
    response = response.json()
    resp = request.json + [response["choices"][0]["message"]]
    return json(resp)


@app.route("/tools/policy_detail/<policy_number:[a-zA-Z]{3}[0-9]{7}>")
async def pwrdesk_billing(request, policy_number: str):
    ip_address = request.headers.get("X-Forwarded-For", request.ip)
    print(ip_address)
    if  ip_address not in ["172.18.4.202", "172.19.104.165"]:  #Mater, atb's laptop.
        return json({"error": "Unauthorized"}, status=401)

    # Probably unnecessary--the route won't send us here without a valid policy number.
    if not bool(policy_match.fullmatch(policy_number)):
        return json({"error": "Invalid policy number"}, status=400)

    script_dir = "/var/www/apps/pwrdesk/"
    script = "pwrdesk_socket_csc.pl"
    params = f"policy_number={policy_number}"
    # TODO: Decide the domain dynamically.
    powerdesk_url = f"https://avc.devsic.com/applications/pwrdesk/{script}?{params}"

    cdir = getcwd()
    chdir(script_dir)

    process = await asyncio.create_subprocess_exec(
        "perl",
        script,
        params,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    pages = []
    

    

    stdout, _ = await process.communicate()

    if process.returncode != 0:
        return json({"error": "Failed to get policy data"}, status=500)
    else:
        stdout = stdout.decode().strip()

    soup = BeautifulSoup(stdout, "html.parser")
    main_div = soup.find("div", id="main")

    main_div.find("div", id="pwrdesk_search").decompose()

    #TODO: Are there Policy or Coverages tabs? Follow those links and include the pages.

    outp = {
        "policy_number": policy_number,
        "policy_pages": {
            "policy_billing": str(main_div),
        },
        "powerdesk_url": powerdesk_url,
    }

    chdir(cdir)

    return json(outp)


if __name__ == "__main__":
    app.run(host=host, port=port, debug=DEBUG, auto_reload=AUTO_RELOAD)
