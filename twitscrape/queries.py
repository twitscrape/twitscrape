import json
import logging
from typing import Optional

from requests.exceptions import RequestException
from twitscrape.session import twitter_session
from twitscrape.settings import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.log_level)


BASE_URL = "https://twitter.com/i/api/graphql"
USER_BY_NAME = f"Vf8si2dfZ1zmah8ePYPjDQ/UserByScreenNameWithoutResults"
USER_TWEETS = "L15nBTK_B0O_NMEpnsH4MQ/UserTweets"


def query(query_id_name: str, variables: dict, ignore_error=False) -> dict:
    """
    Establish a guest session over tor and attempt a GraphQL call.
    If an error is raised that may be due to server side blocking, or tor connectivity failure, retry.
    :param query_id_name: segment of query URL of the format BASE62ID/QueryName
    :param variables: variables required by specified query
    :param ignore_error: ignore "errors" key in GraphQL response if HTTP 200 Status received
    :return: the data value from the GraphQL response
    """
    while True:
        try:
            with twitter_session() as s:
                url = f"{BASE_URL}/{query_id_name}"
                r = s.get(
                    url,
                    params={"variables": json.dumps(variables)},
                )
                if r.status_code == 200:
                    contents = r.json()
                    if "errors" in contents:
                        # Generally indicates an incorrect query or variables
                        err = GraphQlError(
                            contents["errors"],
                            query_name=query_id_name,
                            variables=variables,
                        )
                        if ignore_error:
                            logger.exception(err)
                        else:
                            raise err
                    return contents["data"]
                if r.status_code == 404:
                    raise GraphQlIncompatibility(
                        f"The query {query_id_name} returned a 404, this likely means the API has changed and this tool is no longer compatible"
                    )
                logger.debug(
                    f"Request failed with status code: {r.status_code}. Re-circuiting..."
                )
        except RequestException as e:
            logger.debug(f"Request failed with exception: {e!r}. Re-circuiting...")


def query_user_id(screen_name: str) -> str:
    variables = {"screen_name": screen_name, "withHighlightedLabel": True}
    data = query(USER_BY_NAME, variables=variables)
    return data["user"]["rest_id"]


def query_user_tweets(user_id: str, count: int = 20, cursor: Optional[str] = None):
    variables = {
        "userId": user_id,
        "count": count,
        "cursor": cursor,
        "withHighlightedLabel": True,
        "withTweetQuoteCount": False,
        "includePromotedContent": False,
        "withTweetResult": False,
        "withReactions": False,
        "withUserResults": False,
        "withVoice": False,
        "withNonLegacyCard": False,
        "withBirdwatchPivots": False,
    }
    data = query(USER_TWEETS, variables=variables, ignore_error=True)
    instructions = data["user"]["result"]["timeline"]["timeline"]["instructions"]
    return instructions


class GraphQlError(Exception):
    def __init__(
        self,
        errors: list,
        query_name: str,
        variables: Optional[dict] = None,
    ):
        query_id, name = query_name.split("/")
        self.name = name
        self.id = query_id
        self.errors = errors
        self.variables = variables
        messages = [repr(error["message"]) for error in errors]
        err_message = ", ".join(messages)
        self.message = f"Errors in query {name!r}: {err_message}"
        super().__init__(self.message)


class GraphQlIncompatibility(Exception):
    pass
