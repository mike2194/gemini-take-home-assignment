
# Gemini Take Home Assignment

## Objective
The purpose of this script is to collect historical price data from Gemini's REST API for a given trading symbol (specified by "--chain") and write event data to stdout, to be handled by an alert system.  Output will only be generated if the calculated standard deviation is greater than a given threshold (specified by "--threshold").  Absence of output to stdout implies threshold was not crossed and therefore no alert event should be handled.

## Install
* Use pip to install requirements
	```sh
	python3 -m pip install -r requirements.txt
	```
* Or, build Docker container
	```sh
	docker build -t gemini-api-alert:0.1.0 .
	```

## Usage
```
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

## Example
* Python script "apiAlerts.py" can be executed as follows:
	```sh
	python3 ./apiAlerts.py --chain=BTCUSD --threshold=1
	```
* Script may also be executed within a container:
	```sh
	docker run -it --rm --name "gemini-price-alerts" localhost/gemini-price-alert:latest --chain=BTCUSD
	```
* Example output:
	```json
	{
	    "timestamp": "2024-09-27T13:28:31+00:00",
	    "log_level": "ERROR",
	    "trading_pair": "BTCUSD",
	    "deviation": true,
	    "data": {
	        "last_price": 57235.5,
	        "average_price": 56672.66,
	        "stddev": 57.8934046455133,
	        "change": -57.25
	    }
	}
	```
 
## Assignment Submission Notes

### Completion
* Completed in about 10hours, including 2 re-writes because I don't know Gemini's API very well. I initially made use of the "v1/pricefeed" endpoint which would have collected price data over time to calculate standard deviation, but soon realized this was not necessary nor fit the instructions. 
* I chose to output to stdout a JSON object containing the results.  Logging (sent to stderr) is separate and intended for analyzing the script's status.  The output data could be piped to another, more generic, script which performs the intended routing and delivery of the alert event (such as triggering pagerduty incident, etc).

### Requirements
* Requirements are defined by [requirements.txt](./requirements.txt).
* Installation and execution instructions are described above in [Install](#install) and [Usage](#usage) sections.
* Example methods for executing the script are provided in [Example](#example) section.

### Implementation Notes
* I would also like to refactor the main() function to include only the essential controls, moving the math calculations and item factories into separate functions and thus making main() more readable.
* There is a somewhat significant question of whether to use "candles" or "ticker" api endpoint to collect price data for calculation. Implementing one or the other is somewhat trivial, thus I've included both "apiAlerts-ticker.py" for "ticker" endpoint and "apiAlerts.py" for "candles" endpoint.
  * The "candles" endpoint does provide a timestamp for each price explicitly, while the timestamp must be inferred from "ticker" data.
  * However, "open" and "close" values from "ticker" seem to be reversed -- I'd want to specifically discuss this point in the followup.
  * For example:
    * "ticker" returned `{"open": "57292.74", "close": "57178.25"}`
    * whereas "candles" returned the latest price: `{'timestamp': '2024-09-26T19:00:00+00:00', 'price': 57292.74}` and the oldest: `{'timestamp': '2024-09-25T21:00:00+00:00', 'price': 57178.25}`.
    * Therefore, response data from "candles" is more intuitive to work with, while "ticker" data is more ambiguous (ordered in timestamp descending, per API docs).
    * In a real scenario, I would want to discuss this issue with the trading team to better understand which is (if one is not) more meaningful to calculate standard deviation for the purpose of alerting and notification.  The importance of this point is based on preventing alert fatigue.
* This alert script / micro-app needs some unit tests, too.  However,

### Hypothetically
I don't like the overall implementation design and would question why project requirements defined implementation details at all. I agree with the overall objective, to generating alert events based on some calculation of historical price data. However, as an SRE, I would prefer to maintain a more generic "price-exporter" application whose data is scraped and recorded into TSDB (Time Series Database), then simply write alert rules that calculate [in this example] standard deviation of historical prices by defining the PrometheusRule alerts (or make use of a recording rule to track standard deviation over time). This way, the price data could be visualized in dashboards, additional alert rules could be more easily implemented by application engineers (self-service), etc., instead of what could turn into an accumulation of one-off scripts that are more difficult to manage, quickly become _stale_, and not DRY (Don't Repeat Yourself).

Something like the following would be the resulting Prometheus alert rule:
```yaml
- alert: PriceDeviation_Stddev
  expr: |
    stddev_over_time(chain_historical_price{trading_pair="BTCUSD"}[24h:1h]) > 1
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
