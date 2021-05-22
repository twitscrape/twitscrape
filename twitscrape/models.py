from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class Tweet(BaseModel):
    user_id: str
    tweet_id: str
    created_at: datetime
    text: str
    retweeted_status: Optional["Tweet"] = None

    @classmethod
    def parse(cls, data: dict) -> "Tweet":
        legacy = data["legacy"]
        retweeted_status = (
            Tweet.parse(legacy["retweeted_status"])
            if "retweeted_status" in legacy
            else None
        )
        created_at = datetime.strptime(legacy["created_at"], "%a %b %d %H:%M:%S %z %Y")
        return Tweet(
            user_id=legacy["user_id_str"],
            tweet_id=legacy["id_str"],
            created_at=created_at,
            text=legacy["full_text"],
            retweeted_status=retweeted_status,
        )

    def get_body(self):
        if self.retweeted_status is None:
            return self.text
        return self.retweeted_status.get_body()

    def __hash__(self):
        return hash(self.tweet_id)


# Due to recursive definition of retweeted_status, need to update refs
Tweet.update_forward_refs()


class TweetsWithCursors(BaseModel):
    timeline_tweets: List[Tweet]
    cursor_next: str
    cursor_previous: str
    pinned_tweet: Optional[Tweet]
