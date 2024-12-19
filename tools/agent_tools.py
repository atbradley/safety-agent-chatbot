import json
import logging
import re
from datetime import datetime
from typing import Optional

import requests

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


def _get_auto_or_ota_policy(self, policy_number: str) -> str:
    """
    Takes a policy number and returns either 'AUTO' for auto policies or 'OTA' for other policies.
    """
    return (
        "AUTO"
        if policy_number[:3] in ["PRV", "ANH", "AME", "COM", "CNH", "CME"]
        else "OTA"
    )


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

    def get_policy_data(self, policy_number: str) -> str:
        """
        Return information about an individual insurance policy. policy_number is the number
        of the policy you need information for.

        Note that the exact format of the information, and the kind of information returned,
        may vary by the type of policy.

        :param policy_number The policy number you need information about.
        """
        # TODO: check whether we're in prod. How?
        production = False

        if not _check_policy_format(policy_number):
            raise ValueError(r"Not a valid policy number: %s" % (policy_number,))

        url = f"https://avc.devsic.com/pwrdchat/tools/policy_detail/{policy_number}"

        try:
            response = requests.get(url, verify=False)
            outp = response.json()
            return json.dumps(outp)
        except Exception as e:
            raise e

    def search_policies(
        self,
        policy_type: str,
        # policy_num: Optional[str] = None,
        insured: str,
        # eff_date: Optional[str] = None,
        city: str,
        state: str,
        zipcode: str,
    ) -> str:
        """
        Search for a policy using one or more of the parameters listed below.

        If this returns more than five policies, you should ask the user for more details to narrow down the search.

        The policy_type parameter must be one of: "Auto", "OTA", "Personal Auto", "Commercial Auto", "Homeowner",
        "Dwelling Fire", "Umbrella", "Business Owner", "Commercial Umbrella".

        Be sure to use the city, state, and zipcode parameters if you have the relevant information.

        :param policy_type
        :param insured: The policyholder's full or partial name. Do not include titles (like "Mr.", "Ms.", or "Dr.")
        :param eff_date: The effective date of the policy.
        :param city: The policyholder's city. Set to an empty string if you don't know this.
        :param state: The policyholder's state. Set to an empty string if you don't know this.
        :param zipcode: The policyholder's zip code. Set to an empty string if you don't know this.
        """
        # The model's usage of this tool is flaky. Better docstring/system prompt?
        # PPA (01) CA (10) HO (24) DF (22) UMB (44) BOP (75) CMU (46)
        # https://safety.stagesic.com/policy/search.pl?city=mansfield&insured=test&test=1
        params = dict(
            filter(
                lambda x: x[0] != "self" and type(x[1]) in [int, str] and x[1] != "",
                locals().items(),
            )
        )
        params["test"] = 1  # TODO: distinguish between test and prod.
        auto = False

        auto_pol_types = {
            "Personal Auto": "01",
            "Commercial Auto": "10",
        }

        ota_pol_types = {
            "Homeowner": "24",
            "Dwelling Fire": "22",
            "Umbrella": "44",
            "Business Owner": "75",
            "Commercial Umbrella": "46",
        }

        params["policy_type"] = params["policy_type"].title()

        if params["policy_type"] == "Auto":
            auto = True
            del params["policy_type"]
        elif params["policy_type"] == "Ota":
            del params["policy_type"]
        elif params["policy_type"] in auto_pol_types.keys():
            params["policy_type"] = auto_pol_types[params["policy_type"]]
        elif params["policy_type"] in ota_pol_types.keys():
            params["policy_type"] = ota_pol_types[params["policy_type"]]
        else:
            raise ValueError("Invalid policy type")

        print(params)

        url = (
            "https://autoclaims-dev.safetyinsurance.com/TESTDP/X0116SRWSR"
            if auto
            else "https://safety.devsic.com/policy/search.pl"
        )
        print(url)
        searchresp = requests.get(url, params=params, verify=False)
        
        try:
            outp = searchresp.json()
            if auto:
                outp = outp["policysearch"]
        except KeyError as e:
            # We might not find "policysearch"
            return json.dumps({'error': "No results."})
        except Exception as e:
            return json.dumps({'error': e})

        pol_types = {v: k for k, v in (auto_pol_types | ota_pol_types).items()}

        for pol in outp:
            pol["powerdesk_url"] = _powerdesk_link(pol["policy_num"])
            pol["policy_type"] = pol_types[str(pol["risk_type"])]
            del pol["risk_type"]

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
