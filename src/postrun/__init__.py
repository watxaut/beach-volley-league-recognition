"""Post-run reconstruction layer (AGENTS.md §6: hindsight over the stream).

Turns the causal single-pass stream into a match that makes sense: points
with a start (serve) and an end (ball death), possessions per side, at most
three touches per possession with alternating players, and a score that
follows the serve.
"""
