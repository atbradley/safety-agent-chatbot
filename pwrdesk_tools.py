import json

from async_lru import alru_cache
from bs4 import BeautifulSoup
from urllib.parse import urlencode
import httpx
import logging
from sanic import request
import os
import re

logger = logging.getLogger(__name__)

class Pwrdesk_Tools:
    SCRIPT_DIR = "/var/www/apps/pwrdesk/"
    policy_match = re.compile(r"[a-z]{3}[0-9]{7}", re.IGNORECASE)

    def __init__(self, request: request):
        self.request = request


    @staticmethod
    @alru_cache(ttl=3600)
    async def _get_broker_numbers(o: str) -> list[str]:
        """
        Retrieve broker numbers for a given organization.
        """
        # TODO.
        # Return as a list:
        sql = """WITH brokers AS (
                SELECT broker_name, broker_num FROM master_broker WHERE obsolete = 0
                UNION SELECT 'Safety Insurance', '#####'
                ) 
                SELECT broker_num FROM brokers WHERE broker_name = ?;"""

    @staticmethod
    @alru_cache(ttl=600)
    async def _get_policy_page(script, params, session, cert):
        """
        Retrieve a single policy page from PowerDesk.
        """
        process = await asyncio.create_subprocess_exec(
            "perl",
            script,
            params,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                "HTTP_COOKIE": f"session_id_pwrdesk={session}",
                "SSL_CLIENT_S_DN": cert,
            },
        )

        stdout, _ = await process.communicate()

        if process.returncode != 0:
            return False
        else:
            fullpage = stdout.decode().strip()

        soup = BeautifulSoup(fullpage, "html5lib")
        main_div = soup.find("div", id="main")

        main_div.find("div", id="pwrdesk_search").decompose()
        return (main_div.prettify(), fullpage)

    @staticmethod
    async def _get_coverage_pages(policy_number, session, cert):
        coverages = []
        outp = []
        async with asyncio.TaskGroup() as tg:
            for i in range(1, 4):
                coverages.append(
                    tg.create_task(
                        get_policy_page(
                            "pwrdesk_socket.pl",
                            f"page=iapw_p22.html&policy_number={policy_number}&p_end=2.0&p_veh={i:03d}&prod=1",
                            session,
                            cert,
                        )
                    )
                )

        if not coverages[0].result():
            return []
        num_vehicles = coverages[0].result()[1].count("<17>")
        coverages = coverages[:num_vehicles]
        async with asyncio.TaskGroup() as tg:
            for i in range(len(coverages), num_vehicles):
                coverages.append(
                    tg.create_task(
                        get_policy_page(
                            "pwrdesk_socket.pl",
                            f"page=iapw_p22.html&policy_number={policy_number}&p_end=2.0&p_veh={i:03d}&prod=1",
                            session,
                            cert,
                        )
                    )
                )

        for i, v in enumerate(coverages):
            if (
                v.result() and num_vehicles >= i + 1
            ):  # Not an error and there are this many vehicles on the policy.
                outp.append(v.result()[1])

        return coverages

    @staticmethod
    async def _get_policy_pages(policy_number, session, cert):
        cdir = os.getcwd()
        os.chdir(__class__.SCRIPT_DIR)
        script = "pwrdesk_socket_csc.pl"
        params = f"policy_number={policy_number}"

        async with asyncio.TaskGroup() as tg:
            pages = {}
            pages["billing"] = tg.create_task(
                __class__._get_policy_page(script, params, session, cert)
            )
            if policy_number[:3] in AUTO_PREFIXES:
                script = "pwrdesk_socket.pl"
                pages["policy"] = tg.create_task(
                    __class__._get_policy_page(
                        script,
                        f"policy_number={policy_number}&policy_year=2024&page=iapw_p1a.html&prod=1",
                        session,
                        cert,
                    )
                )
                pages["operators"] = tg.create_task(
                    __class__._get_policy_page(
                        script,
                        f"policy_number={policy_number}&p_end=020;page=iapw_p23.html&prod=1",
                        session,
                        cert,
                    )
                )
                coverages = tg.create_task(
                    __class__._get_coverage_pages(policy_number, session, cert)
                )

        os.chdir(cdir)

        powerdesk_url = POWERDESK_ROOT + "policy_search.pl?pol_search=" + policy_number
        policy_pages = {k: v.result()[0] for (k, v) in pages.items() if v.result()}
        policy_pages["coverages"] = coverages.result()

        for k, v in pages.items():
            if v.result():
                with open(f"{k}.html", "w") as f:
                    f.write(v.result()[0])

        outp = {
            "policy_number": policy_number,
            "policy_pages": policy_pages,
            "powerdesk_url": powerdesk_url,
        }

        return outp

    async def pwrdesk_detail(self, policy_number: str) -> dict:
        """
        Receive details of a policy from PowerDesk. Returns a dictionary containing several HTML snippets.

        Parameters
        ----------
        policy_number : str
            The policy number to retrieve information about.

        Returns
        -------
        str
            Returns a dictionary containing several HTML snippets representing information about a policy.
        """
        logger.info("starting pwrdesk_detail, policy number " + policy_number)
        
        # Probably unnecessary--the route won't send us here without a valid policy number.
        if not bool(__class__.policy_match.fullmatch(policy_number)):
            return json({"error": "Invalid policy number"}, status=400)

        cert = self.request.args.get("cert", self.request.headers.get("ssl_client_s_dn"))
        session_id = self.request.args.get(
            "session", self.request.cookies.get("session_id_pwrdesk")
        )

        print(policy_number, session_id, cert)

        outp = await __class__._get_policy_pages(policy_number, session_id, cert)
        logger.debug("pwrdesk_detail returning " + json.dumps(outp))

        logger.info("pwrdesk_detail finished.")

        return json.dumps(outp)

    async def policy_search(self, q: str, lob: str = ""):
        """
        Search for a policy by insured's name and address, optionally filtering by line of business.

        Parameters
        ----------
        q : str
            A search query string.

        lob: {'umb', 'home', 'bop', 'dfire', 'auto', 'cmu'}, optional
           The line of business to search. If None, search all lines of business. 
           The options are: 'umb': personal umbrella; 'home': homeowners; 'bop': businessowners; 
           'dfire': dwelling fire; 'auto': personal auto; 'cmu': commercial umbrella.
           Default is None.

        Returns
        -------
        str
            Returns a dictionary containing several HTML snippets representing information about a policy.
        """

        logger.info("starting minifile_search, query " + q)

        # TODO: Restrict search results by broker_num
        url_base = "https://safety.devsic.com/minifile/search"
        query_string = urlencode(
            {
                "json": 1,
                "query": q,
                "line_of_business": lob,
            }
        )

        try:
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get("%s?%s" % (url_base, query_string))
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            self.logger.critical(f"HTTP Exception for {exc.request.url} - {exc}")
            raise exc

        logger.debug("Returning data: %s" % json.dumps(resp.json()))
        # Return the JSON response
        return resp.json()
