
# Gemini Take Home Assignment

## Objective
The purpose of this script is to collect historical price data from Gemini's REST API for a given trading symbol (specified by "--chain") and trigger an alert event if the calculated standard deviation is greater than a given threshold (specified by "--threshold").

## Usage
```man
Usage: main.py [OPTIONS]

	Gemini REST API alert script for calculated standard deviation from hourly
	prices for past 24 hours.

	Trigger an alert event for

	Returns:     Calculated standard deviation (value) for given symbol, as
	provided by "--chain"

Options:
	-c, --chain TEXT                Filter prices by specific chain (example:
																	"BTCUSD", "ETHUSD", "BTCETH", ...)
																	[required]
	-n, --dry-run                   Dry-run will prevent sending alert event
	-t, --threshold FLOAT           Override default threshold for calculated
																	standard deviation to trigger alert
																	(Default: 1.0)
	-f, --output-format [json|yaml|prometheus]
																	Select output format (Default: json)
	-z, --timezone TEXT             Define timezone for output data (Default:
																	UTC)
	--log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
																	Log level to output (Default: INFO)
	--help                          Show this message and exit.
```

## Example Usage
* Python script "apiAlerts.py" can be executed as follows:
	```sh
	python3 ./apiAlerts.py --chain=BTCUSD

* Script may also be run as a container container:
	```sh
	# build container
	docker build -t gemini-price-alert:latest .
	# run container
  docker run -it --rm --name "gemini-price-alerts" localhost/gemini-price-alert:latest --chain=BTCUSD
	```

## Notes and Future Changes
* Completed in about 10hours, including 2 re-writes because I don't know Gemini's API very well.
* I chose to output to stdout a JSON object containing the results.  Logging (sent to stderr) is separate and intended for analyzing the script's status.  The output data could be piped to another, more generic, script which performs the intended routing and delivery of the alert event (such as triggering pagerduty incident, etc).
* There is a somewhat significant question of whether to use "candles" or "ticker" for the price data to be calculated. Implementing one or the other is somewhat trivial, thus I've included both "apiAlerts-ticker.py" for "ticker" and "apiAlerts.py" for "candles".  The "candles" endpoint does denote the timestamp for each price explicitly, while the timestamp must be inferred from "ticker" data).  However, "open" and "close" values from "ticker" seem to be reversed -- I'd like to discuss this in the followup as they do not correlate with the "changes" list of prices.
	For example, "ticker" returned `{"open": "57292.74", "close": "57178.25"}`
	whereas "candles" returned `{'timestamp': '2024-09-26T19:00:00+00:00', 'price': 57292.74}` (most recent) and `{'timestamp': '2024-09-25T21:00:00+00:00', 'price': 57178.25}` oldest.
	Therefore, response data from "candles" is more intuitive to work with while "ticker" data is more ambiguous.  In a real scenario, I would want to discuss this issue with the trading team to better understand which is more meaningful for this alert rule.
* I would also like to refactor the main() function to include only the essential controls, moving the math calculations and item factories into separate functions and thus making main() more readable.
* This micro-app/script needs some unit tests.  However...
* (Hypothetically) I don't like the overall implementation design and would question why the project requirements defined implementation details at all.  I could agree that generating alert events based on some calculation of historical price data.  Although, I would prefer to maintain a more generic "price-exporter" application who's data is scraped and recorded into TSDB, then simply write alert rules that calculate [in this example] standard deviation of historical prices and then define the alert rules as "PrometheusRule" objects or similar.  This way, the price data is queryable and can be visualized in dashboards, etc., instead of an eventual accumulation of one-off scripts that are very not DRY.
  Something like this would be the alert query:
  ```yaml
  alert: PriceDeviation_Stddev
  expr: |
    stddev_over_time(price{trading_pair="BTCUSD"}[24h:1h]) > 1
  for: 15m
  labels:
    severity: warning
  annotations:
    summary: |
      Standard Deviation of {{ $labels.trading_pair }} Prices are >= 1 for past 24hrs.
      Hold on to your hats and wallets!
    description: |
      {{ $labels.trading_pair }} Price Deviations for last 24hrs was {{ humanize $value }}.
      Transaction volume may be higher than normal, 
    action: |
      Confirm status of beverage refridgerator.
  ```

