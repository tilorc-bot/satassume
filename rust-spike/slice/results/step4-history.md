### Rust against Python, same query, order and seed

| run | wl | queries Py/Rust | total rows | answers differ | msgs differ | sessions | end state differ | stream differ | session count differ | dropped/created |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| recorded | dev | 1985/1985 | yes | 0 | 0 | 918 | 0 | 0 | 0 | 0/0 |
| recorded | fuzz | 3000/3000 | yes | 0 | 0 | 3133 | 0 | 0 | 0 | 0/0 |
| shuffle1 | dev | 1985/1985 | yes | 0 | 0 | 912 | 0 | 0 | 0 | 0/0 |
| shuffle1 | fuzz | 3000/3000 | yes | 0 | 0 | 3142 | 0 | 0 | 0 | 0/0 |
| shuffle2 | dev | 1985/1985 | yes | 0 | 0 | 914 | 0 | 0 | 0 | 0/0 |
| shuffle2 | fuzz | 3000/3000 | yes | 0 | 0 | 3141 | 0 | 0 | 0 | 0/0 |
| fork | dev | 1985/1985 | yes | 0 | 0 | 3332 | 0 | 0 | 0 | 0/0 |
| fork | fuzz | 3000/3000 | yes | 0 | 0 | 4943 | 0 | 0 | 0 | 0/0 |
| twice | dev | 3970/3970 | yes | 0 | 0 | 918 | 0 | 0 | 0 | 0/0 |
| twice | fuzz | 6000/6000 | yes | 0 | 0 | 3133 | 0 | 0 | 0 | 0/0 |
| seed1 | dev | 1985/1985 | yes | 0 | 0 | 918 | 0 | 0 | 0 | 0/0 |
| seed1 | fuzz | 3000/3000 | yes | 0 | 0 | 3133 | 0 | 0 | 0 | 0/0 |
| seed2 | dev | 1985/1985 | yes | 0 | 0 | 918 | 0 | 0 | 0 | 0/0 |
| seed2 | fuzz | 3000/3000 | yes | 0 | 0 | 3133 | 0 | 0 | 0 | 0/0 |

Runs that differ or didn't finish: 0

### Each backend against itself: what history moves

| run, against recorded | wl | Python: answers moved | Rust: answers moved | Python: state moved | Rust: state moved | same queries? |
|---|---|---:|---:|---:|---:|---|
| shuffle1 | dev | 0 | 0 | 335 | 335 | yes |
| | | query 873 state moved: Python True, Rust True | | | | |
| shuffle1 | fuzz | 0 | 0 | 86 | 86 | yes |
| shuffle2 | dev | 0 | 0 | 358 | 358 | yes |
| | | query 873 state moved: Python True, Rust True | | | | |
| shuffle2 | fuzz | 0 | 0 | 91 | 91 | yes |
| fork | dev | 0 | 0 | 1549 | 1549 | yes |
| fork | fuzz | 0 | 0 | 2981 | 2981 | yes |
| seed1 | dev | 0 | 0 | 27 | 27 | yes |
| seed1 | fuzz | 0 | 0 | 131 | 131 | yes |
| seed2 | dev | 0 | 0 | 19 | 19 | yes |
| seed2 | fuzz | 0 | 0 | 225 | 225 | yes |

### Run 3: the same query twice in a row

| wl | queries | Python: repeat's answer differs | Rust: repeat's answer differs | same queries? | Python: repeat vs recorded answer | Rust: repeat vs recorded answer |
|---|---:|---:|---:|---|---:|---:|
| dev | 1985 | 0 | 0 | yes | 0 | 0 |
| fuzz | 3000 | 0 | 0 | yes | 0 | 0 |

### Answers across all orders, and answer digests

- dev: `31cd0945c07f02a6`: 12 runs
- fuzz: `173502b6ef285ad6`: 12 runs

Rust runs in total: {'reentry': 0, 'entry_raises': 0, 'python_solvers_made': 0}
