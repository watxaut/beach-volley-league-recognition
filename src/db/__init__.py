"""SQLite storage layer: schema, ingest, metrics.

Kept deliberately separate from the extraction pipeline: extraction writes
``output/<stem>/pipeline_output.json`` (canonical JSON contract), this
package upserts that file into ``data/volley.db`` and serves queries for
the metrics module and the local web UI.
"""
