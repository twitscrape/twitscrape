import itertools
import logging
import time
from datetime import datetime, timezone
from multiprocessing.connection import Connection
from typing import Optional, Iterator, List

from twitscrape.models import Tweet, TweetsWithCursors
from twitscrape.queries import query_user_tweets
from twitscrape.settings import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.log_level)


def get_last_tweets(
    user_id: str, count: int = settings.tweet_count, include_retweets: bool = True
) -> List[Tweet]:
    tweets = user_tweets(user_id, include_retweets=include_retweets)
    # Take count elements from tweets
    last_tweets = itertools.islice(tweets, count)
    return list(last_tweets)


def stream_tweets(
    user_id: str,
    initial_count: int = 5,
    polling_seconds: int = 10 * 60,
    include_retweets: bool = True,
) -> Iterator[Tweet]:
    """
    Get the most recent tweets by a user and periodically return all new tweets by that user
    """
    start_time: float = time.time()
    iteration: int = 0
    last_tweet_time: datetime = datetime.fromtimestamp(0, tz=timezone.utc)
    logger.debug(f"Getting {initial_count} most recent tweets")
    initial_tweets = get_last_tweets(
        user_id, count=initial_count, include_retweets=include_retweets
    )
    for tweet in reversed(initial_tweets):
        last_tweet_time = max(last_tweet_time, tweet.created_at)
        yield tweet
    while True:
        iteration += 1
        wake_time = start_time + (polling_seconds * iteration)
        delta = max(wake_time - time.time(), 0)
        logger.debug(f"Sleeping for {int(delta)} seconds")
        time.sleep(delta)
        logger.debug(f"Checking for tweets since {last_tweet_time.isoformat()}")
        tweets = user_tweets(user_id, include_retweets=include_retweets)

        def is_new(t: Tweet):
            return t.created_at > last_tweet_time

        new_tweets = itertools.takewhile(is_new, tweets)
        for tweet in reversed(list(new_tweets)):
            last_tweet_time = max(last_tweet_time, tweet.created_at)
            yield tweet


def user_tweets(
    user_id: str,
    include_retweets: bool = True,
) -> Iterator[Tweet]:
    """
    Get an iterator over a Twitter user's tweets, starting from most recent
    :param user_id: Twitter user ID as obtained from query_user_id
    :param include_retweets: Whether to return retweets as well as original tweets
    :return:
    """
    cursor_next: Optional[str] = None
    pinned_tweet: Optional[Tweet] = None
    # For tracking whether pinned tweet has been returned
    sent_pinned: bool = False

    while True:
        # Request two more entries than required to account for cursors
        tweets_cursored = _get_user_tweets_batch(user_id, cursor=cursor_next)
        if tweets_cursored.pinned_tweet is not None and pinned_tweet is None:
            pinned_tweet = tweets_cursored.pinned_tweet
        cursor_next = tweets_cursored.cursor_next
        if len(tweets_cursored.timeline_tweets) == 0:
            break
        for current_tweet in tweets_cursored.timeline_tweets:
            # Check if pinned tweet needs to be sent
            if (
                not sent_pinned
                and pinned_tweet is not None
                and current_tweet.created_at < pinned_tweet.created_at
            ):
                yield pinned_tweet
            if include_retweets or current_tweet.retweeted_status is None:
                yield current_tweet
    if not sent_pinned and pinned_tweet is not None:
        yield pinned_tweet


def by_created_at(tweet: Tweet) -> datetime:
    return tweet.created_at


def _get_user_tweets_batch(
    user_id: str,
    cursor: Optional[str] = None,
) -> TweetsWithCursors:
    """
    Get a batch of user tweets starting from a cursor, sorted from most recent
    :param user_id: User to get tweets of
    :param cursor: Optional cursor to get the next or previous batch
    """
    logger.debug(f"Requesting {settings.batch_count} tweets")
    instructions = query_user_tweets(user_id, cursor=cursor, count=settings.batch_count)

    # Handle pinned tweets
    pinned_tweets = [
        instruction["entry"]["content"]["itemContent"]["tweet"]
        for instruction in instructions
        if instruction["type"] == "TimelinePinEntry"
        # Filter out tweets without read permission
        and "legacy" in instruction["entry"]["content"]["itemContent"]["tweet"]
    ]
    pinned_tweet: Optional[Tweet] = None
    if pinned_tweets:
        assert len(pinned_tweets) == 1, "Multiple pinned messages"
        pinned_tweet = Tweet.parse(pinned_tweets[0])

    # Handle timeline tweets
    timeline_entries = [
        instruction["entries"]
        for instruction in instructions
        if instruction["type"] == "TimelineAddEntries"
    ][0]
    timeline_tweets_unparsed = [
        entry["content"]["itemContent"]["tweet"]
        for entry in timeline_entries
        if entry["content"]["entryType"] == "TimelineTimelineItem"
        # Filter out tweets without read permission
        and "legacy" in entry["content"]["itemContent"]["tweet"]
    ]
    timeline_tweets = [Tweet.parse(tweet) for tweet in timeline_tweets_unparsed]

    # Get cursors for pagination
    cursor_previous = [
        entry["content"]["value"]
        for entry in timeline_entries
        if entry["content"]["entryType"] == "TimelineTimelineCursor"
        and entry["content"]["cursorType"] == "Top"
    ][0]
    cursor_next = [
        entry["content"]["value"]
        for entry in timeline_entries
        if entry["content"]["entryType"] == "TimelineTimelineCursor"
        and entry["content"]["cursorType"] == "Bottom"
    ][0]

    logger.debug(f"Received {len(timeline_tweets)} tweets")
    ordered_tweets = list(sorted(timeline_tweets, key=by_created_at, reverse=True))
    return TweetsWithCursors(
        timeline_tweets=ordered_tweets,
        cursor_next=cursor_next,
        cursor_previous=cursor_previous,
        pinned_tweet=pinned_tweet,
    )


def send_streamed_tweets(
    send_conn: Connection,
    user_id: str,
    initial_count: int = 5,
    polling_seconds: int = 10 * 60,
    include_retweets: bool = True,
):
    """
    Stream tweets as per stream_tweats sending over multiprocessing pipe to parent process
    """
    stream = stream_tweets(
        user_id=user_id,
        initial_count=initial_count,
        polling_seconds=polling_seconds,
        include_retweets=include_retweets,
    )
    for tweet in stream:
        send_conn.send(tweet)
