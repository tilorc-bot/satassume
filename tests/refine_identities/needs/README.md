Failing tests that an author needs the engine to make pass. One file per
request, named `test_<author>_<topic>.py`, with the failing assertion and a
docstring saying which table row needs it. The engine agent makes it pass
on `ri/engine` and moves it into `test_engine.py` (or deletes it if the
capability is covered there).
