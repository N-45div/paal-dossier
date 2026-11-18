import os

import uvicorn

from app.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT") or 8080),
                workers=1, log_level="warning", access_log=False)
