# Hallucination Checklist (H0-H5)

| Code | Check | How it is caught |

| H0 | Missing `module` / `endmodule` | Runner string check |

| H1 | Missing or invented ports | Compare module header with expected ports |

| H2 | `#delay` in synthesizable code | Regex |

| H3 | Blocking `=` in a clocked block | Regex on `always @(posedge ...)` |

| H4 | Does not compile with `iverilog` | Verifier harness |

| H5 | Markdown fences or prose in the `.v` file | Check for backticks |

Model output is untrusted. The harness result decides PASS/FAIL, not the model.