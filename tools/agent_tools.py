import json
import logging
import re
from datetime import datetime
from urllib.parse import quote_plus

import requests

TOOLSROOT = "https://safety.devsic.com/apis/pwrdesk_chat/tools/"

# TODO: Put this someplace better.
logging.basicConfig(
    filename="/home/adbradley/policy-tools.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _check_policy_format(policy_number):
    logging.debug("Checking format of policy number %s" % policy_number)
    return bool(re.match(r"([a-z]{3})?\d{7}", policy_number, re.IGNORECASE))


def _powerdesk_link(policy_number: str) -> str:
    if _check_policy_format(policy_number):
        return (
            "https://avc.devsic.com/applications/pwrdesk/policy_search.pl?pol_search="
            + policy_number
        )
    else:
        raise ValueError(r"Not a valid policy number: %s" % (policy_number,))


class Tools:
    def __init__(self):
        pass

    def get_policy_data(self, policy_number: str, user: str, session: str) -> str:
        """
        Return information about an individual insurance policy. policy_number is the number
        of the policy you need information for.

        Note that the exact format of the information, and the kind of information returned,
        may vary by the type of policy, but should always include billing information, including
        AutoPay eligibility, due dates and amounts, and installment plan details.

        :param policy_number: The policy number you need information about.
        :param user: A user ID. Another assistant will provide this to you.
        :param session: A session ID. Another assistant will provide this to you.
        """
        # TODO: check whether we're in prod. How?
        # production = False

        if not _check_policy_format(policy_number):
            raise ValueError(r"Not a valid policy number: %s" % (policy_number,))

        url = f"{TOOLSROOT}policy_detail/{policy_number}"

        try:
            response = requests.get(
                url, params={"cert": user, "session": session}, verify=False
            )
            outp = response.json()
            return json.dumps(outp)
        except Exception as e:
            raise e

    def search_policies(self, search_keywords: str, user: str, session: str) -> str:
        """
        Search for a policy using one or more of the parameters listed below.

        If this returns more than five policies, you will be prompted to ask the user for more details to narrow down the search.

        Be sure to use the city, state, and zipcode parameters if you have the relevant information.

        The search_keywords parameter is a string-separated list. To search for "John Smith in Boston" set search_keywords to
        "John Smith Boston". To search for "John Smith on Custom House Street in Boston", set search_keywords to "john smith
        custom house boston".

        :param search_keywords: Any parts of the insured's name or address that are available, space-separated.
        :param user: A user ID. This will be provided by another assistant.
        :param session: A session id, provided by another assistant.
        """
        url = f"{TOOLSROOT}minifile/search/{quote_plus(search_keywords)}"
        searchresp = requests.get(
            url, params={"cert": user, "session": session}, verify=False
        )

        try:
            outp = searchresp.json()
        except Exception as e:
            return json.dumps({"error": str(e)})

        return json.dumps(outp)

    def get_powerdesk_link(self, policy_number: str) -> str:
        """
        Return a URL to find information about a policy on PowerDesk. PowerDesk is
        the web application Safety Insurance agents use to look up information about
        their customers' policies.

        :param policy_number The number of the policy you want a link for.
        """
        return _powerdesk_link(policy_number)

    def get_current_time(self) -> str:
        """
        Get the current time in a more human-readable format.
        :return: The current time.
        """
        logging.debug("Getting current time for the model.")
        now = datetime.now()
        current_time = now.strftime("%I:%M:%S %p")  # Using 12-hour format with AM/PM
        current_date = now.strftime(
            "%A, %B %d, %Y"
        )  # Full weekday, month name, day, and year

        return f"Current Date and Time = {current_date}, {current_time}"
