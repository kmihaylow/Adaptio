"""Dev server entry: python -m adaptio.main"""

import uvicorn

from . import config  # noqa: F401  (loads .env)


def main() -> None:
    uvicorn.run("adaptio.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
