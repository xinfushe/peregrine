import ccxt.async as ccxt
import asyncio
import json


class CollectionBuilder:

    def __init__(self):
        all_exchanges = ccxt.exchanges
        # bter frequently has a broken API and flowbtc and yunbi always throw request timeouts.
        [all_exchanges.remove(exchange_name) if exchange_name in all_exchanges else None for exchange_name in ['bter', 'flowbtc', 'yunbi']]
        self.exchanges = all_exchanges
        # keys are market names and values are an array of names of exchanges which support that market
        self.collections = {}
        # stores markets which are only available on one exchange: keys are markets names and values are exchange names
        self.singularly_available_markets = {}

    def build_all_collections(self, write=True, ccxt_errors=False):
        """
        Refer to glossary.md for the definition of a "collection"
        :param write: If true, will write collections and singularly_available_markets to json files in /collections
        :param ccxt_errors: If true, this method will raise the errors ccxt raises
        :return:
        """
        futures = [asyncio.ensure_future(self._add_exchange_to_collections(exchange_name, ccxt_errors)) for exchange_name in
                   self.exchanges]
        asyncio.get_event_loop().run_until_complete(asyncio.gather(*futures))

        if write:
            with open('collections/collections.json', 'w') as outfile:
                json.dump(self.collections, outfile)

            with open('collections/singularly_available_markets.json', 'w') as outfile:
                json.dump(self.singularly_available_markets, outfile)

        return self.collections

    async def _add_exchange_to_collections(self, exchange_name: str, ccxt_errors=False):
        exchange = await self._get_exchange(exchange_name, ccxt_errors)
        if exchange is None:
            return
        for market_name in exchange.symbols:
            if market_name in self.collections:
                self.collections[market_name].append(exchange_name)
            elif market_name in self.singularly_available_markets:
                self.collections[market_name] = [self.singularly_available_markets[market_name], exchange_name]
                del self.singularly_available_markets[market_name]
            else:
                self.singularly_available_markets[market_name] = exchange_name

    @staticmethod
    async def _get_exchange(exchange_name: str, ccxt_errors=False):
        """
        :param ccxt_errors: if true, raises errors ccxt raises when calling load_markets. The common ones are
        RequestTimeout and ExchangeNotAvailable, which are caused by problems with exchanges' APIs.
        """
        exchange = getattr(ccxt, exchange_name)()

        if ccxt_errors:
            await exchange.load_markets
        else:
            try:
                await exchange.load_markets()
            except ccxt.BaseError:
                return None

        return exchange


class SpecificCollectionBuilder(CollectionBuilder):

    def __init__(self, rules, blacklist=False):
        """
        Rules is a dict which takes strings as values and keys. Look at this part of the ccxt manual:
        https://github.com/ccxt/ccxt/wiki/Manual#user-content-exchange-structure for insight into what are acceptable
        rules. Typical use case is 'countries' as a value and Australia, Bulgaria, Brazil, British Virgin Islands,
        Canada, China, Czech Republic, EU, Germany, Hong Kong, Iceland, India, Indonesia, Israel, Japan, Mexico,
        New Zealand, Panama, Philippines, Poland, Russia, Seychelles, Singapore, South Korea, St. Vincent & Grenadines,
        Sweden, Tanzania, Thailand, Turkey, US UK, Ukraine, or Vietnam as a key.
        :param rules:
        :param blacklist:
        """
        super().__init__()
        self.blacklist = blacklist
        self.rules = rules

    async def _add_exchange_to_collections(self, exchange_name: str, ccxt_errors=False):
        exchange = await self._get_exchange(exchange_name, ccxt_errors)
        if exchange is None:
            return

        for key, desired_value in self.rules.items():
            try:
                actual_value = getattr(exchange, key)
            except AttributeError:
                raise ValueError("{} is not a valid property of {}".format(key, exchange.name))
            if isinstance(actual_value, str):
                # Note, this line is A XOR B where A is self.blacklist and B is actual_value != desired_value
                if self.blacklist != (actual_value != desired_value):
                    return
            elif isinstance(actual_value, list):
                # The comment above the previous conditional also explains this conditional
                if self.blacklist != (desired_value not in actual_value):
                    return
            else:
                raise ValueError("The rules parameter for SpecificCollectionBuilder takes only strings and lists"
                                 "as values.")

        for market_name in exchange.symbols:
            if market_name in self.collections:
                self.collections[market_name].append(exchange_name)
            elif market_name in self.singularly_available_markets:
                self.collections[market_name] = [self.singularly_available_markets[market_name], exchange_name]
                del self.singularly_available_markets[market_name]
            else:
                self.singularly_available_markets[market_name] = exchange_name


def build_all_collections(write=True, ccxt_errors=False):
    builder = CollectionBuilder()
    return builder.build_all_collections(write, ccxt_errors)


def build_specific_collections(rules, blacklist=False, write=False):
    builder = SpecificCollectionBuilder(rules, blacklist)
    return builder.build_all_collections(write)


build_all_collections()
