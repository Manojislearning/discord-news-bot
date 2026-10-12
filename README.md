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

## Channel hi test

A server manager can run `/hi-start channel:#your-test-channel` to send
`hi` every **5 seconds**, starting immediately. The test is bounded to
**12 messages** (about one minute), and only one test can run per server.

Use `/hi-stop` to cancel it early. The bot requires **View Channel** and
**Send Messages** permissions in the selected channel. These slash commands
only work while `bot.py` is running as a connected Discord bot, not from
the one-shot GitHub Actions `send-hi.yml` workflow.

Run this only in channels designated for bot testing; do not use it to spam
server members or maintain artificial activity.
