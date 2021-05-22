import logging
from contextlib import contextmanager
from typing import ContextManager

from requests import Session
from torpy.http.requests import tor_requests_session

from twitscrape.settings import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.log_level)
authorization = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:78.0) Gecko/20100101 Firefox/78.0",
    "content-type": "application/json",
    "authorization": authorization,
}


@contextmanager
def twitter_session() -> ContextManager[Session]:
    """Context manager providing an authenticated twitter session over a tor circuit"""
    while True:
        with tor_requests_session(headers=headers) as s:
            r = s.post("https://api.twitter.com/1.1/guest/activate.json")
            if r.status_code == 429:
                logger.debug("Client rate limited, re-circuiting...")
            elif r.status_code != 200:
                raise ValueError(f"Failed to get guest token: {r!r}")
            token = r.json()["guest_token"]
            s.headers.update({"x-guest-token": token})
            logger.debug("Obtained token")
            yield s
            return
