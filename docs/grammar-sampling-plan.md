# Grammar Sampling Module — Design Plan

## 1. Goal

Replace the hard-coded demo DFA (`A+ B A* C`) with a principled, reproducible pipeline for sampling random formal grammars. The first grammar class is **Strictly Local (SL_k) with a minimum word length constraint**. The pipeline produces an automaton validator and exposes analysis tools (Perron eigenvalue, word-count spectrum). Everything is serialisable to disk and loadable by the puzzle-generation layer.

---

## 2. Strictly Local Languages — Primer

A language L over alphabet Σ is **strictly k-local** (SL_k) if there exists a set of forbidden k-grams F ⊆ Σ^k such that:

> w ∈ L  ⟺  no k-gram of w is in F

Example (Σ = {A, B, C}, k = 3, F = {"AAA", "BCB"}):
- "ABCABC" — accepted (no forbidden 3-gram)
- "AAAB"   — rejected ("AAA" ∈ F)

### Minimum word length

Pure SL_k does not naturally block short strings: a word of length < k has no k-grams to check and therefore passes trivially. For puzzle generation, very short words are useless, so we add a `min_word_length` parameter. The empty word is always excluded (effectively `min_word_length ≥ 1`; we default to `k`).

---

## 3. DFA Construction

### 3.1 Standard SL_k DFA

The standard construction uses (k−1)-gram states:
- **States**: all (k−1)-grams over Σ, plus one dead/sink state
- **Start state**: the empty (k−1)-gram (no history yet)
- **Transition**: reading symbol σ from state `s` → state `s[1:] + σ`, unless the k-gram `s + σ` is forbidden, in which case → dead state (absorbing)
- **Accepting states**: all non-dead states

### 3.2 Warmup Phase for min_word_length

To bake `min_word_length` into the automaton (not a separate pre-check), we augment the state space with a warmup counter:

```
state = (phase, (k−1)-gram history)

phase ∈ {0, 1, …, min_word_length − 1, READY}
```

- **Phases 0 … min_word_length − 1**: non-accepting; forbidden-pattern violations still send to dead state
- **READY**: standard SL_k behaviour (accepting iff not dead)
- **Transition**: phase increments by 1 on each symbol until READY; forbidden patterns are checked at every step

This is still a valid DFA. For typical parameters (k = 3, min_word_length ≤ 10, |Σ| ≤ 15) the state count stays in the hundreds.

The resulting language is: `{w : len(w) ≥ min_word_length AND no k-gram of w is in F}`. This is regular and characterised by a small, human-readable set of forbidden patterns plus one length parameter.

### 3.3 DFA Minimisation (optional)

The warmup-augmented DFA often contains redundant states (many warmup states that behave identically once READY is reached). Minimisation via **automata-lib** reduces the state space to the canonical minimal DFA, which is useful for prompt serialisation (smaller state descriptions → fewer tokens).

Minimisation is controlled by a configuration flag (`minimize_dfa: true/false`). When enabled:
1. Build the warmup-augmented DFA
2. Convert to an `automata-lib` `DFA` object
3. Call `.minify()`
4. Convert back to our `DFA` dataclass

`automata-lib` will be added as a project dependency.

---

## 4. Proposed Architecture

```
src/
└── grammar/                   ← new top-level package
    ├── __init__.py
    ├── alphabet.py            ← alphabet sampling strategies
    ├── sl_grammar.py          ← SLGrammar class + sampling logic + DFA builder
    ├── analysis.py            ← Perron eigenvalue, word-count spectrum
    ├── serialization.py       ← save / load (JSON)
    └── cli.py                 ← UV entry-point handlers
```

Configuration for SL-specific parameters lives in `config/grammar_configs.yaml` (new file, separate from `model_configs.yaml`).

---

## 5. Module Responsibilities

### 5.1 `alphabet.py`

```python
class AlphabetSampler(Protocol):
    def sample(self, size: int, seed: int) -> tuple[str, ...]

class LetterAlphabetSampler:
    """Draws letters without replacement; case controlled by config."""
    def sample(self, size: int, seed: int) -> tuple[str, ...]
```

Parameters come from `GrammarConfig` (see §7). Case (`"upper"` / `"lower"`) defaults to `"upper"` for consistency with the existing codebase.

### 5.2 `sl_grammar.py`

```python
@dataclass(frozen=True)
class SLGrammar:
    alphabet:         tuple[str, ...]
    k:                int                   # forbidden pattern length
    forbidden:        frozenset[str]        # all forbidden k-grams
    min_word_length:  int
    seed:             int                   # seed used to sample this grammar

    def accepts(self, word: str) -> bool
    def to_dfa(self, minimize: bool = False) -> DFA   # uses DFA from domain/models.py
    def describe(self) -> str
```

`accepts` is implemented directly (no DFA needed): check length, then scan k-grams. `to_dfa` builds the warmup-augmented automaton and optionally minimises it.

Sampling function:

```python
def sample_sl_grammar(
    alphabet:          tuple[str, ...],
    k:                 int,
    forbidden_fraction: float,    # fraction of all k-grams independently forbidden
    min_word_length:   int,
    seed:              int,
) -> SLGrammar
```

Each of the |Σ|^k possible k-grams is independently included in F with probability `forbidden_fraction`. The resulting forbidden set is stored in the `SLGrammar` dataclass.

### 5.3 `analysis.py`

```python
def perron_eigenvalue(grammar: SLGrammar) -> float
def count_words(grammar: SLGrammar, length: int) -> int
def word_count_spectrum(grammar: SLGrammar, max_length: int) -> dict[int, int]
```

**Perron eigenvalue**: build the de Bruijn transition graph (nodes = legal (k−1)-grams, edges = non-forbidden transitions), compute `numpy.linalg.eigvals` of the adjacency matrix, return the largest real eigenvalue. λ > 1 means the language grows exponentially — desirable for puzzle generation.

**word_count_spectrum**: dynamic programming over the transition graph; counts paths of length `l` from the start node to accepting nodes for each `l` in `[1, max_length]`.

### 5.4 `serialization.py`

All parameters — both the sampled grammar and every configuration value that was active during sampling — are stored together for full traceability. This means the file is self-contained: you can reproduce the exact grammar and understand every knob that was used, even without the `grammar_configs.yaml` that was in effect at sampling time.

JSON format:

```json
{
  "schema_version": 1,
  "type": "sl",
  "name": "experiment_01",
  "alphabet": ["A", "B", "C", "D", "E"],
  "k": 3,
  "forbidden": ["AAA", "BCB", "CAC"],
  "min_word_length": 3,
  "seed": 42,
  "sampling_config": {
    "alphabet_size": 5,
    "forbidden_fraction": 0.35,
    "alphabet_case": "upper",
    "minimize_dfa": true,
    "auto_resample": {
      "enabled": true,
      "max_attempts": 20,
      "perron_min": 1.1,
      "perron_max": 50.0,
      "resample_length_min": 3,
      "resample_length_max": 7,
      "min_word_count": 20
    }
  }
}
```

```python
def save_grammar(grammar: SLGrammar, config: SLSamplingConfig, path: str | Path) -> None
def load_grammar(path: str | Path) -> tuple[SLGrammar, SLSamplingConfig]
```

The DFA is **not** stored; it is rebuilt from the grammar on load. The grammar JSON is the single source of truth.

---

## 6. Auto-Resampling

Controlled by the `auto_resample` section of `GrammarConfig`. When enabled, `sample_sl_grammar` wraps sampling in a retry loop:

**Rejection criteria** (any one triggers a resample):
1. `perron_eigenvalue(grammar) < config.perron_min` — language too sparse
2. `perron_eigenvalue(grammar) > config.perron_max` — language too dense (trivial)
3. `sum(word_count_spectrum(grammar, max_length=config.resample_length_max).values()) < config.min_word_count` — too few words in the puzzle-relevant length range (`[config.resample_length_min, config.resample_length_max]`, default `[3, 7]`)

After `max_attempts` failed attempts a `GrammarSamplingError` is raised (informing the user to adjust parameters).

The internal retry loop advances the seed deterministically (`seed + attempt`) so each attempt is reproducible.

---

## 7. Configuration (`config/grammar_configs.yaml`)

New file, separate from `model_configs.yaml`. Loaded by a `GrammarConfig` dataclass analogous to `ModelConfig`:

```yaml
sl_grammar:
  alphabet_case: "upper"          # "upper" | "lower"
  minimize_dfa: true

  auto_resample:
    enabled: true
    max_attempts: 20
    perron_min: 1.1               # minimum acceptable Perron eigenvalue
    perron_max: 50.0              # maximum acceptable Perron eigenvalue
    resample_length_min: 3        # word-count check window
    resample_length_max: 7
    min_word_count: 20            # min total words in [length_min, length_max]
```

`GrammarConfig` is loaded by the existing environment handler (`src/llm/env.py` or a parallel `src/grammar/config.py`) so all grammar tooling can read it without re-parsing.

---

## 8. CLI Entry Points

Add to `pyproject.toml` (and add `automata-lib` to `dependencies`):

```toml
[project.scripts]
sample-grammar  = "src.grammar.cli:cmd_sample"
check-grammar   = "src.grammar.cli:cmd_check"
analyze-grammar = "src.grammar.cli:cmd_analyze"
```

### `uv run sample-grammar`

Every parameter has a global default from `grammar_configs.yaml`. Any of them can be overridden individually on the command line; unspecified flags fall back to the yaml value. The resolved values (yaml + CLI overrides) are written into the `sampling_config` block of the output file.

```
# Output
--name TEXT                 Grammar name; file is saved as <name>.json
--output-dir PATH           Directory to write the file (default: grammars/)

# Grammar structure
--alphabet-size INT         Number of symbols          [yaml: n/a, default: 5]
--k INT                     Forbidden pattern length   [yaml: n/a, default: 3]
--forbidden-fraction FLOAT  Fraction of k-grams to forbid independently
                                                       [yaml: sl_grammar.forbidden_fraction]
--min-word-length INT       Minimum accepted word length
                            (default: k if omitted)    [yaml: n/a]
--seed INT                  Random seed                [yaml: n/a, default: 42]

# DFA options
--alphabet-case upper|lower                            [yaml: sl_grammar.alphabet_case]
--minimize-dfa / --no-minimize-dfa                     [yaml: sl_grammar.minimize_dfa]

# Auto-resampling
--auto-resample / --no-auto-resample                   [yaml: sl_grammar.auto_resample.enabled]
--max-attempts INT                                     [yaml: sl_grammar.auto_resample.max_attempts]
--perron-min FLOAT                                     [yaml: sl_grammar.auto_resample.perron_min]
--perron-max FLOAT                                     [yaml: sl_grammar.auto_resample.perron_max]
--resample-length-min INT                              [yaml: sl_grammar.auto_resample.resample_length_min]
--resample-length-max INT                              [yaml: sl_grammar.auto_resample.resample_length_max]
--min-word-count INT                                   [yaml: sl_grammar.auto_resample.min_word_count]

# Output behaviour
--show-stats                Print Perron eigenvalue and word-count spectrum after sampling
```

Example:
```
uv run sample-grammar --name exp_01 --alphabet-size 6 --seed 7 --perron-min 2.0
```
This uses yaml defaults for everything except alphabet size, seed, and the Perron lower bound.

### `uv run check-grammar`

```
GRAMMAR_FILE            Path to grammar JSON
--word TEXT             Single word to validate
--words-file PATH       File with one word per line; prints acceptance table
```

### `uv run analyze-grammar`

```
GRAMMAR_FILE            Path to grammar JSON
--max-length INT        Analyse word counts up to this length (default: 12)
```

Outputs: Perron eigenvalue, minimised-DFA state count (if minimisation is on), word-count spectrum table.

---

## 9. Integration with the Existing Pipeline

Scenario generation is driven by `src.cli:main`, which loads a `GeneratorConfig`
and delegates to `src.generator.engine.ScenarioGenerator`. Grammar files are
referenced through the config's `grammar_path`.

Pipeline:
1. Load `SLGrammar` from JSON via `load_grammar(grammar_path)`
2. Use the resulting `StrictlyLocalLanguage` in `ScenarioGenerator`
3. Validate generated moves through the shared formal validation interface
3. Use that `DFA` in place of the demo DFA

Everything downstream (word enumeration, scoring, legal move enumeration) is unchanged — the converted `DFA` is structurally identical to the demo DFA.

---

## 10. Seeded Randomness

All sampling functions accept an explicit `seed: int` and create their own `random.Random(seed)` / `numpy.random.default_rng(seed)` internally. No global state is mutated. The seed is stored in the grammar JSON so every sample is exactly reproducible.

---

## 11. New Dependency

`automata-lib` must be added to `pyproject.toml`:

```toml
dependencies = [
    ...
    "automata-lib>=8.0.0",
]
```

---

## 12. Documentation Updates

Once the implementation is complete, two files must be updated:

**`README.md`** — add a "Grammar Sampling" section covering:
- Purpose of the grammar module (SL_k with min-word-length, seeded reproducibility)
- The three new UV commands (`sample-grammar`, `check-grammar`, `analyze-grammar`) with short examples
- Where generated grammar files live (`grammars/`) and how to pass one to `scrabble-prototype` via `--grammar`
- How to configure global defaults (`config/grammar_configs.yaml`)

**`CLAUDE.md`** — add:
- The new `src/grammar/` package and what each module does (one line each)
- The `config/grammar_configs.yaml` file and its role
- The three new UV entry points with their flag summaries
- The `SLGrammar` dataclass to the key data structures section
- The `grammars/` output directory convention

---

## 13. Remaining Open Questions

**Q1 — Grammar class extensibility.**
The `AlphabetSampler` protocol and `SLGrammar` are designed so a future grammar type (e.g. TSL, LT, regular grammar) can be added without touching the existing interface. `grammar_configs.yaml` uses a top-level key per grammar type (`sl_grammar`, and later `tsl_grammar` etc.). This should be enough to keep the door open without over-engineering now.

**Q2 — Forbidden-fraction default.**
0.35 is a placeholder. A good default depends on alphabet size and k: for |Σ| = 5, k = 3 there are 125 possible 3-grams; 0.35 forbids ~44 of them. Whether that reliably produces λ > 1 needs empirical testing during implementation. We may want to expose a helper that suggests a `forbidden_fraction` given a target Perron range.
