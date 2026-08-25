import csv
import io

import httpx


class EtherCalc:
    def __init__(self, base_url, room):
        self.base_url = base_url.rstrip("/")
        self.room_url = f"{self.base_url}/_/{room}"

    async def append(self, operation, turn=None, request=""):
        row = io.StringIO()

        csv.writer(
            row,
            lineterminator="\n",
        ).writerow(
            [
                turn,
                operation["agent_name"],
                operation["role"],
                request,
                operation["content"],
            ]
        )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    self.room_url,
                    content=row.getvalue(),
                    headers={"Content-Type": "text/csv"},
                )

            response.raise_for_status()

        except Exception:
            raise
