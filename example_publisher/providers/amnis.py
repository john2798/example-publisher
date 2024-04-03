import asyncio
from math import floor

import requests
import time

from example_publisher.config import AmnisConfig
from example_publisher.provider import Provider, Symbol, Price
from typing import Dict
from structlog import get_logger

from pythclient.pythclient import PythClient
from pythclient.pythaccounts import PythPriceAccount

log = get_logger()


class Amnis(Provider):
    def __init__(self, config: AmnisConfig) -> None:
        self._prices: Dict[Symbol, Price] = {}
        self._config = config
        self._client = PythClient(
            solana_endpoint=config.http_endpoint,
            solana_ws_endpoint=config.ws_endpoint,
            first_mapping_account_key=config.first_mapping,
            program_key=config.program_key,
        )

        self._st_apt_symbol = "Crypto.STAPT/USD"

    def upd_products(self, *args) -> None:
        pass

    async def _update_loop(self) -> None:
        while True:
            await self._update_prices()
            await asyncio.sleep(self._config.update_interval_secs)

    # st_apt price = apt price * st_apt rate
    async def _update_prices(self) -> None:
        await self._client.refresh_all_prices()
        data = await self._client.get_all_accounts()
        for item in data:
            if isinstance(item, PythPriceAccount) and item.product is not None:
                symbol = item.product.symbol
                if symbol == "Crypto.APT/USD":
                    print(f"APT: {item.aggregate_price}")
                    apt_price = item.aggregate_price

                    # get stAPT price
                    st_apt_rate = self.get_st_apt_rate()
                    if st_apt_rate is None:
                        continue
                    price = apt_price * st_apt_rate

                    self._prices[self._st_apt_symbol] = Price(
                        price,
                        price * self._config.confidence_ratio_bps / 10000,
                        floor(time.time()),
                    )

        log.info("updated stAPT price", prices=self._prices)

    def get_st_apt_rate(self):
        try:
            payload = {
                "type": "entry_function_payload",
                'function': f'0x111ae3e5bc816a5e63c2da97d0aa3886519e0cd5e4b046659fa35796bd11542a::stapt_token::stapt_price',
                "type_arguments": [],
                "arguments": []
            }
            data = requests.post(self._config.node_url + "/view", json=payload)
            return int(data.json()[0]) / 10 ** 8
        except Exception as e:
            log.error("Error getting stAPT rate", error=e)
            return None

    def latest_price(self, symbol: Symbol):
        if symbol not in self._prices:
            return None
        return self._prices[symbol]
