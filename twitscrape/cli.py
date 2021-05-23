import typer

from twitscrape.queries import query_user_id
from twitscrape.twitscrape import get_last_tweets, stream_tweets

cli = typer.Typer(add_completion=False)


@cli.command()
def get(
    username: str,
    count: int = typer.Option(5, help="Number of tweets to get"),
    include_retweets: bool = typer.Option(
        False, "--retweets/--no-retweets", help="Include retweets"
    ),
):
    """
    Get the most recent tweets of a user
    """
    user_id = query_user_id(username)
    tweets = get_last_tweets(user_id, count=count, include_retweets=include_retweets)
    for tweet in tweets:
        print(tweet.get_body())


@cli.command()
def stream(
    username: str,
    serve: bool = typer.Option(
        False, help="Start a webserver to serve all tweets so far"
    ),
    count: int = typer.Option(5, help="Number of initial tweets to get"),
    include_retweets: bool = typer.Option(
        False, "--retweets/--no-retweets", help="Include retweets"
    ),
    minutes: float = typer.Option(10.0, help="Time between checking for tweets"),
):
    """
    Stream tweets from a user
    """
    user_id = query_user_id(username)
    polling_seconds = int(minutes * 60)
    if serve:
        from twitscrape.app import run_app

        run_app(
            user_id,
            initial_count=count,
            polling_seconds=polling_seconds,
            include_retweets=include_retweets,
        )
    else:
        for tweet in stream_tweets(
            user_id,
            initial_count=count,
            polling_seconds=polling_seconds,
            include_retweets=include_retweets,
        ):
            print(tweet.get_body())
