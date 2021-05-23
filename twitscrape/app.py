import asyncio
from multiprocessing import Process, Pipe
from typing import List

from fastapi import FastAPI

from twitscrape.models import Tweet
from twitscrape.settings import settings
from twitscrape.twitscrape import send_streamed_tweets

tweets: List[Tweet] = []
recv, send = Pipe(duplex=False)

app = FastAPI(title="TwitScrape", description="Unauthenticated Twitter Scraper")


@app.get("/", response_model=List[Tweet])
def list_tweets() -> List[Tweet]:
    return tweets


async def recv_tweets():
    """
    Poll pipe for tweets sent by child process without blocking event loop
    """
    while True:
        try:
            if recv.poll():
                tweet = recv.recv()
                print(tweet.get_body())
                tweets.append(tweet)
            else:
                await asyncio.sleep(0.5)
        except EOFError:
            return


@app.on_event("startup")
async def start_recv():
    asyncio.create_task(recv_tweets())


def run_app(
    *args,
    **kwargs,
):
    """
    Start worker process to stream tweets and run API
    """
    import uvicorn

    stream_proc = Process(
        target=send_streamed_tweets,
        name="streamthread",
        args=(send, *args),
        kwargs=kwargs,
    )
    stream_proc.start()
    try:
        uvicorn.run(app, host=settings.host, port=settings.port, workers=1)
    finally:
        stream_proc.kill()
