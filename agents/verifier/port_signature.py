"""Shared parser to extract ports from a Verilog module header."""

import re

def port_signature(code: str) -> dict[str, tuple[str, int]]:
    """
    Parses the RTL and returns {port_name: (direction, width)}.
    Raises ValueError if the header cannot be parsed.
    """
    # Find the module header: everything between 'module name(' and ');'
    match = re.search(r"module\s+\w+\s*\((.*?)\);", code, re.DOTALL)
    if not match:
        raise ValueError("Could not find a valid module header ending in ');'")
    
    header = match.group(1)
    
    # Remove comments
    header = re.sub(r"//.*", "", header)
    header = re.sub(r"/\*.*?\*/", "", header, flags=re.DOTALL)
    
    ports = {}
    
    # Split by comma to get individual ports
    parts = header.split(",")
    
    current_dir = None
    current_width = 1
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Look for direction
        dir_match = re.search(r"\b(input|output|inout)\b", part)
        if dir_match:
            current_dir = dir_match.group(1)
        
        # Look for width [x:y]
        width_match = re.search(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", part)
        if width_match:
            msb = int(width_match.group(1))
            lsb = int(width_match.group(2))
            current_width = abs(msb - lsb) + 1
        else:
            current_width = 1
            
        if not current_dir:
            raise ValueError(f"Could not determine direction for port in: {part}")
            
        # Extract the name (the last word in the part)
        words = re.findall(r"[a-zA-Z_]\w*", part)
        if not words:
            continue
        name = words[-1]
        
        ports[name] = (current_dir, current_width)
        
    return ports