# Alonzo: Church-Inspired Functional Utilities
A lightweight Python library providing high-order functions for elegant data pipelines. Named in honor of Alonzo Church, this module focuses on combinators that allow for the composition of logic through pure functional patterns.

## Features
- Pipeline Composition: Chain functions together without nested parentheses.

- Parallel Execution: Apply multiple functions to a single input simultaneously.

- Safe Execution: Built-in None handling to prevent AttributeError or TypeError in long chains.

- Lazy-Ready: Built on top of functools and itertools for efficiency.

## Usage
1. Sequential Pipelines
Use sequential to create a "pipeline" where the output of one function becomes the input of the next.

```python
from alonzo.church import sequential

def double(x): return x * 2
def increment(x): return x + 1

pipeline = sequential([double, increment, str])
print(pipeline(5))  # Output: "11"
```
2. Parallel Processing (Juxtaposition)
Use parallel to apply multiple independent functions to the same piece of data, returning a tuple of results.

```python
from alonzo.church import parallel

def square(x): return x * x
def cube(x): return x ** 3

ops = parallel([square, cube])
print(ops(3))  # Output: (9, 27)
```
3. Conditional Branching
The branch function acts as a functional if-else statement, returning a function that chooses a path based on a predicate.

```python
from alonzo.church import branch

is_even = lambda x: x % 2 == 0
process = branch(is_even, lambda x: x // 2, lambda x: x * 3 + 1)

print(process(10)) # Output: 5
print(process(3))  # Output: 10
```
## Core Concepts
    
| Function   | Logic                 | Functional Equivalent|
|------------|-----------------------|----------------------|
| sequential | f(g(h(x)))            | Compose / Pipe       |
| parallel   | (f(x),g(x))           | Juxtaposition        |
| branch     | P(x)→f(x):g(x)        | Ternary / Conditional|
| safe_call  | f(x) if x is not None | Maybe Monad (Partial)|

## Installation
Simply drop church.py into your project or include the alonzo directory in your PYTHONPATH.

```python
from alonzo.church import sequential, parallel, branch
```

