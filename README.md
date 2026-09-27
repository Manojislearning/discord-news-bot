# Discord News Bot

A Discord bot that reads RSS feeds exported from Feedly as OPML.

## Features

- Automatically checks feeds every 30 minutes.
- Posts up to 10 new articles per check.
- `/randomnews` returns one random article.
- `/news` returns up to 10 available articles.
- Remembers already-posted links in `seen_links.json`.
- Keeps the Discord token out of GitHub by loading it from `.env`.

## Local setup

1. Install Python 3.11+.
2. Clone/download this repository.
3. In the project folder run:

   ```
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to a new file named `.env`.
5. Put your Discord bot token and channel ID in `.env`.
6. Export your Feedly subscriptions as OPML and save the file as:

   ```
   feedly.opml
   ```

   beside `bot.py`.

7. Run:

   ```
   python bot.py
   ```

## Important

Never commit your real `.env` file or Discord bot token to GitHub.
