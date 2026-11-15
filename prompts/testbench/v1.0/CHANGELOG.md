# Testbench Prompt Changelog

A prompt change creates a new version folder (v1.1, v2.0, ...); this file lists every version.

## v1.0 - initial version
- One self-checking Verilog-2001 testbench module named <dut_name>_tb, no ports, `timescale 1ns/1ps
- DUT instantiated once with exact module and port names
- Clock generated in the testbench; reset first, active-low synchronous rst_n by default
- Expected values come from the specification through a behavioural reference model, never from the DUT's own logic
- Covers reset, normal operation including boundaries, and a reset in the middle of operation
- Prints exactly PASS or FAIL: <reason> (agreed markers, matched by classify_failure), then $finish
- Watchdog so a testbench can never hang the harness
