# Lokales Slot-CSP

Das CSP wird nur für einen einzelnen Wortslot gebaut. Es sieht nie das gesamte Board.

## Input

```python
language: StrictlyLocalLanguage
template: SlotTemplate
domains: list[set[Symbol]]
```

`domains[i]` beschreibt, welche Symbole an Wortposition `i` erlaubt sind.

Beispiel:

```text
length = 5
domains = [
  {A,B,C,D,E,F},
  {A},
  {A,B,C,D,E,F},
  {D},
  {A,B,C,D,E,F}
]
```

Hier sind Position `1` und `3` durch Overlaps mit bestehenden Boardzellen festgelegt.

## Constraint-Extraktion

Aus dem Template und dem Board werden Domains gebaut:

- freie Zelle: Domain ist das gesamte Alphabet.
- Anchor-Zelle: Domain ist `{anchor_symbol}`.
- belegte Crossing-Zelle: Domain ist `{existing_symbol}`.

Zusätzlich gilt für V1:

- Länge mindestens `3`.
- keine verbotenen Snippets.
- keine Wörter der Länge `1` oder `2`.

## OR-Tools-Modell

Jede Wortposition wird als Integer-Variable modelliert.

```python
x[i] in domain_ids[i]
```

Die Strictly-Local-Sprache wird in einen DFA kompiliert und über `AddAutomaton` eingebunden:

```python
model.AddAutomaton(
    x,
    start_state,
    final_states,
    transitions,
)
```

Der Solver liefert:

```python
list[Symbol] | None
```

`None` bedeutet, dass für dieses Template kein Wort existiert, das Sprache und Positionsconstraints erfüllt.

## k = 2

V1 startet mit `k = 2`. Der DFA-Zustand entspricht im Kern dem letzten gelesenen Symbol plus Startzustand. Für die Startsprache mit verbotenen Doppelungen sind Übergänge `A -> A`, `B -> B` usw. verboten.

## k = 3 und mixed-width

`k = 3` bleibt Target Picture. Dann speichert der DFA-Zustand den letzten Suffix bis Länge `2`. Mixed-width forbidden snippets der Länge `2` und `3` lassen sich über denselben DFA-Compiler abbilden. Der Solver sieht weiterhin nur einen Automaten.
