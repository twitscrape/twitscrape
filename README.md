# TwitScrape

TwitScrape is an unauthenticated CLI Twitter Feed.

## Installation

TwitScrape uses `poetry` for package management, install poetry with
```bash
pip3 install --user poetry
```

From the root of the repository, install `twitscrape` and it's dependencies with
```bash
poetry install
```

## Usage

For CLI help, pass `--help` to the command, or the relevant subcommand

```bash
twitscrape --help
```


### Streaming Tweets

```
Usage: twitscrape stream [OPTIONS] USERNAME

  Stream tweets from a user

Arguments:
  USERNAME  [required]

Options:
  --serve / --no-serve        Start a webserver to serve all tweets so far [default: False]
  --count INTEGER             Number of initial tweets to get  [default: 5]
  --retweets / --no-retweets  Include retweets  [default: False]
  --minutes FLOAT             Time between checking for tweets  [default: 10.0]
  --help                      Show this message and exit.
```
Get the most recent **COUNT** many tweets from a user, and then periodically display all new tweets
```bash
twitscrape stream username
```

Start an HTTP server to provide all tweets received so far
```bash
twitscrape stream username --serve
```
By default, the server binds to 0.0.0.0:8000, but can be changed by specifying the HOST and PORT environment variables.

With default settings, a JSON representation can be requested with
```bash
curl http://localhost:8000/
```

### Getting Tweets

```
Usage: twitscrape get [OPTIONS] USERNAME

  Get the most recent tweets of a user

Arguments:
  USERNAME  [required]

Options:
  --count INTEGER             Number of tweets to get  [default: 5]
  --retweets / --no-retweets  Include retweets  [default: False]
  --help                      Show this message and exit.
```

Get the 10 most recent tweets by the user `username`

````bash
twitscrape get --count 10 username
````
By default, retweets won't be included. To include retweets, pass `--retweets` to the command.


## Design

For a more raw record of the exploration of Twitter's API see [NOTES](NOTES)

TwitScrape is broken down into four layers responsible for retrieving and presenting the layer.

1. Session - Establishing Tor connections and managing guest "authentication"
2. Queries - Serializing query parameters, retrying failed queries and partially unnesting response data
3. TwitScrape - Business logic, pagination of results and timed polling of tweets
4. CLI/HTTP API - Presentation layer

### Session

"Authenticating" the client as a valid guest user is managed by `twitscrape/session.py` and is achieved by:

1) Using a Tor connection and changing to a fresh connection if an HTTP 401 (Unauthorized), HTTP 429 (Rate Limited) or
   connection failure occurs
2) Setting the necessary headers, specifically the `authorization` header to the static guest bearer token, and the
   `x-guest-token` based off a POST to `/guest/activate.json`
   
Currently a new session is established for every query, which adds a high time overhead, which may be worth resolving in
the future. Given the timing requirements of this tool, it has not been addressed.

This layer provides a degree of reliability during the establishment of the session, but retrying of queries beyond the
inital token request, is the responsibility of the query layer.

### Queries

The **queries** layer uses the HTTP sessions from the **session** layer to make "authenticated" queries to static, known
GraphQL URLs. The `query` function handles serializing the query variables, and retrying a request with a fresh session
if a **recoverable** error occurs.

A recoverable error is an error that could likely be caused by a breakage at the network layer, the guest auth layer or
an HTTP status this is not 200 (successful) or 404 (see below).

The unrecoverable errors of note are:

- 404 - Likely indicates a change in the prepared queries leading to an API incompatibility
- 200, but errors in response - Unless the query expects possible GraphQL errors, this indicates a likely error in our
  usage of the API

### Business Logic Layer

The key business logic that handles combining the results of multiple layers is managed in `twitscrape/twitscrape.py`.

It handles parsing the response of queries, as well as using the GraphQL APIs cursor pagination to provided a way to
iterate over a user's tweets.

This layer makes heavy use of Python generators with the `user_tweets` function providing a way to lazily iterate over
a series of Tweets.

### CLI

The CLI layer uses the `typer` library (which in-turn wraps `click`), as it provides a consise way of defining a CLI.

The `@cli.command` decorator uses the name and type signatures of the functions it wraps to automatically generate CLI
docs accessible via `--help`.

### HTTP API

The HTTP API logic is defined in `twitscrape/app.py` and starts a second process for scraping the tweets, which it
communicates with via a pipe. The design choice of using a separate process was due to the chosen tor library not
supporting asyncio, and as such using at least a separate thread is prefered, the choice of using a separate process is
due to the ability for Python to kill a process on termination, but not easily a thread.


## Assumptions

The application consumes Twitter's un-documented prepared-query GraphQL API.

Any breaking changes to that API may lead to this tool no longer working.

Assumptions particularly of note are that:

- The static guest token will remain static
- Twitter's prepared query URLs will remain valid

To handle the case of prepared query URLs changing, the query layer will treat HTTP 404's as a critical error as this
likely indicates a change to API and not something that can be gracefully recovered from.
