# Asynchrone Ausfuehrung

## Concurrency-Window

Evaluate erzeugt fuer wartende Jobs asynchrone Tasks und begrenzt die
gleichzeitigen Jobausfuehrungen rund um den Provideraufruf mit einem globalen
Semaphore.
`max_concurrency` bestimmt die Groesse dieses Concurrency-Windows. Der Default
ist zehn.

Sobald ein aktiver Aufruf abgeschlossen ist, belegt der naechste wartende Job
den freien Slot. Das Limit gilt ueber alle Modellprofile hinweg, nicht separat
pro Modell.

Die Tasks nutzen die asynchrone LiteLLM-Schnittstelle. Backoff- und
Cooldown-Wartezeiten finden ausserhalb des Semaphores statt und halten keinen
Concurrency-Slot belegt.

Die Orchestrierung liegt in `runner.py`. `job_execution.py` besitzt Semaphore,
Cooldowns, Retry-Policy, Provideraufruf, Parsing und Evaluation.

## Rate Limits

Rate Limits sind modell-, projekt- und organisationsabhaengig. Die
Implementierung codiert deshalb keine OpenAI-Tierwerte fest ein.

Aktuelle Limits muessen in der Provider-Konsole geprueft werden. Fuer OpenAI
beschreiben die offiziellen Seiten sowohl die organisations- und
projektbezogenen Limits als auch die modellbezogenen Tabellen:

- <https://platform.openai.com/docs/guides/rate-limits/usage-tiers>
- <https://platform.openai.com/docs/models/gpt-5-mini>

Retryreihenfolge:

1. `Retry-After`-Header des Providers,
2. relevante Rate-Limit-Reset-Header,
3. exponentielles Backoff mit zufaelligem Jitter.

`429`, Timeouts und temporaere `5xx`-Fehler sind retrybar. Authentifizierungs-,
Bad-Request-, Schema- und Content-Policy-Fehler werden nicht automatisch
wiederholt.

Ein modellbezogener Rate-Limit-Fehler setzt einen Cooldown fuer dieses
Modellprofil. Andere Modellprofile duerfen weiterlaufen. Wartende Retries
halten keinen globalen Concurrency-Slot besetzt.

Fehlgeschlagene Requests zaehlen bei Providern haeufig selbst gegen
Minutenlimits. Backoff darf deshalb nicht als enge Retry-Schleife
implementiert werden.

## Persistenz

Jedes finale Attempt-Artefakt speichert:

- einen UTC-Zeitstempel,
- die gemessene LLM-Laufzeit,
- Retry-Nummer,
- Provider- und Modellmetadaten,
- Usage,
- Rate-Limit-Metadaten, soweit verfuegbar,
- Rohantwort oder Fehlerklassifikation,
- Parsing- und Evaluationsergebnis.

Einzelne Provider-Retries werden ueber `retry_count` zusammengefasst und
derzeit nicht als separate Dateien materialisiert.

Nach einem erfolgreichen Provideraufruf wird derselbe Job nicht erneut
gesendet, auch wenn die Modellantwort fachlich ungueltig war.

## Deterministische Reihenfolge

Die Jobliste wird vor dem Start deterministisch mit einem aus der Run-Config
abgeleiteten Seed gemischt. Dadurch werden Complexity-Tiers und Modelle nicht
systematisch in zeitliche Bloecke gelegt, die mit Providerlast oder
Tageszeiteffekten korrelieren koennten.
