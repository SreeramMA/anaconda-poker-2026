# IIT Pokerbots 2026 - Anaconda Engine

This is the reference implementation of the engine for playing Anaconda poker for the IIT-Pokerbots Finals of 2026.

## Documentation

For a detailed guide on how to build your bot, including available classes, methods, and game logic, please refer to **[BOT_GUIDE.md](BOT_GUIDE.md)**.

## Folder Structure & Imports

To ensure your bot runs correctly, especially regarding imports, you must maintain the following folder structure. All of your bot files should be located in the `bots/` directory. The `pkbot` package must also be in this directory.

```text
.
├── bots/
│   ├── example.py        # Example bot implementation
│   ├── my_awesome_bot.py # Your bot implementation
│   └── pkbot/            # Game engine package (do not modify)
├── logs/                 # Game logs directory
├── config.py             # Configuration for the engine
├── engine.py             # The game engine executable
└── requirements.txt      # Python dependencies
```

**Crucial:** Do not move `pkbot` or change the import statements in `bot.py`. The engine relies on `pkbot` being importable as a local package relative to your bot.

## How to Run

0. **Clone this repository**
   Clone this repository into your system to run test matches between bots of your choice.

1. **Install Dependencies:**
   Make sure you have Python/Python 3 installed, then run:
    ```bash
    pip install -r requirements.txt
    ```

2. **Configure the Match:**
   Edit `config.py` to specify which bots to run. You can point to different bot files here.

3. **Start the Engine:**
   Execute the engine script from the root directory:
   ```bash
    python engine.py
   ```
   This will launch the game engine and spawn two instances of the bots defined in `config.py`.

   You can also run with compressed logs using `python engine.py --small_log`.

## Developing Your Bot

Code out your bot in `bot.py`. You primarily need to implement the `Player` class methods to decide which action to take.

Refer to **BOT_GUIDE.md** for:
*   Detailed API documentation.
*   Explanation of `PokerState`, `GameInfo`, and `Observation` objects.
*   Available actions and game logic.
