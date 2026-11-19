"""Entry point: python -m app."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT") or 8080),
        workers=1,
        access_log=False,
        backlog=512,
    )
