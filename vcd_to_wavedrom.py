"""
VCD to WaveDrom Converter - Convert VCD files to WaveDrom JSON format.

Parses Value Change Dump (VCD) files and generates WaveDrom JSON
for waveform visualization.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING

import config

if TYPE_CHECKING:
    from verilog_parser import Port


@dataclass
class VCDSignal:
    """Represents a signal in a VCD file."""
    id: str
    name: str
    width: int
    scope: str = ""
    values: List[Tuple[int, str]] = field(default_factory=list)  # (time, value)
    
    def get_value_at(self, time: int) -> str:
        """Get signal value at a specific time."""
        last_value = 'x'
        for t, v in self.values:
            if t > time:
                break
            last_value = v
        return last_value


@dataclass
class VCDData:
    """Parsed VCD file data."""
    timescale: str = "1ns"
    signals: Dict[str, VCDSignal] = field(default_factory=dict)
    end_time: int = 0


class VCDParser:
    """Parse VCD (Value Change Dump) files."""
    
    def __init__(self):
        self.signals: Dict[str, VCDSignal] = {}
        self.id_to_signal: Dict[str, VCDSignal] = {}
        self.current_scope: List[str] = []
        self.timescale = "1ns"
        self.end_time = 0
    
    def parse(self, vcd_content: str) -> VCDData:
        """Parse VCD content and return structured data."""
        self.signals = {}
        self.id_to_signal = {}
        self.current_scope = []
        self.end_time = 0
        
        lines = vcd_content.split('\n')
        i = 0
        
        # Parse header section
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('$timescale'):
                i, self.timescale = self._parse_timescale(lines, i)
            elif line.startswith('$scope'):
                scope_match = re.match(r'\$scope\s+(\w+)\s+(\w+)', line)
                if scope_match:
                    self.current_scope.append(scope_match.group(2))
            elif line.startswith('$upscope'):
                if self.current_scope:
                    self.current_scope.pop()
            elif line.startswith('$var'):
                self._parse_var(line)
            elif line.startswith('$enddefinitions'):
                i += 1
                break
            
            i += 1
        
        # Parse value changes
        current_time = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            if line.startswith('#'):
                # Timestamp
                try:
                    current_time = int(line[1:])
                    self.end_time = max(self.end_time, current_time)
                except ValueError:
                    pass
            elif line.startswith('$'):
                # Skip VCD commands in value section
                pass
            elif line.startswith('b') or line.startswith('B'):
                # Binary value for multi-bit signal
                match = re.match(r'[bB]([01xXzZ]+)\s+(\S+)', line)
                if match:
                    value, sig_id = match.groups()
                    self._record_value(sig_id, current_time, value)
            elif len(line) >= 2 and line[0] in '01xXzZ':
                # Single bit value
                value = line[0]
                sig_id = line[1:].strip()
                self._record_value(sig_id, current_time, value)
            
            i += 1
        
        return VCDData(
            timescale=self.timescale,
            signals=self.signals,
            end_time=self.end_time
        )
    
    def _parse_timescale(self, lines: List[str], start_idx: int) -> Tuple[int, str]:
        """Parse timescale directive."""
        i = start_idx
        content = []
        while i < len(lines):
            line = lines[i].strip()
            content.append(line)
            if '$end' in line:
                break
            i += 1
        
        full_line = ' '.join(content)
        match = re.search(r'(\d+\s*\w+)', full_line)
        if match:
            return i, match.group(1).replace(' ', '')
        return i, "1ns"
    
    def _parse_var(self, line: str) -> None:
        """Parse variable declaration."""
        # $var wire 8 ! data [7:0] $end
        # $var reg 1 " clk $end
        match = re.match(
            r'\$var\s+(\w+)\s+(\d+)\s+(\S+)\s+(\S+)(?:\s+\[[\d:]+\])?\s*\$end',
            line
        )
        if match:
            var_type, width, sig_id, name = match.groups()
            scope = '.'.join(self.current_scope)
            full_name = f"{scope}.{name}" if scope else name
            
            signal = VCDSignal(
                id=sig_id,
                name=name,
                width=int(width),
                scope=scope
            )
            
            self.signals[full_name] = signal
            self.id_to_signal[sig_id] = signal
    
    def _record_value(self, sig_id: str, time: int, value: str) -> None:
        """Record a value change for a signal."""
        if sig_id in self.id_to_signal:
            self.id_to_signal[sig_id].values.append((time, value.lower()))


class WaveDromGenerator:
    """Generate WaveDrom JSON from VCD data."""
    
    # Signal groups for logical ordering
    SIGNAL_GROUPS = [
        # Group 0: Clock signals
        ['clk', 'clock', 'clk_ena'],
        # Group 1: Reset signals
        ['rst', 'reset', 'rstn', 'rst_n', 'resetn'],
        # Group 2: Status signals
        ['full', 'a_full', 'almost_full'],
        # Group 3: Read control
        ['rd_en', 're', 'read', 'rd'],
        # Group 4: Read data
        ['dout', 'rdata', 'rd_data', 'data_out', 'q'],
        # Group 5: Write control
        ['wr_en', 'we', 'write', 'wr'],
        # Group 6: Empty status
        ['empty', 'a_empty', 'almost_empty'],
        # Group 7: Write data
        ['din', 'wdata', 'wr_data', 'data_in', 'd'],
        # Group 8: Other control
        ['en', 'enable', 'valid', 'ready', 'start', 'done'],
        # Group 9: Address/data
        ['addr', 'address', 'data'],
    ]
    
    # Internal signal patterns to exclude
    INTERNAL_SIGNAL_PATTERNS = [
        'i',        # Loop variables
        'j',
        'k',
        'genvar',
        'memory',   # Memory arrays
        'mem',
        'cnt_',     # Internal counters (but keep exposed ones)
    ]
    
    def __init__(
        self,
        max_signals: int = None,
        max_time_steps: int = None,
        signal_priority: List[str] = None,
        wavedrom_config: Dict[str, Any] = None,
        wavedrom_head: Dict[str, Any] = None,
        wavedrom_foot: Dict[str, Any] = None,
        io_ports_only: bool = True,
        io_port_names: List[str] = None,
        port_definitions: List["Port"] = None,
        use_port_order: bool = True,
        use_vcd_order: bool = False,
        match_original: bool = False
    ):
        self.max_signals = max_signals or config.MAX_SIGNALS
        self.max_time_steps = max_time_steps or config.MAX_TIME_STEPS
        self.signal_priority = signal_priority or config.SIGNAL_PRIORITY
        self.wavedrom_config = wavedrom_config or config.WAVEDROM_CONFIG
        self.wavedrom_head = wavedrom_head or config.WAVEDROM_HEAD
        self.wavedrom_foot = wavedrom_foot or config.WAVEDROM_FOOT
        
        # match_original mode: include all signals and use VCD order
        if match_original:
            self.io_ports_only = False
            self.use_vcd_order = True
            self.use_port_order = False
        else:
            self.io_ports_only = io_ports_only
            self.use_vcd_order = use_vcd_order
            self.use_port_order = use_port_order
        
        self.io_port_names = set(p.lower() for p in (io_port_names or []))
        self.port_definitions = port_definitions or []
        # Build name mapping: signal name -> Port for display name lookup
        self.port_name_map: Dict[str, "Port"] = {
            p.name.lower(): p for p in self.port_definitions
        }
    
    def _is_internal_signal(self, signal: VCDSignal) -> bool:
        """Check if a signal is likely an internal signal (not I/O port)."""
        name_lower = signal.name.lower()
        
        # If we have a list of I/O port names, use it
        if self.io_port_names:
            return name_lower not in self.io_port_names
        
        # Otherwise use heuristics
        # Single-character names are often loop variables
        if len(signal.name) == 1 and signal.name in 'ijklmn':
            return True
        
        # Check against internal signal patterns
        for pattern in self.INTERNAL_SIGNAL_PATTERNS:
            if signal.name == pattern or signal.name.startswith(pattern + '_'):
                # But allow signals that are also common I/O names
                if name_lower in ['cnt', 'count', 'counter']:
                    return False
                return True
        
        # Signals with 'internal' or 'reg' in scope are internal
        if 'internal' in signal.scope.lower():
            return True
        
        return False
    
    def _get_display_name(self, signal: VCDSignal) -> str:
        """Get display name for signal, with bit range if available from port definitions.
        
        Args:
            signal: The VCD signal to get display name for
            
        Returns:
            Full signal name with bit range (e.g., 'data[7:0]') if port definition exists,
            otherwise the original signal name.
        """
        name_lower = signal.name.lower()
        if name_lower in self.port_name_map:
            port = self.port_name_map[name_lower]
            return port.get_full_name()
        return signal.name
    
    def _sort_by_port_order(self, signals: List[VCDSignal]) -> List[VCDSignal]:
        """Sort signals by Verilog port definition order.
        
        Args:
            signals: List of VCD signals to sort
            
        Returns:
            Signals sorted by the order they appear in the Verilog port definitions.
            Signals not found in port definitions are placed at the end.
        """
        if not self.port_definitions:
            return signals
        
        port_order = {p.name.lower(): i for i, p in enumerate(self.port_definitions)}
        
        def order_key(sig: VCDSignal) -> int:
            return port_order.get(sig.name.lower(), 999)
        
        return sorted(signals, key=order_key)
    
    def generate(self, vcd_data: VCDData, io_port_names: List[str] = None) -> Dict[str, Any]:
        """Generate WaveDrom JSON from VCD data."""
        if not vcd_data.signals:
            return {
                "signal": [],
                "config": self.wavedrom_config.copy(),
                "head": self.wavedrom_head.copy(),
                "foot": self.wavedrom_foot.copy()
            }
        
        # Update I/O port names if provided
        if io_port_names:
            self.io_port_names = set(p.lower() for p in io_port_names)
        
        # Filter signals
        signals_list = list(vcd_data.signals.values())
        
        if self.io_ports_only:
            signals_list = [s for s in signals_list if not self._is_internal_signal(s)]
        
        # Sort signals based on settings
        if self.use_vcd_order:
            # Keep original VCD order (order signals appear in VCD file)
            sorted_signals = signals_list
        elif self.use_port_order and self.port_definitions:
            sorted_signals = self._sort_by_port_order(signals_list)
        else:
            sorted_signals = self._sort_signals_by_group(signals_list)
        
        # Limit number of signals
        signals_to_show = sorted_signals[:self.max_signals]
        
        # Determine time step
        time_step = self._calculate_time_step(vcd_data)
        
        # Generate WaveDrom signal entries
        wavedrom_signals = []
        for signal in signals_to_show:
            wave_entry = self._generate_wave_entry(signal, time_step, vcd_data.end_time)
            if wave_entry:
                wavedrom_signals.append(wave_entry)
        
        # Build complete WaveDrom JSON with config, head, foot, and signals
        return {
            "signal": wavedrom_signals,
            "config": self.wavedrom_config.copy(),
            "head": self.wavedrom_head.copy(),
            "foot": self.wavedrom_foot.copy()
        }
    
    def _sort_signals_by_group(self, signals: List[VCDSignal]) -> List[VCDSignal]:
        """Sort signals by logical groups for better visual organization."""
        def group_key(sig: VCDSignal) -> Tuple[int, int, str]:
            name_lower = sig.name.lower()
            
            # Find which group this signal belongs to
            for group_idx, group_patterns in enumerate(self.SIGNAL_GROUPS):
                for pattern_idx, pattern in enumerate(group_patterns):
                    if pattern == name_lower or name_lower.startswith(pattern) or name_lower.endswith(pattern):
                        return (group_idx, pattern_idx, sig.name)
            
            # Signals not in any group go last
            return (len(self.SIGNAL_GROUPS), 0, sig.name)
        
        return sorted(signals, key=group_key)
    
    def _sort_signals(self, signals: List[VCDSignal]) -> List[VCDSignal]:
        """Sort signals by priority (clocks and resets first). Legacy method."""
        def priority_key(sig: VCDSignal) -> Tuple[int, str]:
            name_lower = sig.name.lower()
            for i, pattern in enumerate(self.signal_priority):
                if pattern in name_lower:
                    return (i, sig.name)
            return (len(self.signal_priority), sig.name)
        
        return sorted(signals, key=priority_key)
    
    def _calculate_time_step(self, vcd_data: VCDData) -> int:
        """Calculate appropriate time step for WaveDrom."""
        if vcd_data.end_time == 0:
            return 1
        
        # Try to find the clock period
        for signal in vcd_data.signals.values():
            if 'clk' in signal.name.lower() and signal.values:
                # Find minimum time between transitions
                transitions = [t for t, _ in signal.values if t > 0]
                if len(transitions) >= 2:
                    min_period = min(
                        transitions[i+1] - transitions[i] 
                        for i in range(len(transitions)-1)
                    )
                    if min_period > 0:
                        return min_period
        
        # Fall back to dividing end time by max steps
        return max(1, vcd_data.end_time // self.max_time_steps)
    
    def _generate_wave_entry(
        self,
        signal: VCDSignal,
        time_step: int,
        end_time: int
    ) -> Optional[Dict[str, Any]]:
        """Generate a WaveDrom wave entry for a signal."""
        if not signal.values:
            return None
        
        num_steps = min(self.max_time_steps, max(1, end_time // time_step))
        
        if signal.width == 1:
            return self._generate_single_bit_wave(signal, time_step, num_steps)
        else:
            return self._generate_multi_bit_wave(signal, time_step, num_steps)
    
    def _generate_single_bit_wave(
        self,
        signal: VCDSignal,
        time_step: int,
        num_steps: int
    ) -> Dict[str, Any]:
        """Generate wave string for single-bit signal."""
        wave = ""
        last_value = None
        
        # Check if this is a clock signal
        is_clock = 'clk' in signal.name.lower() or 'clock' in signal.name.lower()
        
        for step in range(num_steps):
            time = step * time_step
            value = signal.get_value_at(time)
            
            if is_clock and step > 0:
                # Use 'p' or 'n' for clock signals
                if step == 1:
                    wave = 'p' + '.' * (num_steps - 1)
                    break
            
            if value == last_value:
                wave += '.'
            elif value == '1':
                wave += '1'
            elif value == '0':
                wave += '0'
            elif value in ('x', 'X'):
                wave += 'x'
            elif value in ('z', 'Z'):
                wave += 'z'
            else:
                wave += 'x'
            
            last_value = value
        
        # Use display name with bit range if available
        display_name = self._get_display_name(signal)
        return {"name": display_name, "wave": wave}
    
    def _generate_multi_bit_wave(
        self,
        signal: VCDSignal,
        time_step: int,
        num_steps: int
    ) -> Dict[str, Any]:
        """Generate wave string for multi-bit signal."""
        wave = ""
        data = []
        last_value = None
        
        for step in range(num_steps):
            time = step * time_step
            value = signal.get_value_at(time)
            
            if value == last_value:
                wave += '.'
            else:
                # Check for x or z values
                if 'x' in value.lower():
                    wave += 'x'
                elif 'z' in value.lower():
                    wave += 'z'
                else:
                    wave += '='
                    # Convert binary to hex for display
                    try:
                        hex_val = format(int(value, 2), 'X')
                        data.append(hex_val)
                    except ValueError:
                        data.append(value[:8])  # Truncate long values
            
            last_value = value
        
        # Use display name with bit range if available
        display_name = self._get_display_name(signal)
        result = {"name": display_name, "wave": wave}
        if data:
            result["data"] = data
        return result


def vcd_to_wavedrom(
    vcd_content: str, 
    io_port_names: List[str] = None,
    port_definitions: List["Port"] = None,
    match_original: bool = False
) -> Dict[str, Any]:
    """Convenience function to convert VCD to WaveDrom JSON.
    
    Args:
        vcd_content: VCD file content as string
        io_port_names: Optional list of I/O port names to filter signals
        port_definitions: Optional list of Port objects for signal name formatting
                         and ordering. When provided, signals will be named with
                         bit ranges (e.g., 'data[7:0]') and ordered by port definition.
        match_original: If True, include all signals and use VCD order to match
                       original waveform images from the dataset.
    """
    parser = VCDParser()
    vcd_data = parser.parse(vcd_content)
    
    generator = WaveDromGenerator(
        io_ports_only=not match_original,
        io_port_names=io_port_names,
        port_definitions=port_definitions,
        use_port_order=port_definitions is not None and not match_original,
        match_original=match_original
    )
    return generator.generate(vcd_data, io_port_names=io_port_names)


def vcd_to_wavedrom_json(vcd_content: str) -> str:
    """Convert VCD content to WaveDrom JSON string."""
    wavedrom_dict = vcd_to_wavedrom(vcd_content)
    return json.dumps(wavedrom_dict, indent=2)


def vcd_to_wavedrom_with_order(
    vcd_content: str,
    signal_order: List[str],
    port_definitions: List["Port"] = None
) -> Dict[str, Any]:
    """Convert VCD to WaveDrom with custom signal ordering.
    
    Args:
        vcd_content: VCD file content as string
        signal_order: List of signal names in desired order
        port_definitions: Optional list of Port objects for signal name formatting
        
    Returns:
        WaveDrom dictionary with signals ordered according to signal_order
    """
    parser = VCDParser()
    vcd_data = parser.parse(vcd_content)
    
    generator = WaveDromGenerator(
        io_ports_only=False,  # Include all signals
        port_definitions=port_definitions,
        use_port_order=False,
        use_vcd_order=False,  # We'll apply custom order
        match_original=False
    )
    
    wavedrom_dict = generator.generate(vcd_data)
    
    # Reorder signals according to the provided order
    if signal_order and wavedrom_dict.get('signal'):
        from signal_order_extractor import reorder_wavedrom_signals
        wavedrom_dict = reorder_wavedrom_signals(wavedrom_dict, signal_order)
    
    return wavedrom_dict


# Test the converter
if __name__ == "__main__":
    sample_vcd = """$timescale 1ns $end
$scope module dut $end
$var wire 1 ! clk $end
$var wire 1 " rst $end
$var wire 8 # count [7:0] $end
$upscope $end
$enddefinitions $end
#0
0!
1"
b00000000 #
#5
1!
#10
0!
0"
#15
1!
b00000001 #
#20
0!
#25
1!
b00000010 #
#30
0!
#35
1!
b00000011 #
#40
0!
#45
1!
b00000100 #
#50
$end
"""
    
    result = vcd_to_wavedrom_json(sample_vcd)
    print("WaveDrom JSON:")
    print(result)
