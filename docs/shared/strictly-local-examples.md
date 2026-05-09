# Strictly-Local-Beispiele

Diese Beispiele dienen als Intuition für Strictly Local Languages. Bei `k = 2` werden benachbarte Symbolpaare geprüft. Bei `k = 3` werden lokale Fenster der Länge `3` geprüft. Grenzmarker wie `<` und `>` können Wortanfang und Wortende repräsentieren.

## 1. Alternierende `A/B`-Wörter

Alphabet: `{A, B}`, `k = 2`.

Erlaubte Paare:

```text
<A
AB
BA
B>
```

Gültig: `AB`, `ABAB`. Ungültig: `A`, `ABA`, `BB`.

## 2. Keine gleichen Symbole nebeneinander

Alphabet: `{A, B, C}`, `k = 2`.

Erlaubt sind Paare `XY` mit `X != Y`.

Gültig: `ABCACB`. Ungültig: `ABBC`, `CCAB`.

## 3. Start mit `A`, Ende mit `C`

Alphabet: `{A, B, C}`, `k = 2`.

Start erlaubt nur `<A`, Ende erlaubt nur `C>`, innen sind beliebige Paare erlaubt.

Gültig: `AC`, `ABBC`, `ACC`. Ungültig: `BAC`, `ABA`.

## 4. Jedes `B` muss direkt von `C` gefolgt werden

Alphabet: `{A, B, C}`, `k = 2`.

Nach `B` ist nur `C` erlaubt.

Gültig: `ABCAC`, `BC`, `ACBC`. Ungültig: `ABA`, `AB`, `BBA`.

## 5. `C` darf nur direkt nach `A` auftreten

Alphabet: `{A, B, C}`, `k = 2`.

Vor `C` muss `A` stehen.

Gültig: `AC`, `BACAB`, `AACA`. Ungültig: `BC`, `CC`, `CBAC`.

## 6. Kein Teilstring `ABA`

Alphabet: `{A, B}`, `k = 3`.

Alle Tripel sind erlaubt außer `ABA`.

Gültig: `ABBBA`, `BAAAB`. Ungültig: `ABAB`, `BABA`.

## 7. Kein Symbol dreimal hintereinander

Alphabet: `{A, B, C}`, `k = 3`.

Verboten sind `AAA`, `BBB` und `CCC`.

Gültig: `AABCCBA`. Ungültig: `AAAB`, `ABCCC`.

## 8. Jedes Dreierfenster enthält `C`

Alphabet: `{A, B, C}`, `k = 3`.

Erlaubt sind nur Tripel, in denen `C` vorkommt.

Gültig: `ABCAC`, `CACB`. Ungültig: `ABBA`, weil `ABB` kein `C` enthält.

## 9. Kein isoliertes `A`

Alphabet: `{A, B}`, `k = 3`.

Verboten sind lokale Kontexte, in denen `A` allein zwischen Nicht-`A`s steht, zum Beispiel `BAB`, `<AB` und `BA>`.

Gültig: `AA`, `BBAABB`, `AAAAB`. Ungültig: `BAB`, `AB`, `BA`.

## 10. `B`s treten nur in Paaren auf

Alphabet: `{A, B}`, `k = 3`.

Verboten sind einzelne `B`s wie `ABA`, `<BA`, `AB>` und Dreierblöcke `BBB`.

Gültig: `ABB`, `ABBA`, `AABBAABB`. Ungültig: `ABA`, `ABBB`, `BA`.
