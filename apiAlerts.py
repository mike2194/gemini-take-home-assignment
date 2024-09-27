#!/usr/bin/env python3

import json
import requests
import click
import logging
from datetime import datetime
from datetime import timezone as tz
from datetime import timedelta
from zoneinfo import ZoneInfo
from statistics import stdev
from statistics import mean
# import numpy

GEMINI_API_URL = "https://api.sandbox.gemini.com/"


@click.command()
@click.option(
    "-c",
    "--chain",
    required=True,
    help='Filter prices by specific chain (example: "BTCUSD", "ETHUSD", "BTCETH", ...)',
)
@click.option(
    "-n",
    "--dry-run",
    "dry_run",
    flag_value=True,
    default=False,
    help="Dry-run will prevent sending alert event",
)
@click.option(
    "-t",
    "--threshold",
    type=click.FLOAT,
    default=1.0,
    help="Override default threshold for calculated standard deviation to trigger alert (Default: 1.0)",
)
@click.option(
    "-f",
    "--output-format",
    type=click.Choice(["json", "yaml", "prometheus"]),
    default="json",
    help="Select output format (Default: json)",
)
@click.option(
    "-z",
    "--timezone",
    type=click.STRING,
    default="UTC",
    help="Define timezone for output data (Default: UTC)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Log level to output (Default: INFO)",
)
def main(chain, dry_run, threshold, output_format, timezone, log_level):
    """
    Gemini REST API alert script for calculated standard deviation from hourly prices for past 24 hours.

    Trigger an alert event for

    Returns:
        Calculated standard deviation (value) for given symbol, as provided by "--chain"
    """

    logging.basicConfig(
        format="%(asctime)s %(levelname)s - AlertingTool - %(message)s",
        level=log_level.upper(),
    )

    """
    initialize some basic values we need
    """
    output_data = {}
    std_dev = float()
    tz_user = ZoneInfo(timezone)
    ts_now_utc = datetime.now(tz.utc)
    ts_now = ts_now_utc.astimezone(tz=tz_user)
    ts_now_iso8601 = ts_now.isoformat(timespec="seconds")
    format = output_format.lower()

    if dry_run:
        logging.info(f"DRY_RUN - Alert events will not be triggered")

    """
    get list of prices for each hour for past 24hrs
    """
    prices = get_candle_by_symbol(chain, "1hr")

    if prices:
        """
        collect 1hr price candles data for past 24hrs
        """
        price_data = []
        prices_hourly = []
        for x in prices:
            pts_seconds = float(x[0]) / 1000
            pts = datetime.fromtimestamp(pts_seconds, tz=tz.utc)
            # use 25 hours timedelta to include the full hour from 24hrs ago
            if pts >= ts_now_utc - timedelta(hours=25):
                price_timestamp = pts.isoformat(timespec="auto")
                price_close = float(x[4])
                price_data.append({"timestamp": price_timestamp, "price": price_close})
                prices_hourly.append(price_close)

        logging.debug(f"prices for each hour over last 24 hours: {price_data}")

        """
        calculate most recent price
        """
        last_price = float(prices_hourly[0])

        """
        calculate average price
        """
        average_price = mean(prices_hourly)

        """
        calculate change in price over time range
        """
        price_change = float(prices_hourly[0]) - float(prices_hourly[-1])

        """
        calculate standard deviation of prices changes
        """
        std_dev = stdev(prices_hourly)

        if std_dev >= threshold:
            logging.info(
                f"Calculated standard deviation ({std_dev}) >= threshold ({threshold:.1f}). Alert event would have been triggered."
            )
        else:
            logging.info(
                f"Calculated standard deviation ({std_dev}) <= threshold ({threshold:.1f}). Alert event would not have been triggered."
            )

        """
        define output data
        """
        output_data = {
            "last_price": float(last_price),
            "average_price": float(average_price),
            "stddev": float(std_dev),
            "change": float(price_change),
        }

    try:
        if dry_run:
            write_output(ts_now_iso8601, chain, output_data, log_level, format)
        elif std_dev >= threshold:
            write_output(ts_now_iso8601, chain, output_data, log_level, format)
        return None

    except UnboundLocalError as e:
        logging.error(e)
        output_data = {"error": f"{e}"}
        write_output(ts_now_iso8601, chain, output_data, log_level, format)
        return None


## use statistics module instead of numpy bc this not complex
# def stdev(data):
#    """
#    Calculates the standard deviation of a list of numerical values.
#
#    Args:
#        data: A list of numerical values.
#
#    Returns:
#        The standard deviation of the data as a float.
#    """
#    arr = numpy.array(data)
#    #mean = numpy.mean(arr, axis=0)
#    std_dev = numpy.std(arr, axis=0)
#    return std_dev


def get_candle_by_symbol(symbol, timeframe):
    """
    Retrieves ticker hourly prices for past 24 hours.
    API Documentation: [Ticker V2](https://docs.gemini.com/rest-api/?python#ticker-v2)
    API Endpoint: '/v2/ticker/:symbol'
    Endpoint Description: This endpoint retrieves information about recent trading activity for the provided symbol.

    Args:
        symbol: which blockchain to retrieve data for by symbol (string).  example: "BTCUSD",

    Returns:
        ticker price data for a given symbol
        > API Response (obj):
        >     FIELD       TYPE                DESCRIPTION
        >     symbol      string              BTCUSD etc.
        >     open        decimal             Open price from 24 hours ago
        >     high        decimal             High price from 24 hours ago
        >     low         decimal             Low price from 24 hours ago
        >     close       decimal             Close price (most recent trade)
        >     changes     array of decimals   Hourly prices descending for past 24 hours
        >     --          decimal             Close price for each hour
        >     bid         decimal             Current best bid
        >     ask         decimal             Current best offer
    """
    logging.info(f"Requesting ticker data for symbol {symbol}")
    try:
        response = requests.get(
            GEMINI_API_URL + "v2/candles/" + symbol.lower() + "/" + timeframe
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        prices = response.json()

        # DEBUG
        logging.debug(json.dumps(prices, indent=4))

        return prices

    except requests.exceptions.RequestException as e:
        logging.error(f"Unable to fetch data from Gemini API: {e}")
        return None


def write_output(timestamp_now, chain, output_data, log_level, format):
    """
    write output data to stdout in provided format

    Args:
        output:  data object of output data
        format:  data output format (must be one of: json, yaml, prometheus)

    Returns:
        None
    """
    output = {
        "timestamp": timestamp_now,
        "log_level": log_level.upper(),
        "trading_pair": chain.upper(),
        "deviation": False,
        "data": output_data,
        # { "error": None }
        # { "last_price": float(), "average_price": string(), "stddev": float(), "change": float() }
    }
    if output_data["stddev"] > 0:
        output["deviation"] = True

    if format == "yaml":
        # TODO: output-format="yaml"
        print(f'NOT IMPLEMENTED.  Please use "--output-format=json".')
    elif format == "prometheus":
        # TODO: output-format="prometheus"
        print(f'NOT IMPLEMENTED.  Please use "--output-format=json".')
    elif format == "json":
        print(json.dumps(output, indent=4))
    return None


if __name__ == "__main__":
    main()
