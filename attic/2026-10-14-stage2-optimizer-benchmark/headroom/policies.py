"""The two random policies. Pure functions of (seed, results so far); no simulator knowledge.

An allocation is a tuple of pool sizes. Limits are the benchmark's own: each pool >= 1 and
<= cap, where cap = total headcount of the starting allocation (bpm-r-opt's max_resources).
Every run gets 20 evaluations; the first is always the starting allocation, as in bpm-r-opt.
"""
import random

BUDGET = 20


def front(results):
    """Allocations not beaten on both cost and cycle time. results: {alloc: (cost, time)}"""
    return sorted(a for a, (c, t) in results.items()
                  if not any(c2 <= c and t2 <= t and (c2 < c or t2 < t) for c2, t2 in results.values()))


def blind(start, cap, seed, evaluate):
    """Blind random: every pool size drawn uniformly from 1..cap, independently. Ignores all results."""
    rng = random.Random(seed)
    results = {start: evaluate(start)}
    while len(results) < BUDGET:
        a = tuple(rng.randint(1, cap) for _ in start)
        if a not in results:
            results[a] = evaluate(a)
    return results


def one_pool(start, cap, seed, evaluate):
    """Random one-pool change: take a random allocation from the best set found so far, pick one
    pool at random, flip a coin for shrink or grow, then pick the new size at random:
    shrink -> uniform in 1..size-1, grow -> uniform in size+1..min(cap, 2*size).
    It never looks at utilisation or at which pool is busy; it only keeps what was not beaten."""
    rng = random.Random(seed)
    results = {start: evaluate(start)}
    while len(results) < BUDGET:
        a = list(rng.choice(front(results)))
        i = rng.randrange(len(a))
        if rng.random() < 0.5:
            if a[i] == 1:
                continue
            a[i] = rng.randint(1, a[i] - 1)
        else:
            hi = min(cap, 2 * a[i])
            if hi <= a[i]:
                continue
            a[i] = rng.randint(a[i] + 1, hi)
        if tuple(a) not in results:
            results[tuple(a)] = evaluate(tuple(a))
    return results


if __name__ == "__main__":  # self-check with a fake evaluator: cost = headcount, time = 100/min pool
    fake = lambda a: (sum(a), 100 / min(a))
    for pol in (blind, one_pool):
        r = pol((20, 40, 7, 1), 68, 0, fake)
        assert len(r) == BUDGET and (20, 40, 7, 1) in r
        assert all(1 <= x <= 68 for a in r for x in a)
        assert pol((20, 40, 7, 1), 68, 0, fake) == r  # same seed, same run
    assert front({(1,): (1, 5), (2,): (2, 5), (3,): (3, 1)}) == [(1,), (3,)]
    print("ok")
