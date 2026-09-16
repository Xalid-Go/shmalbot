# -*- coding: utf-8 -*-
"""Entrypoint for cloud platforms (Infrlo, Render, Heroku, etc.) that execute `python app.py` by default."""
import asyncio
from main import main

if __name__ == "__main__":
    asyncio.run(main())
