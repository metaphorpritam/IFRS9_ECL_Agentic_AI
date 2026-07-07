"""Agent layer: typed, deterministic tools + (Day 4) the LangGraph router.

THE GOVERNING RULE: the LLM never does arithmetic. Every number the agent
reports comes from the frozen engine via the typed tool calls in this
package; the LLM only routes, parameterises and narrates.
"""
