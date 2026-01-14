"""
Verilog Parser - Extract module structure from Verilog code.

Supports Verilog-2001 ANSI-style and non-ANSI port declarations.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Port:
    """Represents a Verilog port."""
    name: str
    direction: str  # 'input', 'output', 'inout'
    width: int = 1
    msb: Optional[int] = None
    lsb: Optional[int] = None
    is_reg: bool = False
    is_signed: bool = False
    
    def __post_init__(self):
        if self.msb is not None and self.lsb is not None:
            self.width = abs(self.msb - self.lsb) + 1
    
    def get_full_name(self) -> str:
        """Generate full signal name with bit range like 'data[7:0]'.
        
        Returns:
            Signal name with bit range if multi-bit or explicitly declared,
            otherwise just the signal name for implicit single-bit signals.
        """
        if self.width == 1:
            # Only show range if explicitly declared
            if self.msb is not None and self.lsb is not None:
                return f"{self.name}[{self.msb}:{self.lsb}]"
            return self.name  # Implicit single-bit signal, no range
        else:
            msb = self.msb if self.msb is not None else self.width - 1
            lsb = self.lsb if self.lsb is not None else 0
            return f"{self.name}[{msb}:{lsb}]"


@dataclass
class Parameter:
    """Represents a Verilog parameter."""
    name: str
    value: str
    width: Optional[int] = None


@dataclass
class VerilogModule:
    """Represents a parsed Verilog module."""
    name: str
    ports: List[Port] = field(default_factory=list)
    parameters: List[Parameter] = field(default_factory=list)
    raw_code: str = ""
    
    @property
    def inputs(self) -> List[Port]:
        return [p for p in self.ports if p.direction == 'input']
    
    @property
    def outputs(self) -> List[Port]:
        return [p for p in self.ports if p.direction == 'output']
    
    @property
    def inouts(self) -> List[Port]:
        return [p for p in self.ports if p.direction == 'inout']
    
    def get_clock_signals(self) -> List[Port]:
        """Find likely clock signals based on naming conventions."""
        clock_patterns = ['clk', 'clock', 'CLK', 'CLOCK']
        return [p for p in self.inputs 
                if any(pat in p.name.lower() for pat in ['clk', 'clock']) and p.width == 1]
    
    def get_reset_signals(self) -> List[Port]:
        """Find likely reset signals based on naming conventions."""
        return [p for p in self.inputs 
                if any(pat in p.name.lower() for pat in ['rst', 'reset']) and p.width == 1]


class VerilogParser:
    """Parse Verilog code to extract module structure."""
    
    def __init__(self):
        # Regex patterns for Verilog parsing
        self._module_pattern = re.compile(
            r'module\s+(\w+)\s*'  # module name
            r'(?:#\s*\((.*?)\))?\s*'  # optional parameters
            r'\((.*?)\)\s*;',  # port list
            re.DOTALL
        )
        
        # ANSI-style port in module header: input [7:0] data, input wire clk
        # Handles parameterized widths like [C_WIDTH-1:0]
        self._ansi_port_pattern = re.compile(
            r'(input|output|inout)\s+'
            r'(?:reg\s+|wire\s+)?'  # optional reg/wire (non-capturing)
            r'(signed\s+)?'  # optional signed
            r'(?:\[([^\]]+):([^\]]+)\]\s+)?'  # optional bit range with expressions
            r'(\w+)',  # signal name
            re.IGNORECASE
        )
        
        # Non-ANSI port declaration: input [7:0] data;
        self._port_decl_pattern = re.compile(
            r'(input|output|inout)\s+'
            r'(reg|wire)?\s*'
            r'(signed)?\s*'
            r'(?:\[([^\]]+):([^\]]+)\])?\s*'
            r'([\w\s,]+)\s*;',
            re.IGNORECASE
        )
        
        # Parameter declaration
        self._param_pattern = re.compile(
            r'parameter\s+'
            r'(?:\[(\d+):(\d+)\])?\s*'
            r'(\w+)\s*=\s*([^,;\)]+)',
            re.IGNORECASE
        )
        
        # Localparam declaration
        self._localparam_pattern = re.compile(
            r'localparam\s+'
            r'(?:\[(\d+):(\d+)\])?\s*'
            r'(\w+)\s*=\s*([^,;]+)',
            re.IGNORECASE
        )
    
    def parse(self, verilog_code: str) -> Optional[VerilogModule]:
        """Parse Verilog code and return module structure."""
        # Remove comments
        code = self._remove_comments(verilog_code)
        
        # Find module declaration
        module_match = self._module_pattern.search(code)
        if not module_match:
            return None
        
        module_name = module_match.group(1)
        param_section = module_match.group(2) or ""
        port_section = module_match.group(3) or ""
        
        # Parse parameters from #(...) section
        parameters = self._parse_parameters(param_section)
        
        # Also parse parameters from module body
        body_start = module_match.end()
        endmodule_match = re.search(r'\bendmodule\b', code[body_start:], re.IGNORECASE)
        if endmodule_match:
            module_body = code[body_start:body_start + endmodule_match.start()]
            parameters.extend(self._parse_parameters(module_body))
        else:
            module_body = code[body_start:]
        
        # Try ANSI-style ports first (in module header)
        ports = self._parse_ansi_ports(port_section)
        
        # If no ANSI ports found, look for non-ANSI declarations in body
        if not ports:
            port_names = self._extract_port_names(port_section)
            ports = self._parse_non_ansi_ports(module_body, port_names)
        
        return VerilogModule(
            name=module_name,
            ports=ports,
            parameters=parameters,
            raw_code=verilog_code
        )
    
    def _remove_comments(self, code: str) -> str:
        """Remove single-line and multi-line comments."""
        # Remove multi-line comments /* ... */
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        # Remove single-line comments // ...
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        return code
    
    def _parse_parameters(self, text: str) -> List[Parameter]:
        """Parse parameter declarations."""
        parameters = []
        
        for match in self._param_pattern.finditer(text):
            msb, lsb, name, value = match.groups()
            width = None
            if msb is not None and lsb is not None:
                width = abs(int(msb) - int(lsb)) + 1
            parameters.append(Parameter(
                name=name.strip(),
                value=value.strip().rstrip(','),
                width=width
            ))
        
        return parameters
    
    def _parse_ansi_ports(self, port_section: str) -> List[Port]:
        """Parse ANSI-style port declarations from module header."""
        ports = []
        seen_names = set()
        
        # Split by comma, but be careful with bit ranges
        # Use regex to find all port declarations
        for match in self._ansi_port_pattern.finditer(port_section):
            direction = match.group(1).lower()
            is_signed = match.group(2) is not None
            msb_str = match.group(3)
            lsb_str = match.group(4)
            name = match.group(5)
            
            # Skip if name is a reserved word (wire, reg, etc.)
            if name.lower() in ('wire', 'reg', 'signed', 'unsigned'):
                continue
            
            # Skip duplicates
            if name in seen_names:
                continue
            seen_names.add(name)
            
            # Parse bit indices
            msb = self._parse_bit_index(msb_str)
            lsb = self._parse_bit_index(lsb_str)
            
            # Determine width - use 8 as default for parameterized widths
            width = 1
            if msb_str is not None and lsb_str is not None:
                if msb is not None and lsb is not None:
                    width = abs(msb - lsb) + 1
                else:
                    # Parameterized width - default to 8
                    width = 8
                    msb = 7
                    lsb = 0
            
            ports.append(Port(
                name=name,
                direction=direction,
                width=width,
                msb=msb,
                lsb=lsb,
                is_reg=False,
                is_signed=is_signed
            ))
        
        return ports
    
    def _extract_port_names(self, port_section: str) -> List[str]:
        """Extract port names from non-ANSI module header."""
        # Remove any type declarations that might be in header
        clean = re.sub(r'(input|output|inout|reg|wire|\[[^\]]+\])', '', port_section, flags=re.IGNORECASE)
        # Split by comma and clean up
        names = [n.strip() for n in clean.split(',')]
        return [n for n in names if n and re.match(r'^\w+$', n)]
    
    def _parse_non_ansi_ports(self, body: str, port_names: List[str]) -> List[Port]:
        """Parse non-ANSI port declarations from module body."""
        ports = []
        port_name_set = set(port_names)
        
        for match in self._port_decl_pattern.finditer(body):
            direction = match.group(1).lower()
            is_reg = match.group(2) and match.group(2).lower() == 'reg'
            is_signed = match.group(3) is not None
            msb_str = match.group(4)
            lsb_str = match.group(5)
            names_str = match.group(6)
            
            # Parse bit range - might contain parameters
            msb = self._parse_bit_index(msb_str) if msb_str else None
            lsb = self._parse_bit_index(lsb_str) if lsb_str else None
            
            # Split multiple port names
            for name in names_str.split(','):
                name = name.strip()
                if name and (not port_name_set or name in port_name_set):
                    ports.append(Port(
                        name=name,
                        direction=direction,
                        msb=msb,
                        lsb=lsb,
                        is_reg=is_reg,
                        is_signed=is_signed
                    ))
        
        return ports
    
    def _parse_bit_index(self, index_str: str) -> Optional[int]:
        """Parse a bit index, which might be a number or expression."""
        if index_str is None:
            return None
        index_str = index_str.strip()
        
        # Try direct integer
        try:
            return int(index_str)
        except ValueError:
            pass
        
        # Try simple expression like "WIDTH-1"
        match = re.match(r'(\w+)\s*-\s*(\d+)', index_str)
        if match:
            # Return None for parameterized widths - will default to 8
            return None
        
        return None


def parse_verilog(code: str) -> Optional[VerilogModule]:
    """Convenience function to parse Verilog code."""
    parser = VerilogParser()
    return parser.parse(code)


# Test the parser
if __name__ == "__main__":
    test_code = '''
    module axi_fifo #(
        parameter WIDTH = 8,
        parameter DEPTH = 16
    )(
        input wire clk,
        input wire rst,
        input wire [WIDTH-1:0] din,
        input wire wr_en,
        input wire rd_en,
        output wire [WIDTH-1:0] dout,
        output wire full,
        output wire empty
    );
        // Module body
    endmodule
    '''
    
    module = parse_verilog(test_code)
    if module:
        print(f"Module: {module.name}")
        print(f"Parameters: {[(p.name, p.value) for p in module.parameters]}")
        print(f"Inputs: {[(p.name, p.width) for p in module.inputs]}")
        print(f"Outputs: {[(p.name, p.width) for p in module.outputs]}")
        print(f"Clock signals: {[p.name for p in module.get_clock_signals()]}")
        print(f"Reset signals: {[p.name for p in module.get_reset_signals()]}")
