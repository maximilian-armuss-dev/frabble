# Asynchrone Ausführung

## Concurrency-Window

Evaluate erzeugt für wartende Jobs asynchrone Tasks und begrenzt die
gleichzeitigen Jobausführungen rund um den Provideraufruf mit einem globalen
Semaphore.
`max_concurrency` bestimmt die Größe dieses Concurrency-Windows. Der Default
ist zehn.

Sobald ein aktiver Aufruf abgeschlossen ist, belegt der nächste wartende Job
den freien Slot. Das Limit gilt über alle Modellprofile hinweg, nicht separat
pro Modell.

Die Tasks nutzen die asynchrone LiteLLM-Schnittstelle. Backoff- und
Cooldown-Wartezeiten finden außerhalb des Semaphores statt und halten keinen
Concurrency-Slot belegt.

Die Orchestrierung liegt in `runner.py`. `job_execution.py` besitzt Semaphore,
Cooldowns, Retry-Policy, Provideraufruf, Parsing und Evaluation.

## Rate Limits

Rate Limits sind modell-, projekt- und organisationsabhängig. Die
Implementierung codiert deshalb keine OpenAI-Tierwerte fest ein.

Aktuelle Limits müssen in der Provider-Konsole geprüft werden. Für OpenAI
beschreiben die offiziellen Seiten sowohl die organisations- und
projektbezogenen Limits als auch die modellbezogenen Tabellen:

- <https://platform.openai.com/docs/guides/rate-limits/usage-tiers>
- <https://platform.openai.com/docs/models/gpt-5-mini>

Retryreihenfolge:

1. `Retry-After`-Header des Providers,
2. relevante Rate-Limit-Reset-Header,
3. exponentielles Backoff mit zufälligem Jitter.

`429`, Timeouts und temporäre `5xx`-Fehler sind retrybar. Authentifizierungs-,
Bad-Request-, Schema- und Content-Policy-Fehler werden nicht automatisch
wiederholt.

Ein modellbezogener Rate-Limit-Fehler setzt einen Cooldown für dieses
Modellprofil. Andere Modellprofile dürfen weiterlaufen. Wartende Retries
halten keinen globalen Concurrency-Slot besetzt.

Fehlgeschlagene Requests zählen bei Providern häufig selbst gegen
Minutenlimits. Backoff darf deshalb nicht als enge Retry-Schleife
implementiert werden.

## Persistenz

Jedes finale Attempt-Artefakt speichert:

- einen UTC-Zeitstempel,
- die gemessene LLM-Laufzeit,
- Retry-Nummer,
- den für den Run konfigurierten Reasoning-Effort,
- Provider- und Modellmetadaten,
- Usage,
- Rate-Limit-Metadaten, soweit verfügbar,
- Rohantwort oder Fehlerklassifikation,
- Parsing- und Evaluationsergebnis.

Einzelne Provider-Retries werden über `retry_count` zusammengefasst und
derzeit nicht als separate Dateien materialisiert.

Nach einem erfolgreichen Provideraufruf wird derselbe Job nicht erneut
gesendet, auch wenn die Modellantwort fachlich ungültig war.

## Deterministische Reihenfolge

Die Jobliste wird vor dem Start deterministisch mit einem aus der Run-Config
abgeleiteten Seed gemischt. Dadurch werden Complexity-Tiers und Modelle nicht
systematisch in zeitliche Blöcke gelegt, die mit Providerlast oder
Tageszeiteffekten korrelieren könnten.
