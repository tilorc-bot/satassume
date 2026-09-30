"""Memory of one cold pass of the refine stream.

* ``StreamPeakRSS.peakmem_stream``: asv's own ``peakmem_`` type, the
  process's peak resident set size (``maxrss``) after the pass.  It covers
  the whole process: the interpreter, SymPy and the loaded stream (about
  the same at every commit) as well as the engine, so a change shows up as
  a shift above that floor, with some noise from the allocator.
* ``StreamPythonMemory``: Python allocations traced by ``tracemalloc``
  from just before the pass (after the imports and the stream are loaded):
  ``track_python_peak`` is the highest the pass took them, and
  ``track_python_retained`` what is still held after it with the engine
  alive (its fact cache, the template registry's caches, and SymPy's own
  caches filled by the pass).  Much less noisy than RSS; tracemalloc slows
  the pass about 2x, which is why it is not the timing run.
"""
import gc
import tracemalloc

from .counters import answer, load_stream


class StreamPeakRSS:
    timeout = 600

    def setup(self):
        self.stream = [(p, a) for p, a, _ in load_stream()]
        import satassume.sympy_api  # noqa: F401  (import before the measurement)

    def peakmem_stream(self):
        answer(self.stream)


class StreamPythonMemory:
    timeout = 900

    def setup_cache(self):
        stream = [(p, a) for p, a, _ in load_stream()]
        import satassume.sympy_api  # noqa: F401
        gc.collect()
        tracemalloc.start()
        base = tracemalloc.get_traced_memory()[0]
        tracemalloc.reset_peak()
        _, eng = answer(stream)
        peak = tracemalloc.get_traced_memory()[1]
        gc.collect()
        retained = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()
        del eng
        return {"peak": peak - base, "retained": retained - base}

    def track_python_peak(self, m):
        return m["peak"]
    track_python_peak.unit = "bytes"

    def track_python_retained(self, m):
        return m["retained"]
    track_python_retained.unit = "bytes"
